"""SanitizingFilter — redact sensitive patterns from log output.

Attach ``SanitizingFilter`` to any logger or handler to automatically
replace credentials (API keys, tokens, secrets, passwords, etc.) with
``***REDACTED***`` before the log message is emitted.
"""

import logging
import re
from typing import List, Pattern

# ---------------------------------------------------------------------------
# Compiled secret patterns
# ---------------------------------------------------------------------------
# Each pattern is a 2-group regex: group(1) = label prefix, group(2) = value.
# The substitution keeps group(1) and replaces group(2) with ***REDACTED***.
# For single-group patterns (e.g. bare sk-...) the whole match is replaced.

SECRET_PATTERNS: List[Pattern] = [
    # api_key / api-key / apikey = "value"
    re.compile(
        r"(api[_-]?key\s*[:=]\s*[\"']?)([A-Za-z0-9_\-+=/]{8,})",
        re.IGNORECASE,
    ),
    # token = "value"  (generic; avoid matching short non-secret tokens)
    re.compile(
        r"(\btoken\s*[:=]\s*[\"']?)([A-Za-z0-9_\-+=/.]{8,})",
        re.IGNORECASE,
    ),
    # secret / secret_key / ... = "value"
    re.compile(
        r"(secret[_-]?key\s*[:=]\s*[\"']?)([A-Za-z0-9_\-+=/]{8,})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\bsecret\s*[:=]\s*[\"']?)([A-Za-z0-9_\-+=/]{8,})",
        re.IGNORECASE,
    ),
    # password = "value"
    re.compile(
        r"(password\s*[:=]\s*[\"']?)([A-Za-z0-9_\-!@#$%^&*()+]{6,})",
        re.IGNORECASE,
    ),
    # OpenAI / LLM API key prefixes: sk-...
    re.compile(r"(sk-)[A-Za-z0-9]{20,}"),
    # Slack Bot / App tokens: xoxb- / xoxa- / xoxp- / xoxr- / xoxs-
    re.compile(r"(xox[brapse]-)[A-Za-z0-9-]+"),
    # GitHub personal access tokens: ghp_ / ghs_ / ghu_ / ghb_ / gho_
    re.compile(r"(gh[psubo]_)[A-Za-z0-9]{36,}"),
    # Discord bot token (typical format: 24-char hex . 10-char hex . 27-char base64)
    re.compile(
        r"([A-Za-z0-9_\-+=/]{20,}\.[A-Za-z0-9_\-+=/]{6,}\.[A-Za-z0-9_\-+=/]{20,})"
    ),
]


def sanitize_message(msg: str) -> str:
    """Return *msg* with every known secret pattern redacted."""
    for pattern in SECRET_PATTERNS:
        # Patterns with 2 groups: keep the label, redact the value
        if pattern.groups == 2:
            msg = pattern.sub(r"\1***REDACTED***", msg)
        else:
            # Single group: redact the entire match
            msg = pattern.sub("***REDACTED***", msg)
    return msg


class SanitizingFilter(logging.Filter):
    """A logging filter that redacts credentials from every log record.

    Usage::

        logging.getLogger().addFilter(SanitizingFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitize *record* in-place and always return True (keep record)."""
        # Sanitise the main message string
        if isinstance(record.msg, str):
            original = record.msg
            record.msg = sanitize_message(record.msg)
            # If the message changed and there are positional args, sanitise
            # those too so that ``logger.info("key=%s", api_key)`` is covered.
            if record.msg != original and record.args:
                sanitized_args = tuple(
                    sanitize_message(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
                record.args = sanitized_args
        return True  # never drop records
