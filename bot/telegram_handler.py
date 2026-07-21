import sys
import time
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_USER_ID
from bot.db import get_state, update_state, reset_state, log_post_history
from bot.groq_client import GroqClient
from bot.linkedin_client import LinkedInClient

class TelegramHandler:
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.user_id = TELEGRAM_USER_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.groq = GroqClient()
        self.linkedin = LinkedInClient()

    def send_message(self, text: str, reply_markup: dict = None) -> int:
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.user_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        res = requests.post(url, json=payload).json()
        if not res.get("ok"):
            print(f"Telegram error details: {res}", file=sys.stderr)
            return None
        return res["result"]["message_id"]

    def edit_message(self, message_id: int, text: str, reply_markup: dict = None):
        url = f"{self.base_url}/editMessageText"
        payload = {
            "chat_id": self.user_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        requests.post(url, json=payload)

    def get_approval_keyboard(self) -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "✅ Approve", "callback_data": "approve"},
                    {"text": "🔄 Regenerate", "callback_data": "regenerate"}
                ],
                [
                    {"text": "📝 Edit Draft", "callback_data": "edit"},
                    {"text": "❌ Cancel", "callback_data": "cancel"}
                ]
            ]
        }

    def fetch_updates(self):
        url = f"{self.base_url}/getUpdates"
        params = {"offset": self.offset, "timeout": 20}
        try:
            res = requests.get(url, params=params, timeout=25).json()
            if res.get("ok"):
                return res["result"]
        except Exception as e:
            print(f"Polling warning: {e}", file=sys.stderr)
        return []

    def start_polling_loop(self, timeout_hours: float = 2.0):
        """Starts long-polling wait loop. Prevents VM from locking up indefinitely."""
        start_time = time.time()
        timeout_seconds = timeout_hours * 3600
        print("Telegram bot polling started...")

        # Initialize by asking user for topic
        msg_id = self.send_message("☕️ <b>Good morning!</b> What should today's LinkedIn post be about?")
        update_state(step="AWAITING_TOPIC", last_message_id=msg_id)

        while True:
            if time.time() - start_time > timeout_seconds:
                self.send_message("⏳ <i>No response received. Session timed out to preserve system resources.</i>")
                reset_state()
                break

            updates = self.fetch_updates()
            for u in updates:
                self.offset = u["update_id"] + 1
                
                # Check messages
                if "message" in u:
                    msg = u["message"]
                    if msg["chat"]["id"] != self.user_id:
                        continue
                    self.handle_text_message(msg)
                    
                # Check inline button presses
                elif "callback_query" in u:
                    query = u["callback_query"]
                    if query["message"]["chat"]["id"] != self.user_id:
                        continue
                    
                    # Answer immediately so the user's UI doesn't spin
                    requests.post(f"{self.base_url}/answerCallbackQuery", json={"callback_query_id": query["id"]})
                    self.handle_callback_query(query)

            time.sleep(1)

    def handle_text_message(self, msg: dict):
        state = get_state()
        step = state.get("step")
        text_received = msg["text"]

        if step == "AWAITING_TOPIC":
            self.send_message("✍️ <i>Working with Llama 3.3 to construct your post...</i>")
            try:
                draft = self.groq.generate_post(text_received)
                update_state(step="AWAITING_APPROVAL", prompt_topic=text_received, current_draft=draft)
                
                preview_text = f"📝 <b>Generated Post Preview:</b>\n\n{draft}"
                msg_id = self.send_message(preview_text, reply_markup=self.get_approval_keyboard())
                update_state(last_message_id=msg_id)
            except Exception as e:
                self.send_message(f"❌ Error generating post: {str(e)}")

        elif step == "AWAITING_EDIT_INSTRUCTIONS":
            self.send_message("🛠 <i>Applying updates to your draft...</i>")
            try:
                original_draft = state.get("current_draft")
                new_draft = self.groq.edit_post(original_draft, text_received)
                update_state(step="AWAITING_APPROVAL", current_draft=new_draft)
                
                preview_text = f"📝 <b>Updated Post Preview:</b>\n\n{new_draft}"
                msg_id = self.send_message(preview_text, reply_markup=self.get_approval_keyboard())
                update_state(last_message_id=msg_id)
            except Exception as e:
                self.send_message(f"❌ Error modifying post: {str(e)}")

    def handle_callback_query(self, query: dict):
        state = get_state()
        data = query["data"]
        message_id = query["message"]["message_id"]

        if data == "approve":
            self.edit_message(message_id, "🚀 <i>Publishing to your LinkedIn Company Page...</i>")
            try:
                caption = state.get("current_draft")
                post_urn = self.linkedin.publish_post(caption)
                
                # Format URL based on the restli URN
                post_id = post_urn.split(":")[-1]
                linkedin_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}"
                
                self.edit_message(message_id, f"✅ <b>Successfully Posted to LinkedIn!</b>\n\n🔗 <a href='{linkedin_url}'>View Post on LinkedIn</a>")
                log_post_history(caption, post_urn)
                reset_state()
                sys.exit(0) # Complete successfully
            except Exception as e:
                self.send_message(f"❌ Failed to publish: {str(e)}")
                self.edit_message(message_id, "⚠️ Publication failed. Let's try again below.", reply_markup=self.get_approval_keyboard())

        elif data == "regenerate":
            self.edit_message(message_id, "🔄 <i>Regenerating alternative variation...</i>")
            try:
                topic = state.get("prompt_topic")
                new_draft = self.groq.generate_post(topic, temperature=0.85) # High temp to force variation
                update_state(step="AWAITING_APPROVAL", current_draft=new_draft)
                
                preview_text = f"📝 <b>New Draft Variation:</b>\n\n{new_draft}"
                self.edit_message(message_id, preview_text, reply_markup=self.get_approval_keyboard())
            except Exception as e:
                self.send_message(f"❌ Error during regeneration: {str(e)}")

        elif data == "edit":
            update_state(step="AWAITING_EDIT_INSTRUCTIONS")
            self.edit_message(message_id, "💬 <b>Please reply with edits.</b>\n\nYou can input instructions (e.g. <i>'make it tone more professional'</i>) or reply with a raw replacement text.")

        elif data == "cancel":
            self.edit_message(message_id, "❌ <b>Session Cancelled.</b> This post was discarded.")
            reset_state()
            sys.exit(0)