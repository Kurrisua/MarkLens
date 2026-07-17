"""Server-registered trademark source adapters and idempotent ingestion."""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import IngestionRun, SourceDefinition, Trademark
from .retrieval import normalize_text


@dataclass(frozen=True)
class SourceLicense:
    name: str
    url: str | None
    summary: str


@dataclass(frozen=True)
class SourcePage:
    records: list[dict[str, Any]]
    next_cursor: str | None
    done: bool


@dataclass(frozen=True)
class TrademarkIngestRecord:
    source_record_id: str
    name: str
    application_number: str
    applicant: str
    nice_classes: list[int]
    goods_services: list[str]
    status: str
    status_date: date | None
    application_date: date | None
    source_url: str
    image_path: str | None = None
    is_demo: bool = False
    raw: dict[str, Any] | None = None


class TrademarkSourceAdapter(ABC):
    source_key: str
    display_name: str
    adapter_type: str
    allowed_domains: tuple[str, ...] = ()
    rate_limit_per_minute: int | None = None

    @abstractmethod
    def license_info(self) -> SourceLicense: ...

    @abstractmethod
    def health_check(self) -> tuple[bool, str]: ...

    @abstractmethod
    def fetch_page(self, cursor: str | None, limit: int) -> SourcePage: ...

    @abstractmethod
    def normalize(self, raw_record: dict[str, Any]) -> TrademarkIngestRecord: ...


class JsonSourceAdapter(TrademarkSourceAdapter):
    adapter_type = "json"

    def __init__(
        self,
        source_key: str,
        display_name: str,
        path: Path,
        license_info: SourceLicense,
    ) -> None:
        self.source_key = source_key
        self.display_name = display_name
        self.path = path
        self._license = license_info

    def license_info(self) -> SourceLicense:
        return self._license

    def health_check(self) -> tuple[bool, str]:
        return self.path.exists(), "ready" if self.path.exists() else "文件不存在"

    def _records(self) -> list[dict[str, Any]]:
        with self.path.open(encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, list):
            raise ValueError("JSON 数据源根节点必须是数组")
        return payload

    def fetch_page(self, cursor: str | None, limit: int) -> SourcePage:
        records = self._records()
        start = int(cursor or 0)
        page = records[start : start + limit]
        next_index = start + len(page)
        return SourcePage(
            page, str(next_index) if next_index < len(records) else None, next_index >= len(records)
        )

    def normalize(self, raw_record: dict[str, Any]) -> TrademarkIngestRecord:
        return normalize_generic_record(raw_record)


class CsvSourceAdapter(JsonSourceAdapter):
    adapter_type = "csv"

    def _records(self) -> list[dict[str, Any]]:
        with self.path.open(encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))


class RegisteredHttpSourceAdapter(TrademarkSourceAdapter, ABC):
    """Base for future licensed HTTP sources.

    Adapters must hard-code their host allowlist and are registered at server startup.
    No API accepts a caller-provided URL.
    """

    adapter_type = "http"
    allowed_domains: tuple[str, ...]
    rate_limit_per_minute: int

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "allowed_domains", ()):
            raise TypeError("HTTP 数据源必须声明 allowed_domains")
        if not getattr(cls, "rate_limit_per_minute", 0):
            raise TypeError("HTTP 数据源必须声明 rate_limit_per_minute")


IPO_CZ_DATASET_URL = (
    "https://isdv.upv.gov.cz/webapp/webapp.opendata.datovasada"
    "?ptyp=tm96&pid=20260620diff"
)
IPO_CZ_TERMS_URL = "https://isdv.upv.gov.cz/doc/opendata/doc/podminky_uziti.html"

