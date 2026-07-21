import json

from app.models import QuizSession

# The seeded quiz's answers keyed by question id (ids 1-5 are stable: the
# seed inserts them in order into a fresh per-test database). Used by the
# tests that need to hand-build a submission; the fetch-and-answer flow
# lives in the take_seed_quiz fixture (conftest).
_ANSWERS_BY_ID = {
    "1": "hello",
    "2": "goodbye",
    "3": "hola",
    "4": "hola",
    "5": "hola como estas",
}


def _get_auth_headers(client, username="quizuser", email="quizuser@example.com", password="password1234"):
    client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    login = client.post("/auth/login", data={"username": username, "password": password})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_seeded_quiz(client):
    response = client.get("/quizzes/1")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Greetings Quiz"
    assert len(data["questions"]) == 5
    question_types = {q["question_type"] for q in data["questions"]}
    assert question_types == {"multiple_choice", "fill_blank", "listening", "sentence_order"}
    assert data["session_id"] is None  # anonymous fetches record no session


def test_get_quiz_creates_session_for_logged_in_user(client, session):
    headers = _get_auth_headers(client)
    data = client.get("/lessons/1/quiz", headers=headers).json()
    assert isinstance(data["session_id"], int)
    row = session.get(QuizSession, data["session_id"])
    assert row is not None
    assert json.loads(row.question_ids_json) == [q["id"] for q in data["questions"]]


def test_get_missing_quiz_returns_404(client):
    response = client.get("/quizzes/999")
    assert response.status_code == 404


def test_get_quiz_by_lesson(client):
    response = client.get("/lessons/1/quiz")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_quiz_by_lesson_missing_returns_404(client):
    response = client.get("/lessons/999/quiz")
    assert response.status_code == 404


def test_submit_quiz_requires_auth(client):
    response = client.post("/quizzes/1/submit", json={"session_id": 1, "answers": {"1": "hello"}})
    assert response.status_code == 401


def test_submit_requires_session_id_field(client):
    # v0.0.9 contract: a submission without its session is malformed.
    headers = _get_auth_headers(client, username="schemauser", email="schemauser@example.com")
    response = client.post("/quizzes/1/submit", json={"answers": {"1": "hello"}}, headers=headers)
    assert response.status_code == 422


def test_submit_full_correct_scores_100(client, take_seed_quiz):
    headers = _get_auth_headers(client, username="fullcorrect", email="fullcorrect@example.com")
    result = take_seed_quiz(headers).json()
    assert result["score"] == 100.0
    assert result["total_questions"] == 5
    assert result["correct_count"] == 5


def test_submit_all_wrong_scores_0(client, take_seed_quiz):
    headers = _get_auth_headers(client, username="allwrong", email="allwrong@example.com")
    result = take_seed_quiz(headers, wrong=99).json()
    assert result["score"] == 0.0
    assert result["correct_count"] == 0


def test_unanswered_served_questions_count_as_wrong(client):
    # The v0.0.7-review exploit: submit one known-correct answer for a
    # 100% score and the perfect_quiz badge. Grading against the served
    # set closes it -- the other four served questions count as wrong.
    headers = _get_auth_headers(client, username="cherry", email="cherry@example.com")
    quiz = client.get("/lessons/1/quiz", headers=headers).json()
    response = client.post(
        f"/quizzes/{quiz['id']}/submit",
        json={"session_id": quiz["session_id"], "answers": {"1": "hello"}},
        headers=headers,
    )
    result = response.json()
    assert result["total_questions"] == 5
    assert result["correct_count"] == 1
    assert result["score"] == 20.0
    assert "perfect_quiz" not in {a["code"] for a in result["new_achievements"]}


def test_answers_outside_served_set_are_ignored(client):
    headers = _get_auth_headers(client, username="extra", email="extra@example.com")
    quiz = client.get("/lessons/1/quiz", headers=headers).json()
    answers = dict(_ANSWERS_BY_ID)
    answers["999"] = "whatever"
    result = client.post(
        f"/quizzes/{quiz['id']}/submit",
        json={"session_id": quiz["session_id"], "answers": answers},
        headers=headers,
    ).json()
    assert result["total_questions"] == 5
    assert result["score"] == 100.0


