from datetime import date
from typing import Dict, List

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)
    native_language: str = "en"


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    native_language: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


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


class VocabularyRead(BaseModel):
    id: int
    word: str
    translation: str
    example_sentence: str


class QuizQuestionRead(BaseModel):
    id: int
    question_text: str
    options: List[str]


class QuizRead(BaseModel):
    id: int
    title: str
    quiz_type: str
    questions: List[QuizQuestionRead]


class QuizSubmission(BaseModel):
    answers: Dict[str, str]  # {question_id (str): given_answer}


class QuizResult(BaseModel):
    score: float
    total_questions: int
    correct_count: int


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


class VocabularySuggestionRead(BaseModel):
    vocabulary_item_id: int
    word: str
    translation: str
    lesson_id: int
    frequency: int
