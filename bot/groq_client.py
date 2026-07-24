import requests
from config import GROQ_API_KEY, GROQ_MODEL
from bot.prompts import (
    SYSTEM_PROMPT,
    get_generation_prompt,
    get_edit_prompt,
    get_news_grounded_generation_prompt,
    get_news_topic_summary_prompt,
)


class GroqClient:
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def generate_post(self, user_input: str, temperature: float = 0.7) -> str:
        prompt = get_generation_prompt(user_input)
        return self._call_api(prompt, temperature)

    def edit_post(self, original_draft: str, feedback: str) -> str:
        # Check if user has pasted a massive chunk of text, indicating a full replacement
        if len(feedback.strip()) > 300 and "\n" in feedback:
            return feedback.strip()

        prompt = get_edit_prompt(original_draft, feedback)
        return self._call_api(prompt, temperature=0.5)

    def generate_post_from_news(self, user_topic: str, news_block: str, temperature: float = 0.7) -> str:
        """Generate a post grounded in a curated list of recent news items."""
        prompt = get_news_grounded_generation_prompt(user_topic, news_block)
        return self._call_api(prompt, temperature)

    def generate_post_from_single_article(self, news_block: str, temperature: float = 0.6) -> str:
        """Summarize a single picked article into a LinkedIn post."""
        prompt = get_news_topic_summary_prompt(news_block)
        return self._call_api(prompt, temperature)

    def _call_api(self, prompt: str, temperature: float) -> str:
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }

        response = requests.post(self.url, headers=self.headers, json=payload, timeout=60)
        if response.status_code != 200:
            raise Exception(f"Groq API returned an error: {response.status_code} - {response.text}")

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
