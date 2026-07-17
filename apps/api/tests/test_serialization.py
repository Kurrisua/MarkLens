from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.serialization import json_compatible, json_dumps


def test_json_compatible_converts_nested_application_values() -> None:
    value = {
        "status_date": date(2026, 6, 20),
        "generated_at": datetime(2026, 7, 17, 10, 30, 45),
        "identifier": UUID("12345678-1234-5678-1234-567812345678"),
        "score": Decimal("0.785714"),
        "items": ({"effective_to": None},),
    }

    converted = json_compatible(value)

    assert converted["status_date"] == "2026-06-20"
    assert converted["generated_at"] == "2026-07-17T10:30:45"
    assert converted["identifier"] == "12345678-1234-5678-1234-567812345678"
    assert converted["score"] == pytest.approx(0.785714)
    assert converted["items"] == [{"effective_to": None}]
    assert '"status_date": "2026-06-20"' in json_dumps(value)


def test_json_compatible_rejects_unknown_types() -> None:
    with pytest.raises(TypeError, match="不支持写入 JSON"):
        json_compatible(object())
