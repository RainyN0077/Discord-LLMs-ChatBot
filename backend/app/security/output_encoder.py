"""Output encoder — sanitise LLM responses before they reach end users.

Provides one public function:
    encode_output(text) -> str

Encoding strategy:
  1. HTML-escape special characters (&, <, >, ") so that raw HTML/JS
     rendered in a web or Discord context is inert.
  2. Strip <script>...</script> blocks entirely (defence-in-depth).
"""

import html
import logging
import re

logger = logging.getLogger(__name__)

_SCRIPT_TAG = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)


def encode_output(text: str) -> str:
    """Return *text* with dangerous characters / tags neutralised.

    - HTML special characters are escaped with ``html.escape``.
    - ``<script>`` blocks are removed entirely (they are never needed in
      LLM output for this application).
    """
    if not isinstance(text, str):
        text = str(text)

    # Remove <script>...</script> blocks first while they are still
    # identifiable (handles nested attributes, line breaks).
    stripped = _SCRIPT_TAG.sub("", text)

    # HTML-escape remaining dangerous characters.
    encoded = html.escape(stripped, quote=True)

    return encoded
