import pytest

from app.ocr_service import (
    is_multimodal_llm,
    get_ocr_timeout_seconds,
    _normalize_provider,
    _build_endpoint,
    _fallback_base_url,
    build_ocr_runtime_config,
    has_ocr_model_config,
    _build_image_list,
    _sanitize_ocr_text,
    OCR_TIMEOUT_SECONDS,
    DEFAULT_OCR_PROMPT_TEMPLATE,
    OCR_SYSTEM_PROMPT,
)


class TestIsMultimodalLLM:
    def test_is_multimodal_llm_true(self):
        assert is_multimodal_llm({"llm_is_multimodal": True}) is True

    def test_is_multimodal_llm_false(self):
        assert is_multimodal_llm({"llm_is_multimodal": False}) is False

    def test_is_multimodal_llm_default(self):
        assert is_multimodal_llm({}) is True


class TestGetOcrTimeoutSeconds:
    def test_get_ocr_timeout_seconds_default(self):
        assert get_ocr_timeout_seconds({}) == OCR_TIMEOUT_SECONDS

    def test_get_ocr_timeout_seconds_disabled(self):
        assert get_ocr_timeout_seconds({"ocr_timeout_disabled": True}) is None

    def test_get_ocr_timeout_seconds_custom(self):
        assert get_ocr_timeout_seconds({"ocr_timeout_seconds": 30}) == 30

    def test_get_ocr_timeout_seconds_invalid(self):
        assert get_ocr_timeout_seconds({"ocr_timeout_seconds": "not-a-number"}) == OCR_TIMEOUT_SECONDS

    def test_get_ocr_timeout_seconds_clamped(self):
        assert get_ocr_timeout_seconds({"ocr_timeout_seconds": 0}) == 1
        assert get_ocr_timeout_seconds({"ocr_timeout_seconds": 100000}) == 86400


class TestNormalizeProvider:
    def test_normalize_provider_openai_compatible(self):
        assert _normalize_provider("openai_compatible") == "openai"
        assert _normalize_provider("openai-compatible") == "openai"

    def test_normalize_provider_gemini(self):
        assert _normalize_provider("gemini") == "google"
        assert _normalize_provider("google") == "google"

    def test_normalize_provider_anthropic_compatible(self):
        assert _normalize_provider("anthropic_compatible") == "anthropic"
        assert _normalize_provider("anthropic-compatible") == "anthropic"

    def test_normalize_provider_xai(self):
        assert _normalize_provider("xai") == "grok"
        assert _normalize_provider("grok") == "grok"
        assert _normalize_provider("x.ai") == "grok"

    def test_normalize_provider_pass_through(self):
        assert _normalize_provider("unknown_provider") == "unknown_provider"


class TestBuildEndpoint:
    def test_build_endpoint_no_base(self):
        assert _build_endpoint(None, None) is None
        assert _build_endpoint("", "8080") is None

    def test_build_endpoint_with_port(self):
        assert _build_endpoint("http://localhost", "8080") == "http://localhost:8080"

    def test_build_endpoint_already_has_port(self):
        assert _build_endpoint("http://localhost:8080", "9090") == "http://localhost:8080"

    def test_build_endpoint_empty_port(self):
        assert _build_endpoint("http://localhost", "") == "http://localhost"
        assert _build_endpoint("http://localhost", None) == "http://localhost"


class TestFallbackBaseUrl:
    def test_fallback_base_url_openai(self):
        assert _fallback_base_url({"openai_base_url": "http://openai.test"}, "openai") == "http://openai.test"
        assert _fallback_base_url({"base_url": "http://fallback.test"}, "openai") == "http://fallback.test"

    def test_fallback_base_url_anthropic(self):
        assert _fallback_base_url({"anthropic_base_url": "http://anthro.test"}, "anthropic") == "http://anthro.test"

    def test_fallback_base_url_grok(self):
        assert _fallback_base_url({"grok_base_url": "http://grok.test"}, "grok") == "http://grok.test"

    def test_fallback_base_url_unknown(self):
        assert _fallback_base_url({}, "unknown") is None


class TestBuildOcrRuntimeConfig:
    def test_build_ocr_runtime_config(self):
        config = {
            "ocr_provider": "openai",
            "api_key": "sk-test",
            "ocr_api_key": "",
            "ocr_base_url": "http://ocr.test",
            "ocr_model_name": "gpt-4o",
        }
        result = build_ocr_runtime_config(config)
        assert result["llm_provider"] == "openai"
        assert result["api_key"] == "sk-test"
        assert result["base_url"] == "http://ocr.test"
        assert result["model_name"] == "gpt-4o"
        assert result["stream_response"] is False


class TestHasOcrModelConfig:
    def test_has_ocr_model_config_true(self):
        cfg = {"api_key": "sk-test", "ocr_model_name": "gpt-4o"}
        assert has_ocr_model_config(cfg) is True

    def test_has_ocr_model_config_false_missing_key(self):
        cfg = {"api_key": "", "ocr_model_name": "gpt-4o"}
        assert has_ocr_model_config(cfg) is False

    def test_has_ocr_model_config_false_missing_model(self):
        cfg = {"api_key": "sk-test", "ocr_model_name": ""}
        assert has_ocr_model_config(cfg) is False


class TestBuildImageList:
    def test_build_image_list_with_label(self):
        images = [{"label": "Screenshot", "bytes": b"fake"}]
        result = _build_image_list(images)
        assert "Screenshot" in result

    def test_build_image_list_without_label(self):
        images = [{"bytes": b"fake1"}, {"bytes": b"fake2"}]
        result = _build_image_list(images)
        assert "1. Image 1" in result
        assert "2. Image 2" in result

    def test_build_image_list_empty(self):
        result = _build_image_list([])
        assert result == ""


class TestSanitizeOcrText:
    def test_sanitize_ocr_text(self):
        assert _sanitize_ocr_text("  hello world  ") == "hello world"

    def test_sanitize_ocr_text_think_tags(self):
        text = "Before <thinking>secret thoughts</thinking> After"
        result = _sanitize_ocr_text(text)
        assert "Before" in result
        assert "After" in result
        assert "secret" not in result

    def test_sanitize_ocr_text_dsml(self):
        text = 'Text <|DSML|function_calls>something</|DSML|function_calls> more'
        result = _sanitize_ocr_text(text)
        assert "Text" in result
        assert "more" in result
        assert "DSML" not in result

    def test_sanitize_ocr_text_dsml_single_tag(self):
        text = 'Text <|DSML|something> more'
        result = _sanitize_ocr_text(text)
        assert "DSML" not in result

    def test_sanitize_ocr_text_empty(self):
        assert _sanitize_ocr_text("") == ""
        assert _sanitize_ocr_text("  ") == ""


class TestConstants:
    def test_ocr_system_prompt_not_empty(self):
        assert len(OCR_SYSTEM_PROMPT) > 0

    def test_default_ocr_prompt_template_not_empty(self):
        assert len(DEFAULT_OCR_PROMPT_TEMPLATE) > 0
