import html
import secrets
import sys
import time

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_USER_ID
from bot.db import (
    get_bot_offset,
    get_state,
    log_post_history,
    reset_state,
    save_bot_offset,
    update_state,
)
from bot.groq_client import GroqClient
from bot.linkedin_client import LinkedInClient
import setup_linkedin_oauth as oauth


class TelegramHandler:
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.user_id = TELEGRAM_USER_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.groq = GroqClient()
        self.linkedin = LinkedInClient()

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

    def format_draft_preview(self, title: str, draft: str) -> str:
        return f"<b>{html.escape(title)}:</b>\n\n{html.escape(draft or '')}"

    def send_ready_message(self):
        self.send_message(
            "<b>LinkedIn bot is online.</b>\n\n"
            "Send a topic or draft and I will generate a LinkedIn post for approval.\n\n"
            "Commands: /new, /cancel, /status, /reauth"
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
