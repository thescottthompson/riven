"""Add InfringingHash table

Revision ID: a1f2c3d4e5b6
Revises: b1345f835923
Create Date: 2026-05-13 22:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1f2c3d4e5b6"
down_revision: Union[str, None] = "b1345f835923"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "InfringingHash",
        sa.Column("infohash", sa.String(), nullable=False),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("infohash"),
    )
    op.create_index(
        "ix_infringinghash_service", "InfringingHash", ["service"], unique=False
    )
    op.create_index(
        "ix_infringinghash_recorded_at",
        "InfringingHash",
        ["recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_infringinghash_recorded_at", table_name="InfringingHash")
    op.drop_index("ix_infringinghash_service", table_name="InfringingHash")
    op.drop_table("InfringingHash")
