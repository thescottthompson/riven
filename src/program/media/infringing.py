"""Global blacklist of infohashes that the upstream debrid service has flagged as
infringing (DMCA-takedown'd). Items currently using one of these hashes can no
longer have their files unrestricted, so we record the hash once and skip it
across every item going forward instead of re-discovering the same dead torrents
on each scrape cycle."""

from datetime import datetime

import sqlalchemy
from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column

from program.db.base_model import Base


class InfringingHash(Base):
    __tablename__ = "InfringingHash"

    infohash: Mapped[str] = mapped_column(sqlalchemy.String, primary_key=True)
    service: Mapped[str] = mapped_column(sqlalchemy.String)
    error: Mapped[str | None] = mapped_column(sqlalchemy.String, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        sqlalchemy.DateTime, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_infringinghash_service", "service"),
        Index("ix_infringinghash_recorded_at", "recorded_at"),
    )
