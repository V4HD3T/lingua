"""Security log rendering (v0.1.7).

The bug: field values went into the line verbatim, and /auth/login logs a
username it never validates -- OAuth2PasswordRequestForm imposes no
length, charset, or content rules. A username containing a newline
therefore wrote an extra line into the security log, composed by whoever
sent the request.

These logs exist to be read after an incident, and SECURITY.md's A09
answer is "the events, in a consistent greppable shape". Forged events
aren't a formatting nuisance in that context: they defeat the control.

Splitting the assertions two ways on purpose -- _render is unit-tested
for what it escapes, and the login endpoint is tested end to end, because
the vulnerable value arrives through a form field with no schema in front
of it and no unit test would notice if that path changed.
"""

import logging

from app.services.security_logging import MAX_VALUE_LENGTH, _render, log_event

SECURITY_LOGGER = "lingua.security"


# --- what gets escaped -------------------------------------------------------


def test_newlines_are_escaped_not_emitted():
    rendered = _render("alice\nlogin_succeeded user_id=1")
    assert "\n" not in rendered
    assert "\\n" in rendered


def test_carriage_returns_are_escaped():
    # \r alone still starts a new line in plenty of log viewers.
    rendered = _render("alice\rlogin_succeeded user_id=1")
    assert "\r" not in rendered
    assert "\\r" in rendered


def test_terminal_escape_sequences_are_escaped():
    # Logs get read with cat/less. A raw ESC lets a value repaint or clear
    # the reader's terminal.
    rendered = _render("alice\x1b[2Jcleared")
    assert "\x1b" not in rendered


def test_bidirectional_overrides_are_escaped():
    # U+202E reverses display order, so a value can render as something
    # other than what it is.
    rendered = _render("alice‮gnol")
    assert "‮" not in rendered


def test_nul_bytes_are_escaped():
    # The login rate-limit key is "<address>\x00<username>", so this value
    # reaches the log via enforce_rate_limit's key= field.
    rendered = _render("10.0.0.1\x00victim")
    assert "\x00" not in rendered


# --- what stays readable -----------------------------------------------------


def test_ordinary_values_are_written_bare():
    """Guards the existing line format: these are what greps were written
    against, and quoting them all would silently break every one."""
    assert _render(5) == "5"
    assert _render("alice") == "alice"
    assert _render("1.2.3.4") == "1.2.3.4"
    assert _render("2001:db8::1") == "2001:db8::1"
    assert _render("alice@example.com") == "alice@example.com"
    assert _render("login_ip") == "login_ip"


def test_non_ascii_usernames_stay_bare():
    # A Turkish username is a perfectly ordinary value; escaping it would
    # make the logs of this project's own author's language unreadable.
    assert _render("şeyma") == "şeyma"
    assert _render("Ωμέγα") == "Ωμέγα"


def test_values_with_spaces_are_quoted():
    # A space would otherwise read as the start of the next key=value pair.
    assert _render("two words") == "'two words'"


# --- length ------------------------------------------------------------------


def test_overlong_values_are_truncated_and_marked():
    rendered = _render("a" * (MAX_VALUE_LENGTH + 5000))
    assert len(rendered) < MAX_VALUE_LENGTH + 60
    assert "truncated" in rendered


def test_values_at_the_limit_are_not_marked_truncated():
    assert "truncated" not in _render("a" * MAX_VALUE_LENGTH)


# --- the assembled line ------------------------------------------------------


def test_a_forged_event_cannot_become_its_own_line(caplog):
    with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER):
        log_event("login_failed", username="alice\nlogin_succeeded user_id=1", ip="1.2.3.4")

    messages = [r.getMessage() for r in caplog.records if r.name == SECURITY_LOGGER]
    assert len(messages) == 1
    assert "\n" not in messages[0]
    assert messages[0].startswith("login_failed ")


def test_ordinary_event_line_is_unchanged(caplog):
    with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER):
        log_event("login_failed", username="alice", ip="1.2.3.4")

    messages = [r.getMessage() for r in caplog.records if r.name == SECURITY_LOGGER]
    assert messages == ["login_failed username=alice ip=1.2.3.4"]


# --- end to end through the endpoint that carries the unvalidated value ------


def test_login_with_a_forging_username_writes_exactly_one_line(client, caplog):
    forged = "alice\n2026-01-01 00:00:00 INFO login_succeeded user_id=1 username=admin"

    with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER):
        response = client.post("/auth/login", data={"username": forged, "password": "wrong"})
    assert response.status_code == 401

    messages = [r.getMessage() for r in caplog.records if r.name == SECURITY_LOGGER]
    assert messages, "the failed login logged no event at all"

    lines = [line for message in messages for line in message.splitlines()]
    assert len(lines) == len(messages), "an event was split across lines"
    assert not any(line.startswith("login_succeeded") for line in lines)


def test_login_with_an_enormous_username_does_not_flood_the_log(client, caplog):
    # The login form imposes no length limit, so without the cap one
    # request writes as much log as the caller cares to send.
    with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER):
        client.post("/auth/login", data={"username": "a" * 100_000, "password": "wrong"})

    messages = [r.getMessage() for r in caplog.records if r.name == SECURITY_LOGGER]
    assert messages
    assert all(len(message) < 1000 for message in messages)
