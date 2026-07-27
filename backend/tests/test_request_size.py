"""Request bodies are bounded (v0.1.20).

Individual fields were capped by their schemas; the request itself was
not, and neither was the one container in it. A 20,000-key `answers` dict
in a ~4 MB body was accepted and parsed.
"""

import json

from app.config import settings


def _register(client, username="ada"):
    password = "correct horse battery"
    client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
            "native_language": "en",
        },
    )
    tokens = client.post(
        "/auth/login", data={"username": username, "password": password}
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_an_oversized_body_is_refused_before_it_is_read(client):
    oversized = "x" * (settings.max_request_body_bytes + 1024)
    response = client.post(
        "/translate",
        content=json.dumps({"text": oversized, "source_lang": "en", "target_lang": "es"}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


def test_the_limit_is_generous_next_to_what_the_api_actually_accepts(client):
    """A translation caps at 2000 characters, so the largest ordinary body
    is orders of magnitude below the ceiling. Asserted so that tightening
    the limit can't silently start refusing valid requests."""
    largest_translation = "é" * 2000  # multi-byte, so bytes > characters
    response = client.post(
        "/translate",
        json={"text": largest_translation, "source_lang": "en", "target_lang": "es"},
    )
    assert response.status_code == 200


def test_a_malformed_content_length_is_rejected_not_crashed(client):
    response = client.post(
        "/translate",
        content=b'{"text":"hi","source_lang":"en","target_lang":"es"}',
        headers={"Content-Type": "application/json", "Content-Length": "not-a-number"},
    )
    assert response.status_code in (400, 422)


def test_the_answers_dict_is_bounded(client):
    headers = _register(client)
    quiz = client.get("/lessons/1/quiz", headers=headers).json()

    response = client.post(
        f"/quizzes/{quiz['id']}/submit",
        json={
            "session_id": quiz["session_id"],
            "answers": {str(i): "x" for i in range(5000)},
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_a_normal_submission_is_unaffected(client):
    """The bound has to sit above any real quiz, or it breaks the feature
    it was added to protect."""
    headers = _register(client, "bob")
    quiz = client.get("/lessons/1/quiz", headers=headers).json()

    response = client.post(
        f"/quizzes/{quiz['id']}/submit",
        json={
            "session_id": quiz["session_id"],
            "answers": {str(q["id"]): "whatever" for q in quiz["questions"]},
        },
        headers=headers,
    )
    assert response.status_code == 200


def test_the_413_still_carries_the_security_headers(client):
    """The size check sits inside the header middleware on purpose -- a
    rejected request is still a response a browser will read."""
    oversized = "x" * (settings.max_request_body_bytes + 1024)
    response = client.post(
        "/translate",
        content=json.dumps({"text": oversized, "source_lang": "en", "target_lang": "es"}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Content-Security-Policy"] == "default-src 'self'"
