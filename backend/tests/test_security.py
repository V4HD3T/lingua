import re

from starlette.requests import Request

from app.config import settings
from app.services.email_service import get_email_service
from app.services.rate_limiter import client_ip


def _register_and_login(client, username="secuser", email="secuser@example.com", password="password1234"):
    client.post("/auth/register", json={"username": username, "email": email, "password": password})
    login = client.post("/auth/login", data={"username": username, "password": password})
    return login.json()


# --- Rate limiting ---


def test_login_rate_limited_after_too_many_attempts(client):
    client.post(
        "/auth/register",
        json={"username": "ratelimited", "email": "ratelimited@example.com", "password": "correct-password"},
    )
    for _ in range(5):
        response = client.post(
            "/auth/login", data={"username": "ratelimited", "password": "wrong-password"}
        )
        assert response.status_code == 401

    sixth = client.post("/auth/login", data={"username": "ratelimited", "password": "wrong-password"})
    assert sixth.status_code == 429


def test_successful_login_resets_rate_limit(client):
    client.post(
        "/auth/register",
        json={"username": "retryok", "email": "retryok@example.com", "password": "correct-password"},
    )
    for _ in range(4):
        client.post("/auth/login", data={"username": "retryok", "password": "wrong-password"})

    success = client.post("/auth/login", data={"username": "retryok", "password": "correct-password"})
    assert success.status_code == 200

    # the failed attempts before the success shouldn't count against the
    # limit anymore
    again = client.post("/auth/login", data={"username": "retryok", "password": "correct-password"})
    assert again.status_code == 200


def test_logging_in_as_yourself_does_not_clear_another_accounts_failures(client):
    """The v0.1.6 bypass, end to end.

    Login used to be limited per address, and a success reset that whole
    address. So an attacker holding any account of their own could spend
    guesses on a victim, log in as themselves to zero the counter, and go
    again -- turning 5/min into roughly the global backstop's 120/min.
    """
    client.post(
        "/auth/register",
        json={"username": "victim", "email": "victim@example.com", "password": "victim-password"},
    )
    client.post(
        "/auth/register",
        json={"username": "attacker", "email": "attacker@example.com", "password": "attacker-password"},
    )

    for _ in range(4):
        guess = client.post("/auth/login", data={"username": "victim", "password": "wrong"})
        assert guess.status_code == 401

    # The attacker's own, entirely legitimate login.
    own = client.post(
        "/auth/login", data={"username": "attacker", "password": "attacker-password"}
    )
    assert own.status_code == 200

    # The victim's budget must be exactly where it was left: one guess
    # remaining, then throttled.
    assert (
        client.post("/auth/login", data={"username": "victim", "password": "wrong"}).status_code
        == 401
    )
    blocked = client.post("/auth/login", data={"username": "victim", "password": "wrong"})
    assert blocked.status_code == 429, "logging in as another account restored the victim's budget"


def test_username_case_does_not_mint_a_fresh_budget(client):
    # The pair key folds case, so capitalisation can't be used to open a
    # second budget against the same account.
    client.post(
        "/auth/register",
        json={"username": "casey", "email": "casey@example.com", "password": "casey-password"},
    )
    for variant in ("casey", "CASEY", "Casey", "cAsEy", "casEY"):
        assert (
            client.post("/auth/login", data={"username": variant, "password": "wrong"}).status_code
            == 401
        )

    blocked = client.post("/auth/login", data={"username": "CaSeY", "password": "wrong"})
    assert blocked.status_code == 429


def test_spraying_many_usernames_from_one_address_is_capped(client, monkeypatch):
    """Keying the budget per (address, username) is what fixes the reset
    bypass -- but on its own it would hand one address 5 guesses per
    username and no total cap at all. The address-wide failure budget is
    the other half of that fix; each username below is distinct, so only
    it can produce a 429."""
    from app.services.rate_limiter import login_ip_rate_limiter

    monkeypatch.setattr(login_ip_rate_limiter, "max_attempts", 6)
    statuses = [
        client.post(
            "/auth/login", data={"username": f"sprayed{i}", "password": "one-common-password"}
        ).status_code
        for i in range(10)
    ]
    assert 429 in statuses, f"spraying was never throttled: {statuses}"


