"""Build a professional, clearly fictional trademark-registration attachment pair.

The files are intentionally labelled as a course demo and contain the field
labels used by MarkLens' attachment normalizer (name, purpose and Nice classes).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    HRFlowable,
    Image as PdfImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "attachments"
DOCX_OUT = OUT / "MarkLens_商标注册资料示例_星瀚智联.docx"
PDF_OUT = OUT / "MarkLens_商标注册资料示例_星瀚智联.pdf"
LOGO_OUT = OUT / "MarkLens_星瀚智联_图样.png"

NAVY = "13263F"
TEAL = "006B63"
PALE_TEAL = "E9F4F1"
LIGHT = "F3F6F8"
MUTED = "5B6B7C"


def chinese_font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=0)
    return ImageFont.load_default()


def build_logo() -> None:
    """A restrained abstract star/lens image; it is a fictional sample mark."""
    img = Image.new("RGBA", (1200, 620), "white")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((28, 28, 1172, 592), radius=40, fill="#F5FAF9", outline="#B8DAD3", width=4)
    draw.ellipse((100, 130, 410, 440), fill="#006B63")
    draw.ellipse((145, 175, 365, 395), outline="white", width=18)
    draw.ellipse((205, 235, 305, 335), fill="white")
    # Four compact rays make the image read as a star plus lens, not an official emblem.
    draw.polygon([(255, 78), (275, 125), (255, 154), (235, 125)], fill="#D5A84B")
    draw.polygon([(455, 285), (405, 305), (376, 285), (405, 265)], fill="#D5A84B")
    draw.polygon([(255, 495), (275, 448), (255, 419), (235, 448)], fill="#D5A84B")
    title = chinese_font(80)
    sub = chinese_font(33)
    draw.text((500, 185), "星瀚智联", fill="#13263F", font=title)
    draw.text((505, 300), "XINGHAN INTELLIGENCE", fill="#006B63", font=sub)
    draw.text((505, 365), "课程演示图样 · 非官方商标", fill="#5B6B7C", font=sub)
    img.save(LOGO_OUT)


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_widths(table, widths_cm: list[float]) -> None:
    table.autofit = False
    for row in table.rows:
        for index, width in enumerate(widths_cm):
            row.cells[index].width = Cm(width)
            for cell in (row.cells[index],):
                set_cell_margins(cell)
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def run_font(run, size: float = 10.5, color: str = NAVY, bold: bool = False) -> None:
    run.font.name = "Hiragino Sans GB"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Hiragino Sans GB")
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    run.bold = bold


def set_paragraph(paragraph, before=0, after=6, line=1.1, align=None) -> None:
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line
    if align is not None:
        paragraph.alignment = align


def write_cell(cell, text: str, *, bold=False, color=NAVY, size=10.2) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    set_paragraph(p, after=0, line=1.08)
    r = p.add_run(text)
    run_font(r, size=size, color=color, bold=bold)


def add_heading(doc: Document, number: str, title: str) -> None:
    p = doc.add_paragraph()
    set_paragraph(p, before=12, after=6, line=1.1)
    r = p.add_run(f"{number}  {title}")
    run_font(r, size=13, color="2E74B5", bold=True)


def header_footer(doc: Document) -> None:
    section = doc.sections[0]
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)
    header = section.header.paragraphs[0]
    set_paragraph(header, after=0)
    left = header.add_run("MARKLENS  |  品牌资料归一化测试")
    run_font(left, size=8.5, color=MUTED, bold=True)
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer = section.footer.paragraphs[0]
    set_paragraph(footer, after=0)
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    f = footer.add_run("课程演示样本 · 不构成商标注册申请文件或法律意见")
    run_font(f, size=8.5, color=MUTED)


def build_docx() -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.1)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    header_footer(doc)
    normal = doc.styles["Normal"]
    normal.font.name = "Hiragino Sans GB"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Hiragino Sans GB")
    normal.font.size = Pt(10.5)

    p = doc.add_paragraph()
    set_paragraph(p, after=6, align=WD_ALIGN_PARAGRAPH.CENTER)
    r = p.add_run("商标注册申请材料")
    run_font(r, size=22, color=NAVY, bold=True)
    p = doc.add_paragraph()
    set_paragraph(p, after=13, align=WD_ALIGN_PARAGRAPH.CENTER)
    r = p.add_run("Trademark Registration Materials · Course Demonstration Sample")
    run_font(r, size=9.5, color=TEAL, bold=True)

    meta = doc.add_table(rows=2, cols=4)
    meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta.style = "Table Grid"
    set_table_widths(meta, [2.0, 5.0, 2.0, 5.0])
    values = [
        ("样本编号", "ML-DEMO-2026-001", "版本", "V1.0"),
        ("编制日期", "2026 年 7 月 25 日", "文件状态", "课程演示 · 仅供测试"),
    ]
    for row, data in zip(meta.rows, values):
        for i, value in enumerate(data):
            label = i % 2 == 0
            write_cell(row.cells[i], value, bold=label, color=NAVY if label else MUTED)
            if label:
                shade(row.cells[i], LIGHT)

    note = doc.add_table(rows=1, cols=1)
    note.style = "Table Grid"
    note.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_widths(note, [14.0])
    shade(note.cell(0, 0), PALE_TEAL)
    write_cell(note.cell(0, 0), "重要说明：本文件由 MarkLens 为课程演示与附件识别测试而制作。主体、图样、商品/服务和申请信息均为虚构示例，不具有任何登记、申请或法律证明效力。", bold=False, color=TEAL, size=9.5)

    add_heading(doc, "01", "申请标志基本信息")
    tbl = doc.add_table(rows=4, cols=2)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_widths(tbl, [3.0, 11.0])
    fields = [
        ("商标名称", "星瀚智联"),
        ("标志类型", "文字与图形组合标志（拟申请）"),
        ("使用目的", "用于面向中小企业的品牌管理、商标检索与知识产权咨询服务。"),
        ("商品/服务说明", "提供广告策划、商业管理辅助、软件即服务（SaaS）、商标代理与知识产权咨询等服务。"),
    ]
    for row, (label, value) in zip(tbl.rows, fields):
        shade(row.cells[0], LIGHT)
        write_cell(row.cells[0], label, bold=True)
        write_cell(row.cells[1], value, color=NAVY)

    add_heading(doc, "02", "拟定商品/服务与国际分类")
    classes = doc.add_table(rows=1, cols=3)
    classes.style = "Table Grid"
    classes.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_widths(classes, [2.3, 4.5, 7.2])
    headers = ["国际分类", "服务方向", "拟定服务表述（节选）"]
    for cell, value in zip(classes.rows[0].cells, headers):
        shade(cell, "E8EEF5")
        write_cell(cell, value, bold=True, color=NAVY, size=9.5)
    for row_data in [
        ("第 35 类", "广告与商业管理", "广告宣传；商业管理辅助；市场营销；为商品和服务的买卖双方提供在线市场。"),
        ("第 42 类", "软件与技术服务", "软件即服务（SaaS）；计算机软件设计；平台即服务（PaaS）；数据处理软件的开发。"),
        ("第 45 类", "知识产权服务", "商标代理服务；知识产权咨询；与知识产权有关的法律服务（课程演示用途）。"),
    ]:
        cells = classes.add_row().cells
        for cell, value in zip(cells, row_data):
            write_cell(cell, value, size=9.4)

    add_heading(doc, "03", "标志图样及使用说明")
    image_p = doc.add_paragraph()
    set_paragraph(image_p, after=5, align=WD_ALIGN_PARAGRAPH.CENTER)
    image_p.add_run().add_picture(str(LOGO_OUT), width=Cm(13.5))
    cap = doc.add_paragraph()
    set_paragraph(cap, after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
    r = cap.add_run("图 1  拟申请标志图样（课程演示图）")
    run_font(r, size=9, color=MUTED)
    p = doc.add_paragraph()
    set_paragraph(p, after=4, line=1.15)
    r = p.add_run("图样说明：")
    run_font(r, size=10.5, color=NAVY, bold=True)
    r = p.add_run("以抽象“星芒 + 透镜”构成识别符号，搭配“星瀚智联”文字。实际申请时，应另行核对图样清晰度、显著性、在先权利及商品/服务表述。")
    run_font(r, size=10.5, color=NAVY)

    add_heading(doc, "04", "附件识别字段核对")
    audit = doc.add_table(rows=1, cols=3)
    audit.style = "Table Grid"
    audit.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_widths(audit, [3.7, 6.6, 3.7])
    for cell, value in zip(audit.rows[0].cells, ["系统识别字段", "预期识别结果", "人工复核"]):
        shade(cell, "E8EEF5")
        write_cell(cell, value, bold=True, size=9.5)
    for row_data in [
        ("商标名称", "星瀚智联", "应自动带入"),
        ("使用目的", "品牌管理、检索及知识产权咨询服务", "应自动带入"),
        ("国际分类", "第 35 类、第 42 类、第 45 类", "应自动带入"),
    ]:
        cells = audit.add_row().cells
        for cell, value in zip(cells, row_data):
            write_cell(cell, value, size=9.4)

    add_heading(doc, "05", "声明与提交前复核")
    for text in [
        "本样本仅用于测试 MarkLens 对商标注册相关附件的格式归一化、文本提取和字段预填能力。",
        "系统生成的候选信息须由使用者复核；商标申请应以主管部门规定的材料、流程和专业意见为准。",
        "本文件不包含个人身份信息、真实企业资料、真实申请号或可用于实际提交的授权文件。",
    ]:
        p = doc.add_paragraph(style="List Bullet")
        set_paragraph(p, after=4, line=1.15)
        r = p.add_run(text)
        run_font(r, size=10.2, color=NAVY)
    sign = doc.add_paragraph()
    set_paragraph(sign, before=10, after=0, align=WD_ALIGN_PARAGRAPH.RIGHT)
    r = sign.add_run("MarkLens 课程项目组  |  资料归一化测试样本")
    run_font(r, size=9.5, color=MUTED)
    doc.save(DOCX_OUT)


def build_pdf() -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    doc = SimpleDocTemplate(
        str(PDF_OUT), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=17 * mm,
        title="商标注册申请材料 - 星瀚智联（课程演示样本）",
        author="MarkLens 课程项目组",
    )
    styles = getSampleStyleSheet()
    base = ParagraphStyle("Base", parent=styles["BodyText"], fontName="STSong-Light", fontSize=9.7, leading=15, textColor=colors.HexColor("#13263F"))
    title = ParagraphStyle("TitleCN", parent=base, fontSize=22, leading=28, alignment=TA_CENTER, textColor=colors.HexColor("#13263F"), spaceAfter=3)
    subtitle = ParagraphStyle("Sub", parent=base, fontSize=9.2, leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#006B63"), spaceAfter=10)
    h = ParagraphStyle("H", parent=base, fontSize=13, leading=18, textColor=colors.HexColor("#2E74B5"), spaceBefore=10, spaceAfter=6)
    small = ParagraphStyle("Small", parent=base, fontSize=8.8, leading=13, textColor=colors.HexColor("#5B6B7C"))
    story = [
        Paragraph("商标注册申请材料", title),
        Paragraph("Trademark Registration Materials · Course Demonstration Sample", subtitle),
    ]
    meta = Table([
        ["样本编号", "ML-DEMO-2026-001", "版本", "V1.0"],
        ["编制日期", "2026 年 7 月 25 日", "文件状态", "课程演示 · 仅供测试"],
    ], colWidths=[24*mm, 62*mm, 24*mm, 60*mm])
    meta.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "STSong-Light"), ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.HexColor("#13263F")), ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#F3F6F8")),
        ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#F3F6F8")), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#C8D2DB")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story += [meta, Spacer(1, 7), Table([[Paragraph("<b>重要说明：</b>本文件由 MarkLens 为课程演示与附件识别测试而制作。主体、图样、商品/服务和申请信息均为虚构示例，不具有任何登记、申请或法律证明效力。", ParagraphStyle("Note", parent=small, textColor=colors.HexColor("#006B63"), leading=14))]], colWidths=[170*mm], style=[("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#E9F4F1")), ("BOX", (0,0), (-1,-1), .35, colors.HexColor("#B8DAD3")), ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7)]), Spacer(1, 2)]

    def section(number, label):
        story.append(Paragraph(f"{number}  {label}", h))
    def key_table(rows, widths=(37*mm, 133*mm)):
        table = Table(rows, colWidths=list(widths))
        table.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), "STSong-Light"), ("FONTSIZE", (0,0), (-1,-1), 9.5),
            ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#C8D2DB")), ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#F3F6F8")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
            ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(table)
    section("01", "申请标志基本信息")
    key_table([
        ["商标名称", "星瀚智联"], ["标志类型", "文字与图形组合标志（拟申请）"],
        ["使用目的", "用于面向中小企业的品牌管理、商标检索与知识产权咨询服务。"],
        ["商品/服务说明", "提供广告策划、商业管理辅助、软件即服务（SaaS）、商标代理与知识产权咨询等服务。"],
    ])
    section("02", "拟定商品/服务与国际分类")
    ctable = Table([
        ["国际分类", "服务方向", "拟定服务表述（节选）"],
        ["第 35 类", "广告与商业管理", "广告宣传；商业管理辅助；市场营销；为商品和服务的买卖双方提供在线市场。"],
        ["第 42 类", "软件与技术服务", "软件即服务（SaaS）；计算机软件设计；平台即服务（PaaS）；数据处理软件的开发。"],
        ["第 45 类", "知识产权服务", "商标代理服务；知识产权咨询；与知识产权有关的法律服务（课程演示用途）。"],
    ], colWidths=[28*mm, 43*mm, 99*mm])
    ctable.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "STSong-Light"), ("FONTSIZE", (0,0), (-1,-1), 9),
        ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#C8D2DB")), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E8EEF5")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(ctable)
    section("03", "标志图样及使用说明")
    story += [PdfImage(str(LOGO_OUT), width=154*mm, height=79.5*mm), Spacer(1, 2), Paragraph("图 1  拟申请标志图样（课程演示图）", ParagraphStyle("Cap", parent=small, alignment=TA_CENTER)), Paragraph("<b>图样说明：</b>以抽象“星芒 + 透镜”构成识别符号，搭配“星瀚智联”文字。实际申请时，应另行核对图样清晰度、显著性、在先权利及商品/服务表述。", base)]
    section("04", "附件识别字段核对")
    key_table([["系统识别字段", "预期识别结果"], ["商标名称", "星瀚智联"], ["使用目的", "品牌管理、检索及知识产权咨询服务"], ["国际分类", "第 35 类、第 42 类、第 45 类"]], widths=(53*mm, 117*mm))
    section("05", "声明与提交前复核")
    for text in [
        "本样本仅用于测试 MarkLens 对商标注册相关附件的格式归一化、文本提取和字段预填能力。",
        "系统生成的候选信息须由使用者复核；商标申请应以主管部门规定的材料、流程和专业意见为准。",
        "本文件不包含个人身份信息、真实企业资料、真实申请号或可用于实际提交的授权文件。",
    ]:
        story.append(Paragraph("• " + text, base))
    def page(canvas, doc_):
        canvas.saveState(); canvas.setFont("STSong-Light", 8); canvas.setFillColor(colors.HexColor("#5B6B7C"))
        canvas.drawString(20*mm, 11*mm, "MarkLens · 课程演示样本 · 不构成商标注册申请文件或法律意见")
        canvas.drawRightString(190*mm, 11*mm, f"第 {doc_.page} 页")
        canvas.restoreState()
    doc.build(story, onFirstPage=page, onLaterPages=page)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build_logo()
    build_docx()
    build_pdf()
    print(DOCX_OUT)
    print(PDF_OUT)
