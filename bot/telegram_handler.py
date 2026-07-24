import html
import secrets
import sys
import time

import requests

from config import (
    SEARCH_CACHE_TTL_SECONDS,
    SEARCH_PROVIDER,
    search_provider_configured,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_USER_ID,
)
from bot.db import (
    get_bot_offset,
    get_state,
    get_news_cache,
    log_post_history,
    reset_state,
    save_bot_offset,
    save_news_cache,
    update_state,
)
from bot.groq_client import GroqClient
from bot.linkedin_client import LinkedInClient
from bot.search_client import (
    SearchClient,
    cache_is_fresh,
    get_search_client,
    news_items_from_json,
    news_items_to_json,
    summarize_news_for_prompt,
)
import setup_linkedin_oauth as oauth


class TelegramHandler:
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.user_id = TELEGRAM_USER_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.groq = GroqClient()
        self.linkedin = LinkedInClient()
        # Lazily initialized so absence of API key doesn't break startup.
        self.search: SearchClient | None = None
        try:
            self.search = get_search_client()
        except Exception as e:
            print(f"Search client init warning: {e}", file=sys.stderr)

    def send_message(self, text: str, reply_markup: dict = None) -> int | None:
        payload = {
            "chat_id": self.user_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            res = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=30).json()
        except Exception as e:
            print(f"Telegram send warning: {e}", file=sys.stderr)
            return None

        if not res.get("ok"):
            print(f"Telegram error details: {res}", file=sys.stderr)
            return None
        return res["result"]["message_id"]

    def edit_message(self, message_id: int, text: str, reply_markup: dict = None):
        payload = {
            "chat_id": self.user_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            res = requests.post(f"{self.base_url}/editMessageText", json=payload, timeout=30).json()
            if not res.get("ok"):
                print(f"Telegram edit warning: {res}", file=sys.stderr)
        except Exception as e:
            print(f"Telegram edit warning: {e}", file=sys.stderr)

    def answer_callback(self, callback_query_id: str):
        try:
            requests.post(
                f"{self.base_url}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id},
                timeout=10,
            )
        except Exception as e:
            print(f"Telegram callback warning: {e}", file=sys.stderr)

    def get_approval_keyboard(self) -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "Approve", "callback_data": "approve"},
                    {"text": "Regenerate", "callback_data": "regenerate"},
                ],
                [
                    {"text": "Edit Draft", "callback_data": "edit"},
                    {"text": "Cancel", "callback_data": "cancel"},
                ],
            ]
        }

    def get_news_selection_keyboard(self, num_items: int) -> dict:
        """Inline keyboard: one button per news item, plus 'pick all' and 'cancel'.

        Telegram caps inline keyboards at ~100 buttons / rows. With 8 items
        we use one button per row for readability.
        """
        rows = [
            [{"text": f"#{idx + 1} use this one", "callback_data": f"news:{idx}"}]
            for idx in range(num_items)
        ]
        rows.append([{"text": "Use ALL of the above", "callback_data": "news:all"}])
        rows.append([{"text": "Cancel", "callback_data": "news:cancel"}])
        return {"inline_keyboard": rows}

    def format_news_listing(self, header: str, items: list[dict], topic_query: str | None = None) -> str:
        lines = [f"<b>{html.escape(header)}</b>"]
        if topic_query:
            lines.append(f"<i>Topic: {html.escape(topic_query)}</i>")
        lines.append(f"<i>Provider: {html.escape(SEARCH_PROVIDER)}</i>\n")
        for idx, item in enumerate(items, start=1):
            title = html.escape(item.get("title") or "(untitled)")
            source = html.escape(item.get("source") or "")
            age = html.escape(item.get("age") or "")
            meta = " • ".join(b for b in (source, age) if b)
            # Clip BEFORE escaping so we never chop a partial HTML entity.
            raw_snippet = (item.get("snippet") or "")[:180]
            snippet = html.escape(raw_snippet)
            lines.append(f"<b>{idx}.</b> {title}")
            if meta:
                lines.append(f"    <i>{meta}</i>")
            if snippet:
                lines.append(f"    {snippet}")
        lines.append("\nPick one to ground a LinkedIn post in it, or use ALL for an aggregated post.")
        return "\n".join(lines)

    def search_ready_check(self) -> bool:
        if self.search is None or not self.search.is_available():
            env_var = "TAVILY_API_KEY" if SEARCH_PROVIDER == "tavily" else "SERP_API_KEY"
            self.send_message(
                "<b>Web search not configured.</b>\n\n"
                f"Set <code>SEARCH_PROVIDER={SEARCH_PROVIDER}</code> and "
                f"<code>{env_var}</code> in .env.\n"
                "Then restart the bot."
            )
            return False
        return True

    def format_draft_preview(self, title: str, draft: str) -> str:
        return f"<b>{html.escape(title)}:</b>\n\n{html.escape(draft or '')}"

    def send_ready_message(self):
        self.send_message(
            "<b>LinkedIn bot is online.</b>\n\n"
            "Send a topic or draft and I will generate a LinkedIn post for approval.\n\n"
            "Commands:\n"
            "  /trending — top world news (auto-generate)\n"
            "  /news &#60;topic&#62; — search news for a topic\n"
            "  /new  /cancel  /status  /reauth"
        )

    def sync_offset_to_latest(self):
        """Skip old updates so a restart never republishes an already-approved post."""
        saved_offset = get_bot_offset()
        if saved_offset is not None:
            self.offset = saved_offset
            return

        try:
            res = requests.get(f"{self.base_url}/getUpdates", params={"timeout": 0}, timeout=10).json()
            if res.get("ok") and res["result"]:
                self.offset = max(update["update_id"] for update in res["result"]) + 1
                save_bot_offset(self.offset)
        except Exception as e:
            print(f"Startup offset sync warning: {e}", file=sys.stderr)

    def fetch_updates(self):
        params = {"offset": self.offset, "timeout": 20}
        try:
            res = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=25).json()
            if res.get("ok"):
                return res["result"]
            print(f"Polling warning: {res}", file=sys.stderr)
        except Exception as e:
            print(f"Polling warning: {e}", file=sys.stderr)
        return []

    def start_polling_loop(self):
        self.sync_offset_to_latest()
        print("Telegram bot polling started...")
        self.send_ready_message()

        while True:
            for update in self.fetch_updates():
                self.offset = update["update_id"] + 1
                save_bot_offset(self.offset)

                if "message" in update:
                    msg = update["message"]
                    if msg["chat"]["id"] != self.user_id:
                        continue
                    self.handle_text_message(msg)

                elif "callback_query" in update:
                    query = update["callback_query"]
                    if query["message"]["chat"]["id"] != self.user_id:
                        continue
                    self.answer_callback(query["id"])
                    self.handle_callback_query(query)

            time.sleep(1)

    def handle_text_message(self, msg: dict):
        text_received = msg.get("text", "").strip()
        if not text_received:
            self.send_message("Send text topic or draft.")
            return

        if text_received in {"/start", "/help"}:
            reset_state()
            update_state(step="AWAITING_TOPIC")
            self.send_ready_message()
            return

        if text_received in {"/new", "/reset"}:
            reset_state()
            update_state(step="AWAITING_TOPIC")
            self.send_message("Ready. Send new topic or draft.")
            return

        if text_received == "/cancel":
            reset_state()
            update_state(step="AWAITING_TOPIC")
            self.send_message("Current draft discarded. Send new topic or draft.")
            return

        if text_received == "/status":
            current_step = get_state().get("step") or "AWAITING_TOPIC"
            self.send_message(f"Current state: <code>{html.escape(current_step)}</code>")
            return

        if text_received == "/reauth":
            reset_state()
            update_state(step="AWAITING_REAUTH_CODE")
            auth_url = oauth.build_authorization_url(secrets.token_urlsafe(24))
            self.send_message(
                "<b>LinkedIn Re-Authorization</b>\n\n"
                "Your access token needs renewal. Follow these steps:\n\n"
                f"1. Open this link in your browser:\n{auth_url}\n\n"
                "2. After authorizing, LinkedIn redirects you to a URL containing <code>?code=...</code>\n\n"
                "3. Copy the full <code>code</code> value and paste it here."
            )
            return

        if text_received == "/trending":
            self.handle_trending_command()
            return

        if text_received.startswith("/news"):
            parts = text_received.split(maxsplit=1)
            topic_arg = parts[1].strip() if len(parts) > 1 else ""
            self.handle_news_command(topic_arg)
            return

        state = get_state()
        step = state.get("step")

        if step in (None, "AWAITING_TOPIC"):
            self.generate_draft(text_received)
        elif step == "AWAITING_REAUTH_CODE":
            self.process_reauth_code(text_received)
        elif step == "AWAITING_EDIT_INSTRUCTIONS":
            self.edit_draft(text_received, state.get("current_draft"))
        elif step == "AWAITING_APPROVAL":
            self.send_message("Draft is waiting for approval. Use buttons, or send /new to start over.")
        elif step == "AWAITING_NEWS_SELECTION":
            self.send_message("News list is waiting for a pick. Use the buttons, or send /cancel to discard.")
        else:
            reset_state()
            update_state(step="AWAITING_TOPIC")
            self.generate_draft(text_received)

    def generate_draft(self, topic_or_draft: str):
        self.send_message("<i>Generating LinkedIn draft...</i>")
        try:
            draft = self.groq.generate_post(topic_or_draft)
            update_state(step="AWAITING_APPROVAL", prompt_topic=topic_or_draft, current_draft=draft)
            preview_text = self.format_draft_preview("Generated Post Preview", draft)
            msg_id = self.send_message(preview_text, reply_markup=self.get_approval_keyboard())
            update_state(last_message_id=msg_id)
        except Exception as e:
            self.send_message(f"Error generating post: <code>{html.escape(str(e))}</code>")

    def edit_draft(self, feedback: str, original_draft: str | None):
        if not original_draft:
            reset_state()
            update_state(step="AWAITING_TOPIC")
            self.send_message("No draft found. Send topic or draft again.")
            return

        self.send_message("<i>Applying updates to draft...</i>")
        try:
            new_draft = self.groq.edit_post(original_draft, feedback)
            update_state(step="AWAITING_APPROVAL", current_draft=new_draft)
            preview_text = self.format_draft_preview("Updated Post Preview", new_draft)
            msg_id = self.send_message(preview_text, reply_markup=self.get_approval_keyboard())
            update_state(last_message_id=msg_id)
        except Exception as e:
            self.send_message(f"Error modifying post: <code>{html.escape(str(e))}</code>")

    def handle_callback_query(self, query: dict):
        state = get_state()
        data = query["data"]
        message_id = query["message"]["message_id"]

        # Dispatch news-flow callbacks to the add-on handler.
        if data.startswith("news:"):
            self.handle_news_callback(data, message_id)
            return

        if data == "approve":
            self.publish_approved_post(message_id, state)
        elif data == "regenerate":
            self.regenerate_draft(message_id, state)
        elif data == "edit":
            update_state(step="AWAITING_EDIT_INSTRUCTIONS")
            self.edit_message(message_id, "<b>Reply with edits.</b>\n\nSend instructions or full replacement text.")
        elif data == "cancel":
            self.edit_message(message_id, "<b>Session cancelled.</b> Post discarded.")
            reset_state()
            update_state(step="AWAITING_TOPIC")
            self.send_message("Ready for next post. Send topic or draft anytime.")

    def process_reauth_code(self, code: str):
        self.send_message("<i>Exchanging authorization code for new tokens...</i>")
        try:
            code = code.strip()
            if not code:
                self.send_message("Please paste the authorization code from the redirect URL.")
                return

            author_urn = oauth.perform_reauth(code)
            reset_state()
            update_state(step="AWAITING_TOPIC")
            self.send_message(
                f"<b>Re-authorization successful.</b>\n\n"
                f"LinkedIn profile: <code>{html.escape(author_urn)}</code>\n\n"
                "Ready for next post. Send topic or draft anytime."
            )
        except Exception as e:
            self.send_message(
                f"Re-authorization failed: <code>{html.escape(str(e))}</code>\n\n"
                "The authorization code may have expired (30-minute limit). "
                "Send /reauth to get a fresh link."
            )

    def publish_approved_post(self, message_id: int, state: dict):
        self.edit_message(message_id, "<i>Publishing to LinkedIn profile...</i>")
        try:
            caption = state.get("current_draft")
            if not caption:
                raise Exception("No draft found. Send /new and create a draft first.")

            post_urn = self.linkedin.publish_post(caption)
            linkedin_url = f"https://www.linkedin.com/feed/update/{post_urn}"

            self.edit_message(message_id, f"<b>Posted to LinkedIn.</b>\n\n<a href='{linkedin_url}'>View post</a>")
            log_post_history(caption, post_urn)
            reset_state()
            update_state(step="AWAITING_TOPIC")
            self.send_message("Ready for next post. Send topic or draft anytime.")
        except Exception as e:
            self.send_message(f"Failed to publish: <code>{html.escape(str(e))}</code>")
            self.edit_message(message_id, "Publication failed. Try again below.", reply_markup=self.get_approval_keyboard())

    def regenerate_draft(self, message_id: int, state: dict):
        self.edit_message(message_id, "<i>Regenerating alternative variation...</i>")
        try:
            topic = state.get("prompt_topic")
            if not topic:
                raise Exception("No topic found. Send /new and create a draft first.")

            new_draft = self.groq.generate_post(topic, temperature=0.85)
            update_state(step="AWAITING_APPROVAL", current_draft=new_draft)
            preview_text = self.format_draft_preview("New Draft Variation", new_draft)
            self.edit_message(message_id, preview_text, reply_markup=self.get_approval_keyboard())
        except Exception as e:
            self.send_message(f"Error during regeneration: <code>{html.escape(str(e))}</code>")

    # ------------------------------------------------------------------
    # Web-search add-on: /trending, /news, AWAITING_NEWS_SELECTION
    # ------------------------------------------------------------------
    def handle_trending_command(self):
        if not self.search_ready_check():
            return
        # Avoid re-hitting the provider if we have a fresh cache (same query = None).
        cached_json, saved_at = get_news_cache()
        if cached_json and saved_at and cache_is_fresh(saved_at, SEARCH_CACHE_TTL_SECONDS):
            items = news_items_from_json(cached_json)
            if items:
                self.send_news_listing("Top World News (cached)", items, topic_query=None)
                return
        self.send_message("<i>Fetching top world news...</i>")
        try:
            items = self.search.fetch_trending_now()
        except Exception as e:
            self.send_message(f"News fetch failed: <code>{html.escape(str(e))}</code>")
            return
        if not items:
            self.send_message("No news items returned. Try /news &#60;topic&#62; instead.")
            return
        save_news_cache(news_items_to_json(items), time.time())
        self.send_news_listing("Top World News", items, topic_query=None)

    def handle_news_command(self, topic: str):
        if not self.search_ready_check():
            return
        if not topic:
            self.send_message(
                "Usage: <code>/news &#60;topic&#62;</code>\n\n"
                "Examples:\n"
                "  <code>/news AI regulation</code>\n"
                "  <code>/news layoffs 2026</code>\n"
                "  <code>/news climate</code>"
            )
            return
        self.send_message(f"<i>Searching news for: {html.escape(topic)}...</i>")
        try:
            items = self.search.fetch_topic_news(topic)
        except Exception as e:
            self.send_message(f"News search failed: <code>{html.escape(str(e))}</code>")
            return
        if not items:
            self.send_message("No news items found. Try a different topic or /trending.")
            return
        save_news_cache(news_items_to_json(items), time.time())
        # Remember the topic so we can ground the post on it after the user picks.
        update_state(prompt_topic=topic)
        self.send_news_listing(f"News for: {topic}", items, topic_query=topic)

    def send_news_listing(self, header: str, items: list[dict], topic_query: str | None):
        # Persist the index of the cached items by saving the topic + payload together.
        update_state(
            step="AWAITING_NEWS_SELECTION",
            news_payload=news_items_to_json(items),
            news_saved_at=time.time(),
        )
        body = self.format_news_listing(header, items, topic_query=topic_query)
        msg_id = self.send_message(body, reply_markup=self.get_news_selection_keyboard(len(items)))
        update_state(last_message_id=msg_id)

    def handle_news_callback(self, data: str, message_id: int):
        # data is "news:0" .. "news:N", "news:all", "news:cancel"
        choice = data.split(":", 1)[1]
        if choice == "cancel":
            self.edit_message(message_id, "<b>Cancelled.</b> News list discarded.")
            reset_state()
            update_state(step="AWAITING_TOPIC")
            self.send_message("Ready for next post. Send topic or draft anytime.")
            return

        cached_json, _saved_at = get_news_cache()
        items = news_items_from_json(cached_json) if cached_json else []
        if not items:
            self.edit_message(message_id, "Cached news list expired. Run /trending or /news again.")
            reset_state()
            update_state(step="AWAITING_TOPIC")
            return

        topic = get_state().get("prompt_topic") or "top world news right now"

        if choice == "all":
            news_block = summarize_news_for_prompt(items, max_items=len(items))
            user_topic = topic if topic else "today's biggest news stories"
            self._generate_news_draft(
                message_id,
                title="Aggregated News Post Preview",
                user_topic=user_topic,
                news_block=news_block,
            )
            return

        # Specific item — "news:<idx>"
        try:
            idx = int(choice)
        except ValueError:
            self.edit_message(message_id, "Invalid selection.")
            return
        if idx < 0 or idx >= len(items):
            self.edit_message(message_id, "Selection no longer in cache.")
            return
        chosen = items[idx]
        # If the article has full content (Tavily), render it for the LLM.
        # Otherwise fall back to title + snippet so we still have something to ground on.
        news_block = chosen.get("content") or ""
        if not news_block.strip():
            news_block = (
                f"{chosen.get('title','')}\n"
                f"{chosen.get('source','')} {chosen.get('age','')}\n"
                f"{chosen.get('snippet','')}"
            ).strip()
        self._generate_news_draft(
            message_id,
            title=f"Post from: {chosen.get('title','(no title)')[:40]}",
            user_topic=chosen.get("title") or topic,
            news_block=news_block,
            is_single=True,
        )

    def _generate_news_draft(
        self,
        message_id: int,
        title: str,
        user_topic: str,
        news_block: str,
        is_single: bool = False,
    ):
        self.edit_message(message_id, "<i>Generating news-grounded LinkedIn draft...</i>")
        try:
            if is_single:
                draft = self.groq.generate_post_from_single_article(news_block)
            else:
                draft = self.groq.generate_post_from_news(user_topic, news_block)
        except Exception as e:
            self.edit_message(message_id, f"Draft failed: <code>{html.escape(str(e))}</code>")
            return
        # Transition into the AWAITING_APPROVAL flow the same way generate_draft does.
        update_state(
            step="AWAITING_APPROVAL",
            prompt_topic=user_topic,
            current_draft=draft,
        )
        preview_text = self.format_draft_preview(title, draft)
        new_msg_id = self.send_message(preview_text, reply_markup=self.get_approval_keyboard())
        update_state(last_message_id=new_msg_id)
