"""Make InfringingHash per-service

A hash flagged infringing by one debrid service (e.g. a Real-Debrid 451) may
still be served by another service. The blacklist must therefore be keyed on
(infohash, service) rather than infohash alone, so the downloader only skips a
hash on the service that actually rejected it.

Revision ID: e8d4c2b6f1a3
Revises: c7f3a9b1e2d4
Create Date: 2026-05-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e8d4c2b6f1a3"
down_revision: Union[str, None] = "c7f3a9b1e2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Existing rows were all recorded from Real-Debrid; attribute any
    # unlabelled row to it before `service` becomes part of the primary key.
    bind.execute(
        sa.text(
            "UPDATE \"InfringingHash\" SET service = 'realdebrid' "
            "WHERE service IS NULL OR service = ''"
        )
    )

    with op.batch_alter_table("InfringingHash", schema=None) as batch_op:
        batch_op.drop_constraint("InfringingHash_pkey", type_="primary")
        batch_op.create_primary_key(
            "InfringingHash_pkey", ["infohash", "service"]
        )


def downgrade() -> None:
    bind = op.get_bind()

    # The composite PK permits multiple rows per infohash; collapse to one
    # (keep the alphabetically-lowest service) before restoring the single PK.
    bind.execute(
        sa.text(
            'DELETE FROM "InfringingHash" a USING "InfringingHash" b '
            "WHERE a.infohash = b.infohash AND a.service > b.service"
        )
    )

    with op.batch_alter_table("InfringingHash", schema=None) as batch_op:
        batch_op.drop_constraint("InfringingHash_pkey", type_="primary")
        batch_op.create_primary_key("InfringingHash_pkey", ["infohash"])
