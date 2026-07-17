import json

from app.sources import JsonSourceAdapter, SourceLicense, parse_ipo_cz_st96_record


def test_json_source_paginates_and_normalizes(tmp_path) -> None:
    path = tmp_path / "records.json"
    path.write_text(
        json.dumps(
            [
                {
                    "source_record_id": f"record-{index}",
                    "name": f"标识{index}",
                    "application_number": f"APP{index}",
                    "applicant": "课程组",
                    "nice_classes": [9, 42],
                    "goods_services": ["软件"],
                    "status": "申请中",
                    "source_url": f"demo://record/{index}",
                }
                for index in range(3)
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    adapter = JsonSourceAdapter(
        "test-json",
        "测试 JSON",
        path,
        SourceLicense("test", None, "test only"),
    )

    first = adapter.fetch_page(None, 2)
    second = adapter.fetch_page(first.next_cursor, 2)

    assert len(first.records) == 2
    assert not first.done
    assert len(second.records) == 1
    assert second.done
    assert adapter.normalize(first.records[0]).nice_classes == [9, 42]


def test_ipo_cz_st96_record_is_normalized() -> None:
    payload = b"""<?xml version='1.0' encoding='UTF-8'?>
    <tmk:Trademark xmlns:tmk='http://www.wipo.int/standards/XMLSchema/ST96/Trademark'
      xmlns:com='http://www.wipo.int/standards/XMLSchema/ST96/Common'
      com:operationCategory='Insert'>
      <com:ApplicationNumber><com:ApplicationNumberText>123456</com:ApplicationNumberText></com:ApplicationNumber>
      <com:ApplicationDate>2026-01-02</com:ApplicationDate>
      <tmk:MarkCurrentStatusCode>6</tmk:MarkCurrentStatusCode>
      <tmk:MarkRepresentation><tmk:MarkSignificantVerbalElementText>REAL MARK</tmk:MarkSignificantVerbalElementText></tmk:MarkRepresentation>
      <tmk:GoodsServices><tmk:ClassNumber>9</tmk:ClassNumber><tmk:GoodsServicesDescriptionText>software</tmk:GoodsServicesDescriptionText></tmk:GoodsServices>
      <tmk:Applicant><com:OrganizationStandardName>Example s.r.o.</com:OrganizationStandardName></tmk:Applicant>
    </tmk:Trademark>"""

    record = parse_ipo_cz_st96_record(payload, "TM123456/record.xml")

    assert record["source_record_id"] == "CZ-TM-123456"
    assert record["name"] == "REAL MARK"
    assert record["nice_classes"] == [9]
    assert record["status"] == "已注册"
    assert record["applicant"] == "Example s.r.o."
    assert record["is_demo"] is False
