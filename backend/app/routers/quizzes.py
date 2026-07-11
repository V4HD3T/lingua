import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Quiz, QuizAttempt, QuizQuestion, User
from app.routers.auth import get_current_user
from app.schemas import QuizQuestionRead, QuizRead, QuizResult, QuizSubmission

router = APIRouter(tags=["quizzes"])


@router.get("/quizzes/{quiz_id}", response_model=QuizRead)
def get_quiz(quiz_id: int, session: Session = Depends(get_session)):
    quiz = session.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    questions = session.exec(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)).all()
    return QuizRead(
        id=quiz.id,
        title=quiz.title,
        quiz_type=quiz.quiz_type,
        questions=[
            QuizQuestionRead(
                id=q.id, question_text=q.question_text, options=json.loads(q.options_json)
            )
            for q in questions
        ],
    )


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

    correct_count = 0
    for question in questions:
        given = submission.answers.get(str(question.id))
        if given is not None and given.strip().lower() == question.correct_answer.strip().lower():
            correct_count += 1

    total = len(questions)
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

    return QuizResult(score=score, total_questions=total, correct_count=correct_count)
