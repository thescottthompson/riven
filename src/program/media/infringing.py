"""Per-service blacklist of infohashes that a debrid service has flagged as
infringing (DMCA-takedown'd). A hash is recorded against the specific service
that rejected it — a torrent Real-Debrid 451s may still be served by another
debrid service, so the blacklist is keyed on (infohash, service) rather than
infohash alone."""

from datetime import datetime

import sqlalchemy
from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column

from program.db.base_model import Base


class InfringingHash(Base):
    __tablename__ = "InfringingHash"

    infohash: Mapped[str] = mapped_column(sqlalchemy.String, primary_key=True)
    service: Mapped[str] = mapped_column(sqlalchemy.String, primary_key=True)
    error: Mapped[str | None] = mapped_column(sqlalchemy.String, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        sqlalchemy.DateTime, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_infringinghash_service", "service"),
        Index("ix_infringinghash_recorded_at", "recorded_at"),
    )
