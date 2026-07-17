def _auth_headers(client, username="suggester", email="suggester@example.com", password="password1234"):
    client.post("/auth/register", json={"username": username, "email": email, "password": password})
    login = client.post("/auth/login", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_suggestions_requires_auth(client):
    response = client.get("/users/me/vocabulary-suggestions")
    assert response.status_code == 401


def test_no_suggestions_without_translation_history(client):
    headers = _auth_headers(client)
    response = client.get("/users/me/vocabulary-suggestions", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_frequently_translated_vocabulary_word_is_suggested(client):
    headers = _auth_headers(client)
    # "hola" is one of the two seeded vocabulary words. Translate it twice
    # (the suggestion threshold is min_frequency=2) as part of unrelated
    # sentences, so this is testing real word-boundary matching, not just
    # translating the bare word itself.
    client.post(
        "/translate", json={"text": "hola amigo", "source_lang": "es", "target_lang": "en"}, headers=headers
    )
    client.post(
        "/translate", json={"text": "hola de nuevo", "source_lang": "es", "target_lang": "en"}, headers=headers
    )

    response = client.get("/users/me/vocabulary-suggestions", headers=headers)
    assert response.status_code == 200
    suggestions = response.json()
    assert len(suggestions) == 1
    assert suggestions[0]["word"] == "hola"
    assert suggestions[0]["frequency"] == 2


def test_single_translation_does_not_meet_threshold(client):
    headers = _auth_headers(client)
    client.post(
        "/translate", json={"text": "hola amigo", "source_lang": "es", "target_lang": "en"}, headers=headers
    )
    response = client.get("/users/me/vocabulary-suggestions", headers=headers)
    assert response.json() == []


def test_already_started_word_is_not_suggested(client):
    headers = _auth_headers(client)
    client.post(
        "/translate", json={"text": "hola amigo", "source_lang": "es", "target_lang": "en"}, headers=headers
    )
    client.post(
        "/translate", json={"text": "hola de nuevo", "source_lang": "es", "target_lang": "en"}, headers=headers
    )
    # Start formally learning "hola" (vocabulary_item_id=1) via spaced repetition --
    # it should now be excluded from suggestions, since the whole point is to
    # surface words the learner *hasn't* started on yet.
    client.post("/vocabulary/1/review", json={"quality": 5}, headers=headers)

    response = client.get("/users/me/vocabulary-suggestions", headers=headers)
    assert response.json() == []
