"""Admin content-management API (v0.0.9): authorization, CRUD, and the
explicit destructive cascades."""

import re

from sqlmodel import select

from app.models import User, VocabularyProgress


def _auth_headers(client, username, email, password="password1234"):
    client.post("/auth/register", json={"username": username, "email": email, "password": password})
    login = client.post("/auth/login", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _admin_headers(client, session, username="admin1", email="admin1@example.com"):
    """Registers a user, then promotes them the way scripts/make_admin.py
    does -- directly in the database."""
    headers = _auth_headers(client, username, email)
    user = session.exec(select(User).where(User.username == username)).first()
    user.is_admin = True
    session.add(user)
    session.commit()
    return headers


def test_every_admin_route_is_gated(client):
    """Enumerated rather than sampled (v0.1.11). SECURITY.md's A01 section
    asserts that the whole /admin surface requires the flag; the guard is
    a single router-level dependency, so a route added with its own
    APIRouter -- or that dependency being dropped in a refactor -- would
    open everything at once while the spot-checks below still passed."""
    from app.main import app

    # Read from the generated schema rather than app.routes: FastAPI keeps
    # included routers as internal wrapper objects whose shape has changed
    # across versions, while the schema is a public, stable view of the
    # same thing. It's produced regardless of ENABLE_API_DOCS -- that
    # setting decides whether the schema is *served*, not whether it exists.
    operations = [
        (method, path)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith("/admin")
        for method in methods
    ]
    assert operations, "no /admin operations found -- has the prefix changed?"

    for method, path in operations:
        # Path params just need to parse; auth is refused before any lookup.
        concrete = re.sub(r"\{[^}]+\}", "1", path)
        response = client.request(method.upper(), concrete)
        assert response.status_code == 401, f"{method.upper()} {path} answered {response.status_code}"


def test_admin_endpoints_require_auth(client):
    response = client.post(
        "/admin/courses", json={"language_code": "fr", "title": "F", "level": "A1"}
    )
    assert response.status_code == 401


def test_admin_endpoints_forbidden_for_regular_users(client):
    headers = _auth_headers(client, "regular", "regular@example.com")
    response = client.post(
        "/admin/courses",
        json={"language_code": "fr", "title": "F", "level": "A1"},
        headers=headers,
    )
    assert response.status_code == 403


def test_admin_flag_is_not_mass_assignable(client, session):
    # Registering with is_admin in the payload must not grant it: the
    # field simply doesn't exist on UserCreate.
    client.post(
        "/auth/register",
        json={
            "username": "sneaky",
            "email": "sneaky@example.com",
            "password": "password1234",
            "is_admin": True,
        },
    )
    user = session.exec(select(User).where(User.username == "sneaky")).first()
    assert user.is_admin is False


def test_admin_can_create_full_content_pipeline(client, session):
    headers = _admin_headers(client, session)

    course = client.post(
        "/admin/courses",
        json={"language_code": "tr", "title": "Turkish Basics", "level": "A1", "description": "d"},
        headers=headers,
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    lesson = client.post(
        f"/admin/courses/{course_id}/lessons",
        json={"title": "Selamlar", "order": 1},
        headers=headers,
    )
    assert lesson.status_code == 201
    assert lesson.json()["language_code"] == "tr"
    lesson_id = lesson.json()["id"]

    vocab = client.post(
        f"/admin/lessons/{lesson_id}/vocabulary",
        json={"word": "merhaba", "translation": "hello"},
        headers=headers,
    )
    assert vocab.status_code == 201

    quiz = client.post(f"/admin/lessons/{lesson_id}/quiz", json={"title": "Selam Quiz"}, headers=headers)
    assert quiz.status_code == 201
    quiz_id = quiz.json()["id"]

    question = client.post(
        f"/admin/quizzes/{quiz_id}/questions",
        json={
            "question_type": "fill_blank",
            "question_text": "___ dünya",
            "correct_answer": "merhaba",
            "difficulty": 1,
        },
        headers=headers,
    )
    assert question.status_code == 201
    assert question.json()["correct_answer"] == "merhaba"

    # the new content is served through the public API
    titles = [c["title"] for c in client.get("/courses?limit=100").json()["items"]]
    assert "Turkish Basics" in titles
    public_quiz = client.get(f"/lessons/{lesson_id}/quiz").json()
    assert public_quiz["title"] == "Selam Quiz"
    assert len(public_quiz["questions"]) == 1


def test_admin_can_update_course(client, session):
    headers = _admin_headers(client, session, "admin2", "admin2@example.com")
    response = client.patch("/admin/courses/1", json={"level": "A2"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["level"] == "A2"
    # only the sent field changed
    assert response.json()["title"] == "Spanish for Beginners"
    assert client.get("/courses/1").json()["level"] == "A2"


def test_lesson_can_only_have_one_quiz(client, session):
    headers = _admin_headers(client, session, "admin3", "admin3@example.com")
    response = client.post("/admin/lessons/1/quiz", json={"title": "Second"}, headers=headers)
    assert response.status_code == 400


def test_delete_course_cascades(client, session):
    # a learner builds spaced-repetition progress on the seeded content first
    learner = _auth_headers(client, "learner", "learner@example.com")
    client.post("/vocabulary/1/review", json={"quality": 5}, headers=learner)
    assert session.exec(select(VocabularyProgress)).first() is not None

    headers = _admin_headers(client, session, "admin4", "admin4@example.com")
    response = client.delete("/admin/courses/1", headers=headers)
    assert response.status_code == 204

    assert client.get("/courses/1").status_code == 404
    assert client.get("/lessons/1").status_code == 404
    assert client.get("/lessons/1/quiz").status_code == 404
    # learner progress on the deleted content is gone too -- the documented
    # destructive-cascade decision
    assert session.exec(select(VocabularyProgress)).first() is None


def test_update_question_options_and_delete(client, session):
    headers = _admin_headers(client, session, "admin5", "admin5@example.com")
    response = client.patch(
        "/admin/questions/1", json={"options": ["hello", "goodbye"]}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["options"] == ["hello", "goodbye"]

    assert client.delete("/admin/questions/1", headers=headers).status_code == 204
    public = client.get("/quizzes/1").json()
    assert all(q["id"] != 1 for q in public["questions"])
