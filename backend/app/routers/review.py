from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Course, Lesson, User, VocabularyItem, VocabularyProgress
from app.routers.auth import get_current_user
from app.schemas import AchievementRead, ReviewQueueItem, ReviewResult, ReviewSubmission
from app.services.achievements import check_and_award
from app.services.spaced_repetition import DEFAULT_EASE_FACTOR, compute_next_schedule

router = APIRouter(tags=["review"])


@router.get("/users/me/review-queue", response_model=List[ReviewQueueItem])
def get_review_queue(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Words due for review today: brand-new words the learner hasn't seen
    yet, plus previously-seen words whose SM-2 schedule has come due.
    Ordered so new words come last, after anything already in progress."""
    today = datetime.now(timezone.utc).date()

    all_vocab = session.exec(select(VocabularyItem)).all()
    progress_by_item = {
        p.vocabulary_item_id: p
        for p in session.exec(
            select(VocabularyProgress).where(VocabularyProgress.user_id == current_user.id)
        ).all()
    }

    due: List[ReviewQueueItem] = []
    new: List[ReviewQueueItem] = []

    for item in all_vocab:
        progress = progress_by_item.get(item.id)
        lesson = session.get(Lesson, item.lesson_id)
        if lesson is None:
            continue
        course = session.get(Course, lesson.course_id)

        queue_item = ReviewQueueItem(
            vocabulary_item_id=item.id,
            word=item.word,
            translation=item.translation,
            example_sentence=item.example_sentence,
            lesson_id=item.lesson_id,
            language_code=course.language_code if course else "",
            is_new=progress is None,
        )

        if progress is None:
            new.append(queue_item)
        elif progress.next_review_date <= today:
            due.append(queue_item)

    return due + new


@router.post("/vocabulary/{vocabulary_item_id}/review", response_model=ReviewResult)
def submit_review(
    vocabulary_item_id: int,
    submission: ReviewSubmission,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    vocabulary_item = session.get(VocabularyItem, vocabulary_item_id)
    if not vocabulary_item:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")

    progress = session.exec(
        select(VocabularyProgress).where(
            VocabularyProgress.user_id == current_user.id,
            VocabularyProgress.vocabulary_item_id == vocabulary_item_id,
        )
    ).first()

    if progress is None:
        progress = VocabularyProgress(
            user_id=current_user.id,
            vocabulary_item_id=vocabulary_item_id,
            ease_factor=DEFAULT_EASE_FACTOR,
            interval_days=0,
            repetitions=0,
        )

    outcome = compute_next_schedule(
        quality=submission.quality,
        repetitions=progress.repetitions,
        ease_factor=progress.ease_factor,
        interval_days=progress.interval_days,
    )

    now = datetime.now(timezone.utc)
    progress.repetitions = outcome.repetitions
    progress.ease_factor = outcome.ease_factor
    progress.interval_days = outcome.interval_days
    progress.next_review_date = now.date() + timedelta(days=outcome.interval_days)
    progress.last_reviewed_at = now

    session.add(progress)
    session.commit()
    session.refresh(progress)

    new_achievements = check_and_award(current_user.id, session)

    return ReviewResult(
        vocabulary_item_id=vocabulary_item_id,
        repetitions=progress.repetitions,
        ease_factor=progress.ease_factor,
        interval_days=progress.interval_days,
        next_review_date=progress.next_review_date,
        new_achievements=[
            AchievementRead(code=a.code, name=d.name, description=d.description, earned_at=a.earned_at)
            for a, d in new_achievements
        ],
    )
