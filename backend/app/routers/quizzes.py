import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Course, Lesson, Quiz, QuizAttempt, QuizQuestion, QuizSession, User
from app.routers.auth import get_current_user, get_current_user_optional
from app.schemas import AchievementRead, QuizQuestionRead, QuizRead, QuizResult, QuizSubmission
from app.services.achievements import check_and_award
from app.services.text_normalization import fold_case

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


def _build_quiz_read(quiz: Quiz, session: Session, current_user: Optional[User]) -> QuizRead:
    """Serves the (possibly adaptively filtered) questions for a quiz.

    v0.0.9: when the requester is logged in, the exact served set is
    recorded as a QuizSession and its id is returned -- submissions are
    graded against that set (see submit_quiz). This is what closed the
    v0.0.7-review finding that grading only the submitted answers let a
    client cherry-pick one known answer for a 100% score. Anonymous
    requesters get session_id None; they can't submit anyway."""
    questions = session.exec(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)).all()
    avg_score = _user_average_score(current_user.id, session) if current_user else None
    questions = _select_adaptive_questions(questions, avg_score)

    lesson = session.get(Lesson, quiz.lesson_id)
    course = session.get(Course, lesson.course_id) if lesson else None

    session_id: Optional[int] = None
    if current_user is not None:
        quiz_session = QuizSession(
            user_id=current_user.id,
            quiz_id=quiz.id,
            question_ids_json=json.dumps([q.id for q in questions]),
        )
        session.add(quiz_session)
        session.commit()
        session.refresh(quiz_session)
        session_id = quiz_session.id

    return QuizRead(
        id=quiz.id,
        title=quiz.title,
        quiz_type=quiz.quiz_type,
        language_code=course.language_code if course else "",
        session_id=session_id,
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
    return _build_quiz_read(quiz, session, current_user)


@router.get("/lessons/{lesson_id}/quiz", response_model=QuizRead)
def get_quiz_by_lesson(
    lesson_id: int,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Returns the quiz for a lesson. Added so the frontend can jump from a
    lesson page straight to its quiz without needing to know the quiz ID
    ahead of time. If the requester is logged in and has quiz history, the
    question selection adapts to their recent average score -- and the
    served set is recorded as a QuizSession for grading."""
    quiz = session.exec(select(Quiz).where(Quiz.lesson_id == lesson_id)).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="No quiz found for this lesson")
    return _build_quiz_read(quiz, session, current_user)


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizResult)
def submit_quiz(
    quiz_id: int,
    submission: QuizSubmission,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Grades a submission against the served-question set recorded in the
    QuizSession (v0.0.9).

    This deliberately *reverses* the earlier documented choice of grading
    only the submitted answers: every served question counts toward the
    denominator, unanswered ones count as wrong, and answers for
    questions outside the served set are ignored (they can't raise the
    score, and rejecting them outright would punish stale clients for
    nothing). Sessions are reusable on purpose -- "Try again" resubmits
    the same served set, which is legitimate practice, not an exploit."""
    quiz = session.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    quiz_session = session.get(QuizSession, submission.session_id)
    if (
        quiz_session is None
        or quiz_session.user_id != current_user.id
        or quiz_session.quiz_id != quiz_id
    ):
        # One message for all three failure cases on purpose: no probing
        # which session ids exist or whose they are.
        raise HTTPException(
            status_code=400, detail="Invalid quiz session -- reload the quiz and try again."
        )

    served_ids: List[int] = json.loads(quiz_session.question_ids_json)
    questions_by_id = {
        q.id: q
        for q in session.exec(
            select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)
        ).all()
    }

    # Answers are compared case-insensitively with *language-aware* folding
    # (see app/services/text_normalization.py): the quiz's language comes
    # from its course, and Turkish in particular breaks under plain
    # .lower() ("BAŞINI".lower() != "başını"). With the current Spanish
    # seed content this is a no-op; it matters the moment Turkish course
    # content exists.
    lesson = session.get(Lesson, quiz.lesson_id)
    course = session.get(Course, lesson.course_id) if lesson else None
    quiz_language = course.language_code if course else None

    correct_count = 0
    total = len(served_ids)
    for question_id in served_ids:
        # None if an admin deleted the question after it was served -- it
        # then counts as wrong, which errs against the submitter but keeps
        # the denominator honest.
        question = questions_by_id.get(question_id)
        given = submission.answers.get(str(question_id), "")
        if question and fold_case(given.strip(), quiz_language) == fold_case(
            question.correct_answer.strip(), quiz_language
        ):
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

    new_achievements = check_and_award(current_user, session)

    return QuizResult(
        score=score,
        total_questions=total,
        correct_count=correct_count,
        new_achievements=[
            AchievementRead(code=a.code, name=d.name, description=d.description, earned_at=a.earned_at)
            for a, d in new_achievements
        ],
    )