def test_successful_logins_do_not_consume_the_address_failure_budget(client, monkeypatch):
    """Only failures are charged, which is what makes the address budget
    safe to set tight: a shared address (office NAT, mobile CGNAT) doesn't
    accumulate one just by being busy."""
    from app.services.rate_limiter import login_ip_rate_limiter

    monkeypatch.setattr(login_ip_rate_limiter, "max_attempts", 3)
    client.post(
        "/auth/register",
        json={"username": "busy", "email": "busy@example.com", "password": "busy-password1"},
    )
    for _ in range(10):
        assert (
            client.post(
                "/auth/login", data={"username": "busy", "password": "busy-password1"}
            ).status_code
            == 200
        )


def test_register_rate_limited_after_too_many_attempts(client):
    for i in range(5):
        client.post(
            "/auth/register",
            json={"username": f"burst{i}", "email": f"burst{i}@example.com", "password": "password1234"},
        )
    sixth = client.post(
        "/auth/register",
        json={"username": "burst5", "email": "burst5@example.com", "password": "password1234"},
    )
    assert sixth.status_code == 429


# --- Refresh tokens ---


def test_login_returns_refresh_token(client):
    tokens = _register_and_login(client)
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["refresh_token"] != tokens["access_token"]


def test_refresh_returns_a_working_new_access_token(client):
    tokens = _register_and_login(client, username="refresher", email="refresher@example.com")
    response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200
    new_access_token = response.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {new_access_token}"})
    assert me.status_code == 200


def test_refresh_with_garbage_token_fails(client):
    response = client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401


def test_refresh_rotates_token_old_one_stops_working(client, no_refresh_grace):
    tokens = _register_and_login(client, username="rotator", email="rotator@example.com")
    old_refresh = tokens["refresh_token"]

    first_refresh = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert first_refresh.status_code == 200

    # the old refresh token was single-use; using it again should fail
    # (and per the reuse-detection below, revokes everything)
    second_attempt = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert second_attempt.status_code == 401


def test_reusing_revoked_refresh_token_kills_all_sessions(client, no_refresh_grace):
    tokens = _register_and_login(client, username="thief-target", email="thieftarget@example.com")
    old_refresh = tokens["refresh_token"]

    rotated = client.post("/auth/refresh", json={"refresh_token": old_refresh}).json()
    new_refresh = rotated["refresh_token"]

    # replay the OLD (now-revoked) refresh token, simulating a stolen token
    # being used after the legitimate client already rotated past it
    client.post("/auth/refresh", json={"refresh_token": old_refresh})

    # the legitimate, rotated token should now ALSO be dead as a precaution
    response = client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert response.status_code == 401


# --- v0.1.8: the grace window for a just-rotated token ----------------------
#
# Both of the tests above replay a token milliseconds after rotating it,
# which is now exactly what a browser with two tabs open does. They take
# the `no_refresh_grace` fixture so they still assert what they were
# written to assert -- that a replay OUTSIDE the window is treated as
# theft. The tests below cover inside it.


def test_two_tabs_refreshing_at_once_does_not_kill_the_session(client):
    """The bug: two tabs share one localStorage, refresh independently,
    and both present the same token. That was indistinguishable from
    theft, so an ordinary second tab logged the user out everywhere."""
    tokens = _register_and_login(client, username="twotabs", email="twotabs@example.com")
    shared_refresh = tokens["refresh_token"]

    tab_one = client.post("/auth/refresh", json={"refresh_token": shared_refresh})
    tab_two = client.post("/auth/refresh", json={"refresh_token": shared_refresh})

    assert tab_one.status_code == 200
    assert tab_two.status_code == 200, "the second tab was treated as a token thief"

    # Both tabs come away with a working session, and neither token was
    # collateral damage from the other.
    for issued in (tab_one.json(), tab_two.json()):
        me = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {issued['access_token']}"}
        )
        assert me.status_code == 200
        assert client.post(
            "/auth/refresh", json={"refresh_token": issued["refresh_token"]}
        ).status_code == 200


