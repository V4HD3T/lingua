"""
Achievement badges: gamification beyond the daily streak (e.g. "first
quiz", "100 translations"). A small, static catalogue defined in code --
badges aren't user-generated content, so there's no need for a database
table of badge *definitions*, only of who has *earned* which one
(app.models.Achievement).

check_and_award() is called at the end of the actions that could unlock a
badge (translate, quiz submit, review submit) and is deliberately cheap:
a handful of count queries, then a plain Python comparison against each
badge's threshold. It only ever adds new Achievement rows, never removes
them, and re-checking an already-earned badge is a harmless no-op.
"""

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import Achievement, QuizAttempt, TranslationHistory, VocabularyProgress
from app.services.streaks import compute_streaks, get_activity_dates


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


def _earned_codes_now(user_id: int, session: Session) -> set[str]:
    translation_count = len(
        session.exec(
            select(TranslationHistory.id).where(TranslationHistory.user_id == user_id)
        ).all()
    )
    quiz_attempts = session.exec(
        select(QuizAttempt).where(QuizAttempt.user_id == user_id)
    ).all()
    started_words = len(
        session.exec(
            select(VocabularyProgress.id).where(VocabularyProgress.user_id == user_id)
        ).all()
    )
    current_streak, _ = compute_streaks(get_activity_dates(user_id, session))

    earned = set()
    if translation_count >= 1:
        earned.add("first_translation")
    if translation_count >= 10:
        earned.add("ten_translations")
    if translation_count >= 100:
        earned.add("hundred_translations")
    if quiz_attempts:
        earned.add("first_quiz")
    if any(a.score == 100.0 for a in quiz_attempts):
        earned.add("perfect_quiz")
    if started_words >= 5:
        earned.add("five_words_started")
    if current_streak >= 3:
        earned.add("three_day_streak")
    if current_streak >= 7:
        earned.add("week_streak")
    return earned


def check_and_award(
    user_id: int, session: Session
) -> list[tuple[Achievement, AchievementDefinition]]:
    """Checks every badge's criteria against the user's current activity
    and awards any newly-met ones. Returns just the newly-awarded badges,
    paired with their real earned_at timestamp (empty list if nothing new)."""
    already_earned = {
        a.code
        for a in session.exec(select(Achievement).where(Achievement.user_id == user_id)).all()
    }

    newly_earned_codes = _earned_codes_now(user_id, session) - already_earned
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
