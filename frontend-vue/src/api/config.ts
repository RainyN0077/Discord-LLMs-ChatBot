/**
 * Config API — full per-bot configuration fetch/update.
 *
 * Backend contract (backend/app/routers/bots.py):
 *   GET /api/bots/{bot_id}/config → complete config object
 *   PUT /api/bots/{bot_id}/config → shallow merge (missing fields silently
 *   drop data!), so the client must ALWAYS round-trip the full config
 *   (deep copy → edit → full PUT).
 *
 * Field names mirror backend/app/config_cache.py DEFAULT_CONFIG and
 * backend/app/models.py Config.
 */

import { fetchWithAuth } from './client'
import type { PromptTemplate } from './prompts'

export interface ContextSettings {
  message_limit: number
  char_limit: number
  unlimited_context_length?: boolean
  unlimited_message_count?: boolean
}

export interface CustomParameter {
  name: string
  type: string
  value: string | number | boolean
}

export interface CustomHeader {
  name: string
  value: string
}

/** Shared shape for the ocr / embedding / rerank config groups (prefix + `_`). */
export interface AdvancedProviderConfig {
  provider: string
  api_key: string
  base_url: string | null
  port: string | null
  model_name: string
}

export interface OcrConfig extends AdvancedProviderConfig {
  prompt_template: string
  max_output_chars: number
  timeout_seconds: number
  timeout_disabled: boolean
}

export interface EmbeddingConfig extends AdvancedProviderConfig {
  dimensions: number
}

export interface RerankConfig extends AdvancedProviderConfig {
  // no extra fields beyond AdvancedProviderConfig
}

export interface AutomationConfig {
  auto_interject_enabled: boolean
  auto_interject_interval: number
  auto_interject_min_length: number
  repeat_parrot_enabled: boolean
  repeat_parrot_threshold: number
  repeat_parrot_case_sensitive: boolean
  repeat_parrot_trim_whitespace: boolean
  repeat_parrot_min_length: number
  repeat_parrot_require_multiple_users: boolean
}

export interface SearchSettings {
  enabled: boolean
  api_key: string
  api_url: string
  command: string
  trigger_mode: 'command' | 'keyword'
  keywords: string[]
  require_main_trigger: boolean
  rewrite_query_with_llm: boolean
  search_depth?: string
  max_results: number
  include_date: boolean
  exclude_domains: string[]
  compression_strategy: 'none' | 'truncate' | 'rag'
}

/** User persona portrait (config `user_personas` entry). */
export interface UserPersona {
  id?: string | null
  nickname?: string | null
  prompt?: string | null
  trigger_keywords: string[]
}

/** User inside a blocklist/whitelist rule (config `user_options.rules[*].users`). */
export interface UserBlocklistEntry {
  user_id: string
  user_display_name: string
  blacklist_mode: 'deny_response' | 'block_messages' | 'negative_portrait'
  negative_portrait: string
}

/** One blocklist/whitelist rule. */
export interface ScopeUserRule {
  scope_type: 'global' | 'guild' | 'channel' | 'dm'
  scope_id: string
  mode: 'blacklist' | 'whitelist'
  whitelist_behavior: 'triggers_only' | 'messages_only'
  users: Record<string, UserBlocklistEntry>
}

export interface UserOptionsConfig {
  enabled: boolean
  member_search_timeout_ms?: number
  rules: Record<string, ScopeUserRule>
}

export interface InteractionHistoryConfig {
  enabled: boolean
  max_storage_bytes: number
  auto_prune: boolean
}

/**
 * Scoped prompt entry (config `scoped_prompts.guilds/channels`).
 * Fields ported from legacy `frontend/src/components/ScopedPromptEditor.svelte`
 * (P3 parity): id / enabled / mode(append|override) / prompt.
 */
export interface ScopedPromptEntry {
  id?: string | null
  enabled: boolean
  mode: 'append' | 'override'
  prompt: string
}

/**
 * Role-based config entry (config `role_based_config`).
 * Fields ported from legacy `frontend/src/components/RoleConfigEditor.svelte`
 * (P3 parity): title / prompt / message & char quotas / display_color.
 */
export interface RoleConfigEntry {
  id?: string | null
  title: string
  prompt: string
  enable_message_limit: boolean
  message_limit: number
  message_refresh_minutes: number
  message_output_budget: number
  enable_char_limit: boolean
  char_limit: number
  char_refresh_minutes: number
  char_output_budget: number
  display_color: string
}

