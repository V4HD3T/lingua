"""Redis-backed cache for frequently translated phrases (v0.1.0).

Why cache at all: with the mock translation service this is ceremonial,
but the moment the real NLLB model is active, every /translate request
costs a beam-search generation -- repeated phrases ("hello", lesson
sentences, the demo script) are the textbook case for a read-through
cache.

Two design rules, both load-bearing:

1. Disabled unless REDIS_URL is set. The default dev/test experience
   needs no Redis running; get() returns None and set() is a no-op.
2. The cache must NEVER take translation down. Every Redis operation is
   wrapped, short-timeouted (0.5s), and degrades to "cache miss" on any
   failure -- a dead Redis makes translations slower, not broken. That's
   also why the except clauses are deliberately broad: the failure modes
   of a network cache (connection refused, timeout, protocol error,
   corrupted payload) all have the same correct answer here.

Only the model's output (text, confidence, alternatives) is cached.
History recording, achievements, and idiom warnings stay per-request --
a cache hit must be indistinguishable from a miss to the learner's data.
"""

import hashlib
import json
import logging
from functools import lru_cache
from typing import Optional

from app.config import settings
from app.services.translation_service import TranslationDetail

logger = logging.getLogger(__name__)


class TranslationCache:
    def __init__(self, client, ttl_seconds: int, backend_id: str = "mock", version: int = 1):
        self._client = client  # a redis.Redis, or None when disabled
        self.ttl_seconds = ttl_seconds
        self.backend_id = backend_id  # which translation service produced these entries
        self.version = version  # manual invalidation knob

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _key(self, source_lang: str, target_lang: str, text: str) -> str:
        # Hash the text: user input is unbounded and arbitrary; a digest
        # keeps keys small, safe, and uniform.
        #
        # The backend id and version in the prefix are load-bearing, not
        # decoration: without them, every phrase translated by the mock
        # service stays valid for the full 7-day TTL *after* the real NLLB
        # model is switched on, and learners get served "[en->es] hello"
        # as if it were a real translation. Switching backends now simply
        # misses into a different keyspace.
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
        return (
            f"translation:v{self.version}:{self.backend_id}:"
            f"{source_lang}:{target_lang}:{digest}"
        )

    def get(self, source_lang: str, target_lang: str, text: str) -> Optional[TranslationDetail]:
        if self._client is None:
            return None
        key = self._key(source_lang, target_lang, text)
        try:
            raw = self._client.get(key)
        except Exception:
            logger.warning("translation cache read failed; continuing uncached", exc_info=True)
            return None
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return TranslationDetail(
                translated_text=data["translated_text"],
                confidence=data["confidence"],
                alternatives=list(data["alternatives"]),
            )
        except (ValueError, TypeError, KeyError):
            # A corrupted entry is just a miss; the fresh result will overwrite it.
            return None

    def set(self, source_lang: str, target_lang: str, text: str, detail: TranslationDetail) -> None:
        if self._client is None:
            return
        payload = json.dumps(
            {
                "translated_text": detail.translated_text,
                "confidence": detail.confidence,
                "alternatives": list(detail.alternatives),
            }
        )
        try:
            self._client.setex(self._key(source_lang, target_lang, text), self.ttl_seconds, payload)
        except Exception:
            logger.warning("translation cache write failed; continuing uncached", exc_info=True)


@lru_cache
def get_translation_cache() -> TranslationCache:
    """FastAPI dependency. lru_cache makes it a process-wide singleton, the
    same pattern as get_translation_service / get_email_service."""
    backend_id = "mock" if settings.use_mock_translation else "nllb"
    if not settings.redis_url:
        return TranslationCache(
            None,
            settings.translation_cache_ttl_seconds,
            backend_id=backend_id,
            version=settings.translation_cache_version,
        )

    import redis  # imported lazily: not needed at all in the disabled case

    client = redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=0.5,
        socket_connect_timeout=0.5,
    )
    return TranslationCache(
        client,
        settings.translation_cache_ttl_seconds,
        backend_id=backend_id,
        version=settings.translation_cache_version,
    )
