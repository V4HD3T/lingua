import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app, seed_data
from app.services.email_service import get_email_service
from app.services.rate_limiter import (
    api_rate_limiter,
    login_ip_rate_limiter,
    login_rate_limiter,
    password_reset_rate_limiter,
    register_rate_limiter,
    translate_rate_limiter,
)


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """The rate limiters are module-level singletons (deliberately -- that's
    what makes them actually shared across requests in the real app), and
    Starlette's TestClient always reports the same fake client IP. Without
    this, one test's requests would count against the next test's budget --
    and since v0.0.8's app-wide backstop counts *every* request, the whole
    suite would trip it within seconds."""
    login_rate_limiter.clear_all()
    login_ip_rate_limiter.clear_all()
    register_rate_limiter.clear_all()
    password_reset_rate_limiter.clear_all()
    api_rate_limiter.clear_all()
    translate_rate_limiter.clear_all()
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


SEED_QUIZ_ANSWER_KEY = {
    "What is the English translation of 'hola'?": "hello",
    "What is the English translation of 'adiós'?": "goodbye",
    'Complete the greeting: "___, ¿Cómo estás?"': "hola",
    "What word did you hear?": "hola",
    "Put the words in order to form a greeting.": "hola como estas",
}


@pytest.fixture
def take_seed_quiz(client):
    """Plays the seeded lesson-1 quiz end to end the way the frontend does
    (v0.0.9): fetch the quiz -- which records the served questions as a
    QuizSession -- then submit answers for exactly that served set.
    `wrong` answers that many of the served questions incorrectly (from
    the front), so tests can produce controlled scores regardless of
    which adaptive subset was served."""

    def _take(headers, wrong: int = 0):
        quiz = client.get("/lessons/1/quiz", headers=headers).json()
        answers = {}
        for index, question in enumerate(quiz["questions"]):
            correct = SEED_QUIZ_ANSWER_KEY[question["question_text"]]
            answers[str(question["id"])] = "definitely wrong" if index < wrong else correct
        return client.post(
            f"/quizzes/{quiz['id']}/submit",
            json={"session_id": quiz["session_id"], "answers": answers},
            headers=headers,
        )

    return _take
