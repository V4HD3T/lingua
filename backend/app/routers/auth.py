from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.models import AuthToken, RefreshToken, User
from app.schemas import (
    DailyGoalUpdate,
    EmailVerificationConfirm,
    LogoutRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TimezoneUpdate,
    Token,
    UserCreate,
    UserRead,
)
from app.security import create_access_token, decode_access_token, hash_password, verify_password
from app.services.email_service import EmailService, get_email_service
from app.services.rate_limiter import (
    client_ip as _client_ip,
    enforce_rate_limit as _rate_limit,
    login_ip_rate_limiter,
    login_key as _login_key,
    login_rate_limiter,
    password_reset_rate_limiter,
    register_rate_limiter,
    verification_resend_rate_limiter,
)
from app.services.security_logging import log_event
from app.services.tokens import generate_token, hash_token
from app.services.user_time import is_valid_timezone

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

VERIFICATION_TOKEN_HOURS = 24
PASSWORD_RESET_TOKEN_MINUTES = 30


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite round-trips datetime columns as naive, even though every
    datetime this app stores is created via datetime.now(timezone.utc) --
    without this, comparing a value read back from the database against
    a freshly-created aware datetime raises TypeError. Reattaching UTC
    tzinfo (never converting/shifting, just labeling) is correct here
    specifically because every write path already normalizes to UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _is_benign_rotation_replay(stored: RefreshToken) -> bool:
    """True when a revoked refresh token is being replayed so soon after
    its own rotation that a racing client, not a thief, is the
    overwhelmingly likely explanation (v0.1.8).

    Both conditions are required, and the reason check is the important
    one: without it the grace window would also forgive a token revoked
    by logout, logout-all, or a password reset -- exactly the revocations
    that have to bite immediately, since they are what someone reaches for
    when they think their account is compromised.
    """
    if stored.revoked_reason != "rotated" or stored.revoked_at is None:
        return False
    age = datetime.now(timezone.utc) - _as_aware_utc(stored.revoked_at)
    return age <= timedelta(seconds=settings.refresh_reuse_grace_seconds)


def _issue_tokens(user: User, session: Session) -> Token:
    access_token = create_access_token(subject=str(user.id))

    raw_refresh = generate_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    session.commit()

    return Token(access_token=access_token, refresh_token=raw_refresh)


def _create_auth_token(user_id: int, purpose: str, ttl: timedelta, session: Session) -> str:
    raw = generate_token()
    session.add(
        AuthToken(
            user_id=user_id,
            token_hash=hash_token(raw),
            purpose=purpose,
            expires_at=datetime.now(timezone.utc) + ttl,
        )
    )
    session.commit()
    return raw


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    request: Request,
    session: Session = Depends(get_session),
    email_service: EmailService = Depends(get_email_service),
):
    _rate_limit(register_rate_limiter, _client_ip(request), "register")

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
    try:
        session.commit()
    except IntegrityError:
        # Two registrations for the same username/email racing past the
        # SELECT above: the database's unique constraint is the real
        # guard; the SELECT is only the friendly fast path. Without this,
        # the loser of the race gets an unhandled 500 instead of the same
        # 400 it would have gotten a millisecond later.
        session.rollback()
        raise HTTPException(status_code=400, detail="Username or email is already registered")
    session.refresh(user)

    raw_token = _create_auth_token(
        user.id, "email_verification", timedelta(hours=VERIFICATION_TOKEN_HOURS), session
    )
    verify_link = f"{settings.frontend_base_url}/verify-email?token={raw_token}"
    email_service.send(
        to=user.email,
        subject="Verify your Lingua account",
        body=f"Welcome to Lingua! Verify your email: {verify_link}",
    )

    log_event("user_registered", user_id=user.id, username=user.username)
    return user


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    ip = _client_ip(request)
    # Two budgets, because they stop different attacks (v0.1.6). The pair
    # budget bounds how hard one account can be hammered from one address;
    # the address budget bounds how much guessing that address can do in
    # total, which is what stops spraying one password across many
    # usernames. See app/services/rate_limiter.py: login_key.
    key = _login_key(ip, form_data.username)
    _rate_limit(login_ip_rate_limiter, ip, "login_ip", record=False)
    _rate_limit(login_rate_limiter, key, "login")

    user = session.exec(select(User).where(User.username == form_data.username)).first()
    verified, upgraded_hash = (
        verify_password(form_data.password, user.hashed_password) if user else (False, None)
    )
    if not user or not verified:
        # Charged only on failure, so simply logging in -- however often --
        # never eats into the address budget.
        login_ip_rate_limiter.record(ip)
        log_event("login_failed", username=form_data.username, ip=ip)
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    if upgraded_hash is not None:
        # This account's password was stored under the old bcrypt scheme,
        # which ignored everything past 72 bytes (v0.1.11). Now is the one
        # moment the plaintext exists to rehash with, so take it. Nothing
        # the user sees changes; their next login just uses the new hash.
        user.hashed_password = upgraded_hash
        session.add(user)
        session.commit()
        log_event("password_hash_upgraded", user_id=user.id)

    # Clears this pair only. Previously this reset the whole address, so
    # an attacker holding any account of their own could wipe out a
    # victim's accumulated failures by logging in as themselves.
    login_rate_limiter.reset(key)
    log_event("login_succeeded", user_id=user.id, username=user.username, ip=ip)
    return _issue_tokens(user, session)


