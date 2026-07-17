"""
Personalized vocabulary suggestions, derived from the user's own
translation history.

The idea: if someone keeps translating the same word over and over, that's
a strong, self-reported signal that they haven't learned it yet -- so
surface it as something worth adding to their structured vocabulary
practice. This is the one feature that genuinely connects the translate
module to the learn module, rather than having them sit side by side.

Deliberately simple and explainable: plain word-frequency counting over
the user's own TranslationHistory (both source and target text, so it
doesn't matter which direction they were translating), cross-referenced
against the app's existing VocabularyItem catalogue, excluding words
they've already started reviewing (see spaced_repetition.py /
VocabularyProgress). No ML involved -- the frequency count itself is the
whole signal, and it's easy to verify by hand.
"""

import re
from collections import Counter
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import TranslationHistory, VocabularyItem, VocabularyProgress

_WORD_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)
MIN_WORD_LENGTH = 3


@dataclass
class VocabularySuggestion:
    vocabulary_item_id: int
    word: str
    translation: str
    lesson_id: int
    frequency: int


def _word_frequencies(history: list[TranslationHistory]) -> Counter:
    """Counts, per unique word, how many separate translation *records* it
    appeared in (source or target text) -- not raw token occurrences.

    Deliberately a set-per-record union rather than a flat word count: a
    single translation containing the same word twice (or, with the mock
    translation service, a source word that gets echoed back into the
    "translated" text) shouldn't inflate frequency more than one genuinely
    repeated lookup would. What we want to measure is "how many times did
    the user look this word up", not "how many times does this word appear
    across all their text combined".
    """
    counts: Counter = Counter()
    for record in history:
        combined = f"{record.source_text} {record.target_text}".lower()
        words_in_record = {w for w in _WORD_PATTERN.findall(combined) if len(w) >= MIN_WORD_LENGTH}
        counts.update(words_in_record)
    return counts


def get_personalized_suggestions(
    user_id: int, session: Session, min_frequency: int = 2, limit: int = 10
) -> list[VocabularySuggestion]:
    history = session.exec(
        select(TranslationHistory).where(TranslationHistory.user_id == user_id)
    ).all()
    if not history:
        return []

    frequencies = _word_frequencies(history)

    started_item_ids = {
        p.vocabulary_item_id
        for p in session.exec(
            select(VocabularyProgress).where(VocabularyProgress.user_id == user_id)
        ).all()
    }

    all_vocab = session.exec(select(VocabularyItem)).all()

    suggestions = []
    for item in all_vocab:
        if item.id in started_item_ids:
            continue
        frequency = frequencies.get(item.word.lower(), 0)
        if frequency >= min_frequency:
            suggestions.append(
                VocabularySuggestion(
                    vocabulary_item_id=item.id,
                    word=item.word,
                    translation=item.translation,
                    lesson_id=item.lesson_id,
                    frequency=frequency,
                )
            )

    suggestions.sort(key=lambda s: -s.frequency)
    return suggestions[:limit]