IPO_CZ_STATUS = {
    "1": "申请中",
    "2": "申请后终止",
    "3": "已公告",
    "4": "已撤销",
    "6": "已注册",
    "7": "公告后终止",
    "8": "已注销",
    "9": "已失效",
    "10": "视为未申请",
    "41": "无效",
    "51": "续展宽展期内有效",
    "52": "宽展期届满待处理",
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_xml_text(root: ElementTree.Element, name: str) -> str | None:
    for element in root.iter():
        if _local_name(element.tag) == name and element.text and element.text.strip():
            return element.text.strip()
    return None


def _all_xml_text(root: ElementTree.Element, name: str) -> list[str]:
    return [
        element.text.strip()
        for element in root.iter()
        if _local_name(element.tag) == name and element.text and element.text.strip()
    ]


def _applicant_name(root: ElementTree.Element) -> str:
    applicant = next(
        (element for element in root.iter() if _local_name(element.tag) == "Applicant"),
        None,
    )
    if applicant is None:
        return "申请人未公开"
    return (
        _first_xml_text(applicant, "OrganizationStandardName")
        or _first_xml_text(applicant, "PersonFullName")
        or "申请人未公开"
    )


def parse_ipo_cz_st96_record(xml_content: bytes, member_name: str) -> dict[str, Any]:
    root = ElementTree.fromstring(xml_content)
    application_number = _first_xml_text(root, "ApplicationNumberText")
    if not application_number:
        raise ValueError(f"ST.96 记录缺少申请号：{member_name}")
    verbal_elements = _all_xml_text(root, "MarkSignificantVerbalElementText")
    name = " / ".join(dict.fromkeys(verbal_elements)) or f"图形商标 CZ-{application_number}"
    classes = sorted(
        {
            int(value)
            for value in _all_xml_text(root, "ClassNumber")
            if value.isdigit() and int(value) > 0
        }
    )
    goods_services = list(dict.fromkeys(_all_xml_text(root, "GoodsServicesDescriptionText")))
    status_code = _first_xml_text(root, "MarkCurrentStatusCode") or "unknown"
    image_filename = _first_xml_text(root, "FileName")
    image_member = None
    if image_filename and "/" in member_name:
        image_member = f"{member_name.rsplit('/', 1)[0]}/{image_filename}"
    operation = next(
        (
            value
            for key, value in root.attrib.items()
            if _local_name(key) == "operationCategory"
        ),
        None,
    )
    registration_date = _first_xml_text(root, "RegistrationDate")
    return {
        "source_record_id": f"CZ-TM-{application_number}",
        "name": name,
        "application_number": f"CZ-{application_number}",
        "applicant": _applicant_name(root),
        "nice_classes": classes,
        "goods_services": goods_services,
        "status": IPO_CZ_STATUS.get(status_code, f"状态代码 {status_code}"),
        "status_date": registration_date,
        "application_date": _first_xml_text(root, "ApplicationDate"),
        "source_url": IPO_CZ_DATASET_URL,
        "is_demo": False,
        "jurisdiction": "CZ",
        "registration_number": _first_xml_text(root, "RegistrationNumber"),
        "mark_feature": _first_xml_text(root, "MarkFeatureCategory"),
        "status_code": status_code,
        "operation_category": operation,
        "source_member": member_name,
        "image_zip_member": image_member,
        "data_release": "2026-06-20",
    }


class IpoCzSt96Adapter(TrademarkSourceAdapter):
    """Official Czech IPO ST.96 ZIP adapter for the checked-in sample release."""

    adapter_type = "st96-xml"

    def __init__(self, path: Path) -> None:
        self.source_key = "ipo-cz-st96-20260620"
        self.display_name = "捷克工业产权局真实商标增量（2026-06-20）"
        self.path = path
        self._cache: list[dict[str, Any]] | None = None

    def license_info(self) -> SourceLicense:
        return SourceLicense(
            "IPO CZ 开放数据自由使用条款",
            IPO_CZ_TERMS_URL,
            "官方 ST.96 商标开放数据；可自由提取和使用，数据集声明不含个人数据。",
        )

    def health_check(self) -> tuple[bool, str]:
        return self.path.exists(), "ready" if self.path.exists() else "尚未下载样本 ZIP"

    def _records(self) -> list[dict[str, Any]]:
        if self._cache is None:
            with zipfile.ZipFile(self.path) as archive:
                members = sorted(
                    name for name in archive.namelist() if name.lower().endswith(".xml")
                )
                self._cache = [
                    parse_ipo_cz_st96_record(archive.read(name), name) for name in members
                ]
        return self._cache

    def fetch_page(self, cursor: str | None, limit: int) -> SourcePage:
        records = self._records()
        start = int(cursor or 0)
        page = records[start : start + limit]
        next_index = start + len(page)
        return SourcePage(
            page,
            str(next_index) if next_index < len(records) else None,
            next_index >= len(records),
        )

    def normalize(self, raw_record: dict[str, Any]) -> TrademarkIngestRecord:
        return normalize_generic_record(raw_record)

    def image_bytes(self, member_name: str) -> bytes:
        with zipfile.ZipFile(self.path) as archive:
            return archive.read(member_name)


def _date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _list(value: Any, cast: type = str) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [cast(item) for item in value]
    return [cast(item.strip()) for item in str(value).split("|") if item.strip()]


def normalize_generic_record(raw: dict[str, Any]) -> TrademarkIngestRecord:
    required = ["source_record_id", "name", "application_number", "applicant", "source_url"]
    missing = [field for field in required if not str(raw.get(field, "")).strip()]
    if missing:
        raise ValueError(f"缺少必填字段：{', '.join(missing)}")
    return TrademarkIngestRecord(
        source_record_id=str(raw["source_record_id"]).strip(),
        name=str(raw["name"]).strip(),
        application_number=str(raw["application_number"]).strip(),
        applicant=str(raw["applicant"]).strip(),
        nice_classes=_list(raw.get("nice_classes"), int),
        goods_services=_list(raw.get("goods_services")),
        status=str(raw.get("status") or "状态未知"),
        status_date=_date(raw.get("status_date")),
        application_date=_date(raw.get("application_date")),
        source_url=str(raw["source_url"]),
        image_path=str(raw["image_path"]) if raw.get("image_path") else None,
        is_demo=bool(raw.get("is_demo", False)),
        raw=raw,
    )


class SourceRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, TrademarkSourceAdapter] = {}

    def register(self, adapter: TrademarkSourceAdapter) -> None:
        if adapter.source_key in self._adapters:
            raise ValueError(f"数据源已注册：{adapter.source_key}")
        self._adapters[adapter.source_key] = adapter

    def get(self, source_key: str) -> TrademarkSourceAdapter:
        if source_key not in self._adapters:
            raise KeyError(source_key)
        return self._adapters[source_key]

    def values(self) -> list[TrademarkSourceAdapter]:
        return list(self._adapters.values())


