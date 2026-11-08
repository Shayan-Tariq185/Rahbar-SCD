"""Schema validation and safe fallback for provider responses."""

from __future__ import annotations

from typing import Any

from ..config import Settings
from ..providers.llm.base import LLMProvider
from ..schemas import Answer, Passage


def parse_answer(payload: Any) -> Answer:
    return Answer.model_validate(payload)


def fallback_answer() -> Answer:
    return Answer(
        reasoning="The model response could not be validated.",
        answer="The answer could not be generated reliably from the available evidence.",
        citations=[],
        answered_from_context=False,
        confidence="low",
    )


def generate_and_validate(
    question: str,
    passages: list[Passage],
    provider: LLMProvider,
    settings: Settings,
) -> Answer:
    _ = settings
    retries = 1
    for attempt in range(retries + 1):
        try:
            return parse_answer(provider.generate(question, passages).model_dump())
        except Exception:
            if attempt < retries:
                # retry generation once before fallback
                continue
            return fallback_answer()
    return fallback_answer()
