import json
import logging
import re
import time

import requests
from requests import ConnectionError, Timeout

from config import GROQ_API_KEY, GROQ_MODEL
from bot.prompts import SYSTEM_PROMPT, get_generation_prompt, get_edit_prompt

logger = logging.getLogger(__name__)

MAX_RESEARCH_ARTICLES = 3
MAX_SUMMARY_CHARS = 250
MAX_RESEARCH_INPUT_CHARS = 5200
MAX_COMPLETION_TOKENS = 700
MAX_GROQ_RETRIES = 3


class GroqClient:
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_post(self, user_input, temperature: float = 0.7) -> str:
        logger.info("stage=groq.generate_post status=started input_type=%s", type(user_input).__name__)
        if hasattr(user_input, "articles"):
            prompt_input = self._format_research_bundle(user_input)
        else:
            prompt_input = str(user_input)

        prompt = get_generation_prompt(prompt_input)
        logger.info(
            "stage=groq.prompt status=prepared estimated_tokens=%s prompt_chars=%s",
            self._estimate_tokens(SYSTEM_PROMPT + prompt),
            len(SYSTEM_PROMPT) + len(prompt),
        )
        draft = self._call_api(prompt, temperature)
        logger.info("stage=groq.generate_post status=completed draft_chars=%s", len(draft))
        return draft

    def edit_post(self, original_draft: str, feedback: str) -> str:
        if len(feedback.strip()) > 300 and "\n" in feedback:
            return feedback.strip()

        prompt = get_edit_prompt(original_draft, feedback)
        return self._call_api(prompt, temperature=0.5)

    def _format_research_bundle(self, bundle) -> str:
        lines = [f"Topic:\n{bundle.query}\n"]
        budget_remaining = MAX_RESEARCH_INPUT_CHARS - len(lines[0])

        for index, article in enumerate(bundle.articles[:MAX_RESEARCH_ARTICLES], start=1):
            article_lines = [
                f"ARTICLE {index}",
                f"Title: {article.title}",
                f"Source: {article.domain or article.provider}",
                f"Published: {article.published or ''}",
            ]

            if article.summary:
                article_lines.append(f"Summary: {article.summary[:MAX_SUMMARY_CHARS]}")

            if article.content:
                content_budget = max(0, min(1200, budget_remaining - 300))
                if content_budget:
                    article_lines.append(f"Content: {article.content[:content_budget]}")

            if article.url:
                article_lines.append(f"URL: {article.url}")

            article_text = "\n".join(article_lines)
            if len(article_text) > budget_remaining:
                article_text = article_text[:budget_remaining]

            if not article_text.strip():
                break

            lines.append(article_text)
            budget_remaining -= len(article_text)

            if budget_remaining <= 0:
                break

        return "\n\n".join(lines)

    def _call_api(self, prompt: str, temperature: float) -> str:
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "include_reasoning": False,
            "reasoning_effort": "low",
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }

        for attempt in range(1, MAX_GROQ_RETRIES + 2):
            response = self._post_with_transport_handling(payload)
            logger.info(
                "stage=groq.api status=response attempt=%s status_code=%s",
                attempt,
                response.status_code,
            )

            if response.status_code != 429:
                break

            retry_seconds = self._parse_retry_seconds(response)
            if attempt > MAX_GROQ_RETRIES:
                logger.error(
                    "stage=groq.rate_limit status=exhausted attempts=%s retry_seconds=%s response=%s",
                    attempt,
                    retry_seconds,
                    response.text[:1000],
                )
                raise RuntimeError(
                    "Groq rate limit persisted after retries. Try again shortly."
                )

            wait_seconds = (retry_seconds + 1) * (2 ** (attempt - 1))
            logger.warning(
                "stage=groq.rate_limit status=retry attempt=%s retry_seconds=%s wait_seconds=%s response=%s",
                attempt,
                retry_seconds,
                wait_seconds,
                response.text[:1000],
            )
            time.sleep(wait_seconds)

        if response.status_code != 200:
            raise Exception(
                f"Groq API returned an error: {response.status_code} - {response.text}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            logger.exception("stage=groq.api status=failed reason=invalid_json")
            raise RuntimeError(f"Groq returned invalid JSON: {response.text[:500]}") from exc

        try:
            draft = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            logger.exception("stage=groq.api status=failed reason=unexpected_schema")
            raise RuntimeError(f"Groq response schema was unexpected: {data}") from exc

        if not draft:
            finish_reason = data.get("choices", [{}])[0].get("finish_reason")
            usage = data.get("usage", {})
            raise RuntimeError(
                "Groq returned an empty draft "
                f"(finish_reason={finish_reason}, usage={usage})."
            )

        choice = data.get("choices", [{}])[0]
        logger.info(
            "stage=groq.api status=final finish_reason=%s usage=%s draft_chars=%s",
            choice.get("finish_reason"),
            data.get("usage", {}),
            len(draft),
        )
        return draft

    def _post_with_transport_handling(self, payload):
        try:
            return requests.post(
                self.url,
                headers=self.headers,
                json=payload,
                timeout=60,
            )
        except Timeout as exc:
            logger.exception("stage=groq.api status=failed reason=timeout")
            raise RuntimeError("Groq request timed out. Try again in a moment.") from exc
        except ConnectionError as exc:
            logger.exception("stage=groq.api status=failed reason=connection_error")
            raise RuntimeError("Groq connection failed. Check network/API availability.") from exc
        except requests.RequestException as exc:
            logger.exception("stage=groq.api status=failed reason=request_exception")
            raise RuntimeError(f"Groq request failed: {exc}") from exc

    def _parse_retry_seconds(self, response) -> float:
        message = response.text or ""
        try:
            data = response.json()
            message = data.get("error", {}).get("message") or message
        except (ValueError, AttributeError):
            pass

        match = re.search(r"try again in\s+((?:(?P<minutes>\d+(?:\.\d+)?)m)?(?:(?P<seconds>\d+(?:\.\d+)?)s)?)", message, re.IGNORECASE)
        if match:
            minutes = float(match.group("minutes") or 0)
            seconds = float(match.group("seconds") or 0)
            retry_seconds = minutes * 60 + seconds
            if retry_seconds > 0:
                return retry_seconds

        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

        return 1.0

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)
