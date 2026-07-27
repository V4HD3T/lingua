"""
Achievement badges: gamification beyond the daily streak (e.g. "first
quiz", "100 translations"). A small, static catalogue defined in code --
badges aren't user-generated content, so there's no need for a database
table of badge *definitions*, only of who has *earned* which one
(app.models.Achievement).

check_and_award() is called at the end of the actions that could unlock a
badge (translate, quiz submit, review submit). It only ever adds new
Achievement rows, never removes them.

It used to describe itself as "deliberately cheap: a handful of count
queries". It wasn't (v0.1.19). The counts were `len(session.exec(
select(X.id)).all())` -- every matching row fetched into Python so the
list could be measured -- and the streak criteria recomputed the whole
streak from every timestamp the learner had ever produced. On the hot
path, on every single translation. At 20k history rows that put
/translate at 60 ms against 5 ms, and it grows with the account.

Two changes, both of which lean on badges being permanent:

1. Counting happens in the database (COUNT(*), EXISTS), not by measuring
   a materialised list.
2. A criterion is only evaluated for a badge the learner does not
   already hold. A badge already earned cannot be un-earned, so its
   criterion cannot change the answer -- and after the first week of use
   most of them are earned, which is exactly when the history is large
   enough for the queries to matter. A learner holding every badge
   performs one query here, not five.
"""

from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Achievement, QuizAttempt, TranslationHistory, User, VocabularyProgress
from app.services.streaks import compute_streaks, get_activity_dates
from app.services.user_time import resolve_zone, today_in


@dataclass
class AchievementDefinition:
    code: str
    name: str
    description: str


ACHIEVEMENT_CATALOGUE: list[AchievementDefinition] = [
    AchievementDefinition("first_translation", "First Steps", "Made your first translation."),
    AchievementDefinition("ten_translations", "Chatty", "Made 10 translations."),
    AchievementDefinition("hundred_translations", "Polyglot in Training", "Made 100 translations."),
    AchievementDefinition("first_quiz", "Quiz Taker", "Completed your first quiz."),
    AchievementDefinition("perfect_quiz", "Perfectionist", "Scored 100% on a quiz."),
    AchievementDefinition("five_words_started", "Word Collector", "Started learning 5 words."),
    AchievementDefinition("three_day_streak", "Getting Consistent", "Reached a 3-day streak."),
    AchievementDefinition("week_streak", "Committed", "Reached a 7-day streak."),
]

_CATALOGUE_BY_CODE = {a.code: a for a in ACHIEVEMENT_CATALOGUE}
_ALL_CODES = frozenset(_CATALOGUE_BY_CODE)

# Grouped by the query each group needs, so a group whose badges are all
# already earned costs nothing at all.
_TRANSLATION_THRESHOLDS = {
    "first_translation": 1,
    "ten_translations": 10,
    "hundred_translations": 100,
}
_WORDS_STARTED_THRESHOLDS = {"five_words_started": 5}
_STREAK_THRESHOLDS = {"three_day_streak": 3, "week_streak": 7}


def _count(session: Session, column, *conditions) -> int:
    """COUNT(*) in the database instead of fetching every row to len() the
    list it comes back in."""
    return session.exec(select(func.count(column)).where(*conditions)).one()


def _exists(session: Session, column, *conditions) -> bool:
    """Whether any row matches. LIMIT 1, so "has this learner ever taken a
    quiz" doesn't read their entire attempt history to find out."""
    return session.exec(select(column).where(*conditions).limit(1)).first() is not None


def _newly_earned(user: User, session: Session, already_earned: set[str]) -> set[str]:
    """Which not-yet-held badges the learner now qualifies for.

    Takes `already_earned` so every criterion behind it can be skipped:
    badges are permanent, so a criterion for one already held cannot
    change the answer. See this module's docstring for why that matters
    on the hot path.
    """
    pending = _ALL_CODES - already_earned
    if not pending:
        return set()

    user_id = user.id
    earned: set[str] = set()

    if pending & _TRANSLATION_THRESHOLDS.keys():
        made = _count(session, TranslationHistory.id, TranslationHistory.user_id == user_id)
        earned |= {c for c, need in _TRANSLATION_THRESHOLDS.items() if made >= need}

    if pending & _WORDS_STARTED_THRESHOLDS.keys():
        started = _count(
            session, VocabularyProgress.id, VocabularyProgress.user_id == user_id
        )
        earned |= {c for c, need in _WORDS_STARTED_THRESHOLDS.items() if started >= need}

    if "first_quiz" in pending and _exists(
        session, QuizAttempt.id, QuizAttempt.user_id == user_id
    ):
        earned.add("first_quiz")

    if "perfect_quiz" in pending and _exists(
        session, QuizAttempt.id, QuizAttempt.user_id == user_id, QuizAttempt.score == 100.0
    ):
        earned.add("perfect_quiz")

    if pending & _STREAK_THRESHOLDS.keys():
        # Counted against the learner's own day, the same as the streak
        # they see on their progress page (v0.1.9) -- awarding a badge on
        # a different calendar than the one displayed would be its own
        # bug. This is the expensive criterion (it reads every activity
        # timestamp the account has), which is why skipping it once both
        # streak badges are held is the single biggest saving here.
        zone = resolve_zone(user.timezone)
        current_streak, _ = compute_streaks(
            get_activity_dates(user_id, session, zone), today_in(zone)
        )
        earned |= {c for c, need in _STREAK_THRESHOLDS.items() if current_streak >= need}

    return earned & pending


def check_and_award(
    user: User, session: Session
) -> list[tuple[Achievement, AchievementDefinition]]:
    """Checks every badge's criteria against the user's current activity
    and awards any newly-met ones. Returns just the newly-awarded badges,
    paired with their real earned_at timestamp (empty list if nothing new).

    Takes the User rather than an id as of v0.1.9: the streak badges need
    to know which timezone's calendar to count days on.
    """
    user_id = user.id
    already_earned = {
        a.code
        for a in session.exec(select(Achievement).where(Achievement.user_id == user_id)).all()
    }

    newly_earned_codes = _newly_earned(user, session, already_earned)
    if not newly_earned_codes:
        return []

    new_rows = [Achievement(user_id=user_id, code=code) for code in newly_earned_codes]
    for row in new_rows:
        session.add(row)
    session.commit()
    for row in new_rows:
        session.refresh(row)

    return [(row, _CATALOGUE_BY_CODE[row.code]) for row in new_rows]


def list_earned(user_id: int, session: Session) -> list[tuple[Achievement, AchievementDefinition]]:
    earned = session.exec(
        select(Achievement)
        .where(Achievement.user_id == user_id)
        .order_by(Achievement.earned_at.desc())
    ).all()
    return [(a, _CATALOGUE_BY_CODE[a.code]) for a in earned if a.code in _CATALOGUE_BY_CODE]
