import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Course, Lesson, Quiz, QuizAttempt, QuizQuestion, User
from app.routers.auth import get_current_user, get_current_user_optional
from app.schemas import AchievementRead, QuizQuestionRead, QuizRead, QuizResult, QuizSubmission
from app.services.achievements import check_and_award

router = APIRouter(tags=["quizzes"])

# Adaptive difficulty thresholds: comfortably-scoring learners see harder
# questions; struggling learners see easier ones. Deliberately simple and
# explainable rather than a trained model -- see ARCHITECTURE.md / CHANGELOG.md.
ADAPTIVE_HIGH_SCORE_THRESHOLD = 80.0
ADAPTIVE_LOW_SCORE_THRESHOLD = 50.0


def _question_to_read(q: QuizQuestion) -> QuizQuestionRead:
    return QuizQuestionRead(
        id=q.id,
        question_type=q.question_type,
        question_text=q.question_text,
        options=json.loads(q.options_json),
        audio_text=q.audio_text,
    )


def _select_adaptive_questions(
    questions: List[QuizQuestion], user_avg_score: Optional[float]
) -> List[QuizQuestion]:
    """Biases which questions are served toward the learner's recent
    performance. `user_avg_score` is None for anonymous users or users
    with no quiz history yet -- in that case everything is shown,
    unfiltered, so this only ever kicks in once there's a real signal."""
    if user_avg_score is None:
        return questions

    if user_avg_score >= ADAPTIVE_HIGH_SCORE_THRESHOLD:
        target_difficulties = {2, 3}
    elif user_avg_score < ADAPTIVE_LOW_SCORE_THRESHOLD:
        target_difficulties = {1, 2}
    else:
        return questions

    filtered = [q for q in questions if q.difficulty in target_difficulties]
    return filtered if filtered else questions  # never return an empty quiz


def _user_average_score(user_id: int, session: Session) -> Optional[float]:
    attempts = session.exec(select(QuizAttempt).where(QuizAttempt.user_id == user_id)).all()
    if not attempts:
        return None
    return sum(a.score for a in attempts) / len(attempts)


def _build_quiz_read(
    quiz: Quiz, session: Session, user_avg_score: Optional[float] = None
) -> QuizRead:
    questions = session.exec(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)).all()
    questions = _select_adaptive_questions(questions, user_avg_score)

    lesson = session.get(Lesson, quiz.lesson_id)
    course = session.get(Course, lesson.course_id) if lesson else None

    return QuizRead(
        id=quiz.id,
        title=quiz.title,
        quiz_type=quiz.quiz_type,
        language_code=course.language_code if course else "",
        questions=[_question_to_read(q) for q in questions],
    )


@router.get("/quizzes/{quiz_id}", response_model=QuizRead)
def get_quiz(
    quiz_id: int,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    quiz = session.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    avg_score = _user_average_score(current_user.id, session) if current_user else None
    return _build_quiz_read(quiz, session, avg_score)


@router.get("/lessons/{lesson_id}/quiz", response_model=QuizRead)
def get_quiz_by_lesson(
    lesson_id: int,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Returns the quiz for a lesson. Added so the frontend can jump from a
    lesson page straight to its quiz without needing to know the quiz ID
    ahead of time. If the requester is logged in and has quiz history, the
    question selection adapts to their recent average score."""
    quiz = session.exec(select(Quiz).where(Quiz.lesson_id == lesson_id)).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="No quiz found for this lesson")
    avg_score = _user_average_score(current_user.id, session) if current_user else None
    return _build_quiz_read(quiz, session, avg_score)


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizResult)
def submit_quiz(
    quiz_id: int,
    submission: QuizSubmission,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    questions = session.exec(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)).all()
    if not questions:
        raise HTTPException(status_code=404, detail="Quiz not found")
    questions_by_id = {q.id: q for q in questions}

    # Score against what was actually submitted, not every question that
    # exists in the quiz -- adaptive selection (see _select_adaptive_questions
    # above) may only have shown the learner a subset, and grading against
    # questions they were never shown would unfairly tank their score.
    correct_count = 0
    total = len(submission.answers)
    for question_id_str, given in submission.answers.items():
        question = questions_by_id.get(int(question_id_str)) if question_id_str.isdigit() else None
        if question and given.strip().lower() == question.correct_answer.strip().lower():
            correct_count += 1

    score = round((correct_count / total) * 100, 2) if total else 0.0

    session.add(
        QuizAttempt(
            user_id=current_user.id,
            quiz_id=quiz_id,
            score=score,
            total_questions=total,
        )
    )
    session.commit()

    new_achievements = check_and_award(current_user.id, session)

    return QuizResult(
        score=score,
        total_questions=total,
        correct_count=correct_count,
        new_achievements=[
            AchievementRead(code=a.code, name=d.name, description=d.description, earned_at=a.earned_at)
            for a, d in new_achievements
        ],
    )
