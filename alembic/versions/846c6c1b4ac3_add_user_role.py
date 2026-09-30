"""add user role

Revision ID: 846c6c1b4ac3
Revises: a04448e32f74
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "846c6c1b4ac3"
down_revision: Union[str, Sequence[str], None] = "a04448e32f74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="USER",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "role")