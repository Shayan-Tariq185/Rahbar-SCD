"""Retrieval prompt-injection guardrail (D4).

Inspects retrieved passages BEFORE prompt augmentation, strips or neutralizes
embedded instruction-override directives, and records structured guardrail actions.

Limitation: Heuristic regex detection catches explicit directive patterns (e.g.
'ignore previous instructions', 'system prompt', 'reveal api keys'); it is not a
complete defense against obfuscated, encoded, or multi-turn semantic attacks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..schemas import Passage

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_instructions",
        re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
    ),
    (
        "disregard_instructions",
        re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions?|rules?)", re.IGNORECASE),
    ),
    (
        "override_policy",
        re.compile(r"(?:override|waive|bypass)\s+(?:all\s+)?(?:security\s+)?(?:rules?|policies?)", re.IGNORECASE),
    ),
    (
        "reveal_secrets",
        re.compile(r"(?:reveal|print|leak|output)\s+(?:the\s+)?(?:system\s+prompt|api\s*keys?|secrets?)", re.IGNORECASE),
    ),
    (
        "role_hijack",
        re.compile(r"(?:you\s+are\s+now|act\s+as\s+unrestricted|system\s+override\s*:)", re.IGNORECASE),
    ),
]


@dataclass
class GuardrailOutcome:
    passages: list[Passage]
    actions: list[dict[str, Any]] = field(default_factory=list)
    injection_count: int = 0


def inspect_and_sanitize_passages(passages: list[Passage]) -> GuardrailOutcome:
    """Scan retrieved passages for prompt-injection patterns and neutralize offending lines."""
    sanitized_passages: list[Passage] = []
    actions: list[dict[str, Any]] = []
    injection_count = 0

    for passage in passages:
        matched: list[str] = []
        for label, pattern in _INJECTION_PATTERNS:
            if pattern.search(passage.text):
                matched.append(label)

        if not matched:
            sanitized_passages.append(passage)
            continue

        injection_count += 1
        kept_lines: list[str] = []
        removed_lines = 0
        for line in passage.text.splitlines():
            if any(pat.search(line) for _, pat in _INJECTION_PATTERNS):
                removed_lines += 1
            else:
                kept_lines.append(line)

        cleaned_text = "\n".join(kept_lines).strip()
        if not cleaned_text:
            actions.append(
                {
                    "stage": "retrieval_guardrail",
                    "action": "blocked_injection",
                    "reason": "entire passage matched prompt-injection directive",
                    "matched_patterns": matched,
                    "chunk_ids": [passage.chunk_id],
                }
            )
            continue

        actions.append(
            {
                "stage": "retrieval_guardrail",
                "action": "sanitized_injection",
                "reason": f"stripped {removed_lines} injected line(s) before prompt construction",
                "matched_patterns": matched,
                "chunk_ids": [passage.chunk_id],
            }
        )
        sanitized_passages.append(
            passage.model_copy(
                update={
                    "text": f"{cleaned_text}\n[GUARDRAIL: untrusted instruction stripped]"
                }
            )
        )

    if not actions:
        actions.append(
            {
                "stage": "retrieval_guardrail",
                "action": "pass",
                "reason": "no injection patterns detected",
                "matched_patterns": [],
                "chunk_ids": [p.chunk_id for p in passages],
            }
        )

    return GuardrailOutcome(
        passages=sanitized_passages,
        actions=actions,
        injection_count=injection_count,
    )
