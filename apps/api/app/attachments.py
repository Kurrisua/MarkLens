"""Project attachment normalization for trademark-registration materials."""
from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from sqlalchemy.orm import Session

from .retrieval import save_asset


def _docx_text(content: bytes) -> tuple[str, list[str]]:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        parts = [name for name in archive.namelist() if name.startswith("word/") and name.endswith(".xml")]
        text = []
        for name in parts:
            root = ElementTree.fromstring(archive.read(name))
            text.extend(node.text for node in root.iter() if node.text)
        images = [name for name in archive.namelist() if name.startswith("word/media/")]
    return "\n".join(text), images


def _pdf_text(content: bytes) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages), len(reader.pages)
    except Exception:
        return "", 0


def _extracted_field(text: str, labels: str, limit: int) -> str:
    """Read a labelled value from either prose or a document-table extraction.

    DOCX/PDF readers commonly emit table cells on separate lines (``标签\n值``),
    whereas material typed into a paragraph uses ``标签：值``.  Supporting both
    representations keeps the attachment-created trademark form predictable.
    """
    match = re.search(rf"(?:{labels})\s*(?:[:：]\s*|\n+)([^\n\r]{{2,{limit}}})", text)
    return match.group(1).strip() if match else ""


def extract_attachment(session: Session, content: bytes, filename: str, mime_type: str) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    image_asset_id = None
    if mime_type.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        asset = save_asset(session, content, filename)
        image_asset_id = asset.id
        text = asset.ocr_text or ""
        structure: dict[str, Any] = {"kind": "image", "ocr_model": asset.ocr_model, "pages": 1}
    elif suffix == ".pdf" or mime_type == "application/pdf":
        text, pages = _pdf_text(content)
        structure = {"kind": "pdf", "pages": pages, "normalization": "text-preserved"}
    elif suffix == ".docx" or mime_type.endswith("wordprocessingml.document"):
        text, image_parts = _docx_text(content)
        structure = {"kind": "docx", "parts": ["document", "tables", "headers"], "embedded_images": len(image_parts)}
    else:
        raise ValueError("仅支持 PDF、DOCX、PNG、JPEG 和 WebP 格式。")
    classes = sorted({int(value) for value in re.findall(r"(?:第\s*)?(\d{1,2})\s*类", text) if 1 <= int(value) <= 45})
    trademark_name = _extracted_field(text, r"商标名称|申请商标|名称", 80)
    business_description = _extracted_field(text, r"使用目的|用途|商品[或/服务]*说明", 300)
    return {"normalized_text": text[:30000], "structure": {**structure, "extracted": {"trademark_name": trademark_name, "business_description": business_description, "nice_classes": classes}}, "extracted_image_asset_id": image_asset_id}
