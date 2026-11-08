"""Hosted free-tier provider (Groq, Google AI Studio, OpenRouter). Yours to build.

The key arrives as LLM_API_KEY from a Kubernetes Secret created on the command
line. It never appears in a file you commit, and never in a log line.
"""

from __future__ import annotations

import json
import logging

import httpx

from ...config import Settings
from ...schemas import Answer, Passage
from ...services.validate import fallback_answer, parse_answer

log = logging.getLogger("rahbar.hosted")


class HostedProvider:
    name = "hosted"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings   # hosted_base_url, llm_model, llm_api_key, temperature

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        if not self.settings.llm_api_key:
            log.warning("LLM_API_KEY is empty! Falling back to StubProvider.")
            from .stub import StubProvider

            return StubProvider().generate(question, passages)

        evidence = "\n\n".join(
            f"[{index}] {passage.source} / {passage.section} / page {passage.page}\n"
            f"{passage.text}"
            for index, passage in enumerate(passages, 1)
        )
        prompt = (
            "You are a helpful assistant answering strictly from the provided EVIDENCE.\n"
            "Answer the question directly, cite the exact source and section from the evidence.\n"
            "If the evidence does not contain the answer, say so honestly.\n\n"
            f"EVIDENCE:\n{evidence}\n\n"
            f"QUESTION:\n{question}\n\n"
            f"You must return ONLY a JSON object conforming to this schema:\n"
            f"{json.dumps(Answer.model_json_schema())}"
        )
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": "You are a precise document QA system. Return strictly JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.settings.temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key.strip()}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            for attempt in range(2):
                try:
                    response = client.post(
                        f"{self.settings.hosted_base_url.rstrip('/')}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code != 200:
                        log.error("Hosted LLM API returned status %s: %s", response.status_code, response.text)
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"].strip()
                    if content.startswith("```"):
                        lines = content.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        content = "\n".join(lines).strip()
                    parsed = json.loads(content)
                    return parse_answer(parsed)
                except Exception as exc:
                    log.error("Hosted LLM attempt %d failed: %s", attempt + 1, exc)
                    continue
        return fallback_answer()
