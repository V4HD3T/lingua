from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.database import get_session
from app.models import User
from app.schemas import Token, UserCreate, UserRead
from app.security import create_access_token, decode_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, session: Session = Depends(get_session)):
    existing = session.exec(
        select(User).where((User.username == payload.username) | (User.email == payload.email))
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email is already registered")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        native_language=payload.native_language,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)
) -> User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = session.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    session: Session = Depends(get_session),
) -> Optional[User]:
    """Returns the logged-in user; None if there is no token (for endpoints
    that allow anonymous access, e.g. being able to translate without
    logging in)."""
    if not token:
        return None
    user_id = decode_access_token(token)
    if user_id is None:
        return None
    return session.get(User, int(user_id))


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
