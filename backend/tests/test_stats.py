from datetime import date, timedelta

from app.services.streaks import compute_streaks


# --- Pure unit tests for the streak calculation logic (no DB, fast) ---
#
# `today` is a fixed date passed in, not date.today() (v0.1.9). These
# tests used to read the *local* date while compute_streaks read the *UTC*
# one, so they quietly asserted the two were the same day -- true on a UTC
# CI runner, and false on any developer machine east or west of it during
# the offset window. That divergence was the bug under test; a test that
# shares it can't catch it.

TODAY = date(2026, 3, 14)


def test_streak_empty():
    current, longest = compute_streaks(set(), TODAY)
    assert current == 0
    assert longest == 0


def test_streak_single_day_today():
    today = TODAY
    current, longest = compute_streaks({today}, TODAY)
    assert current == 1
    assert longest == 1


def test_streak_broken_by_gap():
    today = TODAY
    dates = {today, today - timedelta(days=1), today - timedelta(days=5)}
    current, longest = compute_streaks(dates, TODAY)
    assert current == 2  # today + yesterday
    assert longest == 2  # the longest consecutive block is also 2


def test_streak_yesterday_still_counts_as_current():
    today = TODAY
    dates = {today - timedelta(days=1), today - timedelta(days=2)}
    current, longest = compute_streaks(dates, TODAY)
    assert current == 2  # active yesterday, streak isn't broken yet today
    assert longest == 2


def test_streak_two_days_ago_breaks_current():
    today = TODAY
    dates = {today - timedelta(days=2), today - timedelta(days=3)}
    current, longest = compute_streaks(dates, TODAY)
    assert current == 0  # last activity is older than yesterday, streak is broken
    assert longest == 2  # but the longest past block is still 2


def test_streak_longest_can_exceed_current():
    today = TODAY
    dates = {
        today,
        today - timedelta(days=10),
        today - timedelta(days=11),
        today - timedelta(days=12),
        today - timedelta(days=13),
    }
    current, longest = compute_streaks(dates, TODAY)
    assert current == 1  # only active today
    assert longest == 4  # but there's a 4-day block in the past


# --- Endpoint integration tests ---


def _auth_headers(client, username="progress", email="progress@example.com", password="password1234"):
    client.post("/auth/register", json={"username": username, "email": email, "password": password})
    login = client.post("/auth/login", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_new_user_defaults_to_utc(client):
    # The pre-v0.1.9 behaviour, kept as the default: a learner who never
    # reports a zone is treated exactly as before rather than guessed at.
    headers = _auth_headers(client, username="tzdefault", email="tzdefault@example.com")
    assert client.get("/auth/me", headers=headers).json()["timezone"] == "UTC"


def test_reporting_a_timezone_is_persisted(client):
    headers = _auth_headers(client, username="tzset", email="tzset@example.com")
    response = client.patch(
        "/auth/me/timezone", json={"timezone": "Europe/Istanbul"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["timezone"] == "Europe/Istanbul"
    assert client.get("/auth/me", headers=headers).json()["timezone"] == "Europe/Istanbul"


def test_unknown_timezone_is_rejected(client):
    """Validated rather than stored as given: an unrecognised name would
    silently fall back to UTC on every read, leaving the learner with a
    setting that looks saved and does nothing."""
    headers = _auth_headers(client, username="tzbad", email="tzbad@example.com")
    for bad in ("Middle/Earth", "UTC+3", "not a zone"):
        response = client.patch("/auth/me/timezone", json={"timezone": bad}, headers=headers)
        assert response.status_code == 400, bad
    assert client.get("/auth/me", headers=headers).json()["timezone"] == "UTC"


def test_timezone_endpoint_requires_auth(client):
    assert client.patch("/auth/me/timezone", json={"timezone": "UTC"}).status_code == 401


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


def test_stats_after_translation_and_quiz(client, take_seed_quiz):
    headers = _auth_headers(client)

    client.post(
        "/translate",
        json={"text": "hello", "source_lang": "en", "target_lang": "es"},
        headers=headers,
    )
    take_seed_quiz(headers)  # full served set answered correctly -> 100%

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
