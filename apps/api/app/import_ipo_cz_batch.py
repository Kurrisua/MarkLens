"""Import the downloaded official IPO CZ daily trademark batch into MarkLens."""

from __future__ import annotations

from .db import get_session_factory
from .sources import (
    REGISTRY,
    IpoCzSt96BatchAdapter,
    ensure_source_definitions,
    sync_source,
)


def main() -> None:
    adapter = REGISTRY.get("ipo-cz-st96-daily-batch")
    if not isinstance(adapter, IpoCzSt96BatchAdapter):
        raise RuntimeError("IPO CZ 日增量适配器未正确注册")
    ready, detail = adapter.health_check()
    if not ready:
        raise FileNotFoundError(f"真实数据批次不可用：{detail}；请先执行下载命令")

    with get_session_factory()() as session:
        ensure_source_definitions(session)
        run = sync_source(session, adapter.source_key, page_size=250, max_pages=200)

    print(
        "IPO CZ daily-batch import completed: "
        f"fetched={run.fetched_count}, created={run.created_count}, "
        f"updated={run.updated_count}, skipped={run.skipped_count}, failed={run.failed_count}"
    )


if __name__ == "__main__":
    main()