def build_registry() -> SourceRegistry:
    settings = get_settings()
    registry = SourceRegistry()
    registry.register(
        JsonSourceAdapter(
            "demo-json",
            "MarkLens 教学样本（JSON）",
            settings.source_data_dir / "demo-trademarks.json",
            SourceLicense(
                "MarkLens 自建教学数据",
                None,
                "仅供课程演示。记录为合成样本，不代表官方商标数据。",
            ),
        )
    )
    registry.register(
        CsvSourceAdapter(
            "demo-csv",
            "MarkLens 导入格式示例（CSV）",
            settings.source_data_dir / "demo-import.csv",
            SourceLicense(
                "MarkLens 自建教学数据",
                None,
                "演示 CSV 分页、校验、更新和失败恢复。",
            ),
        )
    )
    registry.register(
        IpoCzSt96Adapter(
            settings.source_data_dir.parent / "raw" / "ipo-cz-20260620" / "source.zip"
        )
    )
    return registry


REGISTRY = build_registry()


def ensure_source_definitions(session: Session) -> None:
    for adapter in REGISTRY.values():
        existing = session.scalar(
            select(SourceDefinition).where(SourceDefinition.source_key == adapter.source_key)
        )
        license_info = adapter.license_info()
        if existing:
            existing.name = adapter.display_name
            existing.adapter_type = adapter.adapter_type
            existing.license_name = license_info.name
            existing.license_url = license_info.url
            existing.terms_summary = license_info.summary
            existing.allowed_domains = list(adapter.allowed_domains)
            existing.rate_limit_per_minute = adapter.rate_limit_per_minute
        else:
            session.add(
                SourceDefinition(
                    source_key=adapter.source_key,
                    name=adapter.display_name,
                    adapter_type=adapter.adapter_type,
                    license_name=license_info.name,
                    license_url=license_info.url,
                    terms_summary=license_info.summary,
                    allowed_domains=list(adapter.allowed_domains),
                    rate_limit_per_minute=adapter.rate_limit_per_minute,
                )
            )
    session.commit()


