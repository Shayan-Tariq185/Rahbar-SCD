from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pipeline.clean import clean
from pipeline.extract import extract, render_table
from pipeline.models import Document, Page

from .pdfmaker import scanned_pdf, table_pdf, text_pdf, two_column_pdf


def test_markdown_front_matter_is_dropped_and_tables_become_rows(tmp_path: Path) -> None:
    md = tmp_path / "f.md"
    md.write_text("---\nsource: f.md\n---\n# Title\n\n| Charge | Amount |\n| --- | --- |\n"
                  "| Late | 3,000 |\n| Transcript | 1,500 |\n", encoding="utf-8")
    doc = extract(str(md), "2026", False)
    text = doc.pages[0].text
    assert "source:" not in text
    assert "Charge: Late | Amount: 3,000" in text
    assert "Charge: Transcript | Amount: 1,500" in text
    assert (doc.doc_version, doc.superseded) == ("2026", False)


def test_render_table_keeps_headers_with_each_row() -> None:
    rows = [["Patron\nGroup", "Fine"], ["PhD", "PKR\n10/day"], ["Graduate", None]]
    assert render_table(rows) == ["Patron Group: PhD | Fine: PKR 10/day", "Patron Group: Graduate"]


def test_text_pdf_is_not_ocrd(tmp_path: Path) -> None:
    body = ["1.21 Students are required to maintain 100% attendance in each course."] * 3
    pdf = text_pdf(tmp_path / "t.pdf", [body, body])
    doc = extract(str(pdf), "2026-06", False)
    assert [p.ocr for p in doc.pages] == [False, False]
    assert "100% attendance" in doc.pages[0].text


def test_pdf_table_is_rendered_as_labelled_rows(tmp_path: Path) -> None:
    rows = [["Patron Group", "Loan Limit", "Fine Ceiling"], ["PhD", "07", "PKR 5,000"],
            ["Graduate", "05", "PKR 5,000"]]
    pdf = table_pdf(tmp_path / "tab.pdf", rows, "Library material is issued as follows and"
                    " the loan periods differ by patron group for all members.")
    text = extract(str(pdf), "x", False).pages[0].text
    assert "Patron Group: PhD | Loan Limit: 07 | Fine Ceiling: PKR 5,000" in text


def test_two_column_page_is_read_column_by_column(tmp_path: Path) -> None:
    left = [f"left column line {i} alpha beta gamma delta" for i in range(12)]
    right = [f"right column line {i} epsilon zeta eta theta" for i in range(12)]
    text = extract(str(two_column_pdf(tmp_path / "c.pdf", left, right)), "x", False).pages[0].text
    assert text.index("left column line 11") < text.index("right column line 0")


@pytest.mark.skipif(not shutil.which("tesseract") or not shutil.which("pdftoppm"),
                    reason="needs tesseract-ocr and poppler-utils")
def test_scanned_page_is_ocrd_and_flagged(tmp_path: Path) -> None:
    pdf = scanned_pdf(tmp_path / "scan.pdf", "Attendance policy requires eighty percent")
    page = extract(str(pdf), "2022-05", False).pages[0]
    assert page.ocr is True
    assert "attendance" in page.text.lower()


def test_unsupported_file_type_is_an_error(tmp_path: Path) -> None:
    f = tmp_path / "x.docx"
    f.write_bytes(b"x")
    with pytest.raises(ValueError):
        extract(str(f), "1", False)


def _doc(*texts: str) -> Document:
    return Document("d.pdf", "1", False, [Page("d.pdf", i, t) for i, t in enumerate(texts, 1)])


def test_clean_removes_repeating_header_footer_and_page_numbers() -> None:
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]
    body = "\n".join(f"Body text line about {w} topics." for w in words)
    pages = [f"NUCES Academic Rules\n{body}\nPage {i}\n" for i in range(1, 6)]
    out = clean(_doc(*pages))
    for page in out.pages:
        assert "NUCES Academic Rules" not in page.text
        assert not page.text.lower().startswith("page")
        assert "Body text" in page.text


def test_clean_keeps_numbered_clause_headings() -> None:
    pages = ["Header\n1.21 Attendance Requirements\nBody one.\n3", "Header\n5.4 Academic Warning\nBody two.\n4",
             "Header\n2. Grades\nBody three.\n5"]
    text = "\n".join(p.text for p in clean(_doc(*pages)).pages)
    for heading in ("1.21 Attendance Requirements", "5.4 Academic Warning", "2. Grades"):
        assert heading in text
    assert "Header" not in text


def test_clean_dehyphenates_and_normalises_whitespace() -> None:
    out = clean(_doc("The exami-\nnation   rules\t apply.\n\n\n\nNext.")).pages[0].text
    assert "examination rules apply." in out
    assert "\n\n\n" not in out


def test_clean_does_not_mutate_input_and_keeps_ocr_flag() -> None:
    doc = Document("d.pdf", "1", True, [Page("d.pdf", 1, "a  b", ocr=True)])
    out = clean(doc)
    assert doc.pages[0].text == "a  b" and out.pages[0].ocr is True and out.superseded is True
