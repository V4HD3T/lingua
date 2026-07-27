"""The per-request work must not scale with how long someone has used the
app (v0.1.19).

`check_and_award` runs at the end of every translation, quiz submission
and review. It used to count by fetching every matching row into Python
and measuring the list, and to recompute the streak from every timestamp
the account had ever produced. Both grow forever; the hot path grew with
them.
"""

import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, select

from app.models import Achievement, TranslationHistory, User
from app.services.rate_limiter import api_rate_limiter, translate_rate_limiter

PASSWORD = "correct horse battery"
LOADED_HISTORY = 20_000


@pytest.fixture
def learner(client, session: Session):
    client.post(
        "/auth/register",
        json={
            "username": "ada",
            "email": "ada@example.com",
            "password": PASSWORD,
            "native_language": "en",
        },
    )
    tokens = client.post(
        "/auth/login", data={"username": "ada", "password": PASSWORD}
    ).json()
    user = session.exec(select(User).where(User.username == "ada")).first()
    return user, {"Authorization": f"Bearer {tokens['access_token']}"}


def _load_history(session: Session, user_id: int, count: int = LOADED_HISTORY):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            TranslationHistory(
                user_id=user_id,
                source_text="hello there friend",
                source_lang="en",
                target_text="[en->es] hello there friend",
                target_lang="es",
                created_at=now - timedelta(minutes=i),
            )
            for i in range(count)
        ]
    )
    session.commit()


def _fastest(call, samples=5):
    best = float("inf")
    for _ in range(samples):
        api_rate_limiter.clear_all()
        translate_rate_limiter.clear_all()
        started = time.perf_counter()
        response = call()
        best = min(best, time.perf_counter() - started)
        assert response.status_code == 200, response.text
    return best


def test_translate_does_not_slow_down_as_history_grows(client, session: Session, learner):
    user, headers = learner

    def translate():
        return client.post(
            "/translate",
            json={"text": "hello there", "source_lang": "en", "target_lang": "es"},
            headers=headers,
        )

    empty = _fastest(translate)
    _load_history(session, user.id)
    loaded = _fastest(translate)

    # Before v0.1.19 this ratio was 11x. The assertion is loose because it
    # is guarding an order of magnitude, not a benchmark: the failure this
    # catches is the return of work proportional to history, which shows
    # up as multiples, not percentages.
    assert loaded <= empty * 3, (
        f"/translate went from {empty * 1000:.1f} ms to {loaded * 1000:.1f} ms "
        f"({loaded / empty:.1f}x) after {LOADED_HISTORY} history rows"
    )


def test_stats_stays_under_a_ceiling_as_history_grows(client, session: Session, learner):
    """/users/me/stats is deliberately *not* asserted to be flat.

    It still reads every activity timestamp the learner has, because the
    streak is computed from real activity rather than kept in a counter
    that could drift out of sync with it -- a design choice
    ARCHITECTURE.md makes on purpose and this change does not revisit.
    The counting around it no longer materialises rows, which took the
    endpoint from 15x to ~9x at 20k records.

    So the guard is an absolute ceiling rather than a ratio: it catches
    counting going back to fetching rows (which is what pushed this past
    60 ms before) without claiming a flatness the design doesn't offer.
    """
    user, headers = learner
    _load_history(session, user.id)

    elapsed = _fastest(lambda: client.get("/users/me/stats", headers=headers))
    assert elapsed < 0.15, (
        f"/users/me/stats took {elapsed * 1000:.0f} ms over {LOADED_HISTORY} "
        "history rows"
    )


def test_a_learner_holding_every_badge_stops_paying_for_the_checks(
    client, session: Session, learner
):
    """The mechanism behind most of the saving: badges are permanent, so a
    criterion for one already held cannot change the answer and is not
    evaluated. A fully-decorated account is the cheapest, not the most
    expensive."""
    user, headers = learner
    _load_history(session, user.id)

    def translate():
        return client.post(
            "/translate",
            json={"text": "hello there", "source_lang": "en", "target_lang": "es"},
            headers=headers,
        )

    partial = _fastest(translate)

    from app.services.achievements import ACHIEVEMENT_CATALOGUE

    held = {a.code for a in session.exec(select(Achievement)).all()}
    session.add_all(
        [
            Achievement(user_id=user.id, code=badge.code)
            for badge in ACHIEVEMENT_CATALOGUE
            if badge.code not in held
        ]
    )
    session.commit()

    complete = _fastest(translate)
    assert complete <= partial, (
        f"holding every badge cost {complete * 1000:.1f} ms against "
        f"{partial * 1000:.1f} ms with some still unearned -- the earned "
        "ones are still being re-checked"
    )


def test_suggestions_read_a_bounded_slice_of_history(client, session: Session, learner):
    """Word-frequency over the whole history was 230 ms at 20k records --
    and dominated by whatever the learner was working on a year ago, which
    is the opposite of what this feature is for."""
    user, headers = learner
    _load_history(session, user.id)

    elapsed = _fastest(
        lambda: client.get("/users/me/vocabulary-suggestions", headers=headers)
    )
    assert elapsed < 0.15, f"took {elapsed * 1000:.0f} ms over {LOADED_HISTORY} records"
