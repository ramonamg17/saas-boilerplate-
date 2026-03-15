from difflib import SequenceMatcher

FUZZY_THRESHOLD = 0.85


def _normalize(phrase: str) -> str:
    return phrase.lower().strip()


def _is_similar(a: str, b: str) -> bool:
    ratio = SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()
    return ratio > FUZZY_THRESHOLD


def deduplicate(phrases: list[str]) -> list[str]:
    seen_normalized: set[str] = set()
    unique: list[str] = []

    for phrase in phrases:
        norm = _normalize(phrase)

        if norm in seen_normalized:
            continue

        is_fuzzy_dup = any(_is_similar(phrase, existing) for existing in unique)
        if is_fuzzy_dup:
            continue

        seen_normalized.add(norm)
        unique.append(phrase)

    return unique
