"""
Email delivery abstraction, for account verification and password reset.

Same pattern as TranslationService: an abstract interface with a mock
implementation used in this environment (and in tests), plus a real
implementation stubbed in for when actual credentials are available.

This sandbox has no SMTP credentials and no network access to a mail
provider, so MockEmailService is what actually runs here -- it doesn't
send anything, just records what *would* have been sent, which is enough
to build and test the verification/reset flows end-to-end without a real
mail server. SMTPEmailService is written but unexercised; wire in real
credentials via environment variables before using it.
"""

from functools import lru_cache

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.config import settings


@dataclass
class SentEmail:
    to: str
    subject: str
    body: str


class EmailService(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None:
        ...


@dataclass
class MockEmailService(EmailService):
    """Records emails in memory instead of sending them. Used whenever
    real SMTP credentials aren't configured (the default in this
    sandbox), and in tests, where asserting against `sent_emails` is much
    more useful than actually delivering mail."""

    sent_emails: list[SentEmail] = field(default_factory=list)

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent_emails.append(SentEmail(to=to, subject=subject, body=body))


class SMTPEmailService(EmailService):
    """Real email delivery via SMTP. Not exercised in this sandbox (no
    credentials, no network access to a mail provider) -- written for
    when real SMTP_* environment variables are configured. Uses only the
    Python standard library (smtplib), no extra dependency."""

    def send(self, to: str, subject: str, body: str) -> None:
        import smtplib
        from email.mime.text import MIMEText

        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = settings.smtp_from_address
        message["To"] = to

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_address, [to], message.as_string())


@lru_cache
def get_email_service() -> EmailService:
    """FastAPI dependency. Returns a singleton MockEmailService (so tests
    can inspect .sent_emails across requests within one test), or a real
    SMTPEmailService if credentials are configured."""
    if settings.smtp_host:
        return SMTPEmailService()
    return MockEmailService()
