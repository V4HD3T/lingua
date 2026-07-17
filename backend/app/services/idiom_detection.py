"""
Idiom / non-literal phrase detection.

Honest about what this is: a small, hand-curated dictionary per language,
matched against the input with plain case-insensitive substring search.
This is a deliberately simple, fully deterministic and testable approach —
not a trained classifier or an LLM call (neither is available offline in
this environment). It will only ever catch the specific phrases in the
dictionary below; it won't generalize to idioms it hasn't been told about.
A production version of this feature would more likely use a fine-tuned
classifier or an LLM prompt to flag *any* non-literal phrase, not just
ones from a fixed list -- documented here as a known scope limit, not
hidden behind confident-sounding output.
"""

from dataclasses import dataclass


@dataclass
class IdiomMatch:
    phrase: str
    note: str


# A small starter set per supported language. Matching is substring-based
# and case-insensitive, so entries should be the idiom's base form.
IDIOM_DICTIONARY: dict[str, list[IdiomMatch]] = {
    "en": [
        IdiomMatch("break a leg", "Means \"good luck\" (theater superstition) — not literal."),
        IdiomMatch("piece of cake", "Means \"very easy\" — no cake involved."),
        IdiomMatch("under the weather", "Means \"feeling sick\" — not about the weather."),
        IdiomMatch("spill the beans", "Means \"reveal a secret\" — not literal beans."),
        IdiomMatch("hit the books", "Means \"start studying\" — not literal hitting."),
    ],
    "es": [
        # Note: the conjugating verb (estar/costar/tener) is deliberately left
        # out of the match string so this still catches "está en las nubes",
        # "estaba en las nubes", etc. -- see module docstring for why this is
        # still just substring matching, not real conjugation awareness.
        IdiomMatch("en las nubes", "Literally \"in the clouds\" — means daydreaming/distracted."),
        IdiomMatch("un ojo de la cara", "Literally \"an eye of the face\" — means very expensive."),
        IdiomMatch("tomar el pelo", "Literally \"to take the hair\" — means to tease/kid someone."),
        IdiomMatch("pelos en la lengua", "Literally \"hairs on the tongue\" — (no tener ~) means speaking bluntly."),
    ],
    "tr": [
        IdiomMatch("eli ayağı dolaş", "Literally \"hands and feet get tangled\" — means to fumble or panic."),
        IdiomMatch("içi içine sığma", "Literally \"one's inside doesn't fit inside\" — means overjoyed or impatient."),
        IdiomMatch("dilinin altında", "Literally \"under one's tongue\" — means hiding something one wants to say."),
        IdiomMatch("başını ye", "Literally \"to eat someone's head\" — means to cause someone's ruin."),
    ],
    "de": [
        IdiomMatch("daumen drücken", "Literally \"press thumbs\" — means wishing luck, like crossing fingers."),
        IdiomMatch("ins gras beiß", "Literally \"to bite the grass\" — a euphemism for dying."),
        IdiomMatch("tomaten auf den augen", "Literally \"tomatoes on the eyes\" — means not noticing something obvious."),
    ],
    "fr": [
        IdiomMatch("avoir le cafard", "Literally \"to have the cockroach\" — means feeling down or blue."),
        IdiomMatch("poser un lapin", "Literally \"to place a rabbit\" — means to stand someone up."),
        IdiomMatch("coûter les yeux de la tête", "Literally \"cost the eyes of the head\" — means very expensive."),
    ],
}


def find_idioms(text: str, language_code: str) -> list[IdiomMatch]:
    """Returns every dictionary entry for `language_code` whose phrase
    appears (case-insensitively) inside `text`."""
    entries = IDIOM_DICTIONARY.get(language_code, [])
    lowered = text.lower()
    return [entry for entry in entries if entry.phrase in lowered]