export interface ScopedPromptsConfig {
  guilds: Record<string, ScopedPromptEntry>
  channels: Record<string, ScopedPromptEntry>
}

/**
 * Plugin config registry. The built-in `search` plugin (Tavily) is typed here
 * so the config panel can edit it directly; user plugins stay free-form.
 */
export interface PluginsConfig {
  search?: Partial<SearchSettings>
  [key: string]: unknown
}

/** Full bot configuration object (mirrors DEFAULT_CONFIG + Config model). */
export interface BotConfig {
  bot_id: string
  bot_name: string
  platform: 'discord' | 'qq'
  enabled: boolean
  discord_token: string
  discord_intents: {
    guilds: boolean
    guild_messages: boolean
    direct_messages: boolean
    message_content: boolean
    members: boolean
  }
  llm_provider: string
  api_key: string
  base_url: string | null
  openai_base_url: string | null
  anthropic_base_url: string | null
  grok_base_url: string | null
  deepseek_base_url: string
  siliconflow_base_url: string
  volcengine_base_url: string
  dashscope_base_url: string
  moonshot_base_url: string
  zhipu_base_url: string
  stepfun_base_url: string
  temperature: number | null
  max_tokens: number | null
  top_p: number | null
  top_k: number | null
  frequency_penalty: number | null
  presence_penalty: number | null
  custom_headers: CustomHeader[]
  model_name: string
  llm_is_multimodal: boolean
  ocr_provider: string
  ocr_api_key: string
  ocr_base_url: string | null
  ocr_port: string | null
  ocr_model_name: string
  ocr_prompt_template: string
  ocr_max_output_chars: number
  ocr_timeout_seconds: number
  ocr_timeout_disabled: boolean
  embedding_provider: string
  embedding_api_key: string
  embedding_base_url: string | null
  embedding_port: string | null
  embedding_model_name: string
  embedding_dimensions: number
  rerank_provider: string
  rerank_api_key: string
  rerank_base_url: string | null
  rerank_port: string | null
  rerank_model_name: string
  system_prompt: string
  blocked_prompt_response: string
  bot_nickname: string | null
  trigger_keywords: string[]
  stream_response: boolean
  trigger_match_mode: string
  trigger_case_sensitive: boolean
  auto_interject_enabled: boolean
  auto_interject_interval: number
  auto_interject_min_length: number
  repeat_parrot_enabled: boolean
  repeat_parrot_threshold: number
  repeat_parrot_case_sensitive: boolean
  repeat_parrot_trim_whitespace: boolean
  repeat_parrot_min_length: number
  repeat_parrot_require_multiple_users: boolean
  memory_dedup_threshold: number
  world_book_dedup_threshold: number
  memory_embedding_enabled: boolean
  memory_rerank_enabled: boolean
  auto_memory_enabled: boolean
  auto_memory_min_length: number
  auto_memory_cooldown_seconds: number
  auto_memory_promote_min_observations: number
  auto_memory_promote_min_distinct_users: number
  auto_memory_quality_threshold: number
  auto_memory_direct_promote_ai_tag: boolean
  auto_memory_recall_top_k: number
  auto_memory_recall_char_limit: number
  auto_memory_recall_max_age_days: number
  user_personas: Record<string, UserPersona>
  role_based_config: Record<string, RoleConfigEntry>
  scoped_prompts: ScopedPromptsConfig
  user_options: UserOptionsConfig
  interaction_history: InteractionHistoryConfig
  /** Prompt Studio 14-key template structure (persisted as opaque config key). */
  prompt_templates?: PromptTemplate
  context_mode: 'none' | 'channel' | 'memory'
  channel_context_settings: ContextSettings
  memory_context_settings: ContextSettings
  custom_parameters: CustomParameter[]
  plugins: PluginsConfig
  quota_alert?: Record<string, unknown> | null
  api_secret_key: string
  runtime_type?: string
  /** Legacy passthrough field written by the AstrBot migration toggle. */
  provider_mode?: string
}

/** Fetch the complete config for a bot. */
export async function fetchBotConfig(botId: string): Promise<BotConfig> {
  return fetchWithAuth<BotConfig>(
    `/api/bots/${encodeURIComponent(botId)}/config`,
  )
}

/** Full-body PUT (backend merges shallowly — never send partial objects). */
export async function updateBotConfig(
  botId: string,
  config: BotConfig,
): Promise<{ message: string; status: string }> {
  return fetchWithAuth<{ message: string; status: string }>(
    `/api/bots/${encodeURIComponent(botId)}/config`,
    { method: 'PUT', body: JSON.stringify(config) },
  )
}
