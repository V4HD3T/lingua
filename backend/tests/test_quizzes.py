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
    assert len(data["questions"]) == 1
    assert "merhaba" in data["questions"][0]["options"]


def test_get_missing_quiz_returns_404(client):
    response = client.get("/quizzes/999")
    assert response.status_code == 404


def test_submit_quiz_requires_auth(client):
    response = client.post("/quizzes/1/submit", json={"answers": {"1": "merhaba"}})
    assert response.status_code == 401


def test_submit_quiz_correct_answer_scores_100(client):
    headers = _get_auth_headers(client)
    response = client.post(
        "/quizzes/1/submit", json={"answers": {"1": "merhaba"}}, headers=headers
    )
    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 100.0
    assert result["correct_count"] == 1
    assert result["total_questions"] == 1


def test_submit_quiz_wrong_answer_scores_0(client):
    headers = _get_auth_headers(client, username="quizuser2", email="quizuser2@example.com")
    response = client.post(
        "/quizzes/1/submit", json={"answers": {"1": "hoşça kal"}}, headers=headers
    )
    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 0.0
    assert result["correct_count"] == 0
