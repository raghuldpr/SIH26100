import pytest
from app.db.base import Base
from app.db.session import engine


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure all SQLAlchemy database tables exist during test execution."""
    Base.metadata.create_all(bind=engine)
    yield