def test_grace_does_not_apply_to_a_token_revoked_by_logout(client):
    """Logout has to bite immediately. If the window forgave any revoked
    token rather than specifically a rotated one, a stale tab could
    resurrect a session the user had just deliberately ended."""
    tokens = _register_and_login(client, username="loggedout", email="loggedout@example.com")
    client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})

    replayed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replayed.status_code == 401


def test_grace_does_not_apply_after_a_password_reset(client):
    """Same reasoning, and the case that matters most: a password reset is
    what someone does when they believe they've been compromised."""
    tokens = _register_and_login(client, username="resetter", email="resetter@example.com")
    get_email_service().sent_emails.clear()
    client.post("/auth/request-password-reset", json={"email": "resetter@example.com"})
    token = re.search(r"token=([\w-]+)", get_email_service().sent_emails[0].body).group(1)
    client.post("/auth/reset-password", json={"token": token, "new_password": "brand-new-pass1"})

    replayed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replayed.status_code == 401


def test_grace_does_not_apply_after_logout_all(client):
    tokens = _register_and_login(client, username="everywhere", email="everywhere@example.com")
    client.post(
        "/auth/logout-all", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    replayed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replayed.status_code == 401


def test_replay_after_the_grace_window_still_kills_every_session(client, no_refresh_grace):
    """The property the window trades against, pinned explicitly: once the
    window has passed, a replayed token is theft and takes the whole
    session with it."""
    tokens = _register_and_login(client, username="latethief", email="latethief@example.com")
    rotated = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).json()

    client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert (
        client.post("/auth/refresh", json={"refresh_token": rotated["refresh_token"]}).status_code
        == 401
    )


def test_logout_revokes_refresh_token(client):
    tokens = _register_and_login(client, username="loggerouter", email="loggerouter@example.com")
    logout = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout.status_code == 200

    response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


def test_logout_all_revokes_every_session(client):
    tokens_a = _register_and_login(client, username="multisession", email="multisession@example.com")
    login2 = client.post("/auth/login", data={"username": "multisession", "password": "password1234"})
    tokens_b = login2.json()

    headers = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    response = client.post("/auth/logout-all", headers=headers)
    assert response.status_code == 200

    refresh_a = client.post("/auth/refresh", json={"refresh_token": tokens_a["refresh_token"]})
    refresh_b = client.post("/auth/refresh", json={"refresh_token": tokens_b["refresh_token"]})
    assert refresh_a.status_code == 401
    assert refresh_b.status_code == 401


# --- Email verification ---


def test_new_user_is_not_verified_by_default(client):
    tokens = _register_and_login(client, username="unverified", email="unverified@example.com")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.json()["is_verified"] is False


def test_register_sends_verification_email(client):
    client.post(
        "/auth/register",
        json={"username": "emailcheck", "email": "emailcheck@example.com", "password": "password1234"},
    )
    sent = get_email_service().sent_emails
    assert len(sent) == 1
    assert sent[0].to == "emailcheck@example.com"
    assert "verify-email?token=" in sent[0].body


def test_verify_email_with_token_from_sent_email(client):
    client.post(
        "/auth/register",
        json={"username": "verifyme", "email": "verifyme@example.com", "password": "password1234"},
    )
    sent = get_email_service().sent_emails
    token = re.search(r"token=([\w-]+)", sent[0].body).group(1)

    response = client.post("/auth/verify-email", json={"token": token})
    assert response.status_code == 200

    login = client.post("/auth/login", data={"username": "verifyme", "password": "password1234"})
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["is_verified"] is True


def test_verify_email_with_invalid_token_fails(client):
    response = client.post("/auth/verify-email", json={"token": "not-a-real-token"})
    assert response.status_code == 400


