from typing import Optional, Dict, Any, Set, List

TOPIC_CANONICAL_MAP = {
    "os": "Operating Systems",
    "dbms": "Database Management",
    "cn": "Computer Networks",
    "ai": "Artificial Intelligence",
    "ml": "Machine Learning",
    "dsa": "Data Structures & Algorithms",
}


def normalize_topic(topic: str) -> str:
    """Normalizes a topic name by trimming whitespace, expanding known abbreviations,

    and title-casing.
    """
    cleaned = topic.strip()
    lowered = cleaned.lower()
    if lowered in TOPIC_CANONICAL_MAP:
        return TOPIC_CANONICAL_MAP[lowered]
    return cleaned.title()


def validate_card(card: Dict[str, Any], seen_questions: Set[str]) -> Optional[Dict[str, Any]]:
    """Validates raw card dictionary returned by LLM.

    Rules:
    - Non-empty topic, question, and answer.
    - Exactly 3 non-empty distractors.
    - None of the distractors can match the answer (case-insensitive).
    - Distractors must all be mutually distinct (case-insensitive).
    - Question must not be a duplicate in this deck (case-insensitive).

    Returns normalized card dict or None if invalid.
    """
    if not isinstance(card, dict):
        return None

    # Check required fields exist and are strings
    topic = card.get("topic")
    question = card.get("question")
    answer = card.get("answer")
    distractors = card.get("distractors")

    if not isinstance(topic, str) or not topic.strip():
        return None
    if not isinstance(question, str) or not question.strip():
        return None
    if not isinstance(answer, str) or not answer.strip():
        return None

    # Check distractors list
    if not isinstance(distractors, list) or len(distractors) != 3:
        return None

    norm_answer = answer.strip().lower()
    norm_distractors: List[str] = []
    seen_distractors: Set[str] = set()

    for d in distractors:
        if not isinstance(d, str):
            return None
        stripped_d = d.strip()
        if not stripped_d:
            return None
        lowered_d = stripped_d.lower()
        # Must be different from the answer
        if lowered_d == norm_answer:
            return None
        # Must be unique among distractors
        if lowered_d in seen_distractors:
            return None
        seen_distractors.add(lowered_d)
        norm_distractors.append(stripped_d)

    # Question deduplication check
    norm_q = question.strip().lower()
    if norm_q in seen_questions:
        return None
    seen_questions.add(norm_q)

    return {
        "topic": normalize_topic(topic),
        "question": question.strip(),
        "answer": answer.strip(),
        "distractors": norm_distractors,
    }
