"""Password hashing (v0.1.11).

The bug: bcrypt hashes at most 72 bytes of input and silently ignores the
rest. Two different passwords sharing their first 72 bytes therefore
produce the same hash, and either one unlocks the account. Password
managers generate exactly the kind of long passphrase that runs into
this, and nothing tells the user most of what they chose was discarded.

SECURITY.md had claimed this was "already fixed earlier in this project --
see CHANGELOG.md v0.0.1". It never was: the code did a plain
`CryptContext(schemes=["bcrypt"])`, and the changelog entry cited doesn't
mention bcrypt anywhere. A security document asserting a fix that does not
exist is worse than one admitting the gap, so these tests exist to keep
the claim and the code tied together.
"""

import pytest
from passlib.context import CryptContext
from sqlmodel import select

from app.models import User
from app.schemas import MAX_PASSWORD_LENGTH
from app.security import hash_password, pwd_context, verify_password

# The scheme as it was before this version, for building legacy fixtures.
LEGACY_CONTEXT = CryptContext(schemes=["bcrypt"])

SHARED_PREFIX = "P@ssw0rd-" + "x" * 63  # 72 bytes exactly
LONG_A = SHARED_PREFIX + "-tail-alpha"
LONG_B = SHARED_PREFIX + "-tail-beta"


def test_the_old_scheme_really_did_confuse_long_passwords():
    """Not an abstract concern -- this is the behaviour that shipped."""
    legacy = LEGACY_CONTEXT.hash(LONG_A)
    assert LEGACY_CONTEXT.verify(LONG_B, legacy), (
        "fixture is wrong: these two passwords should collide under plain bcrypt"
    )


def test_long_passwords_are_no_longer_interchangeable():
    stored = hash_password(LONG_A)
    verified, _ = verify_password(LONG_A, stored)
    assert verified
    rejected, _ = verify_password(LONG_B, stored)
    assert not rejected, "everything past 72 bytes is still being ignored"


def test_new_hashes_use_bcrypt_sha256():
    assert pwd_context.identify(hash_password("correct horse battery staple")) == "bcrypt_sha256"


def test_a_wrong_password_is_never_reported_as_upgradable():
    stored = hash_password("the-real-password")
    verified, replacement = verify_password("not-the-password", stored)
    assert verified is False
    assert replacement is None


def test_current_hashes_need_no_replacement():
    stored = hash_password("already-current")
    verified, replacement = verify_password("already-current", stored)
    assert verified is True
    assert replacement is None


def test_legacy_hashes_still_verify_and_offer_a_replacement():
    """Existing accounts must keep working: the plaintext isn't stored, so
    there is no offline migration -- they can only be upgraded at login."""
    legacy = LEGACY_CONTEXT.hash("an-existing-users-password")
    verified, replacement = verify_password("an-existing-users-password", legacy)
    assert verified is True
    assert replacement is not None
    assert pwd_context.identify(replacement) == "bcrypt_sha256"


# --- through the login endpoint ---------------------------------------------


def test_logging_in_upgrades_a_legacy_hash_in_place(client, session):
    """The migration path. An account stored under the old scheme keeps
    working, and quietly stops being vulnerable the first time its owner
    signs in."""
    password = "a-perfectly-ordinary-password"
    session.add(
        User(
            username="veteran",
            email="veteran@example.com",
            hashed_password=LEGACY_CONTEXT.hash(password),
        )
    )
    session.commit()

    first = client.post("/auth/login", data={"username": "veteran", "password": password})
    assert first.status_code == 200

    stored = session.exec(select(User).where(User.username == "veteran")).first()
    assert pwd_context.identify(stored.hashed_password) == "bcrypt_sha256"

    # ...and the account still logs in afterwards, with the same password.
    again = client.post("/auth/login", data={"username": "veteran", "password": password})
    assert again.status_code == 200


def _legacy_account(session, username: str, password: str) -> None:
    session.add(
        User(
            username=username,
            email=f"{username}@example.com",
            hashed_password=LEGACY_CONTEXT.hash(password),
        )
    )
    session.commit()


def test_a_legacy_account_is_still_vulnerable_until_it_is_used(client, session):
    """Recording the limit of the fix rather than overstating it. An
    account whose owner never logs in keeps its old hash, so a password
    differing only past byte 72 still opens it. Nothing can change that
    without the plaintext, which isn't stored."""
    _legacy_account(session, "dormant", LONG_A)

    assert (
        client.post("/auth/login", data={"username": "dormant", "password": LONG_B}).status_code
        == 200
    )


def test_a_legitimate_login_closes_the_truncation_hole(client, session):
    """The migration doing its job: once the real owner signs in, the
    variant that used to work stops working."""
    _legacy_account(session, "longpass", LONG_A)

    assert (
        client.post("/auth/login", data={"username": "longpass", "password": LONG_A}).status_code
        == 200
    )
    assert (
        client.post("/auth/login", data={"username": "longpass", "password": LONG_B}).status_code
        == 401
    )


def test_the_upgrade_binds_to_whatever_password_was_accepted(client, session):
    """A consequence worth stating rather than discovering later: the
    rehash uses the password that was supplied, so if the truncated
    variant is what logs in first, the account ends up bound to *that*.

    It does not widen the hole -- reaching this point already requires
    knowing the first 72 bytes, i.e. essentially the password -- but it
    does make the outcome permanent, and it is the reason the upgrade
    can't be described as simply "fixing" an untouched account."""
    _legacy_account(session, "rebound", LONG_A)

    assert (
        client.post("/auth/login", data={"username": "rebound", "password": LONG_B}).status_code
        == 200
    )
    # The real password no longer works, because the hash is now LONG_B's.
    assert (
        client.post("/auth/login", data={"username": "rebound", "password": LONG_A}).status_code
        == 401
    )


def test_registration_accepts_a_long_passphrase(client):
    response = client.post(
        "/auth/register",
        json={"username": "verbose", "email": "verbose@example.com", "password": LONG_A},
    )
    assert response.status_code == 201
    assert (
        client.post("/auth/login", data={"username": "verbose", "password": LONG_A}).status_code
        == 200
    )


@pytest.mark.parametrize("field", ["register", "reset"])
def test_absurdly_long_passwords_are_refused(client, field):
    too_long = "x" * (MAX_PASSWORD_LENGTH + 1)
    if field == "register":
        response = client.post(
            "/auth/register",
            json={"username": "novella", "email": "novella@example.com", "password": too_long},
        )
    else:
        response = client.post(
            "/auth/reset-password", json={"token": "irrelevant", "new_password": too_long}
        )
    assert response.status_code == 422