# --- v0.1.12: verification stays informational, but becomes visible ---------
#
# Enforcement was considered and deliberately not adopted -- see
# SECURITY.md's A07 section. What changed is that the app now tells people
# where they stand, and a status you can't act on would be worse than
# silence: the registration link is the only one that ever existed and it
# expires after 24 hours.


def test_unverified_account_can_use_the_whole_app(client, take_seed_quiz):
    """Pins the decision rather than leaving it implied. If someone later
    adds a verification gate, this fails and forces the choice to be made
    again on purpose."""
    tokens = _register_and_login(client, username="unenforced", email="unenforced@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/auth/me", headers=headers).json()["is_verified"] is False

    assert client.post(
        "/translate",
        json={"text": "hello there", "source_lang": "en", "target_lang": "es"},
        headers=headers,
    ).status_code == 200
    assert take_seed_quiz(headers).status_code == 200
    assert client.post("/vocabulary/1/review", json={"quality": 4}, headers=headers).status_code == 200
    assert client.get("/users/me/stats", headers=headers).status_code == 200


def test_resend_verification_sends_a_fresh_working_link(client):
    tokens = _register_and_login(client, username="resender", email="resender@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    get_email_service().sent_emails.clear()  # drop the registration email

    response = client.post("/auth/resend-verification", headers=headers)
    assert response.status_code == 200

    sent = get_email_service().sent_emails
    assert len(sent) == 1
    assert sent[0].to == "resender@example.com"
    token = re.search(r"token=([\w-]+)", sent[0].body).group(1)
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    assert client.get("/auth/me", headers=headers).json()["is_verified"] is True


def test_resending_retires_the_previous_link(client):
    """Exactly one live link at a time: an older one left working would
    outlive the reason someone asked for a new one."""
    tokens = _register_and_login(client, username="tworeq", email="tworeq@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    first_token = re.search(
        r"token=([\w-]+)", get_email_service().sent_emails[0].body
    ).group(1)

    get_email_service().sent_emails.clear()
    client.post("/auth/resend-verification", headers=headers)
    second_token = re.search(
        r"token=([\w-]+)", get_email_service().sent_emails[0].body
    ).group(1)

    assert first_token != second_token
    assert client.post("/auth/verify-email", json={"token": first_token}).status_code == 400
    assert client.post("/auth/verify-email", json={"token": second_token}).status_code == 200


def test_resend_is_a_no_op_once_verified(client):
    tokens = _register_and_login(client, username="alreadyok", email="alreadyok@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    token = re.search(r"token=([\w-]+)", get_email_service().sent_emails[0].body).group(1)
    client.post("/auth/verify-email", json={"token": token})

    get_email_service().sent_emails.clear()
    response = client.post("/auth/resend-verification", headers=headers)
    assert response.status_code == 200
    assert get_email_service().sent_emails == []


def test_resend_requires_a_session(client):
    # No email parameter exists, so this can't be pointed at someone
    # else's address -- but it must still refuse anonymous callers.
    assert client.post("/auth/resend-verification").status_code == 401


def test_resend_is_rate_limited_per_account(client):
    tokens = _register_and_login(client, username="spamsend", email="spamsend@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    statuses = [
        client.post("/auth/resend-verification", headers=headers).status_code for _ in range(5)
    ]
    assert 429 in statuses, statuses


def test_verify_email_token_is_single_use(client):
    client.post(
        "/auth/register",
        json={"username": "onceonly", "email": "onceonly@example.com", "password": "password1234"},
    )
    token = re.search(r"token=([\w-]+)", get_email_service().sent_emails[0].body).group(1)

    first = client.post("/auth/verify-email", json={"token": token})
    assert first.status_code == 200
    second = client.post("/auth/verify-email", json={"token": token})
    assert second.status_code == 400


# --- Password reset ---


def test_request_password_reset_sends_email(client):
    client.post(
        "/auth/register",
        json={"username": "forgetful", "email": "forgetful@example.com", "password": "old-password1"},
    )
    get_email_service().sent_emails.clear()  # discard the verification email from registration

    response = client.post("/auth/request-password-reset", json={"email": "forgetful@example.com"})
    assert response.status_code == 200
    sent = get_email_service().sent_emails
    assert len(sent) == 1
    assert "reset-password?token=" in sent[0].body


def test_request_password_reset_for_unknown_email_gives_generic_response(client):
    # Same response either way -- revealing whether an email is registered
    # would let an attacker enumerate accounts.
    known = client.post(
        "/auth/register",
        json={"username": "known", "email": "known@example.com", "password": "password1234"},
    )
    known_response = client.post("/auth/request-password-reset", json={"email": "known@example.com"})
    unknown_response = client.post(
        "/auth/request-password-reset", json={"email": "nobody-here@example.com"}
    )
    assert known.status_code == 201
    assert known_response.status_code == unknown_response.status_code == 200
    assert known_response.json() == unknown_response.json()


def test_reset_password_with_valid_token_changes_password(client):
    client.post(
        "/auth/register",
        json={"username": "resetme", "email": "resetme@example.com", "password": "old-password1"},
    )
    get_email_service().sent_emails.clear()
    client.post("/auth/request-password-reset", json={"email": "resetme@example.com"})
    token = re.search(r"token=([\w-]+)", get_email_service().sent_emails[0].body).group(1)

    reset = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "brand-new-password1"}
    )
    assert reset.status_code == 200

    old_login = client.post("/auth/login", data={"username": "resetme", "password": "old-password1"})
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login", data={"username": "resetme", "password": "brand-new-password1"}
    )
    assert new_login.status_code == 200


