"""Schema-constrained generation, validation, and fallback (Track B).

Track B implements schema-constrained generation with one retry and a safe fallback
if the provider response is invalid or fails schema constraints.
"""

from __future__ import annotations

from ..config import Settings
from ..providers.llm.base import LLMProvider
from ..schemas import Answer, Passage


def generate_and_validate(
    question: str,
    passages: list[Passage],
    provider: LLMProvider,
    settings: Settings,
) -> Answer:
    """Generate an answer using the provider and validate against schema constraints.

    TODO(TrackB): Implement schema validation, one retry on error, and fallback answer generation.
    """
    return provider.generate(question, passages)

