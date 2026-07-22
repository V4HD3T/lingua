"""
Structured logging for security-relevant events (OWASP A09: Security
Logging and Monitoring Failures). Deliberately simple: a dedicated logger
that writes structured (key=value) lines through Python's standard
`logging` module.

This does not stand in for a real log aggregation / alerting pipeline --
in production you'd ship these logs somewhere that can alert on patterns
(e.g. many failed logins for one account, or one IP hitting many
accounts). What it does provide is the actual event data in a consistent,
greppable shape, which is the prerequisite for any of that.

That shape is load-bearing rather than cosmetic, which is why field
values are escaped before they are written (v0.1.7, see _render). One
event per line is the assumption every reader of these logs makes -- a
human grepping, or the aggregator that would eventually alert on them --
so a value that can introduce a newline is a value that can fabricate
events. `/auth/login` logs a username it never validated, which made that
reachable by anyone.
"""

import logging
import re

security_logger = logging.getLogger("lingua.security")
security_logger.setLevel(logging.INFO)

if not security_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    security_logger.addHandler(_handler)


# Values made of these characters are written bare; anything else is
# quoted and escaped. The set covers what this app actually logs unquoted
# -- integers, IPv4/IPv6 addresses, emails, usernames, endpoint names --
# so the common line keeps exactly the shape greps were written against.
# Note \w is Unicode-aware here, so a Turkish or Greek username still logs
# bare; the characters that force quoting are the ones with no business
# being in a log field.
_BARE_VALUE = re.compile(r"\A[\w.:@/+-]*\Z")

# Long enough for any legitimate field this app logs (usernames cap at 50
# on registration), short enough that a caller can't turn one request into
# a megabyte of log. /auth/login is the reason for the cap: it reads its
# username straight off an OAuth2 form, which imposes no length limit at
# all.
MAX_VALUE_LENGTH = 200


def _render(value: object) -> str:
    """Renders one field value safely (v0.1.7).

    The problem this solves: values went into the line verbatim, and
    /auth/login logs a username it never validated. A username containing
    a newline therefore wrote a second line into the log -- one an
    attacker composed. Since these logs exist precisely to be read after
    an incident, and SECURITY.md's A09 answer is "the events, in a
    consistent greppable shape", forged events are not a cosmetic
    problem: they are the failure of the control itself. Anything an
    attacker can write into an audit trail, they can write to say the
    opposite of what happened.

    repr() does the escaping because it is the standard, reversible
    answer: newlines become \\n, control characters and non-printables
    (terminal escape sequences, bidirectional overrides) become numeric
    escapes, and the result is unambiguously delimited by quotes. Values
    that need none of that are passed through bare, so `user_id=5` and
    `ip=1.2.3.4` read exactly as they did before.
    """
    text = str(value)
    if len(text) > MAX_VALUE_LENGTH:
        # The marker contains a space, so a truncated value always ends up
        # quoted -- a reader can't mistake a cut-off value for a whole one.
        text = text[:MAX_VALUE_LENGTH] + " ...truncated"
    return text if _BARE_VALUE.match(text) else repr(text)


def log_event(event: str, **fields: object) -> None:
    """Logs a single structured security event, e.g.:
    log_event("login_failed", username="alice", ip="1.2.3.4")
    -> "login_failed username=alice ip=1.2.3.4"

    Field values are escaped when they contain anything that would break
    the one-event-per-line, key=value shape -- see _render. Field *names*
    need no such treatment: they arrive as Python keyword arguments, so
    they are already identifiers.
    """
    details = " ".join(f"{key}={_render(value)}" for key, value in fields.items())
    security_logger.info("%s %s", _render(event), details)
