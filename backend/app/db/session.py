"""Database engine, session factory and health probe.

The engine is created lazily so tests can override ``DATABASE_URL`` before the
first connection.  Production uses MySQL; SQLite is supported for tests.
"""

import logging
import sqlite3
from functools import lru_cache
from typing import Generator, Optional, Tuple

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """SQLite does not enforce foreign keys unless explicitly enabled."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create (and cache) the SQLAlchemy engine for the configured URL."""
    settings = get_settings()
    url = settings.database_url_value
    kwargs = {
        "pool_pre_ping": True,
        "echo": settings.db_echo,
        "future": True,
    }
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a session and always close it."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database() -> Tuple[str, Optional[str], Optional[str]]:
    """Return ``(status, dialect, detail)`` without raising.

    A failed probe must not crash ``/health``; it is reported as ``error`` and
    the overall service status becomes ``degraded``.
    """
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok", engine.dialect.name, None
    except Exception as exc:  # pragma: no cover - exercised by integration tests
        logger.warning("Database health check failed: %s", exc)
        return "error", None, str(exc)[:300]


def reset_engine_cache() -> None:
    """Clear cached engine/session factory (used by tests)."""
    get_session_factory.cache_clear()
    get_engine.cache_clear()