def _record_hash(record: TrademarkIngestRecord) -> str:
    payload = json.dumps(asdict(record), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sync_source(
    session: Session,
    source_key: str,
    cursor: str | None = None,
    page_size: int = 100,
    max_pages: int = 100,
    ingestion_run_id: str | None = None,
) -> IngestionRun:
    adapter = REGISTRY.get(source_key)
    source = session.scalar(
        select(SourceDefinition).where(SourceDefinition.source_key == source_key)
    )
    if source is None:
        ensure_source_definitions(session)
        source = session.scalar(
            select(SourceDefinition).where(SourceDefinition.source_key == source_key)
        )
    assert source is not None
    run = session.get(IngestionRun, ingestion_run_id) if ingestion_run_id else None
    if run is None:
        run = IngestionRun(source_id=source.id, cursor_started=cursor)
        session.add(run)
    run.status = "running"
    run.started_at = datetime.utcnow()
    session.commit()

    current_cursor = cursor
    for _ in range(max_pages):
        try:
            page = adapter.fetch_page(current_cursor, page_size)
        except Exception as exc:
            run.status = "failed"
            run.errors = [*run.errors, {"cursor": current_cursor, "error": str(exc)[:500]}]
            run.failed_count += 1
            break
        for raw in page.records:
            run.fetched_count += 1
            try:
                record = adapter.normalize(raw)
                digest = _record_hash(record)
                existing = session.scalar(
                    select(Trademark).where(
                        Trademark.source_id == source.id,
                        Trademark.source_record_id == record.source_record_id,
                    )
                )
                values = {
                    "raw_record_hash": digest,
                    "name": record.name,
                    "normalized_name": normalize_text(record.name),
                    "application_number": record.application_number,
                    "applicant": record.applicant,
                    "nice_classes": record.nice_classes,
                    "goods_services": record.goods_services,
                    "status": record.status,
                    "status_date": record.status_date,
                    "application_date": record.application_date,
                    "source_url": record.source_url,
                    "is_demo": record.is_demo,
                    "raw_record": record.raw or raw,
                }
                if existing and existing.raw_record_hash == digest:
                    run.skipped_count += 1
                elif existing:
                    for key, value in values.items():
                        setattr(existing, key, value)
                    run.updated_count += 1
                else:
                    session.add(
                        Trademark(
                            source_id=source.id,
                            source_record_id=record.source_record_id,
                            **values,
                        )
                    )
                    run.created_count += 1
            except Exception as exc:
                run.failed_count += 1
                run.errors = [
                    *run.errors,
                    {
                        "record": str(raw.get("source_record_id", "unknown"))[:160],
                        "error": str(exc)[:500],
                    },
                ][-100:]
        session.commit()
        current_cursor = page.next_cursor
        run.cursor_finished = current_cursor
        session.commit()
        if page.done:
            run.status = "completed" if run.failed_count == 0 else "completed_with_errors"
            break
    else:
        run.status = "partial"
    run.finished_at = datetime.utcnow()
    source.last_synced_at = run.finished_at
    session.commit()
    session.refresh(run)
    return run
