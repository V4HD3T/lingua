"""`/translate`'s language codes are validated at the edge (v0.1.17).

They were the one user-supplied field in the app that nothing checked,
and they reach further than they look: into the database verbatim, into
the shared Redis cache key, and -- once the real model is active -- into
the tokenizer.
"""

import pytest
from sqlmodel import Session, select

from app.models import Language, TranslationHistory
from app.schemas import SUPPORTED_LANGUAGE_CODES
from app.services.translation_cache import TranslationCache


def _translate(client, source="en", target="es", text="hello"):
    return client.post(
        "/translate", json={"text": text, "source_lang": source, "target_lang": target}
    )


def test_every_supported_code_is_accepted(client):
    for code in sorted(SUPPORTED_LANGUAGE_CODES):
        assert _translate(client, source=code).status_code == 200, code
        assert _translate(client, target=code).status_code == 200, code


@pytest.mark.parametrize(
    "code",
    [
        "xx",                 # well-formed but unknown
        "A" * 500,            # unbounded: was stored in the database at full length
        "en:es",              # the separator the cache key is built with
        "../../etc/passwd",
        "eng_Latn",           # the NLLB-internal spelling, not this API's
    ],
)
def test_unknown_codes_are_refused(client, code, session: Session):
    assert _translate(client, source=code).status_code == 422
    assert _translate(client, target=code).status_code == 422
    # Nothing reached the history table on the way to being rejected.
    assert session.exec(select(TranslationHistory)).all() == []


def test_the_ui_catalogue_never_offers_a_code_translate_would_refuse(
    client, session: Session
):
    """The Language table is the dropdown's source and is admin-editable,
    while the engine's set is fixed. If the two ever drift apart the
    frontend offers a language that 422s -- so assert the containment
    rather than trusting the seed data to stay put."""
    catalogue = {row.code for row in session.exec(select(Language)).all()}
    assert catalogue, "seed data should have populated the catalogue"
    assert catalogue <= SUPPORTED_LANGUAGE_CODES


def test_detected_codes_are_always_translatable(client):
    """The auto-detect flow feeds `detect_language`'s answer straight back
    in as source_lang, so the classifier's output set has to be a subset
    of what translate accepts. It is restricted to exactly the engine's
    set -- this pins that it stays so."""
    from app.services.language_detection import _identifier

    detectable = set(_identifier.nb_classes)
    assert detectable <= SUPPORTED_LANGUAGE_CODES

    detected = client.post(
        "/detect-language", json={"text": "This is an unambiguous English sentence."}
    ).json()
    assert _translate(client, source=detected["language_code"]).status_code == 200


def test_cache_keys_are_now_unambiguous():
    """The key is `...:{source}:{target}:{digest}`, colon-joined without
    escaping, so ("a", "b:c") and ("a:b", "c") collided. Validation is
    what closes it: a code containing a colon can no longer get this far.
    Asserting the property at its root -- no supported code contains the
    separator -- rather than asserting the two crafted inputs are refused
    twice over."""
    assert not any(":" in code for code in SUPPORTED_LANGUAGE_CODES)

    cache = TranslationCache(None, 60)
    keys = {
        cache._key(source, target, "hello")
        for source in SUPPORTED_LANGUAGE_CODES
        for target in SUPPORTED_LANGUAGE_CODES
    }
    assert len(keys) == len(SUPPORTED_LANGUAGE_CODES) ** 2