@router.post("/refresh", response_model=Token)
def refresh_access_token(payload: RefreshRequest, session: Session = Depends(get_session)):
    token_hash = hash_token(payload.refresh_token)
    stored = session.exec(select(RefreshToken).where(RefreshToken.token_hash == token_hash)).first()

    if stored is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if stored.revoked_at is not None:
        if _is_benign_rotation_replay(stored):
            # Two tabs sharing one localStorage refresh independently, so
            # both present the same token within milliseconds; a lost
            # response makes a client retry with it too. Treating that as
            # theft logged real users out of every session they had, and
            # filled the audit trail with theft alerts for events that
            # were nothing of the sort. Inside the grace window a rotated
            # token mints a sibling instead -- still recorded, because a
            # burst of these is worth being able to see.
            user = session.get(User, stored.user_id)
            if user is None:
                raise HTTPException(status_code=401, detail="User not found")
            log_event("refresh_token_replayed_within_grace", user_id=stored.user_id)
            return _issue_tokens(user, session)

        # Outside the window, or revoked by something other than rotation:
        # a strong signal of theft/replay, since the legitimate client
        # would have moved on to its replacement. Precautionary response:
        # kill every active session for this user.
        log_event("refresh_token_reuse_detected", user_id=stored.user_id)
        active = session.exec(
            select(RefreshToken).where(
                RefreshToken.user_id == stored.user_id, RefreshToken.revoked_at.is_(None)
            )
        ).all()
        for token in active:
            if token.revoked_at is None:
                token.revoked_at = datetime.now(timezone.utc)
                token.revoked_reason = "reuse_detected"
                session.add(token)
        session.commit()
        raise HTTPException(
            status_code=401, detail="This session has been invalidated. Please log in again."
        )

    if _as_aware_utc(stored.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token has expired")

    user = session.get(User, stored.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    # Rotate: this refresh token is now spent, replaced by a fresh one.
    # The reason is what lets a replay moments from now be recognised as a
    # tab race rather than theft -- see _is_benign_rotation_replay.
    stored.revoked_at = datetime.now(timezone.utc)
    stored.revoked_reason = "rotated"
    session.add(stored)
    session.commit()

    return _issue_tokens(user, session)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, session: Session = Depends(get_session)):
    token_hash = hash_token(payload.refresh_token)
    stored = session.exec(select(RefreshToken).where(RefreshToken.token_hash == token_hash)).first()
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        stored.revoked_reason = "logout"
        session.add(stored)
        session.commit()
        log_event("logout", user_id=stored.user_id)
    return MessageResponse(message="Logged out")


def _user_from_access_token(token: str, session: Session) -> Optional[User]:
    """Resolves an access token to its User. Returns None if the token is
    invalid/expired, its subject isn't a well-formed user id, or the user
    no longer exists. The int() guard means a malformed `sub` claim yields
    a clean None (-> 401 in the callers below) instead of an unhandled
    ValueError (-> 500)."""
    subject = decode_access_token(token)
    if subject is None:
        return None
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        return None
    return session.get(User, user_id)


def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)
) -> User:
    user = _user_from_access_token(token, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    session: Session = Depends(get_session),
) -> Optional[User]:
    """For endpoints that allow anonymous access (e.g. translating without
    logging in): no Authorization header at all -> None, proceed
    anonymously.

    A token that is *present but invalid* is a 401, not None. This
    distinction matters more than it looks: the frontend attaches its
    access token to these endpoints and only knows to refresh an expired
    session when it sees a 401. Before this change, an expired token was
    silently downgraded to anonymous — a 200 response, so no refresh was
    ever triggered — which meant that ~30 minutes after login, every
    translation quietly stopped being saved to history (while the UI kept
    saying "Saved to your translation history") and adaptive quiz
    difficulty silently switched off."""
    if not token:
        return None
    user = _user_from_access_token(token, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """Revokes every refresh token for the current user -- "log out
    everywhere", for when an account may be compromised."""
    active = session.exec(
        select(RefreshToken).where(RefreshToken.user_id == current_user.id)
    ).all()
    now = datetime.now(timezone.utc)
    count = 0
    for token in active:
        if token.revoked_at is None:
            token.revoked_at = now
            token.revoked_reason = "logout_all"
            session.add(token)
            count += 1
    session.commit()
    log_event("logout_all", user_id=current_user.id, sessions_revoked=count)
    return MessageResponse(message=f"Logged out of {count} session(s)")


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: EmailVerificationConfirm, session: Session = Depends(get_session)):
    token_hash = hash_token(payload.token)
    stored = session.exec(
        select(AuthToken).where(
            AuthToken.token_hash == token_hash, AuthToken.purpose == "email_verification"
        )
    ).first()

    if stored is None or stored.used_at is not None or _as_aware_utc(stored.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    user = session.get(User, stored.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    user.is_verified = True
    stored.used_at = datetime.now(timezone.utc)
    session.add(user)
    session.add(stored)
    session.commit()

    log_event("email_verified", user_id=user.id)
    return MessageResponse(message="Email verified")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    email_service: EmailService = Depends(get_email_service),
):
    """Sends a fresh verification link to the address already on file
    (v0.1.12).

    Added because the app now *shows* people whether their email is
    verified, and the original link expires after 24 hours. Telling
    someone their address is unverified while offering no way to fix it
    is worse than not telling them: the registration email is the only
    link that ever existed, and a day later it is gone.

    Takes no email address parameter on purpose. The destination is the
    one on the authenticated account, so this can't be used to send mail
    to an address of the caller's choosing.
    """
    if current_user.is_verified:
        return MessageResponse(message="Your email is already verified.")

    _rate_limit(
        verification_resend_rate_limiter, str(current_user.id), "resend_verification"
    )

    # Retire any link still outstanding, so exactly one works at a time.
    outstanding = session.exec(
        select(AuthToken).where(
            AuthToken.user_id == current_user.id,
            AuthToken.purpose == "email_verification",
            AuthToken.used_at.is_(None),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for token in outstanding:
        token.used_at = now
        session.add(token)
    session.commit()

    raw_token = _create_auth_token(
        current_user.id, "email_verification", timedelta(hours=VERIFICATION_TOKEN_HOURS), session
    )
    verify_link = f"{settings.frontend_base_url}/verify-email?token={raw_token}"
    email_service.send(
        to=current_user.email,
        subject="Verify your Lingua account",
        body=f"Verify your email: {verify_link}",
    )

    log_event("verification_email_resent", user_id=current_user.id)
    return MessageResponse(message="Verification email sent.")


@router.post("/request-password-reset", response_model=MessageResponse)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    session: Session = Depends(get_session),
    email_service: EmailService = Depends(get_email_service),
):
    _rate_limit(password_reset_rate_limiter, _client_ip(request), "request_password_reset")

    # Always return the same message whether or not the email exists --
    # revealing that would let an attacker enumerate registered accounts.
    generic_response = MessageResponse(
        message="If that email is registered, a reset link has been sent."
    )

    user = session.exec(select(User).where(User.email == payload.email)).first()
    if user is None:
        return generic_response

    raw_token = _create_auth_token(
        user.id, "password_reset", timedelta(minutes=PASSWORD_RESET_TOKEN_MINUTES), session
    )
    reset_link = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
    email_service.send(
        to=user.email,
        subject="Reset your Lingua password",
        body=f"Reset your password: {reset_link} (expires in {PASSWORD_RESET_TOKEN_MINUTES} minutes)",
    )
    log_event("password_reset_requested", user_id=user.id)
    return generic_response


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: PasswordResetConfirm, session: Session = Depends(get_session)):
    token_hash = hash_token(payload.token)
    stored = session.exec(
        select(AuthToken).where(
            AuthToken.token_hash == token_hash, AuthToken.purpose == "password_reset"
        )
    ).first()

    if stored is None or stored.used_at is not None or _as_aware_utc(stored.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    user = session.get(User, stored.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    user.hashed_password = hash_password(payload.new_password)
    stored.used_at = datetime.now(timezone.utc)
    session.add(user)
    session.add(stored)

    # A password reset is a strong signal to kill every existing session --
    # if the account was compromised, this cuts off the attacker's access too.
    active = session.exec(
        select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
    ).all()
    now = datetime.now(timezone.utc)
    for token in active:
        if token.revoked_at is None:
            token.revoked_at = now
            token.revoked_reason = "password_reset"
            session.add(token)

    session.commit()
    log_event("password_reset_completed", user_id=user.id)
    return MessageResponse(message="Password has been reset. Please log in again.")


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me/timezone", response_model=UserRead)
def update_timezone(
    payload: TimezoneUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Records where the learner is, so streaks, "reviews today" and review
    scheduling turn over when *their* day does (v0.1.9). The frontend
    reports the browser's zone automatically -- see AuthContext.

    Validated against the tz database rather than stored as given: an
    unrecognised name would silently fall back to UTC on every read (see
    resolve_zone), leaving the learner with a setting that looks saved and
    does nothing.
    """
    if not is_valid_timezone(payload.timezone):
        raise HTTPException(status_code=400, detail="Unknown timezone")

    current_user.timezone = payload.timezone
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/goal", response_model=UserRead)
def update_daily_goal(
    payload: DailyGoalUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    current_user.daily_review_goal = payload.daily_goal
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user
