"""Deleting rows that have stopped meaning anything (v0.1.20).

Three tables only ever grew. `QuizSession` gains a row every time a
logged-in learner opens a quiz — the served-question record that
submissions are graded against — and nothing removed them; the model's
own docstring said "a cleanup job is noted for later alongside
expired-token cleanup", and this is that job. `AuthToken` keeps every
verification and reset link ever issued, spent or expired. `RefreshToken`
keeps every session ever revoked.

None of that is a leak: the rows hold hashes, not credentials, and the
code already refuses to act on them. It is unbounded storage attached to
ordinary use, which for `QuizSession` means a logged-in caller can add
rows as fast as the rate limiter allows.

The retention windows below are the load-bearing part, because a purge
that is too eager silently changes behaviour instead of merely freeing
space. Each one is set past the point where the row can still affect a
decision, not at the point where it stops being interesting.
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, delete, select

from app.config import settings
from app.models import AuthToken, QuizSession, RefreshToken
from app.services.security_logging import log_event

# Verification and password-reset links. Both are single-use and
# short-lived (24h and 30min), so a week past expiry is already long after
# anything can be done with one -- kept that long only so a support
# question days later can still be answered from the table.
AUTH_TOKEN_RETENTION = timedelta(days=7)

# Refresh tokens, counted from expiry rather than from revocation, and
# this is the window that matters most.
#
# /auth/refresh treats a *revoked* token being presented as theft and
# revokes every session the user has. That check needs the row: delete it
# and the replay merely 404s into "Invalid refresh token" -- still
# refused, but silently, with no alarm and no audit entry. So the row has
# to outlive every window in which a stolen copy could plausibly be
# replayed, which is bounded by the token's own lifetime
# (REFRESH_TOKEN_EXPIRE_DAYS, 30 by default). Retaining for that long
# again past expiry keeps reuse detection intact with a wide margin.
REFRESH_TOKEN_RETENTION = timedelta(days=settings.refresh_token_expire_days)

# Served-question sets. Deliberately reusable so "Try again" re-submits
# the same questions (see models.QuizSession), so this must outlast any
# plausible retry -- nobody resumes a quiz a month later, and one who
# tries simply reloads it and gets a fresh session.
QUIZ_SESSION_RETENTION = timedelta(days=30)


def purge_expired(session: Session, now: datetime | None = None) -> dict[str, int]:
    """Deletes rows that can no longer affect any decision.

    Returns a per-table count of what went, so the caller can log it --
    a purge that quietly removes more than expected should be visible in
    the record rather than inferred from a shrinking database.
    """
    now = now or datetime.now(timezone.utc)

    # Spent or expired links, past the grace window. A token that is still
    # unused and still in date is untouched however old the row is.
    auth_cutoff = now - AUTH_TOKEN_RETENTION
    spent_or_expired = session.exec(
        select(AuthToken).where(
            (AuthToken.used_at.is_not(None) & (AuthToken.used_at < auth_cutoff))
            | (AuthToken.expires_at < auth_cutoff)
        )
    ).all()

    refresh_cutoff = now - REFRESH_TOKEN_RETENTION
    dead_refresh = session.exec(
        select(RefreshToken).where(RefreshToken.expires_at < refresh_cutoff)
    ).all()

    quiz_cutoff = now - QUIZ_SESSION_RETENTION
    stale_sessions = session.exec(
        select(QuizSession).where(QuizSession.created_at < quiz_cutoff)
    ).all()

    removed = {
        "auth_tokens": len(spent_or_expired),
        "refresh_tokens": len(dead_refresh),
        "quiz_sessions": len(stale_sessions),
    }
    for row in (*spent_or_expired, *dead_refresh, *stale_sessions):
        session.delete(row)
    session.commit()

    return removed


def purge_and_log(session: Session) -> dict[str, int]:
    """purge_expired, announcing itself only when it actually did
    something -- a line every startup saying "removed nothing" trains
    people to skim past the one that matters."""
    removed = purge_expired(session)
    if any(removed.values()):
        log_event("purged_expired_rows", **removed)
    return removed
