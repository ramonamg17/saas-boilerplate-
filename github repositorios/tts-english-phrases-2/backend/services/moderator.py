from openai import AsyncOpenAI

client = AsyncOpenAI()

FLAGGED_CATEGORIES = {"violence", "sexual", "hate", "harassment"}
MAX_RETRIES = 2
MAX_REMOVED_FRACTION = 0.20


async def _moderate_batch(phrases: list[str]) -> list[bool]:
    """Returns True for each phrase that is safe."""
    if not phrases:
        return []

    response = await client.moderations.create(input=phrases)
    results = []
    for result in response.results:
        flagged = result.flagged
        if not flagged:
            results.append(True)
            continue

        # Any flagged result is unsafe — don't allow partial category pass-through
        results.append(False)

    return results


async def filter_phrases(
    phrases: list[str],
    regenerate_fn=None,
    language: str = "",
    topic: str = "",
) -> list[str]:
    safe_flags = await _moderate_batch(phrases)
    safe_phrases = [p for p, ok in zip(phrases, safe_flags) if ok]

    removed = len(phrases) - len(safe_phrases)
    removed_fraction = removed / len(phrases) if phrases else 0

    if removed_fraction > MAX_REMOVED_FRACTION and regenerate_fn is not None:
        for _ in range(MAX_RETRIES):
            replacement_count = removed + 5
            new_phrases = await regenerate_fn(language, topic, replacement_count)
            new_flags = await _moderate_batch(new_phrases)
            new_safe = [p for p, ok in zip(new_phrases, new_flags) if ok]
            safe_phrases.extend(new_safe)
            if len(safe_phrases) >= len(phrases) * (1 - MAX_REMOVED_FRACTION):
                break

    return safe_phrases
