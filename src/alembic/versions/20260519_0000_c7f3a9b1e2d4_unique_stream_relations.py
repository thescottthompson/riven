"""Deduplicate and enforce unique stream association rows

Duplicate rows in the StreamRelation / StreamBlacklistRelation association
tables make the ORM issue more secondary-table DELETEs than there are rows:
the first per-pair ``DELETE ... WHERE parent_id=? AND child_id=?`` removes
every duplicate, so the paired delete matches 0 rows and raises
``sqlalchemy.orm.exc.StaleDataError``. Removing existing duplicates and adding
a unique constraint keeps the relationship collections consistent.

Revision ID: c7f3a9b1e2d4
Revises: a1f2c3d4e5b6
Create Date: 2026-05-19 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c7f3a9b1e2d4"
down_revision: Union[str, None] = "a1f2c3d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Drop pre-existing duplicate association rows, keeping the lowest id per pair.
    bind.execute(
        sa.text(
            """
            DELETE FROM "StreamRelation"
            WHERE id NOT IN (
                SELECT MIN(id) FROM "StreamRelation"
                GROUP BY parent_id, child_id
            )
            """
        )
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM "StreamBlacklistRelation"
            WHERE id NOT IN (
                SELECT MIN(id) FROM "StreamBlacklistRelation"
                GROUP BY media_item_id, stream_id
            )
            """
        )
    )

    with op.batch_alter_table("StreamRelation", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_streamrelation_parent_child", ["parent_id", "child_id"]
        )

    with op.batch_alter_table("StreamBlacklistRelation", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_streamblacklistrelation_item_stream",
            ["media_item_id", "stream_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("StreamBlacklistRelation", schema=None) as batch_op:
        batch_op.drop_constraint(
            "uq_streamblacklistrelation_item_stream", type_="unique"
        )

    with op.batch_alter_table("StreamRelation", schema=None) as batch_op:
        batch_op.drop_constraint("uq_streamrelation_parent_child", type_="unique")
