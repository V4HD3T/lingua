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
    response = client.post("/quizzes/1/submit", json={"answers": {"1": "hello"}})
    assert response.status_code == 401


def test_submit_quiz_correct_answer_scores_100(client):
    headers = _get_auth_headers(client)
    response = client.post(
        "/quizzes/1/submit", json={"answers": {"1": "hello"}}, headers=headers
    )
    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 100.0
    assert result["correct_count"] == 1
    assert result["total_questions"] == 1


def test_submit_quiz_wrong_answer_scores_0(client):
    headers = _get_auth_headers(client, username="quizuser2", email="quizuser2@example.com")
    response = client.post(
        "/quizzes/1/submit", json={"answers": {"1": "goodbye"}}, headers=headers
    )
    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 0.0
    assert result["correct_count"] == 0


def test_submit_quiz_only_scores_submitted_questions(client):
    # Answering just 1 of the quiz's 5 questions should score against that
    # 1, not be penalized for the 4 left unanswered -- this is what makes
    # scoring consistent with adaptive selection only showing a subset.
    headers = _get_auth_headers(client, username="partial", email="partial@example.com")
    response = client.post(
        "/quizzes/1/submit", json={"answers": {"1": "hello", "2": "goodbye"}}, headers=headers
    )
    result = response.json()
    assert result["total_questions"] == 2
    assert result["correct_count"] == 2
    assert result["score"] == 100.0


def test_submit_quiz_fill_blank_question(client):
    headers = _get_auth_headers(client, username="fillblank", email="fillblank@example.com")
    # question 3 is the fill_blank one, correct_answer="hola"
    response = client.post(
        "/quizzes/1/submit", json={"answers": {"3": "Hola"}}, headers=headers
    )
    result = response.json()
    assert result["correct_count"] == 1  # case-insensitive match


def test_submit_quiz_sentence_order_question(client):
    headers = _get_auth_headers(client, username="sentenceorder", email="sentenceorder@example.com")
    # question 5 is sentence_order, correct_answer="hola como estas"
    correct = client.post(
        "/quizzes/1/submit", json={"answers": {"5": "hola como estas"}}, headers=headers
    ).json()
    assert correct["correct_count"] == 1

    wrong_order = client.post(
        "/quizzes/1/submit", json={"answers": {"5": "estas como hola"}}, headers=headers
    ).json()
    assert wrong_order["correct_count"] == 0


def test_submit_quiz_awards_first_quiz_achievement(client):
    headers = _get_auth_headers(client, username="achiever", email="achiever@example.com")
    response = client.post(
        "/quizzes/1/submit", json={"answers": {"1": "hello"}}, headers=headers
    )
    codes = {a["code"] for a in response.json()["new_achievements"]}
    assert "first_quiz" in codes

    # submitting again shouldn't re-award the same badge
    response2 = client.post(
        "/quizzes/1/submit", json={"answers": {"1": "hello"}}, headers=headers
    )
    assert response2.json()["new_achievements"] == []


def test_adaptive_quiz_hides_hard_questions_for_low_scorers(client):
    headers = _get_auth_headers(client, username="struggling", email="struggling@example.com")
    # Fail the quiz a few times to bring the average score below the low threshold.
    for _ in range(3):
        client.post("/quizzes/1/submit", json={"answers": {"1": "wrong answer"}}, headers=headers)

    response = client.get("/lessons/1/quiz", headers=headers)
    difficulties_shown = {q["question_type"] for q in response.json()["questions"]}
    # difficulty=3 is the sentence_order question -- shouldn't be offered
    # to someone who has been scoring 0%.
    assert "sentence_order" not in difficulties_shown


def test_adaptive_quiz_shows_everything_for_anonymous_users(client):
    response = client.get("/lessons/1/quiz")
    assert len(response.json()["questions"]) == 5
