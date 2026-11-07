"""Grounding, citation validation, and honest abstention (Track B).

Track B implements honest abstention based on similarity thresholds
and validates that model citations strictly match retrieved passages.
"""

from __future__ import annotations

from ..schemas import Answer, Passage


def should_abstain(passages: list[Passage], relevance_floor: float) -> bool:
    """Decide whether the system should abstain from answering.

    TODO(TrackB): Return True if passages is empty or top passage similarity < relevance_floor.
    """
    return False


def check_citations(answer: Answer, passages: list[Passage]) -> Answer:
    """Verify that every citation in the generated answer matches a retrieved passage.

    TODO(TrackB): Filter out hallucinated citations and downgrade confidence if citations are invalid.
    """
    return answer

