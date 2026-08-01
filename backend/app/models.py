from typing import Any, Dict, List, Literal, Optional
from pathlib import Path

from pydantic import BaseModel, Field, ConfigDict

from .ocr_service import DEFAULT_OCR_PROMPT_TEMPLATE, OCR_TIMEOUT_SECONDS


class Persona(BaseModel):
    id: Optional[str] = None
    nickname: Optional[str] = None
    prompt: Optional[str] = None
    trigger_keywords: List[str] = Field(default_factory=list)


class RoleConfig(BaseModel):
    id: Optional[str] = None
    title: str = ""
    prompt: str = ""
    enable_message_limit: bool = False
    message_limit: int = Field(0, ge=0)
    message_refresh_minutes: int = Field(60, ge=1)
    message_output_budget: int = Field(1, ge=1)
    enable_char_limit: bool = False
    char_limit: int = Field(0, ge=0)
    char_refresh_minutes: int = Field(60, ge=1)
    char_output_budget: int = Field(300, ge=0)
    display_color: str = "#ffffff"


class UserBlocklistEntry(BaseModel):
    user_id: str
    user_display_name: str = ""
    blacklist_mode: Literal["negative_portrait", "block_messages", "deny_response"] = "deny_response"
    negative_portrait: str = ""


class UserOptionRule(BaseModel):
    scope_type: Literal["global", "guild", "channel", "dm"] = "global"
    scope_id: str = ""
    mode: Literal["blacklist", "whitelist"] = "blacklist"
    whitelist_behavior: Literal["messages_only", "triggers_only"] = "triggers_only"
    users: Dict[str, UserBlocklistEntry] = Field(default_factory=dict)


class UserOptionsConfig(BaseModel):
    enabled: bool = False
    member_search_timeout_ms: int = Field(5000, ge=1000, le=30000)
    rules: Dict[str, UserOptionRule] = Field(default_factory=dict)


class InteractionHistoryConfig(BaseModel):
    enabled: bool = True
    max_storage_bytes: int = Field(524288000, ge=10485760)
    auto_prune: bool = True


class ContextSettings(BaseModel):
    message_limit: int = Field(ge=0)
    char_limit: int = Field(ge=0)
    unlimited_context_length: bool = False
    unlimited_message_count: bool = False


class CustomParameter(BaseModel):
    name: str
    type: str
    value: Any


class PluginHttpRequestConfig(BaseModel):
    url: str = ""
    method: str = "GET"
    headers: str = "{}"
    body_template: str = "{}"
    allow_internal_requests: bool = False


class PluginConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = "New Plugin"
    enabled: bool = True
    trigger_type: str = "command"
    injection_mode: str = "override"
    triggers: List[str] = Field(default_factory=list)
    action_type: str = "http_request"
    http_request_config: PluginHttpRequestConfig = Field(default_factory=PluginHttpRequestConfig)
    llm_prompt_template: str = "Summarize: {api_result}"


class ScopedPromptItem(BaseModel):
    id: Optional[str] = None
    enabled: bool = True
    mode: str = "append"
    prompt: str = ""


class ScopedPrompts(BaseModel):
    guilds: Dict[str, ScopedPromptItem] = Field(default_factory=dict)
    channels: Dict[str, ScopedPromptItem] = Field(default_factory=dict)


class BotInstanceStatus(BaseModel):
    bot_id: str
    bot_name: str
    platform: str
    adapter: str = ""
    enabled: bool
    status: str = "stopped"
    uptime_seconds: Optional[float] = None


class CreateBotRequest(BaseModel):
    bot_id: str = Field(..., pattern=r'^[a-z0-9_-]+$')
    bot_name: str = "Unnamed Bot"
    platform: Literal["discord", "qq"] = "discord"
    enabled: bool = True
    discord_token: str = ""
    llm_provider: str = "openai"
    api_key: str = ""
    model_name: str = "gpt-4o"


