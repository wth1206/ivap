"""Logging configuration.

Console + rotating file handler, with a ``request_id`` field injected by a
context variable so every log line can be correlated with an HTTP request.
"""

import logging
import logging.config
from contextvars import ContextVar, Token
from typing import Optional

from app.core.config import Settings

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(value: str) -> Token:
    """Bind a request id to the current execution context."""
    return _REQUEST_ID.set(value)


def reset_request_id(token: Token) -> None:
    """Restore the previous request id."""
    _REQUEST_ID.reset(token)


def get_request_id() -> str:
    """Return the current request id, or ``-`` outside a request."""
    return _REQUEST_ID.get()


class RequestIdFilter(logging.Filter):
    """Inject the current request id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.request_id = get_request_id()
        return True


def setup_logging(settings: Settings) -> None:
    """Configure application logging.  Safe to call more than once."""
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log_file = settings.log_dir / "app.log"

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": settings.log_level,
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "default",
                "level": settings.log_level,
                "filename": str(log_file),
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 5,
                "encoding": "utf-8",
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": settings.log_level,
        },
        "loggers": {
            # Let uvicorn logs go through the root handler so they share the format.
            "uvicorn": {"handlers": [], "level": settings.log_level, "propagate": True},
            "uvicorn.error": {"handlers": [], "level": settings.log_level, "propagate": True},
            # We log access ourselves in RequestContextMiddleware; avoid duplicates.
            "uvicorn.access": {"handlers": [], "level": "WARNING", "propagate": False},
        },
    }

    logging.config.dictConfig(config)

    request_id_filter = RequestIdFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(request_id_filter)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Small helper used across modules."""
    return logging.getLogger(name)
