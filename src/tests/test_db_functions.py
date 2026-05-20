# tests/test_db_functions.py
from __future__ import annotations

import os

import pytest
from RTN import ParsedData, Torrent
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

from sqlalchemy.exc import IntegrityError

from program.db.db import db, run_migrations
from program.db.db_functions import (
    MAX_PROCESSING_FAILURES,
    get_item_by_external_id,
    item_exists_by_any_id,
    record_processing_failure,
)
from program.media.item import Episode, MediaItem, Movie, Season, Show
from program.media.state import States
from program.media.stream import Stream, StreamBlacklistRelation, StreamRelation


@pytest.fixture(scope="session")
def test_container():
    # One container for the whole test session
    with PostgresContainer(
        "postgres:16.4-alpine3.20",
        username="postgres",
        password="postgres",
        dbname="riven",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def db_engine(test_container):
    """
    One engine + one migrated schema for the whole test session.
    We also relax durability for speed (safe in tests).
    """
    url = test_container.get_connection_url()
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    # Make Alembic target this DB
    os.environ["DATABASE_URL"] = url

    # Run migrations ONCE (big win)
    run_migrations(database_url=url)

    # Build an engine for tests
    engine = create_engine(url, future=True, pool_pre_ping=True)

    # Speed knobs (commit is much cheaper now)
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(text("SET synchronous_commit = OFF"))
        # Optional extras:
        # conn.execute(text("SET client_min_messages = WARNING"))
        # conn.execute(text("SET log_statement = 'none'"))

    # Rebind global db.* so app code uses this engine
    db.engine = engine
    db.Session.configure(bind=engine)

    yield engine

    engine.dispose()


@pytest.fixture(scope="function")
def test_scoped_db_session(db_engine):
    """
    Hand out a Session for each test. After each test, TRUNCATE all tables
    instead of dropping the schema / rerunning migrations. Very fast.
    """
    session = db.Session()
    try:
        yield session
    finally:
        session.close()
        # Fast cleanup: TRUNCATE everything, reset sequences
        with db_engine.connect() as conn:
            tables = (
                conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                )
                .scalars()
                .all()
            )
            if tables:
                quoted = ", ".join(f'"public"."{t}"' for t in tables)
                conn.execute(text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))
                conn.commit()


def _torrent(rt: str, ih: str, pt: str, rank=100, lev=0.9) -> Torrent:
    pd = ParsedData(parsed_title=pt, raw_title=rt)
    return Torrent(
        raw_title=rt, infohash=ih, data=pd, fetch=True, rank=rank, lev_ratio=lev
    )


def _movie(tmdb_id: str, imdb_id: str | None = None, title="Movie") -> Movie:
    return Movie(
        {"title": title, "tmdb_id": tmdb_id, "imdb_id": imdb_id, "type": "movie"}
    )


def _show_tree(
    tvdb: str, seasons: list[int], eps: int
) -> tuple[Show, list[Season], list[Episode]]:
    show = Show({"title": "Show", "tvdb_id": tvdb, "type": "show"})
    all_s, all_e = [], []
    for s in seasons:
        season = Season({"number": s, "tvdb_id": f"{tvdb}-{s}", "type": "season"})
        season.parent = show
        season.parent_id = show.id
        all_s.append(season)
        for e in range(1, eps + 1):
            ep = Episode({"number": e, "tvdb_id": f"{tvdb}-{s}-{e}", "type": "episode"})
            ep.parent = season
            ep.parent_id = season.id
            all_e.append(ep)
    show.seasons = all_s
    for s in all_s:
        s.episodes = [e for e in all_e if e.parent_id == s.id]
    return show, all_s, all_e


# ------------------------------ Tests -------------------------------------- #


def test_item_exists_by_any_id_paths(test_scoped_db_session):
    mov = _movie("30002", "tt30002", title="Exists Check")
    test_scoped_db_session.add(mov)
    test_scoped_db_session.commit()

    assert item_exists_by_any_id(
        item_id=mov.id,
        tvdb_id=None,
        tmdb_id=None,
        imdb_id=None,
        session=test_scoped_db_session,
    )
    assert item_exists_by_any_id(
        item_id=None,
        tvdb_id=None,
        tmdb_id=30002,
        imdb_id=None,
        session=test_scoped_db_session,
    )
    assert item_exists_by_any_id(
        item_id=None,
        tvdb_id=None,
        tmdb_id=None,
        imdb_id="tt30002",
        session=test_scoped_db_session,
    )


def test_item_exists_by_any_id_negative(test_scoped_db_session):
    assert not item_exists_by_any_id(
        item_id="non_existent",
        tvdb_id=None,
        tmdb_id=None,
        imdb_id=None,
        session=test_scoped_db_session,
    )


def test_stream_relation_rejects_duplicate(test_scoped_db_session):
    """A duplicate (parent_id, child_id) StreamRelation row is rejected.

    Duplicate association rows are what caused the StaleDataError on delete:
    the unique constraint keeps the relationship collection consistent.
    """
    s = test_scoped_db_session

    movie = _movie("40001", "tt40001", title="Dup Stream")
    stream = Stream(_torrent("Dup.Stream.2020", "a" * 40, "Dup Stream"))
    movie.streams.append(stream)
    s.add(movie)
    s.commit()

    s.add(StreamRelation(parent_id=movie.id, child_id=stream.id))

    with pytest.raises(IntegrityError):
        s.commit()

    s.rollback()


def test_stream_blacklist_relation_rejects_duplicate(test_scoped_db_session):
    s = test_scoped_db_session

    movie = _movie("40002", "tt40002", title="Dup Blacklist")
    stream = Stream(_torrent("Dup.Blacklist.2020", "b" * 40, "Dup Blacklist"))
    movie.blacklisted_streams.append(stream)
    s.add(movie)
    s.commit()

    s.add(
        StreamBlacklistRelation(media_item_id=movie.id, stream_id=stream.id)
    )

    with pytest.raises(IntegrityError):
        s.commit()

    s.rollback()


def test_stream_removal_commits_cleanly(test_scoped_db_session):
    """Removing an associated stream deletes exactly one row, no StaleDataError."""
    s = test_scoped_db_session

    movie = _movie("40003", "tt40003", title="Reset Stream")
    stream = Stream(_torrent("Reset.Stream.2020", "c" * 40, "Reset Stream"))
    movie.streams.append(stream)
    s.add(movie)
    s.commit()

    assert (
        s.query(StreamRelation).filter_by(parent_id=movie.id).count() == 1
    )

    movie.streams.clear()
    s.commit()

    assert (
        s.query(StreamRelation).filter_by(parent_id=movie.id).count() == 0
    )


def test_record_processing_failure_marks_failed(test_scoped_db_session):
    """Repeated commit failures eventually move an item to the Failed state."""
    s = test_scoped_db_session

    movie = _movie("40004", "tt40004", title="Failing Item")
    s.add(movie)
    s.commit()
    item_id = movie.id

    for _ in range(MAX_PROCESSING_FAILURES - 1):
        record_processing_failure(item_id, "Updater")

    s.expire_all()
    item = s.query(MediaItem).filter_by(id=item_id).one()
    assert item.failed_attempts == MAX_PROCESSING_FAILURES - 1
    assert item.last_state != States.Failed

    record_processing_failure(item_id, "Updater")

    s.expire_all()
    item = s.query(MediaItem).filter_by(id=item_id).one()
    assert item.failed_attempts == MAX_PROCESSING_FAILURES
    assert item.last_state == States.Failed
