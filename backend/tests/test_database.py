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
