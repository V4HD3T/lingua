from typing import Dict, List

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)
    native_language: str = "tr"


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


class TranslateResponse(BaseModel):
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str


class LanguageRead(BaseModel):
    code: str
    name: str


class CourseRead(BaseModel):
    id: int
    language_code: str
    title: str
    level: str
    description: str


class LessonRead(BaseModel):
    id: int
    title: str
    content: str
    order: int


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
