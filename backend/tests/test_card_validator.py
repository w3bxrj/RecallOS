import pytest
from app.services.card_validator import validate_card, normalize_topic


def test_normalize_topic() -> None:
    """Topics are trimmed and title-cased; common abbreviations are normalized."""
    assert normalize_topic("  operating systems  ") == "Operating Systems"
    assert normalize_topic("os") == "Operating Systems"
    assert normalize_topic("computer networks") == "Computer Networks"


def test_valid_card_accepted() -> None:
    """A valid card with 3 distinct distractors different from the answer is accepted."""
    seen = set()
    raw = {
        "topic": "networks",
        "question": "What is DNS?",
        "answer": "Domain Name System",
        "distractors": ["Dynamic Network Switch", "Data Node Storage", "Direct Name Server"],
    }
    validated = validate_card(raw, seen)
    assert validated is not None
    assert validated["topic"] == "Networks"
    assert validated["question"] == "What is DNS?"
    assert validated["answer"] == "Domain Name System"
    assert len(validated["distractors"]) == 3
    assert "what is dns?" in seen


def test_drop_duplicate_question_case_insensitive() -> None:
    """Duplicate question across the deck is dropped."""
    seen = {"what is dns?"}
    raw = {
        "topic": "Networks",
        "question": "WHAT IS DNS?",
        "answer": "Domain Name System",
        "distractors": ["A", "B", "C"],
    }
    assert validate_card(raw, seen) is None


def test_drop_card_with_fewer_or_more_than_3_distractors() -> None:
    """Cards with != 3 distractors are dropped."""
    seen = set()
    raw2 = {"topic": "T", "question": "Q", "answer": "A", "distractors": ["D1", "D2"]}
    assert validate_card(raw2, seen) is None

    raw4 = {"topic": "T", "question": "Q", "answer": "A", "distractors": ["D1", "D2", "D3", "D4"]}
    assert validate_card(raw4, seen) is None


def test_drop_card_where_distractor_equals_answer() -> None:
    """Cards where any distractor equals the answer (case-insensitive) are dropped."""
    seen = set()
    raw = {
        "topic": "T",
        "question": "Q",
        "answer": "Correct Answer",
        "distractors": ["Wrong 1", "correct answer", "Wrong 2"],
    }
    assert validate_card(raw, seen) is None


def test_drop_card_with_duplicate_distractors() -> None:
    """Cards where distractors are not distinct from each other are dropped."""
    seen = set()
    raw = {
        "topic": "T",
        "question": "Q",
        "answer": "Correct Answer",
        "distractors": ["Duplicate", "duplicate", "Other"],
    }
    assert validate_card(raw, seen) is None


def test_drop_card_with_empty_fields() -> None:
    """Cards with empty string fields are dropped."""
    seen = set()
    raw = {
        "topic": "",
        "question": "Q",
        "answer": "A",
        "distractors": ["D1", "D2", "D3"],
    }
    assert validate_card(raw, seen) is None
