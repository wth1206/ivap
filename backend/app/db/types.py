"""Portable column types."""

from sqlalchemy import BigInteger, Integer


def bigint_pk():
    """BIGINT on MySQL, INTEGER on SQLite (SQLite only autoincrements INTEGER PKs)."""
    return BigInteger().with_variant(Integer, "sqlite")