def test_reset_password_revokes_existing_sessions(client):
    tokens = _register_and_login(client, username="sessionkiller", email="sessionkiller@example.com")
    get_email_service().sent_emails.clear()
    client.post("/auth/request-password-reset", json={"email": "sessionkiller@example.com"})
    token = re.search(r"token=([\w-]+)", get_email_service().sent_emails[0].body).group(1)

    client.post("/auth/reset-password", json={"token": token, "new_password": "another-new-password1"})

    response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


def test_reset_password_with_invalid_token_fails(client):
    response = client.post(
        "/auth/reset-password", json={"token": "not-a-real-token", "new_password": "whatever12"}
    )
    assert response.status_code == 400


# --- Security headers ---


def test_security_headers_present(client):
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "max-age" in response.headers["strict-transport-security"]


def test_data_routes_keep_the_strict_csp(client):
    """v0.1.10 loosens CSP for the documentation shell, which loads its
    bundle from a CDN. Every route that serves data must be untouched by
    that -- no CDN origin should appear anywhere else."""
    for path in ("/health", "/languages", "/courses"):
        csp = client.get(path).headers["content-security-policy"]
        assert csp == "default-src 'self'", path


def test_docs_csp_is_not_served_while_docs_are_disabled(client, monkeypatch):
    """The relaxed policy is gated on the feature being on, not merely on
    the path. With docs disabled these paths 404 -- and a 404 must not
    come back carrying a CDN allowance."""
    from app.config import settings

    assert settings.enable_api_docs is False
    response = client.get("/docs")
    assert response.status_code == 404
    assert response.headers["content-security-policy"] == "default-src 'self'"


def test_docs_csp_allows_the_swagger_bundle_when_enabled(client, monkeypatch):
    """And when they are on, the policy has to actually permit the assets
    the page loads -- otherwise /docs answers 200 and renders nothing,
    which is what it did from v0.0.8 until this version."""
    from app.config import settings

    monkeypatch.setattr(settings, "enable_api_docs", True)
    # Any path in the docs set: the header is decided by the middleware,
    # independently of whether this app instance mounted the route.
    csp = client.get("/docs").headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in csp

    # 'unsafe-inline' for scripts is required, not incidental: FastAPI
    # boots Swagger from an inline <script>. Dropping it puts the page
    # back to answering 200 and drawing nothing -- confirmed in a browser,
    # where the bundle loaded, defined SwaggerUIBundle, and never mounted.
    script_directive = [d for d in csp.split(";") if d.strip().startswith("script-src")][0]
    assert "'unsafe-inline'" in script_directive


