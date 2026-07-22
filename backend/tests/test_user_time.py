"""Whose day is it (v0.1.9).

The bug: every timestamp is stored in UTC, correctly -- but the app also
*asked what day it was* in UTC. A day isn't a physical quantity; it starts
and ends where the person is. In UTC+3 the day rolled at 03:00 local, so a
session at 01:00 counted as yesterday. In UTC-5 it rolled at 19:00, so an
evening review counted as tomorrow and the review queue compared against a
date the learner hadn't reached.

CI never saw it: GitHub runners are UTC, where the two agree by
construction. It surfaced on a developer machine in UTC+3 after local
midnight, which is also why the streak unit tests -- written with
date.today(), the *local* date -- had been asserting that UTC and local
were the same day all along.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlmodel import Session

from app.models import QuizAttempt, TranslationHistory, User
from app.services.streaks import get_activity_dates
from app.services.user_time import (
    is_valid_timezone,
    local_date,
    resolve_zone,
    today_in,
)

ISTANBUL = resolve_zone("Europe/Istanbul")  # UTC+3, no DST
NEW_YORK = resolve_zone("America/New_York")  # UTC-5/-4
UTC_ZONE = resolve_zone("UTC")


# --- the conversion itself ---------------------------------------------------


def test_late_utc_evening_is_already_tomorrow_east_of_utc():
    # 22:30 UTC is 01:30 the next day in Istanbul. Counting this as the
    # UTC date credited the learner's session to the day before.
    moment = datetime(2026, 3, 14, 22, 30, tzinfo=timezone.utc)
    assert local_date(moment, UTC_ZONE) == date(2026, 3, 14)
    assert local_date(moment, ISTANBUL) == date(2026, 3, 15)


def test_early_utc_morning_is_still_yesterday_west_of_utc():
    # 02:00 UTC is 22:00 the previous day in New York -- the direction that
    # credited an evening review to *tomorrow*.
    moment = datetime(2026, 1, 14, 2, 0, tzinfo=timezone.utc)
    assert local_date(moment, UTC_ZONE) == date(2026, 1, 14)
    assert local_date(moment, NEW_YORK) == date(2026, 1, 13)


def test_naive_timestamps_are_read_as_utc():
    # SQLite hands datetimes back without tzinfo, though every one this app
    # writes was created with datetime.now(timezone.utc).
    naive = datetime(2026, 3, 14, 22, 30)
    aware = datetime(2026, 3, 14, 22, 30, tzinfo=timezone.utc)
    assert local_date(naive, ISTANBUL) == local_date(aware, ISTANBUL)


def test_two_sessions_one_local_day_are_one_day():
    # 01:00 and 23:00 on the same Istanbul day are 22:00 and 20:00 UTC on
    # *different* UTC days -- which used to inflate a streak by counting
    # one day of study as two.
    first = datetime(2026, 3, 14, 22, 0, tzinfo=timezone.utc)   # 01:00 local, Mar 15
    second = datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc)  # 23:00 local, Mar 15
    assert local_date(first, UTC_ZONE) != local_date(second, UTC_ZONE)
    assert local_date(first, ISTANBUL) == local_date(second, ISTANBUL)


def test_today_in_a_zone_tracks_that_zone():
    now = datetime.now(timezone.utc)
    assert today_in(UTC_ZONE) == now.date()
    assert today_in(ISTANBUL) == now.astimezone(ISTANBUL).date()
    # And the two genuinely differ for part of every day.
    assert abs((today_in(ISTANBUL) - today_in(NEW_YORK)).days) <= 1


def test_dst_transition_still_yields_one_calendar_day():
    # New York springs forward on 2026-03-08; that day is 23 hours long.
    # Every instant in it must still map to the 8th.
    for hour in (5, 7, 12, 23):
        moment = datetime(2026, 3, 8, hour, 0, tzinfo=timezone.utc)
        assert local_date(moment, NEW_YORK).month == 3


# --- resolving the stored name -----------------------------------------------


def test_valid_zone_names_are_accepted():
    assert is_valid_timezone("Europe/Istanbul")
    assert is_valid_timezone("America/New_York")
    assert is_valid_timezone("UTC")


def test_invalid_zone_names_are_rejected():
    for name in ("Middle/Earth", "not a zone", "UTC+3", "", "../../etc/passwd"):
        assert not is_valid_timezone(name)


@pytest.mark.parametrize("stored", [None, "", "Middle/Earth", "UTC+3"])
def test_unresolvable_stored_zone_falls_back_to_utc(stored):
    """resolve_zone is total on purpose: a row written before the column
    was validated -- or naming a zone a later tzdata release dropped --
    must degrade to the old UTC behaviour, not 500 every stats request."""
    moment = datetime(2026, 3, 14, 22, 30, tzinfo=timezone.utc)
    assert local_date(moment, resolve_zone(stored)) == date(2026, 3, 14)


# --- through the query that feeds streaks ------------------------------------


def _user_with_zone(session: Session, zone_name: str) -> User:
    user = User(
        username=f"user-{zone_name}",
        email=f"{zone_name.replace('/', '-')}@example.com",
        hashed_password="x",
        timezone=zone_name,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_activity_dates_are_counted_in_the_learners_zone(session):
    """The end of the chain that produces a streak: two sessions on one
    Istanbul day must be one activity date, not two."""
    user = _user_with_zone(session, "Europe/Istanbul")
    for moment in (
        datetime(2026, 3, 14, 22, 0, tzinfo=timezone.utc),   # 01:00 local Mar 15
        datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc),   # 23:00 local Mar 15
    ):
        session.add(
            TranslationHistory(
                user_id=user.id,
                source_text="hola",
                source_lang="es",
                target_text="hello",
                target_lang="en",
                created_at=moment,
            )
        )
    session.commit()

    assert get_activity_dates(user.id, session, ISTANBUL) == {date(2026, 3, 15)}
    # Counted in UTC -- the old behaviour -- the same study looks like two
    # separate days, which is a streak the learner did not earn.
    assert get_activity_dates(user.id, session, UTC_ZONE) == {
        date(2026, 3, 14),
        date(2026, 3, 15),
    }


def test_quiz_attempts_are_converted_too(session):
    user = _user_with_zone(session, "America/New_York")
    session.add(
        QuizAttempt(
            user_id=user.id,
            quiz_id=1,
            score=100.0,
            total_questions=1,
            completed_at=datetime(2026, 1, 14, 2, 0, tzinfo=timezone.utc),  # 21:00 Jan 13
        )
    )
    session.commit()

    assert get_activity_dates(user.id, session, NEW_YORK) == {date(2026, 1, 13)}


def test_streak_survives_studying_late_east_of_utc(session):
    """The user-visible symptom, at the level that produced it: studying at
    01:00 local on three consecutive Istanbul days is a 3-day streak. Read
    in UTC those instants fall on three days too -- but shifted back one,
    so 'today' never matched and the streak read as broken."""
    user = _user_with_zone(session, "Europe/Istanbul")
    local_days = [date(2026, 3, 13), date(2026, 3, 14), date(2026, 3, 15)]
    for day in local_days:
        # 01:00 local == 22:00 UTC the previous day
        session.add(
            TranslationHistory(
                user_id=user.id,
                source_text="hola",
                source_lang="es",
                target_text="hello",
                target_lang="en",
                created_at=datetime.combine(day - timedelta(days=1), datetime.min.time())
                .replace(hour=22, tzinfo=timezone.utc),
            )
        )
    session.commit()

    assert get_activity_dates(user.id, session, ISTANBUL) == set(local_days)
