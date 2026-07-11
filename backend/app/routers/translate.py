from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Language, TranslationHistory, User
from app.routers.auth import get_current_user, get_current_user_optional
from app.schemas import LanguageRead, TranslateRequest, TranslateResponse
from app.services.translation_service import TranslationService, get_translation_service

router = APIRouter(tags=["translate"])


@router.get("/languages", response_model=List[LanguageRead])
def list_languages(session: Session = Depends(get_session)):
    return session.exec(select(Language)).all()


@router.post("/translate", response_model=TranslateResponse)
def translate_text(
    payload: TranslateRequest,
    session: Session = Depends(get_session),
    service: TranslationService = Depends(get_translation_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Translates text in real time. If logged in, it's saved to history;
    if not (anonymous use), only the translation result is returned."""
    translated = service.translate(payload.text, payload.source_lang, payload.target_lang)

    if current_user is not None:
        record = TranslationHistory(
            user_id=current_user.id,
            source_text=payload.text,
            source_lang=payload.source_lang,
            target_text=translated,
            target_lang=payload.target_lang,
        )
        session.add(record)
        session.commit()

    return TranslateResponse(
        source_text=payload.text,
        translated_text=translated,
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
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
