from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.models import User
from app.routers.auth import get_current_user
from app.schemas import VocabularySuggestionRead
from app.services.personalized_suggestions import get_personalized_suggestions

router = APIRouter(tags=["suggestions"])


@router.get("/users/me/vocabulary-suggestions", response_model=List[VocabularySuggestionRead])
def get_vocabulary_suggestions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Words the user keeps typing/receiving in their own translations,
    matched against the app's vocabulary catalogue, excluding words they've
    already started formally learning. See
    app/services/personalized_suggestions.py for the (deliberately simple,
    frequency-based) logic -- this is the one feature that actually
    connects the translate and learn modules."""
    suggestions = get_personalized_suggestions(current_user.id, session)
    return [
        VocabularySuggestionRead(
            vocabulary_item_id=s.vocabulary_item_id,
            word=s.word,
            translation=s.translation,
            lesson_id=s.lesson_id,
            frequency=s.frequency,
        )
        for s in suggestions
    ]
