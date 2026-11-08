from __future__ import annotations

from run_eval import citation_validity, gate, recall_at_k, summarise


def test_recall_matches_section_prefix() -> None:
    relevant = [{"source": "rules.pdf", "section": "5.4"}]
    retrieved = [{"source": "rules.pdf", "section": "5.4 Academic Warning"}]

    assert recall_at_k(relevant, retrieved, 5) == 1.0


def test_recall_returns_none_without_relevant_passages() -> None:
    assert recall_at_k([], [], 5) is None


def test_citation_validity_rejects_unknown_citations() -> None:
    response = {
        "citations": [
            {"source": "rules.pdf", "section": "5.4", "page": 2},
            {"source": "other.pdf", "section": "1.1", "page": 1},
        ],
        "retrieved": [
            {"source": "rules.pdf", "section": "5.4", "page": 2},
        ],
    }

    assert citation_validity(response) == 0.5


def test_summary_and_gate_measure_abstention_and_citations() -> None:
    rows = [
        {
            "type": "ordinary",
            "relevant": [{"source": "rules.pdf", "section": "1.1"}],
            "must_abstain": False,
            "response": {
                "answered_from_context": True,
                "citations": [{"source": "rules.pdf", "section": "1.1", "page": 1}],
                "retrieved": [
                    {"source": "rules.pdf", "section": "1.1", "page": 1},
                ],
            },
        },
        {
            "type": "abstain",
            "relevant": [],
            "must_abstain": True,
            "response": {
                "answered_from_context": False,
                "citations": [],
                "retrieved": [],
            },
        },
    ]

    result = summarise(rows)
    assert result["recall_at_5"] == 1.0
    assert result["citation_validity"] == 1.0
    assert result["abstention_correctness"] == 1.0
    assert gate(result, None) == []
