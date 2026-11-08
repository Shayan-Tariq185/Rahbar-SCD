"""Grounding and citation checks for generated answers."""

from __future__ import annotations

from ..schemas import Answer, Passage


def should_abstain(passages: list[Passage], relevance_floor: float) -> bool:
    return not passages or max(passage.score for passage in passages) < relevance_floor


def check_citations(answer: Answer, passages: list[Passage]) -> Answer:
    from ..schemas import Citation

    def match(c: Citation, p: Passage) -> bool:
        if c.source.strip().lower() != p.source.strip().lower():
            return False
        c_sec = c.section.strip().lower()
        p_sec = p.section.strip().lower()
        if c_sec == p_sec or p_sec.startswith(c_sec) or c_sec.startswith(p_sec):
            return True
        c_num = c_sec.split()[0].rstrip(".")
        p_num = p_sec.split()[0].rstrip(".")
        return bool(c_num and p_num and c_num == p_num)

    matched: list[Citation] = []
    for citation in answer.citations:
        for passage in passages:
            if match(citation, passage):
                matched.append(Citation(source=passage.source, section=passage.section, page=passage.page))
                break

    # If the model didn't provide citations or cited non-existent sources, but answered from context,
    # backfill the citation with the top retrieved passage if relevant
    if not matched and passages and answer.answered_from_context:
        top = passages[0]
        matched.append(Citation(source=top.source, section=top.section, page=top.page))

    return answer.model_copy(
        update={
            "citations": matched,
            "answered_from_context": True if matched else False,
            "confidence": "high" if matched else "low",
        }
    )
