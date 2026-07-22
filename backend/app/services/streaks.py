"""
Daily streak computation, shared by app/routers/stats.py (displaying it)
and app/services/achievements.py (awarding streak-based badges).

Moved out to its own module rather than living in the stats router, since
it's genuine business logic used from more than one place -- importing a
"private" underscore-prefixed function from another router module is a
minor architecture smell worth avoiding once there's a second caller.

Rather than keeping a separate "streak counter" table, the streak is
computed directly from the dates on existing TranslationHistory and
QuizAttempt records. This removes any risk of the counter drifting out of
sync with real activity (e.g. if a record is deleted, the counter is still
automatically correct) — the cost is a light computation on every request,
which is negligible at this scale.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.models import QuizAttempt, TranslationHistory
from app.services.user_time import local_date


def get_activity_dates(user_id: int, session: Session, zone: ZoneInfo) -> set[date]:
    """Which calendar days this learner was active on, counted in their own
    zone (v0.1.9). Timestamps are stored in UTC; the day they belong to is
    a question about where the learner is -- see app/services/user_time.py.
    """
    translation_times = session.exec(
        select(TranslationHistory.created_at).where(TranslationHistory.user_id == user_id)
    ).all()
    quiz_times = session.exec(
        select(QuizAttempt.completed_at).where(QuizAttempt.user_id == user_id)
    ).all()
    return {local_date(t, zone) for t in translation_times} | {
        local_date(t, zone) for t in quiz_times
    }


def compute_streaks(activity_dates: set[date], today: date) -> tuple[int, int]:
    """`today` is passed in rather than read from the clock (v0.1.9): only
    the caller knows whose day it is. This also makes the function total --
    same inputs, same answer -- so its tests no longer depend on the
    machine's timezone, which is precisely how the bug this fixes stayed
    invisible (CI runs in UTC, where the two agree)."""
    if not activity_dates:
        return 0, 0

    sorted_dates = sorted(activity_dates)

    longest = 1
    current_run = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i - 1] + timedelta(days=1):
            current_run += 1
        else:
            current_run = 1
        longest = max(longest, current_run)

    current_streak = 0
    if sorted_dates[-1] in (today, today - timedelta(days=1)):
        current_streak = 1
        for i in range(len(sorted_dates) - 1, 0, -1):
            if sorted_dates[i] - sorted_dates[i - 1] == timedelta(days=1):
                current_streak += 1
            else:
                break

    return current_streak, longest
