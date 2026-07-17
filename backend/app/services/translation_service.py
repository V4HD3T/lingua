"""
Translation service abstraction.

Two implementations are provided:
- MockTranslationService: runs without downloading an external model; used
  for development, testing, and demoing this skeleton.
- NLLBTranslationService: real transformer-based multilingual translation via
  HuggingFace `transformers` (facebook/nllb-200-distilled-600M, supports
  200+ languages with a single model). Requires an internet connection to
  download the model on first run.

Which implementation is used is controlled by the USE_MOCK_TRANSLATION flag
in the .env file (see app/config.py). To switch to the real model:
    1) pip install transformers torch sentencepiece
    2) Set USE_MOCK_TRANSLATION=false in .env
    3) The model downloads automatically on first run (~2-3 min).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
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


@dataclass
class TranslationDetail:
    translated_text: str
    confidence: float
    alternatives: list[str]


class TranslationService(ABC):
    @abstractmethod
    def translate_detailed(self, text: str, source_lang: str, target_lang: str) -> TranslationDetail:
        ...

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Convenience wrapper for callers that only want the plain text."""
        return self.translate_detailed(text, source_lang, target_lang).translated_text


class MockTranslationService(TranslationService):
    """A fake translation service for development/testing that runs without
    downloading a model.

    Doesn't perform a real translation; it lets the API contract, the
    database flow, and the learning/quiz modules be developed and tested
    independently of the model.

    `confidence` and `alternatives` here are illustrative placeholders, not
    real model output -- there is no real uncertainty to measure without an
    actual model. `confidence` is a simple, disclosed heuristic (longer
    input -> higher number) purely so the frontend has something dynamic to
    render and test against. `alternatives` are trivial formatting
    variants of the same mock string, clearly not genuine alternative
    translations. Compare against NLLBTranslationService.translate_detailed,
    which computes both from real beam-search output once the real model is
    active.
    """

    def translate_detailed(self, text: str, source_lang: str, target_lang: str) -> TranslationDetail:
        translated = f"[{source_lang}->{target_lang}] {text}"
        word_count = max(1, len(text.split()))
        confidence = round(min(0.98, 0.6 + 0.03 * word_count), 2)
        alternatives = [f"[{source_lang}->{target_lang}] {text}."]
        return TranslationDetail(
            translated_text=translated, confidence=confidence, alternatives=alternatives
        )


class NLLBTranslationService(TranslationService):
    """Real transformer-based translation using facebook/nllb-200-distilled-600M.

    Two code paths:
    - translate_detailed() drops to the low-level tokenizer/model API to get
      genuine beam-search alternatives and a real confidence score (mean
      per-token log-probability of the top sequence, converted to 0-1 via
      exp()). This needs more of the `transformers` API surface than the
      simple translate() path below, and its exact interface (e.g. how the
      NLLB tokenizer exposes language-code token IDs) has changed across
      `transformers` versions -- written to the best of my knowledge, but
      worth a quick sanity check against your installed version before
      relying on it, since it cannot be executed in this sandbox (no
      network access to huggingface.co to fetch the model).
    - translate() keeps using the simpler high-level `pipeline()` wrapper,
      which is more stable across versions, for plain-text-only callers.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.translation_model_name
        self._pipeline = None
        self._model = None
        self._tokenizer = None

    def _get_pipeline(self):
        if self._pipeline is None:
            from transformers import pipeline  # lazy import: only load when actually needed

            self._pipeline = pipeline("translation", model=self.model_name)
        return self._pipeline

    def _get_model_and_tokenizer(self):
        if self._model is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        return self._model, self._tokenizer

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        src = NLLB_LANGUAGE_CODES.get(source_lang, source_lang)
        tgt = NLLB_LANGUAGE_CODES.get(target_lang, target_lang)
        translator = self._get_pipeline()
        result = translator(text, src_lang=src, tgt_lang=tgt)
        return result[0]["translation_text"]

    def translate_detailed(
        self, text: str, source_lang: str, target_lang: str, num_alternatives: int = 2
    ) -> TranslationDetail:
        import torch

        src = NLLB_LANGUAGE_CODES.get(source_lang, source_lang)
        tgt = NLLB_LANGUAGE_CODES.get(target_lang, target_lang)
        model, tokenizer = self._get_model_and_tokenizer()

        tokenizer.src_lang = src
        inputs = tokenizer(text, return_tensors="pt")
        target_lang_id = tokenizer.convert_tokens_to_ids(tgt)

        num_sequences = max(1, num_alternatives + 1)
        outputs = model.generate(
            **inputs,
            forced_bos_token_id=target_lang_id,
            num_beams=max(4, num_sequences),
            num_return_sequences=num_sequences,
            output_scores=True,
            return_dict_in_generate=True,
        )

        texts = tokenizer.batch_decode(outputs.sequences, skip_special_tokens=True)
        scores = (
            outputs.sequences_scores.tolist()
            if getattr(outputs, "sequences_scores", None) is not None
            else [0.0] * len(texts)
        )
        confidence = round(float(torch.exp(torch.tensor(scores[0]))), 3) if scores else 0.0

        primary = texts[0]
        alternatives = [t for t in texts[1:] if t != primary]

        return TranslationDetail(
            translated_text=primary, confidence=confidence, alternatives=alternatives
        )


@lru_cache
def get_translation_service() -> TranslationService:
    """FastAPI dependency: returns the correct service instance based on settings (singleton)."""
    if settings.use_mock_translation:
        return MockTranslationService()
    return NLLBTranslationService()
