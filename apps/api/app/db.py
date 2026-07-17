"""MySQL-only SQLAlchemy session management."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _validate_mysql_url(url: str) -> None:
    if not url.startswith("mysql+"):
        raise RuntimeError("MarkLens 业务数据库仅支持 MySQL SQLAlchemy URL。")


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    _validate_mysql_url(url)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        future=True,
        connect_args={"charset": "utf8mb4"},
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        yield session


def database_health() -> tuple[bool, str]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:  # health endpoint must report rather than crash
        return False, f"{type(exc).__name__}: {str(exc)[:160]}"
