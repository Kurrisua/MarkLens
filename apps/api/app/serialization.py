"""Strict JSON conversion helpers for persisted facts and model inputs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def json_compatible(value: Any) -> Any:
    """Recursively convert supported application values to JSON-native types."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return json_compatible(value.value)
    if isinstance(value, Mapping):
        return {str(key): json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_compatible(item) for item in value]
    raise TypeError(f"不支持写入 JSON 的类型：{type(value).__name__}")


def json_dumps(value: Any) -> str:
    """Serialize application values after applying the strict conversion policy."""
    return json.dumps(json_compatible(value), ensure_ascii=False)
