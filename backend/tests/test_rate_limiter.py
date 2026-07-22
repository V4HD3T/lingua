"""RateLimiter internals (v0.1.5), focused on the attempt table's memory.

The bug: `check()` pruned expired timestamps only for the key it was
asked about, and no code path ever removed a key from `_attempts`. Every
distinct client address seen since process start kept an entry forever,
including entries pruned down to an empty list.

These are unit tests rather than endpoint tests on purpose. Through
TestClient every request resolves to the same rate-limit key (one fake
peer, and TRUSTED_PROXY_HOPS defaults to 0), so table *growth* -- which
is entirely about key cardinality -- can't be provoked from that level.

Timestamps are seeded directly in most tests to keep them deterministic
and fast; the last test drives the real clock end to end so the sweep is
proven to fire on its own rather than only when a test forces it.
"""

import threading
import time
from datetime import datetime, timedelta, timezone

from app.services.rate_limiter import RateLimiter, login_key


def _force_sweep_due(limiter: RateLimiter) -> None:
    """Makes the next check() sweep, without waiting out a real window."""
    limiter._next_sweep = datetime.now(timezone.utc) - timedelta(seconds=1)


def _seed(limiter: RateLimiter, key: str, *ages_in_seconds: float) -> None:
    """Gives `key` an attempt history at the given ages (oldest first, as
    check() appends in chronological order)."""
    now = datetime.now(timezone.utc)
    limiter._attempts[key] = [now - timedelta(seconds=age) for age in sorted(ages_in_seconds, reverse=True)]


# --- what the sweep collects -------------------------------------------------


def test_keys_whose_attempts_all_expired_are_dropped():
    limiter = RateLimiter(max_attempts=5, window_seconds=60)
    _seed(limiter, "gone-quiet", 120, 90)
    _force_sweep_due(limiter)

    limiter.check("someone-else")

    assert "gone-quiet" not in limiter._attempts


def test_keys_pruned_to_an_empty_list_are_dropped():
    # The shape the old code left behind most often: check() filtered the
    # timestamps away but kept the key.
    limiter = RateLimiter(max_attempts=5, window_seconds=60)
    limiter._attempts["emptied"] = []
    _force_sweep_due(limiter)

    limiter.check("someone-else")

    assert "emptied" not in limiter._attempts


def test_keys_with_a_live_attempt_survive_the_sweep():
    limiter = RateLimiter(max_attempts=5, window_seconds=60)
    _seed(limiter, "still-active", 120, 5)  # one expired, one inside the window
    _force_sweep_due(limiter)

    limiter.check("someone-else")

    assert "still-active" in limiter._attempts


# --- the sweep must never be a way out of a limit ----------------------------


def test_a_throttled_key_is_still_throttled_after_a_sweep():
    """The property that rules out an LRU/size-cap design: an attacker
    generating keys must not be able to evict their own live entry and
    start a fresh budget."""
    limiter = RateLimiter(max_attempts=2, window_seconds=60)
    assert limiter.check("attacker") is True
    assert limiter.check("attacker") is True
    assert limiter.check("attacker") is False  # budget spent

    _force_sweep_due(limiter)
    limiter.check("noise")  # triggers the sweep

    assert limiter.check("attacker") is False, "sweep handed back a fresh budget"


def test_sweeping_never_changes_a_limiting_decision():
    """A swept key and an unswept key with the same expired history must
    answer identically -- the sweep is a memory optimisation, not a
    behaviour change."""
    swept = RateLimiter(max_attempts=3, window_seconds=60)
    unswept = RateLimiter(max_attempts=3, window_seconds=60)
    for limiter in (swept, unswept):
        _seed(limiter, "returning-visitor", 300, 200, 100)  # all outside the window

    _force_sweep_due(swept)
    swept.check("noise")

    # Both should now grant the full budget and refuse the one after it.
    for limiter in (swept, unswept):
        assert [limiter.check("returning-visitor") for _ in range(4)] == [
            True,
            True,
            True,
            False,
        ]


