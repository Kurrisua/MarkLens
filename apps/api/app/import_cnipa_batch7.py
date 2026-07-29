"""Prepare and import a bounded, auditable CNIPA batch-7 trademark snapshot.

The official batch supplied with this project contains structured registration,
registrant and goods/service fields plus separate trademark image files.  It
does *not* contain trademark-name text.  The importer deliberately records
that limitation and prevents the generated registration-number display label
from being used as text, phonetic, or semantic search evidence.

No third-party package is required.  Typical usage::

    python -m app.import_cnipa_batch7 prepare \
      --data-dir /path/to/tmInfo --image-dir /path/to/image_26 \
      --bundle-dir /path/to/cnipa-batch7-20k --limit 20000
    python -m app.import_cnipa_batch7 ingest --bundle-dir /path/to/cnipa-batch7-20k
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from .config import get_settings
from .db import get_session_factory
from .models import ImageAsset, IngestionRun, SourceDefinition, Trademark
from .retrieval import AppError, process_image

SOURCE_KEY = "cnipa-trademark-open-data-2026-batch-7"
SOURCE_NAME = "国内真实数据集 · 国家知识产权局商标数据开放（2026年第7次增量）"
SOURCE_URL = "https://sbj.cnipa.gov.cn/sbj/sjfw/sjsj/"
DATA_LABEL = "国内真实数据集"
DATA_NOTICE = (
    "来源为国家知识产权局商标数据开放第 7 次增量。原始开放字段未提供商标名称；"
    "本条以注册号展示，已禁用文字、读音、语义评分，仅用于图样、类别和商品服务辅助筛查。"
)
BASIC_FILE = "注册商标基本信息.csv"
REGISTRANT_FILE = "商标注册人信息.csv"
GOODS_FILE = "注册商标商品服务信息.csv"


def _csv_rows(path: Path):
    csv.field_size_limit(sys.maxsize)
    # The official goods/services export has a small number of malformed UTF-8
    # byte sequences.  Keeping the row and replacing only undecodable bytes is
    # preferable to silently dropping an otherwise genuine registration record.
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        yield from csv.DictReader(handle)


def _nice_class(value: str | None) -> int | None:
    try:
        result = int(str(value or "").strip())
    except ValueError:
        return None
    return result if 1 <= result <= 45 else None


def _date(value: str | None) -> str | None:
    candidate = str(value or "").strip()
    try:
        return date.fromisoformat(candidate).isoformat() if candidate else None
    except ValueError:
        return None


def _image_number(path: Path) -> str:
    """Map `87988341A.jpg` to the official application/registration number."""
    stem = path.stem.strip()
    return stem[:-1] if stem.endswith("A") and stem[:-1].isdigit() else stem


def _record_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def prepare_bundle(data_dir: Path, image_dir: Path, bundle_dir: Path, limit: int) -> dict[str, int]:
    """Create a portable subset manifest with only real matched image records."""
    if limit < 1:
        raise ValueError("limit 必须大于 0")
    basic_path, registrant_path, goods_path = (
        data_dir / BASIC_FILE,
        data_dir / REGISTRANT_FILE,
        data_dir / GOODS_FILE,
    )
    missing = [str(path) for path in (basic_path, registrant_path, goods_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少官方数据文件：" + "、".join(missing))

    images = {
        _image_number(path): path
        for path in sorted(image_dir.glob("*.jpg"))
        if _image_number(path)
    }
    if not images:
        raise FileNotFoundError(f"未在 {image_dir} 找到 JPG 商标图样")

    basic: dict[str, dict[str, object]] = {}
    for row in _csv_rows(basic_path):
        number = str(row.get("注册号/申请号") or "").strip()
        if number not in images:
            continue
        item = basic.setdefault(number, {"classes": set(), "rows": []})
        nice = _nice_class(row.get("国际分类"))
        if nice is not None:
            item["classes"].add(nice)  # type: ignore[index]
        item["rows"].append(row)  # type: ignore[index]

    selected_numbers = [number for number in sorted(images) if number in basic][:limit]
    if len(selected_numbers) < limit:
        raise RuntimeError(f"只有 {len(selected_numbers)} 条图片与基本信息能够匹配，未达到 {limit} 条")
    selected = set(selected_numbers)

    registrants: dict[str, str] = {}
    for row in _csv_rows(registrant_path):
        number = str(row.get("注册号/申请号") or "").strip()
        if number not in selected or number in registrants:
            continue
        registrants[number] = (
            str(row.get("注册人中文名称") or row.get("注册人外文名称") or "原始批次未提供").strip()
        )

    goods: dict[str, list[str]] = {number: [] for number in selected_numbers}
    for row in _csv_rows(goods_path):
        number = str(row.get("注册号/申请号") or "").strip()
        if number not in selected or len(goods[number]) >= 10:
            continue
        value = str(row.get("商品中文名称") or "").strip()
        if value and value not in goods[number]:
            goods[number].append(value)

    bundle_dir.mkdir(parents=True, exist_ok=True)
    image_destination = bundle_dir / "images"
    image_destination.mkdir(exist_ok=True)
    manifest_path = bundle_dir / "records.jsonl"
    copied = 0
    with manifest_path.open("w", encoding="utf-8") as handle:
        for number in selected_numbers:
            basic_item = basic[number]
            rows = list(basic_item["rows"])  # type: ignore[index]
            source_row = rows[0]
            image_path = images[number]
            destination = image_destination / image_path.name
            if not destination.exists():
                shutil.copy2(image_path, destination)
                copied += 1
            classes = sorted(basic_item["classes"])  # type: ignore[index]
            payload = {
                "source_record_id": number,
                "application_number": number,
                "display_name": f"注册号 {number}",
                "applicant": registrants.get(number, "原始批次未提供"),
                "nice_classes": classes,
                "goods_services": goods[number],
                "application_date": _date(source_row.get("申请日期")),
                "status_date": _date(source_row.get("注册公告日期"))
                or _date(source_row.get("专用期结束日期")),
                "image_file": f"images/{image_path.name}",
                "official_basic_records": rows,
                "data_label": DATA_LABEL,
                "data_notice": DATA_NOTICE,
            }
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    metadata = {
        "source_key": SOURCE_KEY,
        "source_name": SOURCE_NAME,
        "official_data_label": DATA_LABEL,
        "records": len(selected_numbers),
        "copied_images": copied,
        "prepared_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_files": [BASIC_FILE, REGISTRANT_FILE, GOODS_FILE],
        "name_field_available": False,
        "encoding_note": "官方 CSV 个别不可解码字节以 Unicode replacement character 保留。",
        "notice": DATA_NOTICE,
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"records": len(selected_numbers), "copied_images": copied}


def _ensure_source(session) -> SourceDefinition:
    source = session.scalar(select(SourceDefinition).where(SourceDefinition.source_key == SOURCE_KEY))
    if source is None:
        source = SourceDefinition(
            source_key=SOURCE_KEY,
            name=SOURCE_NAME,
            adapter_type="official_snapshot",
            license_name="国家知识产权局商标数据开放（注册用户下载）",
            license_url=SOURCE_URL,
            terms_summary=(
                "基于项目持有的国家知识产权局商标数据开放第 7 次增量文件导入。"
                "保留注册号、分类、登记字段、注册人、商品服务与图样；原始文件不含商标名称字段。"
            ),
            allowed_domains=["sbj.cnipa.gov.cn"],
            rate_limit_per_minute=None,
            config={"readonly_snapshot": True, "batch": "2026-07-increment-7"},
            enabled=True,
        )
        session.add(source)
        session.flush()
    return source


def _read_manifest(bundle_dir: Path) -> list[dict[str, object]]:
    path = bundle_dir / "records.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"未找到导入清单：{path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ingest_bundle(bundle_dir: Path, batch_size: int = 100) -> dict[str, int]:
    """Import a prepared bundle in restart-safe batches, without downloading anything."""
    records = _read_manifest(bundle_dir)
    session_factory = get_session_factory()
    created = updated = skipped = images = image_failures = 0
    with session_factory() as session:
        source = _ensure_source(session)
        run = IngestionRun(
            source_id=source.id,
            status="running",
            cursor_started="0",
            fetched_count=len(records),
            started_at=datetime.utcnow(),
        )
        session.add(run)
        session.commit()

        existing = {
            item.source_record_id: item
            for item in session.scalars(
                select(Trademark).where(Trademark.source_id == source.id)
            ).all()
        }
        for offset, record in enumerate(records, start=1):
            number = str(record["source_record_id"])
            image_file = bundle_dir / str(record["image_file"])
            asset_id: str | None = None
            if image_file.is_file():
                try:
                    processed = process_image(image_file.read_bytes(), image_file.name)
                    asset = session.scalar(select(ImageAsset).where(ImageAsset.sha256 == processed.sha256))
                    if asset is None:
                        storage_key = f"cnipa-b7-{uuid4().hex}{processed.extension}"
                        destination = get_settings().upload_dir / storage_key
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(processed.content)
                        asset = ImageAsset(
                            storage_key=storage_key,
                            original_filename=image_file.name[:255],
                            mime_type=processed.mime_type,
                            sha256=processed.sha256,
                            byte_size=len(processed.content),
                            width=processed.width,
                            height=processed.height,
                            ocr_text=None,
                            ocr_confidence=None,
                            ocr_model="batch-import-not-run",
                            phash=processed.phash,
                            is_demo=False,
                        )
                        session.add(asset)
                        session.flush()
                    asset_id = asset.id
                    images += 1
                except (AppError, OSError, ValueError):
                    image_failures += 1

            raw = {
                "jurisdiction": "CN",
                "data_label": record["data_label"],
                "data_notice": record["data_notice"],
                "mark_name_available": False,
                "cnipa_open_data_batch": "2026年第7次增量",
                "official_basic_records": record["official_basic_records"],
                "image_file": str(record["image_file"]),
            }
            values = {
                "raw_record_hash": _record_hash({"record": record, "raw": raw}),
                "name": str(record["display_name"]),
                "normalized_name": "",
                "application_number": str(record["application_number"]),
                "applicant": str(record["applicant"])[:255],
                "nice_classes": list(record["nice_classes"]),
                "goods_services": list(record["goods_services"]),
                "status": "官方开放数据记录（以有效期字段复核）",
                "status_date": _date(str(record.get("status_date") or "")),
                "application_date": _date(str(record.get("application_date") or "")),
                "source_url": SOURCE_URL,
                "image_asset_id": asset_id,
                "is_demo": False,
                "raw_record": raw,
            }
            item = existing.get(number)
            if item is not None and item.raw_record_hash == values["raw_record_hash"]:
                skipped += 1
            elif item is not None:
                for key, value in values.items():
                    setattr(item, key, value)
                updated += 1
            else:
                item = Trademark(source_id=source.id, source_record_id=number, **values)
                session.add(item)
                existing[number] = item
                created += 1
            if offset % batch_size == 0 or offset == len(records):
                run.created_count = created
                run.updated_count = updated
                run.skipped_count = skipped
                run.failed_count = image_failures
                run.cursor_finished = str(offset)
                session.commit()

        source.last_synced_at = datetime.utcnow()
        run.status = "completed"
        run.finished_at = datetime.utcnow()
        run.errors = ([{"warning": "图片处理失败", "count": image_failures}] if image_failures else [])
        session.commit()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "image_links": images,
        "image_failures": image_failures,
    }


def verify_source() -> dict[str, object]:
    """Return a minimal, read-only integrity summary for the imported source."""
    session_factory = get_session_factory()
    with session_factory() as session:
        source = session.scalar(select(SourceDefinition).where(SourceDefinition.source_key == SOURCE_KEY))
        if source is None:
            return {"source_found": False, "source_key": SOURCE_KEY}
        records = list(session.scalars(select(Trademark).where(Trademark.source_id == source.id)).all())
        with_images = sum(1 for item in records if item.image_asset_id)
        labelled = sum(1 for item in records if item.raw_record.get("data_label") == DATA_LABEL)
        no_name_scoring = sum(
            1 for item in records if item.raw_record.get("mark_name_available") is False
        )
        return {
            "source_found": True,
            "source_name": source.name,
            "records": len(records),
            "with_images": with_images,
            "domestic_real_data_labelled": labelled,
            "text_scoring_disabled": no_name_scoring,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="CNIPA 第 7 次增量数据的受限导入工具")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="从官方 CSV 与图样生成可迁移导入包")
    prepare.add_argument("--data-dir", type=Path, required=True)
    prepare.add_argument("--image-dir", type=Path, required=True)
    prepare.add_argument("--bundle-dir", type=Path, required=True)
    prepare.add_argument("--limit", type=int, default=20_000)
    ingest = commands.add_parser("ingest", help="将已准备导入包写入当前 MarkLens 数据库")
    ingest.add_argument("--bundle-dir", type=Path, required=True)
    ingest.add_argument("--batch-size", type=int, default=100)
    commands.add_parser("verify", help="只读核验当前数据库中的第 7 次增量来源")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_bundle(args.data_dir, args.image_dir, args.bundle_dir, args.limit)
    elif args.command == "ingest":
        result = ingest_bundle(args.bundle_dir, args.batch_size)
    else:
        result = verify_source()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
