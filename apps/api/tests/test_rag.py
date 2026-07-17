from datetime import date

import pytest
from langchain_core.documents import Document
from pydantic import ValidationError

from app.rag import (
    REPORT_SECTION_MIN_LENGTHS,
    REPORT_SECTION_ORDER,
    DocumentNarrative,
    citation_from_document,
    validate_document,
)


def citation(effective_from: str = "2019-11-01", effective_to: str | None = None):
    document = Document(
        page_content="申请注册商标不得与在先商标构成相同或者近似。",
        metadata={
            "chunk_id": "chunk-1",
            "source_id": "source-1",
            "title": "中华人民共和国商标法",
            "authority": "全国人大常委会",
            "locator": "第三十条",
            "source_url": "https://flk.npc.gov.cn/",
            "effective_from": effective_from,
            "effective_to": effective_to,
        },
    )
    return citation_from_document(document)


def test_document_validator_accepts_traceable_citation_and_fact() -> None:
    citations = [citation()]
    sections = [
        {
            "section_id": "law",
            "title": "法律依据",
            "content": "候选申请号 MLDEMO202600001。",
            "citation_ids": [citations[0]["citation_id"]],
        }
    ]
    facts = {"candidates": [{"application_number": "MLDEMO202600001"}]}
    assert validate_document(sections, citations, facts, date(2026, 7, 13)) == []


def test_document_validator_blocks_unknown_and_future_citations() -> None:
    citations = [citation("2027-01-01")]
    sections = [
        {
            "section_id": "law",
            "title": "法律依据",
            "content": "无额外事实。",
            "citation_ids": ["cite_missing"],
        }
    ]
    errors = validate_document(sections, citations, {"candidates": []}, date(2026, 7, 13))
    assert {item["code"] for item in errors} == {"INVALID_CITATION", "INAPPLICABLE_CITATION"}


def test_professional_report_schema_requires_all_detailed_sections() -> None:
    sections = [
        {
            "section_id": section_id,
            "title": f"{section_id}章节",
            "content": "分析" * REPORT_SECTION_MIN_LENGTHS[section_id],
            "citation_ids": [],
        }
        for section_id in REPORT_SECTION_ORDER
    ]
    report = DocumentNarrative(sections=sections, citation_ids=[])
    assert [section.section_id for section in report.sections] == REPORT_SECTION_ORDER

    sections[4]["content"] = "分析仍然不足" * 80
    with pytest.raises(ValidationError, match="章节分析不足"):
        DocumentNarrative(sections=sections, citation_ids=[])


def test_document_validator_accepts_audited_foreign_reference() -> None:
    sections = [
        {
            "section_id": "candidates",
            "title": "境外参考",
            "content": "境外记录 MOBIS（申请号：CZ-112239，申请人：MATADOR HOLDING, a.s.）仅用于相似度参考。",
            "citation_ids": [],
        }
    ]
    facts = {
        "candidates": [],
        "foreign_reference_candidates": [
            {
                "application_number": "CZ-112239",
                "applicant": "MATADOR HOLDING, a.s.",
            }
        ],
    }
    assert validate_document(sections, [], facts, date(2026, 7, 17)) == []
