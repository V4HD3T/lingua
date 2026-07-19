"""
Returns the user's progress summary: daily streak, per-course completion
percentage, daily goal progress, and overall quiz/translation statistics.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Course, Lesson, Quiz, QuizAttempt, TranslationHistory, User, VocabularyProgress
from app.routers.auth import get_current_user
from app.schemas import CourseProgress, UserStats
from app.services.streaks import compute_streaks, get_activity_dates

router = APIRouter(tags=["stats"])


def _compute_course_progress(user_id: int, course: Course, session: Session) -> CourseProgress:
    lessons = session.exec(select(Lesson).where(Lesson.course_id == course.id)).all()
    total_lessons = len(lessons)

    completed_lessons = 0
    if total_lessons:
        lesson_ids = [lesson.id for lesson in lessons]
        quizzes = session.exec(select(Quiz).where(Quiz.lesson_id.in_(lesson_ids))).all()
        quiz_id_to_lesson = {quiz.id: quiz.lesson_id for quiz in quizzes}

        if quiz_id_to_lesson:
            attempted_quiz_ids = session.exec(
                select(QuizAttempt.quiz_id).where(
                    QuizAttempt.user_id == user_id,
                    QuizAttempt.quiz_id.in_(list(quiz_id_to_lesson.keys())),
                )
            ).all()
            completed_lesson_ids = {
                quiz_id_to_lesson[qid] for qid in set(attempted_quiz_ids)
            }
            completed_lessons = len(completed_lesson_ids)

    percentage = round((completed_lessons / total_lessons) * 100, 1) if total_lessons else 0.0

    return CourseProgress(
        course_id=course.id,
        course_title=course.title,
        total_lessons=total_lessons,
        completed_lessons=completed_lessons,
        completion_percentage=percentage,
    )


def _reviews_done_today(user_id: int, session: Session) -> int:
    today = datetime.now(timezone.utc).date()
    reviewed = session.exec(
        select(VocabularyProgress.last_reviewed_at).where(
            VocabularyProgress.user_id == user_id
        )
    ).all()
    return sum(1 for t in reviewed if t is not None and t.date() == today)


@router.get("/users/me/stats", response_model=UserStats)
def get_my_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    activity_dates = get_activity_dates(current_user.id, session)
    current_streak, longest_streak = compute_streaks(activity_dates)

    total_translations = len(
        session.exec(
            select(TranslationHistory.id).where(TranslationHistory.user_id == current_user.id)
        ).all()
    )

    attempts = session.exec(
        select(QuizAttempt).where(QuizAttempt.user_id == current_user.id)
    ).all()
    total_quiz_attempts = len(attempts)
    average_quiz_score = (
        round(sum(a.score for a in attempts) / total_quiz_attempts, 1)
        if total_quiz_attempts
        else 0.0
    )

    courses = session.exec(select(Course)).all()
    course_progress = [_compute_course_progress(current_user.id, c, session) for c in courses]

    return UserStats(
        current_streak=current_streak,
        longest_streak=longest_streak,
        total_translations=total_translations,
        total_quiz_attempts=total_quiz_attempts,
        average_quiz_score=average_quiz_score,
        courses=course_progress,
        daily_goal=current_user.daily_review_goal,
        reviews_today=_reviews_done_today(current_user.id, session),
    )
