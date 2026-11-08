"""Identifier helpers."""

from uuid import uuid4


def new_id() -> str:
    """Return a 32-character lowercase UUID hex string."""
    return uuid4().hex
