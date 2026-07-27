"""What the account flows do when the mail server is unreachable (v0.1.15).

All three senders run after their database work is already committed, so
the question these tests answer is what the caller is told about work that
has in fact succeeded -- and, for password reset, whether the failure mode
gives away which addresses are registered.
"""

import pytest
from sqlmodel import Session, select

from app.main import app
from app.models import AuthToken, User
from app.services.email_service import EmailService, get_email_service

PASSWORD = "correct horse battery"


class BrokenEmailService(EmailService):
    """A mail server that refuses the connection, the way a real one does
    when it is down. Raises OSError specifically because that is not an
    smtplib exception -- the handler has to be broad enough for the errors
    the network layer raises, not just the ones smtplib defines."""

    def send(self, to: str, subject: str, body: str) -> None:
        raise OSError("[Errno 111] Connection refused")


@pytest.fixture
def dead_mail_server():
    app.dependency_overrides[get_email_service] = lambda: BrokenEmailService()
    yield
    app.dependency_overrides.pop(get_email_service, None)


def _register(client, username="ada"):
    return client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
            "native_language": "en",
        },
    )


def _auth_headers(client, username="ada"):
    tokens = client.post(
        "/auth/login", data={"username": username, "password": PASSWORD}
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_registration_succeeds_when_the_verification_email_cannot_be_sent(
    client, session: Session, dead_mail_server
):
    """The account is committed before the send is attempted. Failing the
    request would report failure for work that succeeded -- and the
    person's natural retry then hits "already registered"."""
    response = _register(client)

    assert response.status_code == 201, response.text
    assert session.exec(select(User).where(User.username == "ada")).first() is not None

    # And the account is genuinely usable, not just present.
    login = client.post("/auth/login", data={"username": "ada", "password": PASSWORD})
    assert login.status_code == 200


def test_password_reset_answers_identically_whether_or_not_the_address_exists(
    client, dead_mail_server
):
    """The anti-enumeration guarantee has to hold *especially* when things
    are degraded. Only the registered branch sends mail, so an unhandled
    send failure separated the two answers exactly when it mattered."""
    app.dependency_overrides.pop(get_email_service, None)
    _register(client, "bob")
    app.dependency_overrides[get_email_service] = lambda: BrokenEmailService()

    registered = client.post(
        "/auth/request-password-reset", json={"email": "bob@example.com"}
    )
    unknown = client.post(
        "/auth/request-password-reset", json={"email": "nobody@example.com"}
    )

    assert registered.status_code == unknown.status_code == 200
    assert registered.json() == unknown.json()


def test_resend_verification_reports_a_failure_instead_of_claiming_success(client):
    """Sending the mail *is* the point of this endpoint, so unlike
    registration it must not quietly succeed. The caller is authenticated,
    so an honest error tells them nothing they don't already know."""
    _register(client)
    headers = _auth_headers(client)

    app.dependency_overrides[get_email_service] = lambda: BrokenEmailService()
    response = client.post("/auth/resend-verification", headers=headers)
    app.dependency_overrides.pop(get_email_service, None)

    assert response.status_code == 503
    assert "try again" in response.json()["detail"].lower()


def test_a_failed_resend_leaves_the_previous_link_working(client, session: Session):
    """Retiring the outstanding link before the new one is delivered left
    the learner worse off than not clicking at all: old link dead, new one
    never sent."""
    _register(client)
    headers = _auth_headers(client)

    original_link = get_email_service().sent_emails[-1].body
    original_token = original_link.split("token=")[1].strip()

    app.dependency_overrides[get_email_service] = lambda: BrokenEmailService()
    assert client.post("/auth/resend-verification", headers=headers).status_code == 503
    app.dependency_overrides.pop(get_email_service, None)

    verified = client.post("/auth/verify-email", json={"token": original_token})
    assert verified.status_code == 200, verified.text


def test_a_successful_resend_still_retires_the_previous_link(client):
    """The invariant the reordering had to preserve: once a replacement is
    actually delivered, exactly one link works."""
    _register(client)
    headers = _auth_headers(client)

    mail = get_email_service()
    original_token = mail.sent_emails[-1].body.split("token=")[1].strip()

    assert client.post("/auth/resend-verification", headers=headers).status_code == 200
    new_token = mail.sent_emails[-1].body.split("token=")[1].strip()
    assert new_token != original_token

    assert client.post("/auth/verify-email", json={"token": original_token}).status_code == 400
    assert client.post("/auth/verify-email", json={"token": new_token}).status_code == 200


def test_the_undelivered_token_is_never_usable(client, session: Session):
    """A failed resend leaves its unused token row behind. That is only
    acceptable because the raw value went nowhere -- assert the row exists
    and that nothing can be done with it."""
    _register(client)
    headers = _auth_headers(client)

    app.dependency_overrides[get_email_service] = lambda: BrokenEmailService()
    client.post("/auth/resend-verification", headers=headers)
    app.dependency_overrides.pop(get_email_service, None)

    unused = session.exec(
        select(AuthToken).where(
            AuthToken.purpose == "email_verification", AuthToken.used_at.is_(None)
        )
    ).all()
    assert len(unused) == 2  # the original, still live, plus the undelivered one
    # Only hashes are stored, so the undelivered one cannot be reconstructed
    # from the database either.
    assert all(len(token.token_hash) == 64 for token in unused)
