#!/usr/bin/env python3
"""Validate contract examples without third-party dependencies.

This intentionally implements only the JSON Schema features used by MarkLens contracts.
It keeps the first-day validation command available before dependencies are installed.
CI may add a full JSON Schema/OpenAPI validator later.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = {
    "v0.1": {
        "case-context.json": "case-context.schema.json",
        "evidence-bundle.json": "evidence-bundle.schema.json",
        "risk-assessment.json": "risk-assessment.schema.json",
        "document-draft.json": "document-draft.schema.json",
        "agent-run.json": "agent-run.schema.json",
        "error-response.json": "error-response.schema.json",
    },
    "v0.2": {
        "case-context.json": "case-context.schema.json",
        "asset-result.json": "asset-result.schema.json",
        "evidence-bundle.json": "evidence-bundle.schema.json",
        "risk-assessment.json": "risk-assessment.schema.json",
        "document-draft.json": "document-draft.schema.json",
        "consultation-answer.json": "consultation-answer.schema.json",
        "agent-run.json": "agent-run.schema.json",
        "source-definition.json": "source-definition.schema.json",
        "ingestion-run.json": "ingestion-run.schema.json",
        "error-response.json": "error-response.schema.json",
    },
}


class ContractError(Exception):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"{path.relative_to(ROOT)} 无法解析：{error}") from error


def matches_type(value: Any, expected: str) -> bool:
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: (
            isinstance(item, (int, float)) and not isinstance(item, bool)
        ),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    return checks[expected](value)


def validate(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if expected:
        expected_types = [expected] if isinstance(expected, str) else expected
        if not any(matches_type(value, item) for item in expected_types):
            return [f"{path}: 期望类型 {expected_types}，实际为 {type(value).__name__}"]

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: 必须等于 {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} 不在允许值中")

    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        errors.append(f"{path}: 字符串过短")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: 小于最小值 {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: 大于最大值 {schema['maximum']}")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: 缺少必填字段 {key!r}")
        if schema.get("additionalProperties") is False:
            for key in value.keys() - properties.keys():
                errors.append(f"{path}: 包含未定义字段 {key!r}")
        for key, item in value.items():
            if key in properties:
                errors.extend(validate(item, properties[key], f"{path}.{key}"))

    if isinstance(value, list):
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(validate(item, item_schema, f"{path}[{index}]"))
        if schema.get("uniqueItems") and len(
            {json.dumps(item, sort_keys=True) for item in value}
        ) != len(value):
            errors.append(f"{path}: 数组元素必须唯一")

    return errors


def validate_local_openapi_refs(contract_dir: Path) -> list[str]:
    openapi_path = contract_dir / "openapi.yaml"
    content = openapi_path.read_text(encoding="utf-8")
    references = re.findall(r"\$ref:\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))", content)
    errors: list[str] = []
    for groups in references:
        reference = next(item for item in groups if item)
        if reference.startswith("#"):
            continue
        local_path = (contract_dir / reference).resolve()
        if contract_dir.resolve() not in local_path.parents or not local_path.is_file():
            errors.append(f"openapi.yaml: 本地引用不存在或越界：{reference}")
    return errors


def main() -> int:
    errors: list[str] = []
    total = 0
    for version, pairs in CONTRACTS.items():
        contract_dir = ROOT / "contracts" / version
        for example_name, schema_name in pairs.items():
            total += 1
            example = read_json(contract_dir / "examples" / example_name)
            schema = read_json(contract_dir / "schemas" / schema_name)
            errors.extend(
                f"{version}/{example_name} {message}"
                for message in validate(example, schema)
            )
        errors.extend(validate_local_openapi_refs(contract_dir))

    if errors:
        print("Contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"Validated {total} examples and local OpenAPI references (contract-v0.1 + v0.2)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
