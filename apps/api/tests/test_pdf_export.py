from datetime import datetime

from app.models import DocumentDraft
from app.pdf_export import render_document_pdf


def test_saved_report_renders_as_chinese_capable_pdf() -> None:
    draft = DocumentDraft(
        id="report-test",
        title="“星航”商标注册风险评估报告",
        document_type="trademark_registration_risk_report",
        analysis_id="analysis-test",
        sections=[
            {
                "section_id": "summary",
                "title": "结论摘要",
                "content": "该报告已保存至数据库，可继续编辑并导出 PDF。",
            },
            {
                "section_id": "advice",
                "title": "下一步建议",
                "content": "完成官方检索，并结合实际商品服务范围进行复核。",
            },
        ],
        citations=[{"title": "商标法", "locator": "第三十条"}],
        updated_at=datetime(2026, 7, 21, 12, 0),
    )
    content = render_document_pdf(draft)
    assert content.startswith(b"%PDF")
    assert len(content) > 1_000
