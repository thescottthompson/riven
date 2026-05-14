"""Helpers for tracking and reacting to infohashes that the upstream debrid
service has flagged as infringing (DMCA-takedown'd).

Two responsibilities:
- Persist a global blacklist of bad infohashes in the InfringingHash table so
  every code path (scrape parse, downloader validate, etc.) can skip them.
- When a fresh infringing hash is recorded, cascade a reset() onto every
  MediaItem whose active_stream still points at it so those items rescrape
  and pick up a working torrent without manual intervention.
"""

from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from program.db.db import db_session
from program.media import InfringingHash, MediaItem


def is_infringing(infohash: str) -> bool:
    """Return True if the infohash is on the global infringing list."""

    if not infohash:
        return False

    try:
        with db_session() as session:
            return (
                session.execute(
                    select(InfringingHash.infohash).where(
                        InfringingHash.infohash == infohash.lower()
                    )
                ).first()
                is not None
            )
    except Exception as e:
        logger.debug(f"infringing.is_infringing lookup failed for {infohash}: {e}")
        return False


def get_infringing_set(infohashes: list[str]) -> set[str]:
    """Return the subset of provided infohashes that are on the infringing list."""

    if not infohashes:
        return set()

    normalized = [h.lower() for h in infohashes if h]

    try:
        with db_session() as session:
            rows = session.execute(
                select(InfringingHash.infohash).where(
                    InfringingHash.infohash.in_(normalized)
                )
            ).all()

            return {row[0] for row in rows}
    except Exception as e:
        logger.debug(f"infringing.get_infringing_set lookup failed: {e}")
        return set()


def record_infringing_hash(
    infohash: str,
    service: str,
    error: str | None = None,
) -> bool:
    """Record an infohash as infringing and cascade reset onto affected items.

    Returns True if the hash was newly recorded (so callers can decide whether
    to log loudly), False if it was already known or the write failed.
    """

    if not infohash:
        return False

    normalized = infohash.lower()
    newly_recorded = False

    try:
        with db_session() as session:
            stmt = (
                pg_insert(InfringingHash)
                .values(
                    infohash=normalized,
                    service=service,
                    error=error,
                    recorded_at=datetime.utcnow(),
                )
                .on_conflict_do_nothing(index_elements=["infohash"])
                .returning(InfringingHash.infohash)
            )
            result = session.execute(stmt).first()
            session.commit()
            newly_recorded = result is not None
    except Exception as e:
        logger.warning(
            f"infringing.record_infringing_hash failed for {infohash}: {e}"
        )
        return False

    if newly_recorded:
        logger.warning(
            f"Recorded infringing infohash {normalized} ({service}: {error})"
        )

        try:
            reset_items_using_hash(normalized)
        except Exception as e:
            logger.warning(
                f"infringing.reset_items_using_hash failed for {infohash}: {e}"
            )

    return newly_recorded


def _matches_active(item: MediaItem, hashes: set[str]) -> bool:
    """True if the item's current active_stream uses one of the provided hashes."""

    active = item.active_stream

    if active is None or not active.infohash:
        return False

    return active.infohash.lower() in hashes


def reset_items_using_hash(infohash: str) -> int:
    """Reset every MediaItem whose active_stream points at the given infohash.

    Returns the count of items reset. Best-effort: individual failures are
    logged and skipped so one bad item never blocks the rest.
    """

    normalized = infohash.lower()
    reset_count = 0

    with db_session() as session:
        # Active_stream is stored via a JSON TypeDecorator; rather than rely on
        # provider-specific JSON path operators, we narrow by `active_stream is
        # not null` and match the infohash in Python. The set of items with an
        # active stream is bounded and this path runs rarely (once per fresh
        # infringing hash recorded).
        candidates = (
            session.execute(
                select(MediaItem).where(MediaItem.active_stream.is_not(None))
            )
            .scalars()
            .all()
        )

        targets = [item for item in candidates if _matches_active(item, {normalized})]

        for item in targets:
            try:
                item.reset()
                reset_count += 1
                logger.log(
                    "PROGRAM",
                    f"Reset {item.log_string} ({item.id}) because its active stream {normalized} was flagged infringing",
                )
            except Exception as e:
                logger.warning(
                    f"infringing.reset_items_using_hash: failed to reset {getattr(item, 'log_string', '?')} ({getattr(item, 'id', '?')}): {e}"
                )

        if reset_count:
            session.commit()

    return reset_count


def scan_active_streams_for_infringing() -> int:
    """One-shot maintenance scan: find every item whose active_stream is on the
    infringing list and reset it.

    Useful after the infringing list grows from another source (manual import,
    historical log parsing, etc.).
    """

    reset_count = 0

    with db_session() as session:
        infringing_rows = session.execute(select(InfringingHash.infohash)).all()
        infringing_hashes = {row[0] for row in infringing_rows}

        if not infringing_hashes:
            return 0

        candidates = (
            session.execute(
                select(MediaItem).where(MediaItem.active_stream.is_not(None))
            )
            .scalars()
            .all()
        )

        targets = [
            item for item in candidates if _matches_active(item, infringing_hashes)
        ]

        for item in targets:
            try:
                item.reset()
                reset_count += 1
            except Exception as e:
                logger.warning(
                    f"infringing.scan: failed to reset {getattr(item, 'log_string', '?')} ({getattr(item, 'id', '?')}): {e}"
                )

        if reset_count:
            session.commit()

    if reset_count:
        logger.log(
            "PROGRAM",
            f"Infringing-scan reset {reset_count} items currently using takedown'd hashes",
        )

    return reset_count
