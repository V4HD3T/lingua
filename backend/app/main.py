import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.config import settings
from app.database import engine, init_db
from app.models import Course, Language, Lesson, Quiz, QuizQuestion, VocabularyItem
from app.routers import auth, courses, quizzes, translate


def seed_data(session: Session) -> None:
    """Adds sample language, course, lesson, and quiz data on first run (idempotent).

    Takes the session as a parameter (doesn't open its own session); this way
    tests can also call the same function against their own isolated test
    databases.
    """
    if session.exec(select(Language)).first():
        return  # database is already populated

    session.add_all(
        [
            Language(code="tr", name="Türkçe"),
            Language(code="en", name="English"),
            Language(code="de", name="Deutsch"),
            Language(code="fr", name="Français"),
            Language(code="es", name="Español"),
        ]
    )

    course = Course(
        language_code="en",
        title="English for Beginners",
        level="A1",
        description="Basic vocabulary and phrases commonly used in daily life.",
    )
    session.add(course)
    session.commit()
    session.refresh(course)

    lesson = Lesson(course_id=course.id, title="Greetings", order=1)
    session.add(lesson)
    session.commit()
    session.refresh(lesson)

    session.add_all(
        [
            VocabularyItem(
                lesson_id=lesson.id,
                word="hello",
                translation="merhaba",
                example_sentence="Hello, how are you?",
            ),
            VocabularyItem(
                lesson_id=lesson.id,
                word="goodbye",
                translation="hoşça kal",
                example_sentence="Goodbye, see you soon!",
            ),
        ]
    )

    quiz = Quiz(lesson_id=lesson.id, title="Greetings Quiz", quiz_type="multiple_choice")
    session.add(quiz)
    session.commit()
    session.refresh(quiz)

    session.add(
        QuizQuestion(
            quiz_id=quiz.id,
            question_text="What is the Turkish equivalent of the word 'hello'?",
            correct_answer="merhaba",
            options_json=json.dumps(["merhaba", "hoşça kal", "teşekkürler", "lütfen"]),
        )
    )
    session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        seed_data(session)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for development; restrict to specific origins in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(translate.router)
app.include_router(courses.router)
app.include_router(quizzes.router)


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "app": settings.app_name}
