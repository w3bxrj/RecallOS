import os
import tempfile
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.autogenerate import compare_metadata

from app.models import Base


def get_alembic_config(db_url: str) -> Config:
    """Creates an Alembic Config instance pointing to the given database URL."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(backend_dir, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migrations_on_empty_sqlite_database() -> None:
    """Runs all Alembic migrations on a brand new empty database and proves schema matches models."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "fresh_empty_test.db").replace("\\", "/")
        db_url = f"sqlite:///{db_path}"

        cfg = get_alembic_config(db_url)

        # 1. Run alembic upgrade head on brand new empty database
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        try:
            with engine.connect() as conn:
                # Check alembic current revision is 7a8b9c0d1e2f (head)
                result = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                assert result == "7a8b9c0d1e2f"

                # Verify jobs table columns
                inspector = inspect(conn)
                columns = {col["name"]: col for col in inspector.get_columns("jobs")}

                assert "is_vision" in columns, "Column 'is_vision' missing from migrated jobs table"
                assert "notice" in columns, "Column 'notice' missing from migrated jobs table"

                # Check nullability
                assert columns["is_vision"]["nullable"] is False
                assert columns["notice"]["nullable"] is True

                # Direct metadata comparison (fails if models and migrated schema differ)
                ctx = MigrationContext.configure(conn)
                diffs = compare_metadata(ctx, Base.metadata)

                significant_diffs = [
                    d for d in diffs
                    if not (d[0] == "remove_index" and "sqlite" in db_url)
                ]
                assert significant_diffs == [], f"Schema mismatch detected: {significant_diffs}"

            # 2. Run alembic check to verify models and migrated schema match
            command.check(cfg)
        finally:
            engine.dispose()


def test_migration_safety_on_existing_rows() -> None:
    """Proves that upgrading to 7a8b9c0d1e2f is safe for existing rows in the jobs table."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "existing_rows_test.db").replace("\\", "/")
        db_url = f"sqlite:///{db_path}"

        cfg = get_alembic_config(db_url)

        # 1. Upgrade up to previous revision 513a4776015a
        command.upgrade(cfg, "513a4776015a")

        engine = create_engine(db_url)
        try:
            with engine.begin() as conn:
                # Create a user first (due to foreign key)
                conn.execute(
                    text(
                        "INSERT INTO users (id, email, password_hash, display_name, created_at) "
                        "VALUES (1, 'olduser@example.com', 'hash', 'Old User', '2026-10-25 10:00:00')"
                    )
                )
                # Insert existing job row without is_vision and notice
                conn.execute(
                    text(
                        "INSERT INTO jobs (id, user_id, status, total_chunks, done_chunks, cards_created, created_at) "
                        "VALUES (1, 1, 'ready', 4, 4, 12, '2026-10-25 10:05:00')"
                    )
                )
        finally:
            engine.dispose()

        # 2. Upgrade to head (applies 7a8b9c0d1e2f)
        command.upgrade(cfg, "head")

        # 3. Verify existing row preserved and has server defaults
        engine2 = create_engine(db_url)
        try:
            with engine2.connect() as conn:
                row = conn.execute(
                    text("SELECT id, status, is_vision, notice FROM jobs WHERE id = 1")
                ).fetchone()
                assert row is not None
                assert row[0] == 1
                assert row[1] == "ready"
                assert bool(row[2]) is False, "Existing row should default is_vision to False"
                assert row[3] is None, "Existing row should default notice to None"
        finally:
            engine2.dispose()


def test_migration_downgrade_and_reupgrade() -> None:
    """Proves that downgrade cleanly removes is_vision and notice, and re-upgrade restores them."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "downgrade_test.db").replace("\\", "/")
        db_url = f"sqlite:///{db_path}"

        cfg = get_alembic_config(db_url)

        # Upgrade to head
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                cols = [c["name"] for c in inspector.get_columns("jobs")]
                assert "is_vision" in cols
                assert "notice" in cols
        finally:
            engine.dispose()

        # Downgrade to 513a4776015a
        command.downgrade(cfg, "513a4776015a")

        engine2 = create_engine(db_url)
        try:
            with engine2.connect() as conn:
                inspector = inspect(conn)
                cols = [c["name"] for c in inspector.get_columns("jobs")]
                assert "is_vision" not in cols
                assert "notice" not in cols
        finally:
            engine2.dispose()

        # Re-upgrade to head
        command.upgrade(cfg, "head")

        engine3 = create_engine(db_url)
        try:
            with engine3.connect() as conn:
                inspector = inspect(conn)
                cols = [c["name"] for c in inspector.get_columns("jobs")]
                assert "is_vision" in cols
                assert "notice" in cols
        finally:
            engine3.dispose()


@pytest.mark.skipif(
    not os.environ.get("POSTGRES_TEST_URL"),
    reason="PostgreSQL not running locally or POSTGRES_TEST_URL not set in environment",
)
def test_migrations_on_postgres_if_available() -> None:
    """Runs all Alembic migrations and check on a live PostgreSQL database if configured."""
    pg_url = os.environ["POSTGRES_TEST_URL"]
    cfg = get_alembic_config(pg_url)

    # Upgrade to head
    command.upgrade(cfg, "head")

    # Check matching schema
    command.check(cfg)
