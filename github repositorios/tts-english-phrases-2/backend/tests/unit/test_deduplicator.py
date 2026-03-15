"""
Unit tests for services/deduplicator.py
No external dependencies — pure Python logic.
"""
import pytest
from services.deduplicator import deduplicate


# ── Exact deduplication ───────────────────────────────────────────────────────

def test_exact_duplicate_removed():
    phrases = ["Hello world today", "Hello world today", "Different phrase here"]
    result = deduplicate(phrases)
    assert len(result) == 2


def test_case_insensitive_exact_dedup():
    phrases = ["Hello World Today", "hello world today", "Something else entirely"]
    result = deduplicate(phrases)
    assert len(result) == 2


def test_whitespace_stripped_for_exact_dedup():
    phrases = ["  hello world  ", "hello world", "another phrase here"]
    result = deduplicate(phrases)
    assert len(result) == 2


def test_preserves_first_occurrence_on_exact():
    phrases = ["First Phrase Here", "first phrase here", "Other phrase"]
    result = deduplicate(phrases)
    assert result[0] == "First Phrase Here"


# ── Fuzzy deduplication ───────────────────────────────────────────────────────

def test_fuzzy_near_duplicate_removed():
    # One character difference → ratio well above 0.85
    phrases = [
        "I want to eat some food now",
        "I want to eat some foods now",
        "Completely different sentence here",
    ]
    result = deduplicate(phrases)
    assert len(result) == 2
    assert result[0] == "I want to eat some food now"


def test_sufficiently_different_phrases_kept():
    phrases = [
        "The cat sat on the mat",
        "She runs every morning before work",
        "We bought groceries at the market",
    ]
    result = deduplicate(phrases)
    assert len(result) == 3


def test_fuzzy_threshold_respected():
    # 50% overlap — should NOT be deduped (ratio < 0.85)
    phrases = [
        "apple banana cherry date elderberry",
        "zebra yellow xray walrus violet",
    ]
    result = deduplicate(phrases)
    assert len(result) == 2


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_list_returns_empty():
    assert deduplicate([]) == []


def test_single_phrase_returns_unchanged():
    assert deduplicate(["only one phrase here"]) == ["only one phrase here"]


def test_all_duplicates_leaves_one():
    phrases = ["same phrase again", "same phrase again", "same phrase again"]
    result = deduplicate(phrases)
    assert result == ["same phrase again"]


def test_order_preserved_for_unique_phrases():
    phrases = ["alpha phrase", "beta phrase", "gamma phrase"]
    result = deduplicate(phrases)
    assert result == phrases