class Config(BaseModel):
    bot_id: str = Field(default="", pattern=r'^[a-z0-9_-]*$')
    bot_name: str = "Unnamed Bot"
    platform: Literal["discord", "qq"] = "discord"
    enabled: bool = True
    discord_token: str
    discord_intents: Dict[str, bool] = Field(default_factory=dict)
    llm_provider: str
    api_key: str
    base_url: Optional[str] = None
    openai_base_url: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    grok_base_url: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1)
    top_p: Optional[float] = Field(None, ge=0, le=1)
    top_k: Optional[int] = Field(None, ge=1)
    frequency_penalty: Optional[float] = Field(None, ge=-2, le=2)
    presence_penalty: Optional[float] = Field(None, ge=-2, le=2)
    custom_headers: List[dict] = Field(default_factory=list)
    model_name: str
    llm_is_multimodal: bool = True
    ocr_provider: str = "openai"
    ocr_api_key: str = ""
    ocr_base_url: Optional[str] = None
    ocr_port: Optional[str] = None
    ocr_model_name: str = ""
    ocr_prompt_template: str = DEFAULT_OCR_PROMPT_TEMPLATE
    ocr_max_output_chars: int = Field(4000, ge=200, le=20000)
    ocr_timeout_seconds: int = Field(OCR_TIMEOUT_SECONDS, ge=1, le=86400)
    ocr_timeout_disabled: bool = False
    embedding_provider: str = "openai"
    embedding_api_key: str = ""
    embedding_base_url: Optional[str] = None
    embedding_port: Optional[str] = None
    embedding_model_name: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(1536, ge=1)
    rerank_provider: str = "openai"
    rerank_api_key: str = ""
    rerank_base_url: Optional[str] = None
    rerank_port: Optional[str] = None
    rerank_model_name: str = "gpt-4.1-mini"
    system_prompt: str
    blocked_prompt_response: str
    bot_nickname: Optional[str] = None
    trigger_keywords: List[str]
    stream_response: bool
    trigger_match_mode: str = "contains"
    trigger_case_sensitive: bool = False
    auto_interject_enabled: bool = False
    auto_interject_interval: int = Field(20, ge=1)
    auto_interject_min_length: int = Field(0, ge=0)
    repeat_parrot_enabled: bool = False
    repeat_parrot_threshold: int = Field(3, ge=2)
    repeat_parrot_case_sensitive: bool = False
    repeat_parrot_trim_whitespace: bool = True
    repeat_parrot_min_length: int = Field(2, ge=0)
    repeat_parrot_require_multiple_users: bool = True
    memory_dedup_threshold: Optional[float] = Field(0.0, ge=0, le=1)
    world_book_dedup_threshold: Optional[float] = Field(0.0, ge=0, le=1)
    user_personas: Dict[str, Persona] = Field(default_factory=dict)
    role_based_config: Dict[str, RoleConfig] = Field(default_factory=dict)
    user_options: UserOptionsConfig = Field(default_factory=UserOptionsConfig)
    interaction_history: InteractionHistoryConfig = Field(default_factory=InteractionHistoryConfig)
    scoped_prompts: ScopedPrompts = Field(default_factory=ScopedPrompts)
    context_mode: str
    channel_context_settings: ContextSettings
    memory_context_settings: ContextSettings
    custom_parameters: List[CustomParameter] = Field(default_factory=list)
    plugins: Dict[str, PluginConfig] = Field(default_factory=dict)
    quota_alert: Optional[Dict[str, Any]] = None
    api_secret_key: str


class ClearMemoryRequest(BaseModel):
    channel_id: str


class PluginTriggerRequest(BaseModel):
    plugin_name: str
    args: Dict[str, Any] = Field(default_factory=dict)
    message_content: str = ""
    author_id: int = 0
    author_name: str = "API"
    author_display_name: str = "API"
    channel_id: str = "0"
    guild_id: str = "0"


class DebuggerRequest(BaseModel):
    user_id: str
    channel_id: str
    guild_id: Optional[str] = None
    role_id: Optional[str] = None
    message_content: str
    bot_id: Optional[str] = None


class ModelTestRequest(BaseModel):
    provider: str
    api_key: str
    base_url: Optional[str] = None
    model_name: str
    task: str = "chat"
    ocr_timeout_seconds: Optional[int] = Field(None, ge=1, le=86400)
    ocr_timeout_disabled: bool = False


class AvailableModelsRequest(BaseModel):
    provider: str
    api_key: str
    base_url: Optional[str] = None
    task: str = "chat"


class DirectChatAttachment(BaseModel):
    name: str
    content_type: Optional[str] = None
    data_base64: str
    size: Optional[int] = None


class DirectChatMessage(BaseModel):
    role: str
    content: str


class DirectChatDebugContext(BaseModel):
    user_id: str = "100000000000000001"
    channel_id: str = "100000000000000002"
    guild_id: Optional[str] = None
    role_id: Optional[str] = None


class DirectChatRequest(BaseModel):
    messages: List[DirectChatMessage] = Field(default_factory=list)
    attachments: List[DirectChatAttachment] = Field(default_factory=list)
    include_system_prompt: bool = True
    debug_mode: bool = False
    debug_context: Optional[DirectChatDebugContext] = None
    bot_id: Optional[str] = None


class DirectChatUserDebugDetail(BaseModel):
    original_content: str = ""
    formatted_content: str = ""
    attachment_context: str = ""
    ocr_output: str = ""
    attachment_names: List[str] = Field(default_factory=list)
    used_multimodal_images: bool = False


class DirectChatResponse(BaseModel):
    success: bool
    response: str
    usage: Optional[Dict[str, int]] = None
    provider: str
    model: str
    debug_mode: bool = False
    formatted_user_messages: Optional[List[str]] = None
    debug_user_details: Optional[List[DirectChatUserDebugDetail]] = None


