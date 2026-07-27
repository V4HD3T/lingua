from datetime import datetime, timedelta, timezone
from typing import Optional

# PyJWT replaced python-jose in the post-v0.0.9 dependency response:
# python-jose drags in ecdsa, which pip-audit flags (PYSEC-2026-1325)
# with no fixed version upstream. This app signs HS256 only, so the ECDSA
# code path was pure, never-exercised attack surface. PyJWT is the
# actively maintained standard and has no such dependency.
import jwt
from passlib.context import CryptContext

from app.config import settings

# bcrypt_sha256 first, plain bcrypt kept only to read what's already
# stored (v0.1.11).
#
# bcrypt hashes at most 72 bytes of input and silently ignores the rest,
# which is not a rounding error: two different passwords sharing their
# first 72 bytes produce the same hash, so either one unlocks the account.
# Password managers generate exactly the kind of long passphrase that runs
# into this, and the user gets no indication that most of what they chose
# was thrown away. SECURITY.md previously claimed this was "already fixed
# earlier in this project"; it never was, and the changelog entry it cited
# doesn't mention bcrypt at all.
#
# bcrypt_sha256 is passlib's standard answer: SHA-256 the password first,
# then bcrypt the (fixed-length) digest. The length ceiling disappears
# without giving up bcrypt's deliberate slowness.
#
# Both schemes stay listed, and `deprecated="auto"` marks every scheme
# after the first as needing replacement -- that is what lets
# verify_password() recognise an existing bcrypt hash and hand back a
# replacement, so accounts migrate as people log in rather than in a
# flag-day rewrite nobody can perform (the plaintext isn't stored, so
# there is no offline path).
pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> tuple[bool, Optional[str]]:
    """Checks a password, and reports when its stored hash is outdated.

    Returns (verified, replacement_hash). `replacement_hash` is None
    whenever nothing needs to change -- a wrong password, or a hash
    already using the current scheme. When it isn't None the caller
    should persist it: that is the only moment the plaintext is available
    to rehash with, so an account that never logs in keeps its old hash,
    which is fine because it also never authenticates with it.
    """
    return pwd_context.verify_and_update(plain_password, hashed_password)


def dummy_verify() -> None:
    """Spends the same work `verify_password` would, for a login attempt
    against a username that doesn't exist (v0.1.18).

    Without this, `/auth/login` skipped hashing entirely when the lookup
    found nobody, and bcrypt is deliberately slow: a wrong password for a
    real account took ~200 ms while a wrong password for an invented one
    took ~5 ms. Both answer "Incorrect username or password", so the
    message gives nothing away -- and the clock gave away everything the
    message was written to hide, 40x over and measurable in a single
    request.

    passlib provides this exactly for the purpose: it verifies against a
    hash of a throwaway value, so the cost matches a real verification
    without any branch depending on the username.
    """
    pwd_context.dummy_verify()


def warm_password_hasher() -> None:
    """Builds passlib's dummy hash up front, at startup (see app/main.py).

    It is otherwise constructed on first use, which makes the *first*
    unknown-username login cost a hash plus a verify -- around twice a
    real one. That is still a timing signal, merely an inverted one, and
    it would land on whichever request happened to arrive first after a
    restart. Doing it once at boot removes the case entirely.
    """
    pwd_context.dummy_verify()


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
