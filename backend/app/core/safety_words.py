"""Safety word lists and patterns for content filtering.

Phase 1 uses simple keyword matching and length limits.
Future phases will add ML-based classification.
"""

import re
from typing import Pattern

# Maximum input length (characters) — longer inputs are truncated
MAX_USER_INPUT_LEN: int = 2000

# Blacklisted keywords — any match triggers a refusal
BLACKLIST_KEYWORDS: frozenset[str] = frozenset([
    # Phase 1: minimal set — expand in future phases
    "hack",
    "exploit",
    "injection",
    "bypass",
    "phishing",
    "ransomware",
    "malware",
])

# Fallback response when safety_in blocks the input
SAFETY_BLOCKED_RESPONSE: str = "抱歉，您的消息包含不支持的内容，无法处理。"

# Patterns for output redaction (API keys, tokens, etc.)
_SECRET_PATTERNS: list[tuple[Pattern[str], str]] = [
    # OpenAI-style keys
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "[REDACTED_API_KEY]"),
    # AWS access keys
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    # Generic JWT-like tokens (header.payload.signature)
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED_TOKEN]"),
]


def is_input_safe(text: str) -> tuple[bool, str]:
    """Check if user input passes Phase 1 safety filters.

    Returns (is_safe, reason).
    """
    # Length check
    if len(text) > MAX_USER_INPUT_LEN:
        return False, f"input_too_long: {len(text)} > {MAX_USER_INPUT_LEN}"

    # Keyword check (case-insensitive)
    lower = text.lower()
    for kw in BLACKLIST_KEYWORDS:
        if kw in lower:
            return False, f"blacklist_keyword: {kw}"

    return True, ""


def redact_output(text: str) -> str:
    """Strip secret patterns from LLM output.

    Returns the redacted text.
    """
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
