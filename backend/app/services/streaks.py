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

from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import QuizAttempt, TranslationHistory


def get_activity_dates(user_id: int, session: Session) -> set[date]:
    translation_times = session.exec(
        select(TranslationHistory.created_at).where(TranslationHistory.user_id == user_id)
    ).all()
    quiz_times = session.exec(
        select(QuizAttempt.completed_at).where(QuizAttempt.user_id == user_id)
    ).all()
    return {t.date() for t in translation_times} | {t.date() for t in quiz_times}


def compute_streaks(activity_dates: set[date]) -> tuple[int, int]:
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

    today = datetime.now(timezone.utc).date()
    current_streak = 0
    if sorted_dates[-1] in (today, today - timedelta(days=1)):
        current_streak = 1
        for i in range(len(sorted_dates) - 1, 0, -1):
            if sorted_dates[i] - sorted_dates[i - 1] == timedelta(days=1):
                current_streak += 1
            else:
                break

    return current_streak, longest
