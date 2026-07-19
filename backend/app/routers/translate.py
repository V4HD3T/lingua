from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Language, TranslationHistory, User
from app.routers.auth import get_current_user, get_current_user_optional
from app.schemas import (
    AchievementRead,
    DetectLanguageRequest,
    DetectLanguageResponse,
    IdiomWarning,
    LanguageRead,
    TranslateRequest,
    TranslateResponse,
)
from app.services.idiom_detection import find_idioms
from app.services.language_detection import detect_language
from app.services.achievements import check_and_award
from app.services.translation_service import TranslationService, get_translation_service

router = APIRouter(tags=["translate"])


@router.get("/languages", response_model=List[LanguageRead])
def list_languages(session: Session = Depends(get_session)):
    return session.exec(select(Language)).all()


@router.post("/detect-language", response_model=DetectLanguageResponse)
def detect_language_endpoint(payload: DetectLanguageRequest):
    """Guesses the language of a piece of text, restricted to the app's
    supported languages. `is_reliable` is false for short or ambiguous
    input — see app/services/language_detection.py for why detection on
    short phrases can't be fully trusted with a lightweight, offline model."""
    result = detect_language(payload.text)
    return DetectLanguageResponse(
        language_code=result.language_code,
        confidence=result.confidence,
        is_reliable=result.is_reliable,
    )


@router.post("/translate", response_model=TranslateResponse)
def translate_text(
    payload: TranslateRequest,
    session: Session = Depends(get_session),
    service: TranslationService = Depends(get_translation_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Translates text in real time. If logged in, it's saved to history;
    if not (anonymous use), only the translation result is returned.

    Also returns a confidence score, up to a couple of alternative
    translations, and any idiom warnings matched in the source text --
    see translation_service.py and idiom_detection.py for how each of
    those is actually computed (and their honest limitations)."""
    detail = service.translate_detailed(payload.text, payload.source_lang, payload.target_lang)
    idioms = find_idioms(payload.text, payload.source_lang)

    new_achievements = []
    if current_user is not None:
        record = TranslationHistory(
            user_id=current_user.id,
            source_text=payload.text,
            source_lang=payload.source_lang,
            target_text=detail.translated_text,
            target_lang=payload.target_lang,
        )
        session.add(record)
        session.commit()
        new_achievements = check_and_award(current_user.id, session)

    return TranslateResponse(
        source_text=payload.text,
        translated_text=detail.translated_text,
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        confidence=detail.confidence,
        alternatives=detail.alternatives,
        idiom_warnings=[IdiomWarning(phrase=i.phrase, note=i.note) for i in idioms],
        new_achievements=[
            AchievementRead(
                code=a.code, name=d.name, description=d.description, earned_at=a.earned_at
            )
            for a, d in new_achievements
        ],
    )


@router.get("/translate/history", response_model=List[TranslateResponse])
def translation_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    records = session.exec(
        select(TranslationHistory)
        .where(TranslationHistory.user_id == current_user.id)
        .order_by(TranslationHistory.created_at.desc())
    ).all()
    return [
        TranslateResponse(
            source_text=r.source_text,
            translated_text=r.target_text,
            source_lang=r.source_lang,
            target_lang=r.target_lang,
        )
        for r in records
    ]
