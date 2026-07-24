import sqlite3
import tempfile
import unittest
from pathlib import Path

import bot.db as db
from bot.telegram_handler import TelegramHandler


class FakeGroq:
    def __init__(self):
        self.generate_calls = []
        self.generate_from_news_calls = []
        self.generate_from_single_calls = []

    def generate_post(self, text, temperature=0.7):
        self.generate_calls.append((text, temperature))
        return "Generated LinkedIn draft"

    def generate_post_from_news(self, topic, block, temperature=0.7):
        self.generate_from_news_calls.append((topic, block, temperature))
        return "News-grounded draft"

    def generate_post_from_single_article(self, block, temperature=0.6):
        self.generate_from_single_calls.append((block, temperature))
        return "Single-article draft"


class FakeLinkedIn:
    def __init__(self):
        self.published = []

    def publish_post(self, caption):
        self.published.append(caption)
        return "urn:li:activity:12345"


class FakeSearch:
    def __init__(self, items=None):
        self.items = items or [
            {"title": "AI startup raises $1B", "url": "https://reuters.com/x",
             "snippet": "Reuters summary", "source": "reuters.com",
             "age": "1h", "content": "Full article body here.",
             "image": None, "score": None},
            {"title": "OpenAI ships new model", "url": "https://tc.com/y",
             "snippet": "TC summary", "source": "techcrunch.com",
             "age": "2h", "content": "", "image": None, "score": None},
        ]
        self.is_available_return = True
        self.fetch_calls = []

    def is_available(self):
        return self.is_available_return

    def fetch_trending_now(self, num=None, topic=None):
        self.fetch_calls.append(("trending", None, num, topic))
        return self.items

    def fetch_topic_news(self, topic, num=None):
        self.fetch_calls.append(("topic", topic, num, None))
        return self.items


class CapturingTelegramHandler(TelegramHandler):
    def __init__(self, search=None):
        super().__init__()
        self.sent_messages = []
        self.edited_messages = []
        self.groq = FakeGroq()
        self.linkedin = FakeLinkedIn()
        # Override the auto-built client so tests don't need API keys.
        self.search = search

    def send_message(self, text, reply_markup=None):
        message_id = len(self.sent_messages) + 1
        self.sent_messages.append(
            {"message_id": message_id, "text": text, "reply_markup": reply_markup}
        )
        return message_id

    def edit_message(self, message_id, text, reply_markup=None):
        self.edited_messages.append(
            {"message_id": message_id, "text": text, "reply_markup": reply_markup}
        )


class TelegramFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "state.db"
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.db_path
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_message_generates_draft_and_approve_publishes_to_linkedin(self):
        handler = CapturingTelegramHandler()

        handler.handle_text_message({"chat": {"id": handler.user_id}, "text": "AI automation"})
        state = db.get_state()

        self.assertEqual("AWAITING_APPROVAL", state["step"])
        self.assertEqual("AI automation", state["prompt_topic"])
        self.assertEqual("Generated LinkedIn draft", state["current_draft"])
        self.assertEqual([("AI automation", 0.7)], handler.groq.generate_calls)
        self.assertEqual("Approve", handler.sent_messages[-1]["reply_markup"]["inline_keyboard"][0][0]["text"])

        handler.handle_callback_query(
            {
                "data": "approve",
                "message": {"message_id": handler.sent_messages[-1]["message_id"]},
            }
        )

        self.assertEqual(["Generated LinkedIn draft"], handler.linkedin.published)
        self.assertEqual("AWAITING_TOPIC", db.get_state()["step"])
        self.assertIn("Posted to LinkedIn", handler.edited_messages[-1]["text"])

        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT caption, linkedin_urn FROM history").fetchone()
        finally:
            conn.close()
        self.assertEqual(("Generated LinkedIn draft", "urn:li:activity:12345"), row)

    def test_cancel_keeps_bot_ready_without_exiting(self):
        handler = CapturingTelegramHandler()
        db.update_state(step="AWAITING_APPROVAL", current_draft="Draft")

        handler.handle_callback_query(
            {
                "data": "cancel",
                "message": {"message_id": 99},
            }
        )

        self.assertEqual("AWAITING_TOPIC", db.get_state()["step"])
        self.assertIn("Ready for next post", handler.sent_messages[-1]["text"])

    def test_status_command_uses_current_state(self):
        handler = CapturingTelegramHandler()
        db.update_state(step="AWAITING_APPROVAL")

        handler.handle_text_message({"chat": {"id": handler.user_id}, "text": "/status"})

        self.assertIn("AWAITING_APPROVAL", handler.sent_messages[-1]["text"])

    # ----- News add-on flow ---------------------------------------
    def test_trending_command_fetches_news_and_enters_selection(self):
        search = FakeSearch()
        handler = CapturingTelegramHandler(search=search)

        handler.handle_text_message({"chat": {"id": handler.user_id}, "text": "/trending"})

        state = db.get_state()
        self.assertEqual("AWAITING_NEWS_SELECTION", state["step"])
        self.assertEqual([("trending", None, None, None)], search.fetch_calls)
        # Last message should be the news listing + selection keyboard.
        last = handler.sent_messages[-1]
        self.assertIn("Top World News", last["text"])
        self.assertIn("OpenAI ships new model", last["text"])
        kb = last["reply_markup"]["inline_keyboard"]
        # 2 items + 'use ALL' + 'cancel' rows
        self.assertEqual(4, len(kb))
        self.assertEqual("news:0", kb[0][0]["callback_data"])
        self.assertEqual("news:1", kb[1][0]["callback_data"])
        self.assertEqual("news:all", kb[2][0]["callback_data"])
        self.assertEqual("news:cancel", kb[3][0]["callback_data"])

    def test_news_topic_command_uses_query(self):
        search = FakeSearch()
        handler = CapturingTelegramHandler(search=search)

        handler.handle_text_message(
            {"chat": {"id": handler.user_id}, "text": "/news AI regulation"}
        )

        state = db.get_state()
        self.assertEqual("AWAITING_NEWS_SELECTION", state["step"])
        self.assertEqual("AI regulation", state["prompt_topic"])
        self.assertEqual([("topic", "AI regulation", None, None)], search.fetch_calls)

    def test_news_command_without_topic_shows_usage(self):
        search = FakeSearch()
        handler = CapturingTelegramHandler(search=search)

        handler.handle_text_message({"chat": {"id": handler.user_id}, "text": "/news"})

        self.assertIn("Usage", handler.sent_messages[-1]["text"])
        self.assertNotEqual("AWAITING_NEWS_SELECTION", db.get_state().get("step"))
        # did not query provider
        self.assertEqual([], search.fetch_calls)

    def test_news_callback_specific_index_generates_single_article_post(self):
        search = FakeSearch()
        handler = CapturingTelegramHandler(search=search)
        handler.handle_text_message({"chat": {"id": handler.user_id}, "text": "/trending"})
        last_msg_id = handler.sent_messages[-1]["message_id"]

        handler.handle_callback_query(
            {"data": "news:0", "message": {"message_id": last_msg_id, "chat": {"id": handler.user_id}}}
        )

        state = db.get_state()
        self.assertEqual("AWAITING_APPROVAL", state["step"])
        self.assertEqual("Single-article draft", state["current_draft"])
        self.assertEqual(0, len(handler.groq.generate_calls))
        # Used the Tavily-style full article content for grounding.
        self.assertEqual(1, len(handler.groq.generate_from_single_calls))
        self.assertIn("Full article body here.", handler.groq.generate_from_single_calls[0][0])

    def test_news_callback_all_generates_aggregated_post(self):
        search = FakeSearch()
        handler = CapturingTelegramHandler(search=search)
        handler.handle_text_message({"chat": {"id": handler.user_id}, "text": "/trending"})
        last_msg_id = handler.sent_messages[-1]["message_id"]

        handler.handle_callback_query(
            {"data": "news:all", "message": {"message_id": last_msg_id, "chat": {"id": handler.user_id}}}
        )

        state = db.get_state()
        self.assertEqual("AWAITING_APPROVAL", state["step"])
        self.assertEqual("News-grounded draft", state["current_draft"])
        self.assertEqual(1, len(handler.groq.generate_from_news_calls))
        # Block should mention both articles.
        self.assertIn("AI startup raises $1B", handler.groq.generate_from_news_calls[0][1])

    def test_news_cancel_returns_to_topic(self):
        search = FakeSearch()
        handler = CapturingTelegramHandler(search=search)
        handler.handle_text_message({"chat": {"id": handler.user_id}, "text": "/trending"})
        last_msg_id = handler.sent_messages[-1]["message_id"]

        handler.handle_callback_query(
            {"data": "news:cancel", "message": {"message_id": last_msg_id, "chat": {"id": handler.user_id}}}
        )

        self.assertEqual("AWAITING_TOPIC", db.get_state()["step"])
        self.assertIn("Cancelled", handler.edited_messages[-1]["text"])

    def test_trending_without_available_search_warns(self):
        search = FakeSearch()
        search.is_available_return = False
        handler = CapturingTelegramHandler(search=search)

        handler.handle_text_message({"chat": {"id": handler.user_id}, "text": "/trending"})

        self.assertIn("not configured", handler.sent_messages[-1]["text"])
        # Did not even fetch.
        self.assertEqual([], search.fetch_calls)

    # ----- HTML-safety regression tests -----------------------------------
    def test_ready_message_uses_no_unsupported_html_tags(self):
        """Telegram parse_mode='HTML' rejects tags other than b/i/u/s/strike/del/a/code/pre.

        A literal '<topic>' in send_ready_message was the original source of
        the 'Unsupported start tag "topic"' error. Lock that down here.
        """
        import re
        handler = CapturingTelegramHandler(search=FakeSearch())
        handler.send_ready_message()
        body = handler.sent_messages[-1]["text"]
        # Find every '<word' or '</word' token; only Telegram-supported tags may appear.
        allowed = {"b", "i", "u", "s", "strike", "del", "a", "code", "pre"}
        tags = re.findall(r"</?([a-zA-Z]+)", body)
        unknown = {t for t in tags if t.lower() not in allowed}
        self.assertEqual(set(), unknown, f"Found HTML tags Telegram will reject: {unknown}")
        # And specifically: no naked '<topic>' or '<source>' strings.
        self.assertNotIn("<topic>", body)
        self.assertNotIn("<source>", body)
        self.assertNotIn("<provider>", body)

    def test_news_command_without_topic_uses_entities_not_literal_tags(self):
        handler = CapturingTelegramHandler(search=FakeSearch())
        handler.handle_text_message({"chat": {"id": handler.user_id}, "text": "/news"})
        body = handler.sent_messages[-1]["text"]
        import re
        allowed = {"b", "i", "u", "s", "strike", "del", "a", "code", "pre"}
        tags = re.findall(r"</?([a-zA-Z]+)", body)
        unknown = {t for t in tags if t.lower() not in allowed}
        self.assertEqual(set(), unknown, f"Found HTML tags Telegram will reject: {unknown}")
        self.assertNotIn("<topic>", body)

    def test_news_listing_clamps_snippet_before_escaping(self):
        """Slicing after html.escape can chop < entities; clipping before
        escape guarantees a safe, valid HTML body."""
        handler = CapturingTelegramHandler(search=FakeSearch())
        handler.search.items = [
            {"title": "T", "url": "u", "snippet": "<x>" + "A" * 200, "source": "",
             "age": "", "content": "", "image": None, "score": None},
        ]
        handler.handle_text_message({"chat": {"id": handler.user_id}, "text": "/trending"})
        body = handler.sent_messages[-1]["text"]
        # The escaped form (<x>) must never be truncated mid-entity.
        # In particular there should be no orphan '&l' or '&g' token.
        import re
        orphans = re.findall(r"&(?![a-z]{2,6};|#\d{1,5};|#[xX][0-9a-fA-F]{1,4};)", body)
        self.assertEqual([], orphans)


if __name__ == "__main__":
    unittest.main()
