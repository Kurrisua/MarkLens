"""PDF rendering for saved report drafts."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import DocumentDraft

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 52
BODY_FONT = "STSong-Light"
EMBEDDED_FONT = "MarkLensChinese"
SYSTEM_FONT_PATHS = (
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
)


def _body_font() -> str:
    """Embed a local Chinese font when available; CID is a portable fallback."""
    if EMBEDDED_FONT in pdfmetrics.getRegisteredFontNames():
        return EMBEDDED_FONT
    for path in SYSTEM_FONT_PATHS:
        if path.exists():
            pdfmetrics.registerFont(TTFont(EMBEDDED_FONT, str(path), subfontIndex=0))
            return EMBEDDED_FONT
    if BODY_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(BODY_FONT))
    return BODY_FONT


def _lines(text: str, font: str, size: float, width: float) -> list[str]:
    """Wrap Chinese and mixed text by rendered width, preserving paragraph breaks."""
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = f"{current}{char}"
            if current and pdfmetrics.stringWidth(candidate, font, size) > width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def render_document_pdf(document: DocumentDraft) -> bytes:
    """Render a database-backed draft into a compact, Chinese-capable PDF."""
    font = _body_font()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    page = 1

    def header() -> float:
        pdf.setFillColor("#0E5D55")
        pdf.setFont(font, 9)
        pdf.drawString(MARGIN, PAGE_HEIGHT - 34, "MarkLens · 商标风险初筛报告")
        pdf.setStrokeColor("#D6DED8")
        pdf.line(MARGIN, PAGE_HEIGHT - 42, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 42)
        return PAGE_HEIGHT - 70

    def footer() -> None:
        pdf.setStrokeColor("#D6DED8")
        pdf.line(MARGIN, 38, PAGE_WIDTH - MARGIN, 38)
        pdf.setFillColor("#627068")
        pdf.setFont(font, 8)
        pdf.drawString(MARGIN, 23, "仅供学习和初步决策参考，不构成法律意见。")
        pdf.drawRightString(PAGE_WIDTH - MARGIN, 23, f"第 {page} 页")

    def next_page() -> float:
        nonlocal page
        footer()
        pdf.showPage()
        page += 1
        return header()

    y = header()
    pdf.setFillColor("#15253E")
    pdf.setFont(font, 18)
    for line in _lines(document.title, font, 18, PAGE_WIDTH - 2 * MARGIN):
        pdf.drawString(MARGIN, y, line)
        y -= 26
    y -= 8
    pdf.setFillColor("#627068")
    pdf.setFont(font, 9)
    pdf.drawString(
        MARGIN, y, f"报告编号：{document.id}    保存时间：{document.updated_at:%Y-%m-%d %H:%M}"
    )
    y -= 28

    for section in document.sections:
        heading = str(section.get("title", "报告内容"))
        body = str(section.get("content", ""))
        if y < 90:
            y = next_page()
        pdf.setFillColor("#0E5D55")
        pdf.setFont(font, 13)
        pdf.drawString(MARGIN, y, heading)
        y -= 22
        pdf.setFillColor("#26384E")
        pdf.setFont(font, 10.5)
        for line in _lines(body, font, 10.5, PAGE_WIDTH - 2 * MARGIN):
            if y < 58:
                y = next_page()
                pdf.setFillColor("#26384E")
                pdf.setFont(font, 10.5)
            pdf.drawString(MARGIN, y, line)
            y -= 17
        y -= 12

    if document.citations:
        if y < 105:
            y = next_page()
        pdf.setFillColor("#0E5D55")
        pdf.setFont(font, 13)
        pdf.drawString(MARGIN, y, "参考依据")
        y -= 22
        pdf.setFillColor("#26384E")
        pdf.setFont(font, 9.5)
        for citation in document.citations:
            line = f"· {citation.get('title', '来源')}（{citation.get('locator', '')}）"
            for wrapped in _lines(line, font, 9.5, PAGE_WIDTH - 2 * MARGIN):
                if y < 58:
                    y = next_page()
                    pdf.setFillColor("#26384E")
                    pdf.setFont(font, 9.5)
                pdf.drawString(MARGIN, y, wrapped)
                y -= 15

    footer()
    pdf.save()
    return buffer.getvalue()
