"""Development helpers for creating tables and seeding data.

Production schema changes must go through Alembic; ``create_all`` is kept for
fast local bootstrap and tests.
"""

from app import models  # noqa: F401  (register all ORM models)
from app.db.base import Base
from app.db.session import get_engine


def create_all() -> None:
    Base.metadata.create_all(bind=get_engine())


def drop_all() -> None:
    Base.metadata.drop_all(bind=get_engine())
