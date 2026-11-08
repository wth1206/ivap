"""add knowledge chunk embedding

Revision ID: b0ab7762879b
Revises: 715d6a5194fc
Create Date: 2026-11-06 23:48:22.032652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0ab7762879b'
down_revision: Union[str, None] = '715d6a5194fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_chunks",
        sa.Column("embedding", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "embedding")
