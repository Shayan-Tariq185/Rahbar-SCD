"""Build tiny PDFs for the tests (reportlab), so no binary fixtures are committed."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle


def text_pdf(path: Path, pages: list[list[str]]) -> Path:
    c = canvas.Canvas(str(path), pagesize=A4)
    for lines in pages:
        y = 800
        for line in lines:
            c.drawString(50, y, line)
            y -= 16
        c.showPage()
    c.save()
    return path


def table_pdf(path: Path, rows: list[list[str]], intro: str) -> Path:
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import getSampleStyleSheet

    doc = SimpleDocTemplate(str(path), pagesize=A4)
    table = Table(rows)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.8, colors.black)]))
    doc.build([Paragraph(intro, getSampleStyleSheet()["Normal"]), table])
    return path


def two_column_pdf(path: Path, left: list[str], right: list[str]) -> Path:
    c = canvas.Canvas(str(path), pagesize=A4)
    for x, lines in ((50, left), (320, right)):
        y = 800
        for line in lines:
            c.drawString(x, y, line)
            y -= 14
    c.showPage()
    c.save()
    return path


def scanned_pdf(path: Path, text: str) -> Path:
    """A PDF whose only content is a picture of the text: no text layer at all."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1240, 400), "white")
    font = ImageFont.load_default(size=42)
    ImageDraw.Draw(image).text((40, 150), text, fill="black", font=font)
    png = path.with_suffix(".png")
    image.save(png)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(str(png), 20, 400, width=555, height=180)
    c.showPage()
    c.save()
    return path
