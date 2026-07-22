from datetime import date, datetime
from typing import Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, EmailStr, Field


# Well past any real passphrase, including a long one from a password
# manager (v0.1.11). Not a bcrypt limit -- bcrypt_sha256 removed that --
# just a ceiling so an unbounded string can't be sent to be hashed.
MAX_PASSWORD_LENGTH = 256


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_LENGTH)
    native_language: str = "en"


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    native_language: str
    timezone: str = "UTC"
    daily_review_goal: int
    is_verified: bool
    is_admin: bool = False


class TimezoneUpdate(BaseModel):
    """An IANA zone name, e.g. "Europe/Istanbul" (v0.1.9). The frontend
    reports what the browser says; the endpoint validates it against the
    tz database rather than trusting it, since it's client-supplied and
    ends up deciding which day a learner's activity counts toward."""

    timezone: str = Field(min_length=1, max_length=64)


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=MAX_PASSWORD_LENGTH)


class EmailVerificationConfirm(BaseModel):
    token: str


class MessageResponse(BaseModel):
    message: str


class AchievementRead(BaseModel):
    code: str
    name: str
    description: str
    earned_at: datetime


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source_lang: str
    target_lang: str


class IdiomWarning(BaseModel):
    phrase: str
    note: str


class TranslateResponse(BaseModel):
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    confidence: float = 1.0
    alternatives: List[str] = []
    idiom_warnings: List[IdiomWarning] = []
    new_achievements: List[AchievementRead] = []


class LanguageRead(BaseModel):
    code: str
    name: str


class DetectLanguageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class DetectLanguageResponse(BaseModel):
    language_code: str
    confidence: float
    is_reliable: bool


class CourseRead(BaseModel):
    id: int
    language_code: str
    title: str
    level: str
    description: str


class LessonRead(BaseModel):
    id: int
    course_id: int
    title: str
    content: str
    order: int
    language_code: str
    grammar_note: str
    cultural_note: str


class VocabularyRead(BaseModel):
    id: int
    word: str
    translation: str
    example_sentence: str


class QuizQuestionRead(BaseModel):
    id: int
    question_type: str
    question_text: str
    options: List[str]
    audio_text: Optional[str] = None


class QuizRead(BaseModel):
    id: int
    title: str
    quiz_type: str
    language_code: str
    # v0.0.9: id of the QuizSession recording which questions were served
    # (None for anonymous requesters, who can't submit anyway).
    session_id: Optional[int] = None
    questions: List[QuizQuestionRead]


class QuizSubmission(BaseModel):
    # v0.0.9: the QuizSession id returned by the quiz GET -- grading happens
    # against that session's served-question set, not against whatever
    # subset the client chose to answer.
    session_id: int
    answers: Dict[str, str]  # {question_id (str): given_answer}


class QuizResult(BaseModel):
    score: float
    total_questions: int
    correct_count: int
    new_achievements: List[AchievementRead] = []


class CourseProgress(BaseModel):
    course_id: int
    course_title: str
    total_lessons: int
    completed_lessons: int
    completion_percentage: float


class UserStats(BaseModel):
    current_streak: int
    longest_streak: int
    total_translations: int
    total_quiz_attempts: int
    average_quiz_score: float
    courses: List[CourseProgress]
    daily_goal: int
    reviews_today: int


class ReviewQueueItem(BaseModel):
    vocabulary_item_id: int
    word: str
    translation: str
    example_sentence: str
    lesson_id: int
    language_code: str
    is_new: bool


class ReviewSubmission(BaseModel):
    quality: int = Field(ge=0, le=5)


class ReviewResult(BaseModel):
    vocabulary_item_id: int
    repetitions: int
    ease_factor: float
    interval_days: int
    next_review_date: date
    new_achievements: List[AchievementRead] = []


class VocabularySuggestionRead(BaseModel):
    vocabulary_item_id: int
    word: str
    translation: str
    lesson_id: int
    frequency: int


class DailyGoalUpdate(BaseModel):
    daily_goal: int = Field(ge=1, le=200)


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Pagination envelope shared by list endpoints (v0.0.8).

    `total` is the full matching-row count (ignoring limit/offset), so a
    client can render "showing X of Y" and knows whether another page
    exists without issuing a second request. `limit` is capped at the
    endpoints themselves via Query(..., ge=1, le=100).
    """

    items: List[T]
    total: int
    limit: int
    offset: int


# --- Admin content-management schemas (v0.0.9) ---


class CourseCreate(BaseModel):
    language_code: str
    title: str
    level: str
    description: str = ""


class CourseUpdate(BaseModel):
    language_code: Optional[str] = None
    title: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None


class LessonCreate(BaseModel):
    title: str
    content: str = ""
    order: int = 0
    grammar_note: str = ""
    cultural_note: str = ""


class LessonUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    order: Optional[int] = None
    grammar_note: Optional[str] = None
    cultural_note: Optional[str] = None


class VocabularyCreate(BaseModel):
    word: str
    translation: str
    example_sentence: str = ""


class VocabularyUpdate(BaseModel):
    word: Optional[str] = None
    translation: Optional[str] = None
    example_sentence: Optional[str] = None


class QuizCreate(BaseModel):
    title: str
    quiz_type: str = "multiple_choice"


class QuizUpdate(BaseModel):
    title: Optional[str] = None
    quiz_type: Optional[str] = None


class AdminQuizRead(BaseModel):
    id: int
    lesson_id: int
    title: str
    quiz_type: str


class QuizQuestionCreate(BaseModel):
    question_type: str = "multiple_choice"
    question_text: str
    correct_answer: str
    options: List[str] = []
    audio_text: Optional[str] = None
    difficulty: int = Field(default=1, ge=1, le=3)


class QuizQuestionUpdate(BaseModel):
    question_type: Optional[str] = None
    question_text: Optional[str] = None
    correct_answer: Optional[str] = None
    options: Optional[List[str]] = None
    audio_text: Optional[str] = None
    difficulty: Optional[int] = Field(default=None, ge=1, le=3)


class AdminQuizQuestionRead(BaseModel):
    """Admin view of a question -- includes the correct answer and
    difficulty, which the learner-facing QuizQuestionRead deliberately
    omits."""

    id: int
    question_type: str
    question_text: str
    correct_answer: str
    options: List[str]
    audio_text: Optional[str] = None
    difficulty: int