# --- Optional-auth endpoints: invalid tokens must 401, not silently downgrade ---


def test_optional_auth_endpoint_rejects_invalid_token(client):
    # A *present but invalid* token is a 401, not a silent anonymous
    # downgrade. The frontend attaches its access token to these endpoints
    # and only knows to refresh the session when it sees a 401 -- silently
    # serving an anonymous 200 meant expired sessions kept "working" while
    # history saving and adaptive difficulty quietly switched off.
    response = client.post(
        "/translate",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"text": "hello there", "source_lang": "en", "target_lang": "es"},
    )
    assert response.status_code == 401


def test_optional_auth_endpoint_rejects_expired_token(client):
    from app.security import create_access_token

    _register_and_login(client, username="expiredsess", email="expiredsess@example.com")
    expired = create_access_token(subject="1", expires_minutes=-1)
    response = client.post(
        "/translate",
        headers={"Authorization": f"Bearer {expired}"},
        json={"text": "hello there", "source_lang": "en", "target_lang": "es"},
    )
    assert response.status_code == 401


def test_access_token_with_non_numeric_subject_is_rejected_cleanly(client):
    # A signed token whose `sub` isn't a well-formed user id should be a
    # clean 401, not an unhandled int() ValueError turning into a 500.
    from app.security import create_access_token

    weird = create_access_token(subject="definitely-not-a-user-id")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {weird}"})
    assert response.status_code == 401


# --- v0.0.8: app-wide + /translate rate limiting ---


