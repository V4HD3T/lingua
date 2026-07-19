"""
Helpers shared by the refresh-token and email-verification/password-reset
flows: generate a high-entropy opaque token, hash it for storage, and
validate a presented token against the stored hash.

These are deliberately *not* JWTs. A JWT's whole point is being
self-verifying without a database lookup -- but that's exactly what makes
a JWT hard to revoke early. These tokens are the opposite by design:
opaque random values that only mean anything by being looked up against a
database row (RefreshToken / AuthToken), which is what makes revocation
and single-use enforcement possible in the first place.

Tokens are hashed with SHA-256 before storage, not bcrypt: they're already
high-entropy random values (unlike user-chosen passwords), so there's no
guessing risk to slow down, and the hash here is purely to avoid storing
a bearer credential in plaintext in case the database is ever read by
someone who shouldn't.
"""

import hashlib
import secrets


def generate_token() -> str:
    """A cryptographically secure, URL-safe random token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
