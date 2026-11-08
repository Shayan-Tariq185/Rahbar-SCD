"""Grounding and citation checks for generated answers."""

from __future__ import annotations

from ..schemas import Answer, Passage


def should_abstain(passages: list[Passage], relevance_floor: float) -> bool:
    return not passages or max(passage.score for passage in passages) < relevance_floor


def check_citations(answer: Answer, passages: list[Passage]) -> Answer:
    valid = {
        (passage.source, passage.section, passage.page)
        for passage in passages
    }
    citations = [
        citation
        for citation in answer.citations
        if (citation.source, citation.section, citation.page) in valid
    ]
    if answer.answered_from_context and not citations:
        return answer.model_copy(
            update={"citations": [], "answered_from_context": False, "confidence": "low"}
        )
    return answer.model_copy(update={"citations": citations})
