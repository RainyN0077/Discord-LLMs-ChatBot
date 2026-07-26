"""Input sanitization — detect and filter prompt injection patterns.

Provides two public functions:
    detect_injection(text) -> bool
    sanitize_user_input(text) -> str

Detection is regex + keyword based. Sanitization replaces matched patterns
with a safe placeholder to avoid false-positive blocking of legitimate input.
"""

import logging
import re
import unicodedata
from typing import List, Pattern

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt injection patterns
# ---------------------------------------------------------------------------
# Each pattern targets a known injection vector.  The list is intentionally
# conservative — we prefer false negatives over false positives for normal
# conversational use.
# ---------------------------------------------------------------------------

INJECTION_PATTERNS: List[Pattern] = [
    # Ignore / disregard system instructions
    re.compile(r"ignore\s+(previous|above|all)\s+(instructions?|prompts?|directives?)", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|above|all)\s+(instructions?|prompts?|directives?)", re.IGNORECASE),
    # Role re-assignment
    re.compile(r"(?:act|pretend|behave)\s+as\s+if\s+you\s+are\s+(?:now|actually)\s+a", re.IGNORECASE),
    # System prompt / instruction tag injection
    re.compile(r"\bsystem\s*:", re.IGNORECASE),
    re.compile(r"<\/?system>", re.IGNORECASE),
    re.compile(r"<\/?instruction>", re.IGNORECASE),
    # Forget / reveal attempts
    re.compile(r"forget\s+(everything|all)\s+(instructions?|prompts?|directives?)", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(system\s+)?prompt", re.IGNORECASE),
    # Common jailbreak keywords
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\bDAN\s+mode\b", re.IGNORECASE),
    # Base64-encoded instruction (common injection delivery mechanism)
    re.compile(r"(?:decode|decrypt|base64)\s*(?:and\s*)?(?:execute|run|do|follow|output|print)\s", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9+/]{40,}={0,2}\s*(?:execute|run|do|follow|output)", re.IGNORECASE),
]

# Placeholder used when a pattern is matched during sanitization.
_FILTERED = "[FILTERED]"


def detect_injection(text: str) -> bool:
    """Return True if *text* matches any known prompt injection pattern.

    This is intentionally a shallow scan — it checks the raw text, not
    decoded or transformed forms.  The goal is to flag obvious injection
    attempts without producing excessive false positives.
    """
    normalized = unicodedata.normalize("NFKC", text)
    for pattern in INJECTION_PATTERNS:
        if pattern.search(normalized):
            logger.debug("Injection pattern matched: %r in %r", pattern.pattern, text[:120])
            return True
    return False


def sanitize_user_input(text: str) -> str:
    """Return *text* with known injection patterns replaced by a safe marker.

    This is **not** a security boundary on its own — it is one layer in a
    defence-in-depth strategy.  The LLM system prompt should independently
    instruct the model to ignore injected instructions.
    """
    normalized = unicodedata.normalize("NFKC", text)
    sanitized = normalized
    for pattern in INJECTION_PATTERNS:
        sanitized = pattern.sub(_FILTERED, sanitized)
    return sanitized
