"""Download a bounded, auditable batch of official IPO CZ daily trademark increments."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .config import get_settings

DOWNLOAD_BASE = "https://isdv.upv.gov.cz/doc/opendatast96/tm"


def _filename(release: date) -> str:
    return f"OPENDATAST96_TM_CZ_DIFF_{release:%d-%m-%Y}_0001.zip"


def _download(url: str, destination: Path) -> bool:
    with urlopen(url, timeout=60) as response:  # noqa: S310 - fixed official URL only
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
            shutil.copyfileobj(response, temporary)
            temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path) as archive:
            if not any(name.lower().endswith(".xml") for name in archive.namelist()):
                raise ValueError("官方包中没有 ST.96 XML 记录")
        temporary_path.replace(destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=45, help="回溯的日增量包数量（默认 45）")
    parser.add_argument(
        "--end-date", type=date.fromisoformat, default=date.today(), help="结束日期，格式 YYYY-MM-DD"
    )
    arguments = parser.parse_args()
    if arguments.days < 1 or arguments.days > 180:
        raise SystemExit("--days 必须在 1 到 180 之间")

    destination_dir = get_settings().source_data_dir.parent / "raw" / "ipo-cz-daily"
    destination_dir.mkdir(parents=True, exist_ok=True)
    downloaded = existing = unavailable = 0
    for offset in range(arguments.days):
        release = arguments.end_date - timedelta(days=offset)
        filename = _filename(release)
        destination = destination_dir / filename
        if destination.exists():
            existing += 1
            continue
        try:
            _download(f"{DOWNLOAD_BASE}/{filename}", destination)
            downloaded += 1
        except HTTPError as exc:
            if exc.code == 404:
                unavailable += 1
                continue
            raise
        except URLError as exc:
            raise SystemExit(f"无法连接 IPO CZ 官方数据站：{exc.reason}") from exc
    print(
        "IPO CZ daily packages ready: "
        f"downloaded={downloaded}, existing={existing}, unavailable={unavailable}, "
        f"directory={destination_dir}"
    )


if __name__ == "__main__":
    main()
