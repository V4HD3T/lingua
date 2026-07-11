def test_register_and_login(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "a-strong-password",
            "native_language": "tr",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data

    login_response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "a-strong-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    assert token

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "testuser@example.com"


def test_login_with_wrong_password_fails(client):
    client.post(
        "/auth/register",
        json={"username": "test2", "email": "test2@example.com", "password": "correct-password"},
    )
    response = client.post("/auth/login", data={"username": "test2", "password": "wrong-password"})
    assert response.status_code == 401


def test_duplicate_username_rejected(client):
    payload = {"username": "duplicate", "email": "duplicate@example.com", "password": "password1234"}
    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201
    second = client.post("/auth/register", json=payload)
    assert second.status_code == 400