def test_submit_with_unknown_session_is_rejected(client):
    headers = _get_auth_headers(client, username="nosession", email="nosession@example.com")
    response = client.post(
        "/quizzes/1/submit", json={"session_id": 9999, "answers": _ANSWERS_BY_ID}, headers=headers
    )
    assert response.status_code == 400


def test_submit_with_someone_elses_session_is_rejected(client):
    headers_a = _get_auth_headers(client, username="usera", email="usera@example.com")
    quiz_a = client.get("/lessons/1/quiz", headers=headers_a).json()

    headers_b = _get_auth_headers(client, username="userb", email="userb@example.com")
    response = client.post(
        "/quizzes/1/submit",
        json={"session_id": quiz_a["session_id"], "answers": _ANSWERS_BY_ID},
        headers=headers_b,
    )
    assert response.status_code == 400


def test_session_is_reusable_for_retry(client):
    # The frontend's "Try again" resubmits the same served set without
    # refetching -- deliberately allowed (practice, not an exploit).
    headers = _get_auth_headers(client, username="retryuser", email="retryuser@example.com")
    quiz = client.get("/lessons/1/quiz", headers=headers).json()
    payload = {"session_id": quiz["session_id"], "answers": _ANSWERS_BY_ID}
    first = client.post(f"/quizzes/{quiz['id']}/submit", json=payload, headers=headers)
    second = client.post(f"/quizzes/{quiz['id']}/submit", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["score"] == 100.0


def test_submit_quiz_fill_blank_is_case_insensitive(client):
    headers = _get_auth_headers(client, username="fillblank", email="fillblank@example.com")
    quiz = client.get("/lessons/1/quiz", headers=headers).json()
    answers = dict(_ANSWERS_BY_ID)
    answers["3"] = "HOLA"
    result = client.post(
        f"/quizzes/{quiz['id']}/submit",
        json={"session_id": quiz["session_id"], "answers": answers},
        headers=headers,
    ).json()
    assert result["score"] == 100.0


def test_submit_quiz_sentence_order_wrong_order_is_wrong(client):
    headers = _get_auth_headers(client, username="sentenceorder", email="sentenceorder@example.com")
    quiz = client.get("/lessons/1/quiz", headers=headers).json()
    answers = dict(_ANSWERS_BY_ID)
    answers["5"] = "estas como hola"
    result = client.post(
        f"/quizzes/{quiz['id']}/submit",
        json={"session_id": quiz["session_id"], "answers": answers},
        headers=headers,
    ).json()
    assert result["correct_count"] == 4
    assert result["score"] == 80.0


def test_submit_quiz_awards_first_quiz_achievement(client, take_seed_quiz):
    headers = _get_auth_headers(client, username="achiever", email="achiever@example.com")
    first = take_seed_quiz(headers)
    codes = {a["code"] for a in first.json()["new_achievements"]}
    assert "first_quiz" in codes

    # a second run must not re-award the badge (the fixture refetches, so
    # this also exercises submitting a fresh adaptive session)
    second = take_seed_quiz(headers)
    assert second.json()["new_achievements"] == []


def test_adaptive_quiz_hides_hard_questions_for_low_scorers(client, take_seed_quiz):
    headers = _get_auth_headers(client, username="struggling", email="struggling@example.com")
    for _ in range(3):
        take_seed_quiz(headers, wrong=99)

    response = client.get("/lessons/1/quiz", headers=headers)
    types_shown = {q["question_type"] for q in response.json()["questions"]}
    # difficulty=3 is the sentence_order question -- shouldn't be offered
    # to someone who has been scoring 0%.
    assert "sentence_order" not in types_shown


def test_adaptive_quiz_shows_everything_for_anonymous_users(client):
    response = client.get("/lessons/1/quiz")
    assert len(response.json()["questions"]) == 5


def test_anonymous_quiz_fetch_creates_no_session(client, session):
    """Browsing a lesson page probes for a quiz. That probe is anonymous
    precisely so it doesn't mint a throwaway QuizSession per page view --
    with a growing catalogue that was unbounded write traffic from mere
    reading."""
    from sqlmodel import select

    from app.models import QuizSession

    for _ in range(5):
        assert client.get("/lessons/1/quiz").status_code == 200
    assert session.exec(select(QuizSession)).all() == []
