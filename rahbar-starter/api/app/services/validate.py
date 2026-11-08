"""Validation and safe fallback for model responses."""

from __future__ import annotations

from typing import Any

from ..schemas import Answer


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
