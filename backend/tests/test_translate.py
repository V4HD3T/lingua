def test_list_languages(client):
    response = client.get("/languages")
    assert response.status_code == 200
    codes = {lang["code"] for lang in response.json()}
    assert {"en", "es"}.issubset(codes)


def test_translate_without_auth_works(client):
    response = client.post(
        "/translate",
        json={"text": "Hello world", "source_lang": "en", "target_lang": "es"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_text"] == "Hello world"
    assert data["translated_text"]  # the mock service shouldn't return empty


def test_translate_returns_confidence_and_alternatives(client):
    response = client.post(
        "/translate",
        json={"text": "Hello world, how are you?", "source_lang": "en", "target_lang": "es"},
    )
    assert response.status_code == 200
    data = response.json()
    assert 0.0 <= data["confidence"] <= 1.0
    assert isinstance(data["alternatives"], list)
    assert len(data["alternatives"]) >= 1


def test_translate_confidence_grows_with_longer_text(client):
    short = client.post(
        "/translate", json={"text": "Hi", "source_lang": "en", "target_lang": "es"}
    ).json()
    long = client.post(
        "/translate",
        json={
            "text": "This is a considerably longer sentence with many more words in it.",
            "source_lang": "en",
            "target_lang": "es",
        },
    ).json()
    # documented mock heuristic: longer input -> higher mock confidence
    assert long["confidence"] >= short["confidence"]


def test_translate_flags_known_idiom(client):
    response = client.post(
        "/translate",
        json={
            "text": "Don't worry, it's a piece of cake.",
            "source_lang": "en",
            "target_lang": "es",
        },
    )
    assert response.status_code == 200
    warnings = response.json()["idiom_warnings"]
    assert len(warnings) == 1
    assert warnings[0]["phrase"] == "piece of cake"


def test_translate_no_idiom_warning_for_literal_text(client):
    response = client.post(
        "/translate",
        json={"text": "The train arrives at nine.", "source_lang": "en", "target_lang": "es"},
    )
    assert response.json()["idiom_warnings"] == []


def test_translate_history_requires_auth(client):
    response = client.get("/translate/history")
    assert response.status_code == 401


def test_translate_and_check_history(client):
    client.post(
        "/auth/register",
        json={"username": "translator", "email": "translator@example.com", "password": "password1234"},
    )
    login = client.post("/auth/login", data={"username": "translator", "password": "password1234"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/translate",
        json={"text": "Good morning", "source_lang": "en", "target_lang": "es"},
        headers=headers,
    )

    history = client.get("/translate/history", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["source_text"] == "Good morning"
