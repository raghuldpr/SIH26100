from typing import Any, Dict, Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

connect_args: Dict[str, Any] = {}
engine_kwargs: Dict[str, Any] = {
    "pool_pre_ping": True,
}

# Configure connection pooling appropriate for PostgreSQL / Supabase
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
elif settings.DATABASE_URL:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
    })

# If DATABASE_URL is not set yet, provide a non-blocking fallback for local imports and test suites
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
    Reusable database dependency for FastAPI route handlers.
    Yields a database session and ensures it is properly closed after request processing.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
