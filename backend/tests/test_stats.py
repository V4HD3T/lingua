from datetime import date, timedelta

from app.services.streaks import compute_streaks


# --- Pure unit tests for the streak calculation logic (no DB, fast) ---


def test_streak_empty():
    current, longest = compute_streaks(set())
    assert current == 0
    assert longest == 0


def test_streak_single_day_today():
    today = date.today()
    current, longest = compute_streaks({today})
    assert current == 1
    assert longest == 1


def test_streak_broken_by_gap():
    today = date.today()
    dates = {today, today - timedelta(days=1), today - timedelta(days=5)}
    current, longest = compute_streaks(dates)
    assert current == 2  # today + yesterday
    assert longest == 2  # the longest consecutive block is also 2


def test_streak_yesterday_still_counts_as_current():
    today = date.today()
    dates = {today - timedelta(days=1), today - timedelta(days=2)}
    current, longest = compute_streaks(dates)
    assert current == 2  # active yesterday, streak isn't broken yet today
    assert longest == 2


def test_streak_two_days_ago_breaks_current():
    today = date.today()
    dates = {today - timedelta(days=2), today - timedelta(days=3)}
    current, longest = compute_streaks(dates)
    assert current == 0  # last activity is older than yesterday, streak is broken
    assert longest == 2  # but the longest past block is still 2


def test_streak_longest_can_exceed_current():
    today = date.today()
    dates = {
        today,
        today - timedelta(days=10),
        today - timedelta(days=11),
        today - timedelta(days=12),
        today - timedelta(days=13),
    }
    current, longest = compute_streaks(dates)
    assert current == 1  # only active today
    assert longest == 4  # but there's a 4-day block in the past


# --- Endpoint integration tests ---


def _auth_headers(client, username="progress", email="progress@example.com", password="password1234"):
    client.post("/auth/register", json={"username": username, "email": email, "password": password})
    login = client.post("/auth/login", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_stats_requires_auth(client):
    response = client.get("/users/me/stats")
    assert response.status_code == 401


def test_stats_with_no_activity(client):
    headers = _auth_headers(client)
    response = client.get("/users/me/stats", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["current_streak"] == 0
    assert data["total_translations"] == 0
    assert data["total_quiz_attempts"] == 0
    assert data["courses"][0]["completed_lessons"] == 0
    assert data["daily_goal"] == 10
    assert data["reviews_today"] == 0


def test_stats_reviews_today_counts_todays_reviews(client):
    headers = _auth_headers(client)
    client.post("/vocabulary/1/review", json={"quality": 5}, headers=headers)
    client.post("/vocabulary/2/review", json={"quality": 3}, headers=headers)

    response = client.get("/users/me/stats", headers=headers)
    assert response.json()["reviews_today"] == 2


def test_stats_after_translation_and_quiz(client):
    headers = _auth_headers(client)

    client.post(
        "/translate",
        json={"text": "hello", "source_lang": "en", "target_lang": "es"},
        headers=headers,
    )
    client.post("/quizzes/1/submit", json={"answers": {"1": "hello"}}, headers=headers)

    response = client.get("/users/me/stats", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total_translations"] == 1
    assert data["total_quiz_attempts"] == 1
    assert data["average_quiz_score"] == 100.0
    assert data["current_streak"] == 1  # there's activity today

    course = data["courses"][0]
    assert course["total_lessons"] == 1
    assert course["completed_lessons"] == 1
    assert course["completion_percentage"] == 100.0
