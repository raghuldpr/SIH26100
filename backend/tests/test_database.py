import pytest
from sqlalchemy.orm import Session
from app.config import Settings, settings
from app.db import Base, engine, get_db
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_database_base_metadata():
    """Verify Base declarative base and metadata are configured."""
    assert Base is not None
    assert hasattr(Base, "metadata")


def test_get_db_dependency():
    """Verify get_db dependency yields a valid SQLAlchemy session."""
    db_gen = get_db()
    db = next(db_gen)
    assert isinstance(db, Session)
    try:
        pass
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_database_url_normalization():
    """Verify legacy postgres:// URI scheme is normalized to postgresql://."""
    test_settings = Settings(
        DATABASE_URL="postgres://user:pass@localhost:5432/mydb"
    )
    assert test_settings.DATABASE_URL.startswith("postgresql://")


def test_alembic_config_structure():
    """Verify alembic configuration can load script directory without errors."""
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    assert script is not None


def test_core_and_dependencies_database_imports():
    """Verify get_db is accessible from core, dependencies, and db modules."""
    from app.core.database import get_db as core_get_db, check_database_connection
    from app.dependencies.database import get_db as dep_get_db
    from app.db.session import get_db as session_get_db

    assert core_get_db is not None
    assert dep_get_db is core_get_db
    assert session_get_db is core_get_db


def test_get_db_session_lifecycle_and_rollback():
    """Verify get_db rolls back on exception and closes properly."""
    from app.core.database import get_db

    db_gen = get_db()
    db = next(db_gen)
    assert isinstance(db, Session)

    # Trigger exception inside generator to test rollback & close
    with pytest.raises(RuntimeError, match="Simulated route error"):
        try:
            raise RuntimeError("Simulated route error")
        except RuntimeError as e:
            db_gen.throw(e)


def test_check_database_connection_helper():
    """Verify check_database_connection returns True on working session and False on failure."""
    from unittest.mock import MagicMock
    from app.core.database import check_database_connection, SessionLocal

    # Test with real local session
    db = SessionLocal()
    try:
        assert check_database_connection(db) is True
    finally:
        db.close()

    # Test with failing mock session
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("DB network error")
    assert check_database_connection(mock_db) is False


def test_db_pool_settings_defaults():
    """Verify database pooling configuration defaults."""
    test_settings = Settings()
    assert test_settings.DB_POOL_SIZE == 10
    assert test_settings.DB_MAX_OVERFLOW == 20
    assert test_settings.DB_POOL_TIMEOUT == 30
    assert test_settings.DB_POOL_RECYCLE == 1800

