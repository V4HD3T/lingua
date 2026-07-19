import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app, seed_data
from app.services.email_service import get_email_service
from app.services.rate_limiter import login_rate_limiter, password_reset_rate_limiter, register_rate_limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """The rate limiters are module-level singletons (deliberately -- that's
    what makes them actually shared across requests in the real app), and
    Starlette's TestClient always reports the same fake client IP. Without
    this, one test's failed-login attempts would count against the next
    test's rate limit budget."""
    login_rate_limiter.clear_all()
    register_rate_limiter.clear_all()
    password_reset_rate_limiter.clear_all()
    yield


@pytest.fixture(autouse=True)
def _reset_mock_email_service():
    """get_email_service() is an lru_cache singleton too, so sent_emails
    would otherwise accumulate across every test in the whole run."""
    get_email_service().sent_emails.clear()
    yield


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_data(session)  # start each test with the same sample language/course/quiz data
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