def test_translate_endpoint_is_rate_limited(client, monkeypatch):
    from app.services.rate_limiter import translate_rate_limiter

    monkeypatch.setattr(translate_rate_limiter, "max_attempts", 3)
    payload = {"text": "hello", "source_lang": "en", "target_lang": "es"}
    for _ in range(3):
        assert client.post("/translate", json=payload).status_code == 200
    blocked = client.post("/translate", json=payload)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_general_api_rate_limit_backstop(client, monkeypatch):
    from app.services.rate_limiter import api_rate_limiter

    monkeypatch.setattr(api_rate_limiter, "max_attempts", 5)
    for _ in range(5):
        assert client.get("/languages").status_code == 200
    blocked = client.get("/languages")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_health_endpoint_is_exempt_from_general_rate_limit(client, monkeypatch):
    # Deployment platforms poll /health constantly; it must never 429.
    from app.services.rate_limiter import api_rate_limiter

    monkeypatch.setattr(api_rate_limiter, "max_attempts", 1)
    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_auth_rate_limit_response_includes_retry_after(client):
    for _ in range(5):
        client.post("/auth/login", data={"username": "ghost", "password": "wrong-password"})
    blocked = client.post("/auth/login", data={"username": "ghost", "password": "wrong-password"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


# --- v0.1.4: which address rate limiting actually keys on -------------------
#
# The bug: the image ran uvicorn with `--forwarded-allow-ips "*"`, which
# rewrites request.client from the *leftmost* X-Forwarded-For entry -- a
# value the caller writes. Sending a different one per request handed the
# caller a fresh budget on every per-IP limiter in the deployed app.
#
# Note on what these can and can't prove: uvicorn's ProxyHeadersMiddleware
# is installed by the *server*, not by app.main:app, so TestClient never
# runs it and cannot reproduce the original bypass -- these tests would
# have passed before the fix too. The flag itself is guarded where it
# actually lives, in tests/test_deployment_contracts.py. What's pinned
# here is the app-side resolution that replaced it: which entry of the
# chain becomes the rate-limit key, and that an unconfigured deployment
# ignores the header completely.


PEER = "203.0.113.7"  # the TCP peer -- in production, the proxy


def _request(peer=PEER, xff=None):
    """A Starlette Request with just enough scope for client_ip().

    `xff` may be a string (one header) or a list (several, as a client can
    legally send).
    """
    headers = []
    if xff is not None:
        for value in [xff] if isinstance(xff, str) else xff:
            headers.append((b"x-forwarded-for", value.encode()))
    return Request(
        {"type": "http", "method": "GET", "path": "/", "headers": headers,
         "client": (peer, 443) if peer else None}
    )


def test_forwarded_header_is_ignored_without_configured_proxies():
    # The default. No proxy is declared, so the header carries no
    # authority no matter what it says.
    assert client_ip(_request(xff="1.2.3.4")) == PEER


def test_one_proxy_takes_the_entry_that_proxy_appended(monkeypatch):
    # This is the whole fix: the proxy appends its own peer *last*, so
    # the rightmost entry is the only trustworthy one. "9.9.9.9" here is
    # the attacker's own invention, sent to be picked up as the client.
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    assert client_ip(_request(xff="9.9.9.9, 198.51.100.23")) == "198.51.100.23"


def test_two_proxies_count_further_in_from_the_right(monkeypatch):
    # CDN -> load balancer -> app: the LB appended the CDN's address, the
    # CDN appended the real client's.
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    chain = "9.9.9.9, 198.51.100.23, 192.0.2.60"
    assert client_ip(_request(xff=chain)) == "198.51.100.23"


def test_chain_split_across_several_headers_is_one_chain(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    assert client_ip(_request(xff=["9.9.9.9", "198.51.100.23"])) == "198.51.100.23"


def test_chain_shorter_than_configured_hops_falls_back_to_peer(monkeypatch):
    # The request didn't come through the proxies the config promises, so
    # the header proves nothing. Falling back to the peer over-limits
    # (everyone shares one bucket) instead of under-limiting.
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    assert client_ip(_request(xff="198.51.100.23")) == PEER
    assert client_ip(_request(xff=None)) == PEER


def test_unparseable_entry_falls_back_to_peer(monkeypatch):
    # Never let an arbitrary string become a rate-limit key or land in a
    # security log line as `ip=`.
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    for junk in ("not-an-ip", "", "127.0.0.1.5", "<script>", "1.2.3.4 5.6.7.8"):
        assert client_ip(_request(xff=f"9.9.9.9, {junk}")) == PEER


def test_ports_are_stripped_from_forwarded_entries(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    assert client_ip(_request(xff="198.51.100.23:51234")) == "198.51.100.23"
    assert client_ip(_request(xff="[2001:db8::1]:443")) == "2001:db8::1"
    assert client_ip(_request(xff="2001:db8::1")) == "2001:db8::1"


def test_respelling_an_ipv6_address_does_not_buy_a_second_budget(monkeypatch):
    # Same host, two spellings. Without normalization these would be two
    # separate dict keys, i.e. two separate rate-limit budgets.
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    assert client_ip(_request(xff="2001:db8:0:0:0:0:0:1")) == client_ip(
        _request(xff="2001:db8::1")
    )


def test_varying_the_forwarded_header_cannot_dodge_the_login_limiter(client):
    """End to end through the real app and middleware stack: with no
    proxy configured, a caller inventing a new address per request must
    still land in the same bucket."""
    client.post(
        "/auth/register",
        json={"username": "spoofed", "email": "spoofed@example.com", "password": "correct-password"},
    )
    statuses = [
        client.post(
            "/auth/login",
            data={"username": "spoofed", "password": "wrong-password"},
            headers={"X-Forwarded-For": f"10.0.0.{i}"},
        ).status_code
        for i in range(8)
    ]
    assert 429 in statuses, f"login limiter never engaged: {statuses}"


def test_varying_the_forwarded_header_cannot_dodge_the_translate_limiter(client, monkeypatch):
    from app.services.rate_limiter import translate_rate_limiter

    monkeypatch.setattr(translate_rate_limiter, "max_attempts", 3)
    payload = {"text": "hello", "source_lang": "en", "target_lang": "es"}
    statuses = [
        client.post(
            "/translate", json=payload, headers={"X-Forwarded-For": f"10.0.0.{i}"}
        ).status_code
        for i in range(6)
    ]
    assert 429 in statuses, f"translate limiter never engaged: {statuses}"
