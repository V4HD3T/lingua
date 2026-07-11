"""
Translation service abstraction.

Two implementations are provided:
- MockTranslationService: runs without downloading an external model; used
  for development, testing, and demoing this skeleton.
- NLLBTranslationService: real transformer-based multilingual translation
  via HuggingFace `transformers` (facebook/nllb-200-distilled-600M, supports
  200+ languages with a single model). Requires an internet connection to
  download the model on first run.

Which implementation is used is determined by the USE_MOCK_TRANSLATION flag
in the .env file (see app/config.py). To switch to the real model:
    1) pip install transformers torch sentencepiece
    2) Set USE_MOCK_TRANSLATION=false in .env
    3) The model downloads automatically the first time you run the app (~2-3 min).
"""

from abc import ABC, abstractmethod
from functools import lru_cache

from app.config import settings

# NLLB's FLORES-200 language codes - a commonly used subset.
# Full list: https://github.com/facebookresearch/flores/blob/main/flores200/README.md
NLLB_LANGUAGE_CODES = {
    "tr": "tur_Latn",
    "en": "eng_Latn",
    "de": "deu_Latn",
    "fr": "fra_Latn",
    "es": "spa_Latn",
    "ar": "arb_Arab",
    "ru": "rus_Cyrl",
    "ja": "jpn_Jpan",
    "zh": "zho_Hans",
}


class TranslationService(ABC):
    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        ...


class MockTranslationService(TranslationService):
    """A fake translation service for development/testing that runs without
    downloading a model.

    Doesn't perform a real translation; it allows the API contract, the
    database flow, and the learning/quiz modules to be developed and
    tested independently of the model.
    """

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        return f"[{source_lang}->{target_lang}] {text}"


class NLLBTranslationService(TranslationService):
    """Real transformer-based translation using facebook/nllb-200-distilled-600M."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.translation_model_name
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            from transformers import pipeline  # lazy import: only load when actually needed

            self._pipeline = pipeline("translation", model=self.model_name)
        return self._pipeline

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        src = NLLB_LANGUAGE_CODES.get(source_lang, source_lang)
        tgt = NLLB_LANGUAGE_CODES.get(target_lang, target_lang)
        translator = self._get_pipeline()
        result = translator(text, src_lang=src, tgt_lang=tgt)
        return result[0]["translation_text"]


@lru_cache
def get_translation_service() -> TranslationService:
    """FastAPI dependency: returns the correct service instance based on settings (singleton)."""
    if settings.use_mock_translation:
        return MockTranslationService()
    return NLLBTranslationService()
