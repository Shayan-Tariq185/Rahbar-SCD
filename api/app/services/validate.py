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
    seed: int | None = None,
    strict: bool = False,
) -> Answer:
    _ = settings
    retries = 1
    for attempt in range(retries + 1):
        try:
            if seed is not None:
                try:
                    res = provider.generate(question, passages, seed=seed)
                except TypeError:
                    res = provider.generate(question, passages)
            else:
                res = provider.generate(question, passages)
            if strict and (getattr(provider, "last_error", None) or res == fallback_answer()):
                raise RuntimeError(getattr(provider, "last_error", None) or "Provider returned an invalid-output fallback")
            return parse_answer(res.model_dump())
        except Exception:
            if attempt < retries:
                # retry generation once before fallback
                continue
            if strict:
                raise
            return fallback_answer()
    return fallback_answer()