class DebugCaptureSummary(BaseModel):
    id: str
    captured_at: str
    trigger_message_id: str
    channel_id: str
    guild_id: Optional[str] = None
    user_id: str
    user_name: str
    user_display_name: str
    trigger_sources: List[str] = Field(default_factory=list)
    raw_user_message: str
    provider: str = ""
    model: str = ""


class DebugCaptureDetail(DebugCaptureSummary):
    plugin_outputs: List[str] = Field(default_factory=list)
    formatted_user_request: str = ""
    system_prompt: str = ""
    history_for_llm: List[Dict[str, Any]] = Field(default_factory=list)
    llm_messages: List[Dict[str, Any]] = Field(default_factory=list)
    intermediate_llm_responses: List[str] = Field(default_factory=list)
    raw_llm_response: str = ""
    cleaned_llm_response: str = ""
    usage: Optional[Dict[str, Any]] = None


class DebugSanitizeRequest(BaseModel):
    text: str = ""


class DebugSanitizeResponse(BaseModel):
    original_text: str
    sanitized_text: str


class PromptPreviewTemplates(BaseModel):
    model_config = ConfigDict(extra="allow")


class PromptPreviewScenario(BaseModel):
    model_config = ConfigDict(extra="allow")


class PromptPreviewRequest(BaseModel):
    templates: PromptPreviewTemplates
    scenario: PromptPreviewScenario


class MemoryItem(BaseModel):
    id: Optional[int] = None
    content: str
    timestamp: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    source: Optional[str] = None
    timezone: Optional[str] = None


class WorldBookItem(BaseModel):
    id: Optional[int] = None
    keywords: str
    content: str
    enabled: bool = True
    linked_user_id: Optional[str] = None


class UpdateMemoryRequest(BaseModel):
    content: str


class MemoryCandidateItem(BaseModel):
    id: int
    content_sample: str
    first_seen: str
    last_seen: str
    seen_count: int
    distinct_user_count: int
    promoted: int
    promoted_memory_id: Optional[int] = None
    promoted_at: Optional[str] = None
    last_reason: Optional[str] = None
    user_ids: List[str] = Field(default_factory=list)
    channel_ids: List[str] = Field(default_factory=list)
    source_types: List[str] = Field(default_factory=list)


class PromoteCandidateResponse(BaseModel):
    candidate_id: int
    memory_id: int


class PricingConfig(BaseModel):
    model: str
    input_price_per_1k: float
    output_price_per_1k: float


# ---------------------------------------------------------------------------
# Provider management models (Wave 4, 1.3.6)
# ---------------------------------------------------------------------------


class ProviderInfo(BaseModel):
    """单个 Provider 信息及健康状态."""
    name: str
    model: str
    healthy: Optional[bool] = None
    latency_ms: Optional[float] = None
    configured: bool = False
    is_current: bool = False


class ProviderSwitchRequest(BaseModel):
    """Provider 切换请求（P1-6 修复：增加约束防注入）."""
    provider: str = Field(
        ..., min_length=1, max_length=64,
        pattern=r'^[a-z][a-z0-9_]*$',
        description="Provider name, e.g. 'openai', 'anthropic'",
    )
    model: str = Field(
        ..., min_length=1, max_length=128,
        description="Model name, e.g. 'gpt-4o', 'claude-sonnet-4-20250514'",
    )
    api_key: str = Field(
        ..., min_length=8, max_length=2048,
        description="API key for the new provider",
    )
    base_url: Optional[str] = Field(
        None, max_length=2048,
        pattern=r'^https?://[a-zA-Z0-9.-]+(?::\d{1,5})?(?:/.*)?$',
        description="Optional base URL override for the provider",
    )


class ProviderListResponse(BaseModel):
    """GET /providers 响应."""
    current_provider: str
    current_model: str
    providers: List[ProviderInfo]


class ProviderSwitchResponse(BaseModel):
    """POST /providers/switch 响应."""
    message: str
    previous_provider: str
    current_provider: str
    current_model: str
    status: str


TEXT_ATTACHMENT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", ".xml", ".html",
    ".htm", ".js", ".ts", ".py", ".java", ".c", ".cpp", ".h", ".hpp", ".rs",
    ".go", ".sql", ".ini", ".toml", ".cfg",
}
TEXT_ATTACHMENT_MIME_PREFIXES = ("text/",)
TEXT_ATTACHMENT_MIME_EXACT = {
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-javascript",
    "application/x-yaml",
    "application/yaml",
}
DIRECT_CHAT_MAX_ATTACHMENTS = 10
DIRECT_CHAT_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
DIRECT_CHAT_MAX_TOTAL_ATTACHMENT_BYTES = 20 * 1024 * 1024
DIRECT_CHAT_TEXT_PREVIEW_CHARS = 6000
