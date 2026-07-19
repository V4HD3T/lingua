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
"""

import logging

security_logger = logging.getLogger("lingua.security")
security_logger.setLevel(logging.INFO)

if not security_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    security_logger.addHandler(_handler)


def log_event(event: str, **fields: object) -> None:
    """Logs a single structured security event, e.g.:
    log_event("login_failed", username="alice", ip="1.2.3.4")
    -> "login_failed username=alice ip=1.2.3.4"
    """
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    security_logger.info("%s %s", event, details)
