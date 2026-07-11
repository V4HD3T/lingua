def test_list_languages(client):
    response = client.get("/languages")
    assert response.status_code == 200
    codes = {lang["code"] for lang in response.json()}
    assert {"tr", "en"}.issubset(codes)


def test_translate_without_auth_works(client):
    response = client.post(
        "/translate",
        json={"text": "Merhaba dünya", "source_lang": "tr", "target_lang": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_text"] == "Merhaba dünya"
    assert data["translated_text"]  # mock service shouldn't return empty


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
        json={"text": "Günaydın", "source_lang": "tr", "target_lang": "en"},
        headers=headers,
    )

    history = client.get("/translate/history", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["source_text"] == "Günaydın"
