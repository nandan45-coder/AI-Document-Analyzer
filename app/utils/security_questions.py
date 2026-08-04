"""
Predefined system security questions.
"""

from typing import List

PREDEFINED_SECURITY_QUESTIONS: List[str] = [
    "What was the name of your first pet?",
    "What is your mother's maiden name?",
    "What is your first school name?",
    "In what city or town were you born?",
    "What is your favorite book or movie?",
    "What was the make and model of your first car?",
    "What is your favorite childhood nickname?",
]


def get_security_questions() -> List[str]:
    """Returns the list of predefined security questions."""
    return list(PREDEFINED_SECURITY_QUESTIONS)


def is_valid_security_question(question: str) -> bool:
    """
    Checks whether a given question matches one of the predefined security questions
    (case-insensitive comparison with whitespace stripped).
    """
    cleaned = question.strip().lower()
    return any(q.lower() == cleaned for q in PREDEFINED_SECURITY_QUESTIONS)
