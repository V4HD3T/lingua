import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.config import settings
from app.database import engine, init_db
from app.middleware import SecurityHeadersMiddleware
from app.models import Course, Language, Lesson, Quiz, QuizQuestion, VocabularyItem
from app.routers import achievements, auth, courses, quizzes, review, stats, suggestions, translate
from app.services.security_logging import log_event


def seed_data(session: Session) -> None:
    """Adds sample language, course, lesson, and quiz data on first run
    (idempotent).

    Takes a Session as a parameter (doesn't open its own); this way tests
    can also call the same function against their own isolated test
    databases.
    """
    if session.exec(select(Language)).first():
        return  # database is already populated

    session.add_all(
        [
            Language(code="en", name="English"),
            Language(code="es", name="Español"),
            Language(code="tr", name="Türkçe"),
            Language(code="de", name="Deutsch"),
            Language(code="fr", name="Français"),
        ]
    )

    course = Course(
        language_code="es",
        title="Spanish for Beginners",
        level="A1",
        description="Everyday vocabulary and phrases for getting started in Spanish.",
    )
    session.add(course)
    session.commit()
    session.refresh(course)

    lesson = Lesson(
        course_id=course.id,
        title="Greetings",
        order=1,
        grammar_note=(
            "Spanish greetings don't conjugate by formality the way some other "
            "phrases do, but 'tú' (informal you) vs 'usted' (formal you) will "
            "matter a lot once you get past hello/goodbye — 'hola' and 'adiós' "
            "are safe in both registers."
        ),
        cultural_note=(
            "In much of the Spanish-speaking world, greetings between friends "
            "often come with a single cheek kiss (two in Spain) rather than a "
            "handshake — context and region vary, but don't be surprised by it."
        ),
    )
    session.add(lesson)
    session.commit()
    session.refresh(lesson)

    session.add_all(
        [
            VocabularyItem(
                lesson_id=lesson.id,
                word="hola",
                translation="hello",
                example_sentence="¡Hola! ¿Cómo estás?",
            ),
            VocabularyItem(
                lesson_id=lesson.id,
                word="adiós",
                translation="goodbye",
                example_sentence="Adiós, ¡hasta pronto!",
            ),
        ]
    )

    quiz = Quiz(lesson_id=lesson.id, title="Greetings Quiz", quiz_type="multiple_choice")
    session.add(quiz)
    session.commit()
    session.refresh(quiz)

    session.add_all(
        [
            QuizQuestion(
                quiz_id=quiz.id,
                question_type="multiple_choice",
                question_text="What is the English translation of 'hola'?",
                correct_answer="hello",
                options_json=json.dumps(["hello", "goodbye", "thank you", "please"]),
                difficulty=1,
            ),
            QuizQuestion(
                quiz_id=quiz.id,
                question_type="multiple_choice",
                question_text="What is the English translation of 'adiós'?",
                correct_answer="goodbye",
                options_json=json.dumps(["hello", "goodbye", "please", "sorry"]),
                difficulty=1,
            ),
            QuizQuestion(
                quiz_id=quiz.id,
                question_type="fill_blank",
                question_text="Complete the greeting: \"___, ¿Cómo estás?\"",
                correct_answer="hola",
                options_json=json.dumps([]),
                difficulty=2,
            ),
            QuizQuestion(
                quiz_id=quiz.id,
                question_type="listening",
                question_text="What word did you hear?",
                correct_answer="hola",
                options_json=json.dumps(["hola", "adiós", "gracias", "por favor"]),
                audio_text="hola",
                difficulty=2,
            ),
            QuizQuestion(
                quiz_id=quiz.id,
                question_type="sentence_order",
                question_text="Put the words in order to form a greeting.",
                correct_answer="hola como estas",
                options_json=json.dumps(["como", "estas", "hola"]),
                difficulty=3,
            ),
        ]
    )
    session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.secret_key == "change-this-for-development":
        log_event(
            "insecure_default_secret_key",
            message="SECRET_KEY is still the development default -- set a real secret before deploying.",
        )
    init_db()
    with Session(engine) as session:
        seed_data(session)
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.add_middleware(SecurityHeadersMiddleware)
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
app.include_router(stats.router)
app.include_router(review.router)
app.include_router(suggestions.router)
app.include_router(achievements.router)


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
