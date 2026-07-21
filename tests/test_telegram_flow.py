import sqlite3
import tempfile
import unittest
from pathlib import Path

import bot.db as db
from bot.telegram_handler import TelegramHandler


class FakeGroq:
    def __init__(self):
        self.generate_calls = []

    def generate_post(self, text, temperature=0.7):
        self.generate_calls.append((text, temperature))
        return "Generated LinkedIn draft"


class FakeLinkedIn:
    def __init__(self):
        self.published = []

    def publish_post(self, caption):
        self.published.append(caption)
        return "urn:li:activity:12345"


class CapturingTelegramHandler(TelegramHandler):
    def __init__(self):
        super().__init__()
        self.sent_messages = []
        self.edited_messages = []
        self.groq = FakeGroq()
        self.linkedin = FakeLinkedIn()

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


if __name__ == "__main__":
    unittest.main()
