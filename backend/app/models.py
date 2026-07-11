from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    native_language: str = "tr"
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
    question_text: str
    correct_answer: str
    options_json: str = "[]"  # JSON-encoded list of options


class QuizAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    quiz_id: int = Field(foreign_key="quiz.id")
    score: float
    total_questions: int
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
