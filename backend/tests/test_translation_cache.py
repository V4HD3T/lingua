"""Redis translation cache (v0.1.0): unit behaviour via a stub client, and
the endpoint contract -- a cache hit skips the model but must never skip
history recording, and a cache outage must never break translation."""

from app.services.translation_cache import TranslationCache, get_translation_cache
from app.services.translation_service import TranslationDetail, get_translation_service


class _StubRedis:
    """The two redis-py methods the cache uses, backed by a dict."""

    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value


class _FailingRedis:
    def get(self, key):
        raise ConnectionError("redis down")

    def setex(self, key, ttl, value):
        raise ConnectionError("redis down")


def _detail():
    return TranslationDetail(
        translated_text="[en->es] hi", confidence=0.9, alternatives=["[en->es] hi."]
    )


def test_disabled_cache_is_a_noop():
    cache = TranslationCache(None, ttl_seconds=60)
    assert cache.enabled is False
    assert cache.get("en", "es", "hi") is None
    cache.set("en", "es", "hi", _detail())  # must not raise


def test_roundtrip_via_stub():
    cache = TranslationCache(_StubRedis(), ttl_seconds=60)
    cache.set("en", "es", "hi", _detail())
    got = cache.get("en", "es", "hi")
    assert got is not None
    assert got.translated_text == "[en->es] hi"
    assert got.alternatives == ["[en->es] hi."]


def test_key_includes_language_pair():
    cache = TranslationCache(_StubRedis(), ttl_seconds=60)
    cache.set("en", "es", "hi", _detail())
    assert cache.get("en", "de", "hi") is None
    assert cache.get("tr", "es", "hi") is None


def test_corrupted_entry_is_a_miss():
    stub = _StubRedis()
    cache = TranslationCache(stub, ttl_seconds=60)
    cache.set("en", "es", "hi", _detail())
    corrupted_key = next(iter(stub.store))
    stub.store[corrupted_key] = "{not valid json"
    assert cache.get("en", "es", "hi") is None


def test_failures_degrade_to_cache_miss():
    cache = TranslationCache(_FailingRedis(), ttl_seconds=60)
    assert cache.get("en", "es", "hi") is None
    cache.set("en", "es", "hi", _detail())  # must not raise


class _CountingService:
    def __init__(self):
        self.calls = 0

    def translate_detailed(self, text, source_lang, target_lang):
        self.calls += 1
        return TranslationDetail(
            translated_text=f"[{source_lang}->{target_lang}] {text}",
            confidence=0.5,
            alternatives=[],
        )


def _register_and_login(client):
    client.post(
        "/auth/register",
        json={"username": "cacheuser", "email": "cacheuser@example.com", "password": "password1234"},
    )
    response = client.post("/auth/login", data={"username": "cacheuser", "password": "password1234"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_endpoint_cache_hit_skips_model_but_not_history(client):
    from app.main import app

    counting = _CountingService()
    # One shared instance: a `lambda: TranslationCache(_StubRedis(), 60)`
    # would build a fresh, EMPTY stub for every request -- the second
    # request could never hit what the first one wrote.
    shared_cache = TranslationCache(_StubRedis(), 60)
    app.dependency_overrides[get_translation_service] = lambda: counting
    app.dependency_overrides[get_translation_cache] = lambda: shared_cache

    headers = _register_and_login(client)
    payload = {"text": "cache me", "source_lang": "en", "target_lang": "es"}
    first = client.post("/translate", headers=headers, json=payload)
    second = client.post("/translate", headers=headers, json=payload)

    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["translated_text"] == first.json()["translated_text"]
    assert counting.calls == 1  # the second request was served from cache...
    history = client.get("/translate/history", headers=headers).json()
    assert history["total"] == 2  # ...but BOTH requests were recorded


def test_endpoint_survives_cache_outage(client):
    from app.main import app

    app.dependency_overrides[get_translation_cache] = lambda: TranslationCache(_FailingRedis(), 60)
    response = client.post(
        "/translate", json={"text": "hello", "source_lang": "en", "target_lang": "es"}
    )
    assert response.status_code == 200
