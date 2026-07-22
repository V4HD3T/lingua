from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    native_language: str = "en"
    daily_review_goal: int = 10
    is_verified: bool = False
    # Admin flag is never settable through the public API (UserCreate has no
    # such field -- no mass assignment); promotion happens via
    # scripts/make_admin.py against the database directly.
    is_admin: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Language(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)  # e.g.: "en", "tr", "de"
    name: str


class TranslationHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    source_text: str
    source_lang: str
    target_text: str
    target_lang: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    language_code: str
    title: str
    level: str  # A1, A2, B1, B2, C1, C2
    description: str = ""


class Lesson(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id")
    title: str
    content: str = ""
    order: int = 0
    grammar_note: str = ""
    cultural_note: str = ""


class VocabularyItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lesson_id: int = Field(foreign_key="lesson.id")
    word: str
    translation: str
    example_sentence: str = ""


class Quiz(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lesson_id: int = Field(foreign_key="lesson.id")
    title: str
    quiz_type: str = "multiple_choice"  # multiple_choice, fill_blank, listening


class QuizQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quiz_id: int = Field(foreign_key="quiz.id")
    question_type: str = "multiple_choice"  # multiple_choice, fill_blank, listening, sentence_order
    question_text: str
    correct_answer: str
    options_json: str = "[]"  # JSON-encoded list of options (unused for fill_blank)
    audio_text: Optional[str] = None  # for "listening": text to speak; defaults to question_text
    difficulty: int = 1  # 1=easy, 2=medium, 3=hard -- used for adaptive question selection


class QuizAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    quiz_id: int = Field(foreign_key="quiz.id")
    score: float
    total_questions: int
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QuizSession(SQLModel, table=True):
    """Records exactly which questions were served to a logged-in user when
    they fetched a quiz (v0.0.9). Submissions are graded against this
    served set -- the fix for the v0.0.7-review finding that grading only
    the submitted answers let a client cherry-pick one known answer for a
    100% score and the perfect_quiz badge.

    Sessions are deliberately reusable: "Try again" re-submits the same
    served set, which is legitimate practice, not an exploit. Anonymous
    quiz views create no session (anonymous users can't submit anyway),
    and lesson pages probing for a quiz's existence create orphan sessions
    -- harmless small rows; a cleanup job is noted for later alongside
    expired-token cleanup."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    quiz_id: int = Field(foreign_key="quiz.id")
    question_ids_json: str  # JSON-encoded list of served QuizQuestion ids
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VocabularyProgress(SQLModel, table=True):
    """One row per (user, vocabulary word) — the word's current SM-2
    spaced-repetition schedule for that specific learner."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    vocabulary_item_id: int = Field(foreign_key="vocabularyitem.id")
    ease_factor: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    next_review_date: date = Field(default_factory=lambda: datetime.now(timezone.utc).date())
    last_reviewed_at: Optional[datetime] = None


class Achievement(SQLModel, table=True):
    """One row per (user, badge code) earned. Definitions and unlock
    criteria live in app/services/achievements.py, not in the database --
    the badge catalogue is small, static, and versioned with the code."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    code: str
    earned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RefreshToken(SQLModel, table=True):
    """A server-side-revocable long-lived token used only to mint new
    access tokens (see app/routers/auth.py: /auth/refresh). Only the
    SHA-256 hash of the token value is stored -- a database leak alone
    doesn't hand out usable tokens, since the raw value isn't recoverable
    from the hash."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    token_hash: str = Field(index=True, unique=True)
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    # Why this token was revoked (v0.1.8). Load-bearing, not diagnostic:
    # /auth/refresh forgives a token replayed moments after it was
    # "rotated" (two browser tabs racing), but must never forgive one
    # revoked by "logout", "logout_all", "password_reset", or
    # "reuse_detected" -- those have to take effect immediately. None on
    # rows written before v0.1.8, which are all long expired.
    revoked_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuthToken(SQLModel, table=True):
    """Single-use token for email verification and password reset links.
    One table, distinguished by `purpose`, since both are the same shape
    (hash a random value, expire it, mark it used once). Like
    RefreshToken, only the hash is stored, never the raw token."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    token_hash: str = Field(index=True, unique=True)
    purpose: str  # "email_verification" | "password_reset"
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
