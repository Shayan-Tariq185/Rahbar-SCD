from __future__ import annotations

from pipeline.chunk import chunk
from pipeline.models import Document, Page


def _doc(text: str, source: str = "d.md", version: str = "2026", old: bool = False) -> Document:
    return Document(source, version, old, [Page(source, 1, text)])


RULES = """# Rules

## 1. Attendance

1.1 A student must attend at least 80 percent of lectures.

1.2 Below the minimum the grade is FA.

## 2. Academic warning

2.1 A CGPA below 2.00 means warning.
"""


def test_clauses_become_chunks_with_section_labels_and_heading_context() -> None:
    chunks = chunk(_doc(RULES), 400, 50)
    by_section = {c.section: c for c in chunks}
    assert "1.1 A student must attend at least" in by_section
    first = by_section["1.1 A student must attend at least"]
    assert "\n1. Attendance\n1.1 A student must attend" in "\n" + first.text
    assert "2.1 A CGPA below 2.00 means warning" in by_section


def test_every_chunk_has_required_metadata() -> None:
    for c in chunk(_doc(RULES, "x.pdf", "2023-08", True), 400, 50):
        meta = c.metadata()
        assert set(meta) == {"source", "section", "page", "doc_version", "superseded"}
        assert meta["source"] == "x.pdf" and meta["doc_version"] == "2023-08"
        assert meta["superseded"] is True and meta["page"] >= 1 and meta["section"]


def test_ids_are_stable_unique_and_ordered() -> None:
    a = [c.id for c in chunk(_doc(RULES), 400, 50)]
    b = [c.id for c in chunk(_doc(RULES), 400, 50)]
    assert a == b and len(set(a)) == len(a)
    assert a[0] == "d.md-0000"


def test_a_definition_that_fits_is_never_split() -> None:
    words = " ".join(f"w{i}" for i in range(150))
    text = f"## 4. Definitions\n\n4.1 Plagiarism means {words}.\n"
    chunks = [c for c in chunk(_doc(text), 400, 50) if c.section.startswith("4.1")]
    assert len(chunks) == 1 and "w149" in chunks[0].text


def test_long_section_is_split_under_size_with_overlap() -> None:
    sentences = " ".join(f"Sentence number {i} is here with some words." for i in range(60))
    chunks = chunk(_doc(f"## 9. Long\n\n9.1 {sentences}\n"), 60, 10)
    assert len(chunks) > 2
    for c in chunks:
        assert len(c.text.split()) <= 60
    # the overlap: the last words of a chunk reappear at the start of the next
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        tail = prev.text.split()[-3:]
        assert " ".join(tail) in nxt.text


def test_overlap_larger_than_size_is_clamped_and_terminates() -> None:
    text = "## 1. A\n\n1.1 " + " ".join(f"Word{i}." for i in range(100))
    assert chunk(_doc(text), 10, 50)


def test_table_rows_stay_whole_with_their_headers() -> None:
    rows = "\n".join(f"Charge: Item {i} | Amount (PKR): {i},000" for i in range(30))
    chunks = chunk(_doc(f"## 2. Charges\n\n{rows}\n"), 40, 5)
    assert len(chunks) > 1
    for c in chunks:
        for line in c.text.split("\n"):
            assert line.startswith("2. Charges") or line.startswith("Charge: Item")
            assert "Amount (PKR)" in line or line.startswith("2. Charges") or len(line.split()) < 6


def test_page_of_each_chunk_is_where_it_starts() -> None:
    doc = Document("d.pdf", "1", False, [Page("d.pdf", 1, "1.1 First clause on page one."),
                                         Page("d.pdf", 2, "1.2 Second clause on page two.")])
    assert [c.page for c in chunk(doc, 400, 50)] == [1, 2]


def test_empty_and_tiny_documents_give_no_chunks() -> None:
    assert chunk(_doc(""), 400, 50) == []
    assert chunk(_doc("ok"), 400, 50) == []


def test_heading_without_body_is_carried_into_next_block() -> None:
    chunks = chunk(_doc("# Title\n\n## 1. Topic\n\n1.1 Real clause text lives here."), 400, 50)
    assert len(chunks) == 1 and "Title" in chunks[0].text and "1. Topic" in chunks[0].text