def test_reset_still_clears_a_single_key():
    limiter = RateLimiter(max_attempts=1, window_seconds=60)
    limiter.check("user")
    assert limiter.check("user") is False
    limiter.reset("user")
    assert limiter.check("user") is True


# --- how often it runs -------------------------------------------------------


def test_sweep_runs_at_most_once_per_window(monkeypatch):
    limiter = RateLimiter(max_attempts=1000, window_seconds=60)
    sweeps = []
    original = limiter._sweep

    def counting_sweep(cutoff):
        sweeps.append(cutoff)
        original(cutoff)

    monkeypatch.setattr(limiter, "_sweep", counting_sweep)

    _force_sweep_due(limiter)
    for _ in range(50):
        limiter.check("chatty")

    assert len(sweeps) == 1, f"swept {len(sweeps)} times across 50 checks"


def test_tracked_keys_reports_the_table_size():
    limiter = RateLimiter(max_attempts=5, window_seconds=60)
    assert limiter.tracked_keys == 0
    for i in range(7):
        limiter.check(f"10.0.0.{i}")
    assert limiter.tracked_keys == 7


# --- concurrency -------------------------------------------------------------


def test_concurrent_checks_during_a_sweep_do_not_corrupt_the_table():
    """A sweep deletes from the same dict other threads are checking
    against. It builds its victim list before deleting and holds the lock
    throughout; this fails loudly ("dictionary changed size during
    iteration") if either ever stops being true."""
    limiter = RateLimiter(max_attempts=1000, window_seconds=60)
    errors = []

    def hammer(worker: int) -> None:
        try:
            for i in range(200):
                if i % 50 == 0:
                    _force_sweep_due(limiter)
                limiter.check(f"worker-{worker}-key-{i}")
        except Exception as exc:  # noqa: BLE001 -- the assertion is "nothing raised"
            errors.append(exc)

    threads = [threading.Thread(target=hammer, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, errors


# --- the real clock ----------------------------------------------------------


def test_table_shrinks_on_its_own_once_a_window_passes():
    """End to end with no test-forced sweep: the table grows with distinct
    keys, then collapses by itself after a window. This is the bounded
    behaviour the fix claims -- memory tracks keys seen *in a window*, not
    keys seen ever."""
    limiter = RateLimiter(max_attempts=5, window_seconds=1)

    for i in range(500):
        limiter.check(f"10.0.{i // 256}.{i % 256}")
    assert limiter.tracked_keys == 500

    time.sleep(1.1)  # every attempt above is now outside the window
    limiter.check("the-next-request-that-happens-along")

    assert limiter.tracked_keys == 1


# --- testing a budget without spending from it (v0.1.6) ----------------------


def test_is_exhausted_does_not_consume_budget():
    limiter = RateLimiter(max_attempts=2, window_seconds=60)
    for _ in range(10):
        assert limiter.is_exhausted("quiet") is False
    # All ten questions asked, none of them charged.
    assert limiter.check("quiet") is True
    assert limiter.check("quiet") is True
    assert limiter.check("quiet") is False


def test_is_exhausted_does_not_create_a_table_entry():
    limiter = RateLimiter(max_attempts=2, window_seconds=60)
    limiter.is_exhausted("never-seen")
    assert limiter.tracked_keys == 0


def test_record_consumes_budget_without_reporting():
    limiter = RateLimiter(max_attempts=2, window_seconds=60)
    limiter.record("noisy")
    limiter.record("noisy")
    assert limiter.is_exhausted("noisy") is True


# --- login keys --------------------------------------------------------------


def test_login_key_folds_username_case():
    assert login_key("10.0.0.1", "Casey") == login_key("10.0.0.1", "cAsEy")


def test_login_key_separates_by_address_and_username():
    assert login_key("10.0.0.1", "casey") != login_key("10.0.0.2", "casey")
    assert login_key("10.0.0.1", "casey") != login_key("10.0.0.1", "dana")


def test_login_key_cannot_be_confused_across_pairs():
    """A printable separator like ":" would render these two pairs as the
    same string, letting one pair spend another's budget."""
    assert login_key("10.0.0.1", "2:carol") != login_key("10.0.0.1:2", "carol")
