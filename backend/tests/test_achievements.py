def _auth_headers(client, username="badgeuser", email="badgeuser@example.com", password="password1234"):
    client.post("/auth/register", json={"username": username, "email": email, "password": password})
    login = client.post("/auth/login", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_achievements_requires_auth(client):
    response = client.get("/users/me/achievements")
    assert response.status_code == 401


def test_no_achievements_before_any_activity(client):
    headers = _auth_headers(client)
    response = client.get("/users/me/achievements", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_first_translation_awards_badge(client):
    headers = _auth_headers(client)
    response = client.post(
        "/translate",
        json={"text": "hello there", "source_lang": "en", "target_lang": "es"},
        headers=headers,
    )
    codes = {a["code"] for a in response.json()["new_achievements"]}
    assert "first_translation" in codes

    listed = client.get("/users/me/achievements", headers=headers).json()
    assert any(a["code"] == "first_translation" for a in listed)


def test_badge_is_not_awarded_twice(client):
    headers = _auth_headers(client)
    first = client.post(
        "/translate", json={"text": "one", "source_lang": "en", "target_lang": "es"}, headers=headers
    )
    assert "first_translation" in {a["code"] for a in first.json()["new_achievements"]}

    second = client.post(
        "/translate", json={"text": "two", "source_lang": "en", "target_lang": "es"}, headers=headers
    )
    assert second.json()["new_achievements"] == []


def test_ten_translations_awards_badge(client):
    headers = _auth_headers(client)
    response = None
    for i in range(10):
        response = client.post(
            "/translate",
            json={"text": f"sentence number {i}", "source_lang": "en", "target_lang": "es"},
            headers=headers,
        )
    codes = {a["code"] for a in response.json()["new_achievements"]}
    assert "ten_translations" in codes


def test_perfect_quiz_awards_badge(client):
    headers = _auth_headers(client)
    response = client.post(
        "/quizzes/1/submit", json={"answers": {"1": "hello"}}, headers=headers
    )
    codes = {a["code"] for a in response.json()["new_achievements"]}
    assert "perfect_quiz" in codes
    assert "first_quiz" in codes


def test_imperfect_quiz_does_not_award_perfect_badge(client):
    headers = _auth_headers(client)
    response = client.post(
        "/quizzes/1/submit",
        json={"answers": {"1": "hello", "2": "wrong"}},
        headers=headers,
    )
    codes = {a["code"] for a in response.json()["new_achievements"]}
    assert "perfect_quiz" not in codes
    assert "first_quiz" in codes  # still earned for completing a quiz at all


def test_five_words_started_awards_badge(client):
    headers = _auth_headers(client)
    # only 2 seeded vocabulary items exist, so review the same 2 repeatedly --
    # what matters for this badge is *distinct* vocabulary_item_ids started,
    # so this should NOT be enough on its own.
    client.post("/vocabulary/1/review", json={"quality": 5}, headers=headers)
    response = client.post("/vocabulary/2/review", json={"quality": 5}, headers=headers)
    codes = {a["code"] for a in response.json()["new_achievements"]}
    assert "five_words_started" not in codes
