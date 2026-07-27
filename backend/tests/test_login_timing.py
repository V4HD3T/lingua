"""`/auth/login` takes the same time whether or not the account exists
(v0.1.18).

The error message is deliberately generic -- "Incorrect username or
password", never which of the two was wrong. Before this, the clock said
what the message would not: bcrypt only ran when the lookup found
somebody, so a real account cost ~200 ms and an invented one ~5 ms.
"""

import time

import pytest

from app.services.rate_limiter import login_ip_rate_limiter, login_rate_limiter

PASSWORD = "correct horse battery"


@pytest.fixture
def registered(client):
    client.post(
        "/auth/register",
        json={
            "username": "ada",
            "email": "ada@example.com",
            "password": PASSWORD,
            "native_language": "en",
        },
    )
    # Registration itself hashes, which warms passlib's dummy hash lazily
    # if nothing else has; make that explicit so the first measurement
    # below isn't paying for it.
    from app.security import warm_password_hasher

    warm_password_hasher()
    return client


def _failed_login(client, username):
    login_ip_rate_limiter.clear_all()
    login_rate_limiter.clear_all()
    response = client.post(
        "/auth/login", data={"username": username, "password": "not-the-password"}
    )
    assert response.status_code == 401
    return response


def test_the_hashing_work_is_spent_for_a_username_that_does_not_exist(
    registered, monkeypatch
):
    """The deterministic half: assert the mechanism rather than the clock,
    since a wall-clock assertion on a shared CI runner is the kind of test
    that fails for reasons unrelated to the thing it guards."""
    calls = []
    import app.routers.auth as auth_module

    monkeypatch.setattr(auth_module, "dummy_verify", lambda: calls.append(1))

    _failed_login(registered, "no-such-user")
    assert calls == [1], "unknown username skipped the hashing work"


def test_the_work_is_not_charged_twice_for_a_real_account(registered, monkeypatch):
    """The other direction: a real account must verify its own hash and
    *not* also run the dummy, or an existing user's login would cost
    double and the signal would simply invert."""
    calls = []
    import app.routers.auth as auth_module

    monkeypatch.setattr(auth_module, "dummy_verify", lambda: calls.append(1))

    _failed_login(registered, "ada")
    assert calls == []


def test_both_answers_are_identical(registered):
    known = _failed_login(registered, "ada")
    unknown = _failed_login(registered, "no-such-user")
    assert known.json() == unknown.json()
    assert known.status_code == unknown.status_code


def test_the_two_take_comparably_long(registered):
    """The property itself, measured. Deliberately loose: the guarantee
    worth protecting is "same order of magnitude", and the bug this
    replaces sat at ~2.5% (5 ms against 200 ms), so a 25% floor still
    catches it with a 10x margin while surviving a noisy runner.

    Minimum of several samples rather than a mean -- scheduler noise only
    ever makes a sample slower, so the floor is the honest estimate of
    what the work actually costs.
    """

    def fastest(username, samples=5):
        return min(
            (lambda t0: (_failed_login(registered, username), time.perf_counter() - t0)[1])(
                time.perf_counter()
            )
            for _ in range(samples)
        )

    known = fastest("ada")
    unknown = fastest("no-such-user")

    assert unknown >= known * 0.25, (
        f"unknown-username login was {known / unknown:.0f}x faster "
        f"({unknown * 1000:.1f} ms vs {known * 1000:.1f} ms) -- the response "
        "time distinguishes accounts that exist from ones that don't"
    )
