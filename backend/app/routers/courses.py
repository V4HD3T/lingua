from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Course, Lesson, VocabularyItem
from app.schemas import CourseRead, LessonRead, VocabularyRead

router = APIRouter(tags=["courses"])


def _build_lesson_read(lesson: Lesson, session: Session) -> LessonRead:
    course = session.get(Course, lesson.course_id)
    return LessonRead(
        id=lesson.id,
        course_id=lesson.course_id,
        title=lesson.title,
        content=lesson.content,
        order=lesson.order,
        language_code=course.language_code if course else "",
        grammar_note=lesson.grammar_note,
        cultural_note=lesson.cultural_note,
    )


@router.get("/courses", response_model=List[CourseRead])
def list_courses(session: Session = Depends(get_session)):
    return session.exec(select(Course)).all()


@router.get("/courses/{course_id}", response_model=CourseRead)
def get_course(course_id: int, session: Session = Depends(get_session)):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("/courses/{course_id}/lessons", response_model=List[LessonRead])
def list_lessons(course_id: int, session: Session = Depends(get_session)):
    lessons = session.exec(
        select(Lesson).where(Lesson.course_id == course_id).order_by(Lesson.order)
    ).all()
    return [_build_lesson_read(lesson, session) for lesson in lessons]


@router.get("/lessons/{lesson_id}", response_model=LessonRead)
def get_lesson(lesson_id: int, session: Session = Depends(get_session)):
    lesson = session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return _build_lesson_read(lesson, session)


@router.get("/lessons/{lesson_id}/vocabulary", response_model=List[VocabularyRead])
def list_vocabulary(lesson_id: int, session: Session = Depends(get_session)):
    return session.exec(
        select(VocabularyItem).where(VocabularyItem.lesson_id == lesson_id)
    ).all()
