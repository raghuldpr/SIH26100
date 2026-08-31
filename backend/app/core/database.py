import logging
from typing import Any, Dict, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

connect_args: Dict[str, Any] = {}
engine_kwargs: Dict[str, Any] = {
    "pool_pre_ping": True,
}

# Configure connection pooling appropriate for PostgreSQL / Supabase
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
elif settings.DATABASE_URL:
    engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    })

# Fallback for offline local unit tests / imports when DATABASE_URL is not provided
db_url = settings.DATABASE_URL if settings.DATABASE_URL else "sqlite:///./dev_fallback.db"

engine = create_engine(
    db_url,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI database session dependency.
    Yields a SQLAlchemy Session, handles transaction rollback on exception,
    and guarantees proper session closing in the request teardown lifecycle.
    """
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection(db: Session) -> bool:
    """
    Verifies that the database is reachable and responsive.
    Executes a lightweight SELECT 1 query.
    """
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return result == 1
    except Exception as e:
        logger.error(f"Database connectivity check failed: {type(e).__name__}")
        return False
