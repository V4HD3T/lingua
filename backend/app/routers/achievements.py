from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.models import User
from app.routers.auth import get_current_user
from app.schemas import AchievementRead
from app.services.achievements import list_earned

router = APIRouter(tags=["achievements"])


@router.get("/users/me/achievements", response_model=List[AchievementRead])
def get_my_achievements(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return [
        AchievementRead(
            code=achievement.code,
            name=definition.name,
            description=definition.description,
            earned_at=achievement.earned_at,
        )
        for achievement, definition in list_earned(current_user.id, session)
    ]
