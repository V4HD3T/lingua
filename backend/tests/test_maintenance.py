"""Purging rows that stopped meaning anything (v0.1.20).

Most of these tests are about what must *survive*. A purge that frees
space is easy; a purge that quietly deletes a row something still depends
on changes behaviour, and the failure shows up somewhere else entirely --
which is why the retention windows, not the deletes, are what's asserted
here.
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.config import settings
from app.models import AuthToken, QuizSession, RefreshToken, User
from app.services.maintenance import (
    AUTH_TOKEN_RETENTION,
    QUIZ_SESSION_RETENTION,
    REFRESH_TOKEN_RETENTION,
    purge_expired,
)
from app.services.tokens import generate_token, hash_token

PASSWORD = "correct horse battery"
NOW = datetime.now(timezone.utc)


def _register(client, username="ada"):
    client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
            "native_language": "en",
        },
    )
    tokens = client.post(
        "/auth/login", data={"username": username, "password": PASSWORD}
    ).json()
    return tokens, {"Authorization": f"Bearer {tokens['access_token']}"}


def _user_id(session: Session, username="ada") -> int:
    return session.exec(select(User).where(User.username == username)).first().id


# --- what must survive ------------------------------------------------------


def test_a_live_verification_link_survives_however_old_the_row_is(
    client, session: Session
):
    """Age is not the criterion -- usefulness is. An unused, in-date token
    is untouched even if the row predates the retention window, because
    someone can still click it."""
    _register(client)
    raw = generate_token()
    session.add(
        AuthToken(
            user_id=_user_id(session),
            token_hash=hash_token(raw),
            purpose="email_verification",
            expires_at=NOW + timedelta(hours=12),
            created_at=NOW - timedelta(days=400),
        )
    )
    session.commit()

    purge_expired(session)

    assert client.post("/auth/verify-email", json={"token": raw}).status_code == 200


def test_reuse_detection_still_fires_for_a_recently_revoked_refresh_token(
    client, session: Session, no_refresh_grace
):
    """The window that matters most. `/auth/refresh` treats a revoked
    token being presented as theft and kills every session for that user
    -- but that needs the row. Purge it and the replay merely answers
    "Invalid refresh token": still refused, silently, with no alarm."""
    tokens, _ = _register(client)
    rotated = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert rotated.status_code == 200

    purge_expired(session)

    replay = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401
    assert "invalidated" in replay.json()["detail"].lower(), (
        "the replay was refused as merely unknown rather than detected as reuse "
        "-- the revoked row was purged too early"
    )
    # And the alarm did what it exists to do: the sibling minted by the
    # rotation is dead too.
    still_live = client.post(
        "/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]}
    )
    assert still_live.status_code == 401


def test_a_quiz_session_you_could_still_retry_survives(client, session: Session):
    """Sessions are reusable on purpose -- "Try again" re-submits the same
    served set (models.QuizSession) -- so a purge must not turn a retry
    into "Invalid quiz session"."""
    _, headers = _register(client)
    quiz = client.get("/lessons/1/quiz", headers=headers).json()

    purge_expired(session)

    answers = {str(q["id"]): "whatever" for q in quiz["questions"]}
    resubmit = client.post(
        f"/quizzes/{quiz['id']}/submit",
        json={"session_id": quiz["session_id"], "answers": answers},
        headers=headers,
    )
    assert resubmit.status_code == 200


# --- what must go -----------------------------------------------------------


def test_spent_and_expired_links_are_removed_past_the_grace_window(
    client, session: Session
):
    _register(client)
    user_id = _user_id(session)
    old = NOW - AUTH_TOKEN_RETENTION - timedelta(days=1)
    session.add_all(
        [
            AuthToken(
                user_id=user_id,
                token_hash=hash_token(generate_token()),
                purpose="password_reset",
                expires_at=old,
                used_at=old,
            ),
            AuthToken(
                user_id=user_id,
                token_hash=hash_token(generate_token()),
                purpose="email_verification",
                expires_at=old,  # never used, but long expired
            ),
        ]
    )
    session.commit()
    before = len(session.exec(select(AuthToken)).all())

    removed = purge_expired(session)

    assert removed["auth_tokens"] == 2
    assert len(session.exec(select(AuthToken)).all()) == before - 2


def test_refresh_tokens_are_removed_only_well_past_expiry(client, session: Session):
    _register(client)
    user_id = _user_id(session)
    session.add_all(
        [
            RefreshToken(
                user_id=user_id,
                token_hash=hash_token(generate_token()),
                expires_at=NOW - REFRESH_TOKEN_RETENTION - timedelta(days=1),
                revoked_at=NOW - REFRESH_TOKEN_RETENTION,
                revoked_reason="rotated",
            ),
            RefreshToken(
                user_id=user_id,
                token_hash=hash_token(generate_token()),
                # Expired, but inside retention: reuse detection may still
                # need it.
                expires_at=NOW - timedelta(days=1),
                revoked_at=NOW - timedelta(days=1),
                revoked_reason="rotated",
            ),
        ]
    )
    session.commit()

    removed = purge_expired(session)

    assert removed["refresh_tokens"] == 1


def test_the_retention_window_outlives_a_refresh_token(client):
    """Stated as a relationship rather than a number, because the thing
    that breaks reuse detection is the two drifting apart -- raising
    REFRESH_TOKEN_EXPIRE_DAYS past the retention would do it silently."""
    assert REFRESH_TOKEN_RETENTION >= timedelta(
        days=settings.refresh_token_expire_days
    )


def test_stale_quiz_sessions_are_removed(client, session: Session):
    _, headers = _register(client)
    client.get("/lessons/1/quiz", headers=headers)

    for row in session.exec(select(QuizSession)).all():
        row.created_at = NOW - QUIZ_SESSION_RETENTION - timedelta(days=1)
        session.add(row)
    session.commit()

    removed = purge_expired(session)

    assert removed["quiz_sessions"] == 1
    assert session.exec(select(QuizSession)).all() == []


def test_purging_an_already_clean_database_removes_nothing(client, session: Session):
    _register(client)
    assert purge_expired(session) == {
        "auth_tokens": 0,
        "refresh_tokens": 0,
        "quiz_sessions": 0,
    }
