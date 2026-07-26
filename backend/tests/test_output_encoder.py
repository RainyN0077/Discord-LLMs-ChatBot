"""Tests for output encoder — LLM response sanitisation.

Covers:
  - html.escape(quote=True) escapes double quotes
  - <script> tag stripping
  - Order: strip then escape
"""

import pytest

pytestmark = [pytest.mark.unit]


class TestEncodeOutput:
    """encode_output() should neutralise dangerous characters/tags."""

    def test_escapes_ampersand(self):
        from app.security.output_encoder import encode_output
        result = encode_output("a & b")
        assert result == "a &amp; b"

    def test_escapes_less_than(self):
        from app.security.output_encoder import encode_output
        result = encode_output("<b>bold</b>")
        assert "&lt;b&gt;bold&lt;/b&gt;" in result

    def test_escapes_greater_than(self):
        from app.security.output_encoder import encode_output
        result = encode_output("a > b")
        assert result == "a &gt; b"

    def test_escapes_double_quotes(self):
        """html.escape with quote=True should escape double quotes."""
        from app.security.output_encoder import encode_output
        result = encode_output('say "hello"')
        assert "&quot;" in result
        assert '"' not in result

    def test_strips_script_tag(self):
        """<script>...</script> blocks should be removed entirely."""
        from app.security.output_encoder import encode_output
        result = encode_output("Hello <script>alert('xss')</script> world")
        assert "script" not in result
        assert "alert" not in result

    def test_strips_script_tag_with_attributes(self):
        from app.security.output_encoder import encode_output
        result = encode_output("<script type='text/javascript'>evil()</script>ok")
        assert result == "ok"

    def test_strips_script_tag_multiline(self):
        from app.security.output_encoder import encode_output
        result = encode_output("<script>\n  alert('xss')\n</script>")
        assert result == ""

    def test_strip_before_escape(self):
        """Script tags should be stripped BEFORE HTML escaping.

        If we escaped first, <script> would become &lt;script&gt; and
        the regex would no longer match. The actual implementation
        strips first, then escapes — verify the output is safe.
        """
        from app.security.output_encoder import encode_output
        text = "<script>evil()</script>"
        result = encode_output(text)
        # Script block removed entirely
        assert result == ""
        # If we only escaped, result would be &lt;script&gt;evil()&lt;/script&gt;
        assert "&lt;script&gt;" not in result

    def test_non_string_input(self):
        """Non-string input should be converted to string first."""
        from app.security.output_encoder import encode_output
        result = encode_output(123)
        assert result == "123"

    def test_safe_html_preserved(self):
        """Safe HTML content like <3 should be properly escaped."""
        from app.security.output_encoder import encode_output
        result = encode_output("I <3 Python")
        assert result == "I &lt;3 Python"

    def test_empty_string(self):
        from app.security.output_encoder import encode_output
        assert encode_output("") == ""

    def test_script_in_middle_of_text(self):
        from app.security.output_encoder import encode_output
        result = encode_output("before<script>inner</script>after")
        assert "before" in result
        assert "after" in result
        assert "script" not in result
