/**
 * LLM provider defaults — migrated from the legacy frontend
 * (`frontend/src/lib/providerDefaults.js`, the single source of truth).
 *
 * `KNOWN_PROVIDERS`: the 7 China-hosted providers whose official API base
 * URLs are pre-filled into `openai_base_url` when the field is empty (the
 * Base URL input is hidden for these providers).
 *
 * `PROVIDER_DEFAULTS.baseUrl` values match the legacy file entry-for-entry;
 * `defaultModel` is the first model id of the legacy hardcoded model lists
 * (the design reduces the legacy multi-model lists to a single default).
 */

export const KNOWN_PROVIDERS: string[] = [
  'deepseek',
  'siliconflow',
  'volcengine',
  'dashscope',
  'moonshot',
  'zhipu',
  'stepfun',
]

export interface ProviderDefaults {
  baseUrl: string
  defaultModel?: string
}

export const PROVIDER_DEFAULTS: Record<string, ProviderDefaults> = {
  deepseek: {
    baseUrl: 'https://api.deepseek.com',
    defaultModel: 'deepseek-v4-pro',
  },
  siliconflow: {
    baseUrl: 'https://api.siliconflow.cn/v1',
    defaultModel: 'deepseek-ai/DeepSeek-V4-Flash',
  },
  volcengine: {
    baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    defaultModel: 'doubao-1.5-pro-32k',
  },
  dashscope: {
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    defaultModel: 'qwen3.6-max-preview',
  },
  moonshot: {
    baseUrl: 'https://api.moonshot.cn/v1',
    defaultModel: 'kimi-k2.6',
  },
  zhipu: {
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    defaultModel: 'glm-5.1',
  },
  stepfun: {
    baseUrl: 'https://api.stepfun.com/v1',
    defaultModel: 'step-3.5-flash',
  },
}

/** The 11 main-LLM provider values (i18n labels: `llmProvider.providers.*`). */
export const LLM_PROVIDER_VALUES: string[] = [
  'openai',
  'grok',
  'google',
  'anthropic',
  'deepseek',
  'siliconflow',
  'volcengine',
  'dashscope',
  'moonshot',
  'zhipu',
  'stepfun',
]

export type LLMProviderValue = (typeof LLM_PROVIDER_VALUES)[number]

export interface BaseUrlSource {
  llm_provider: string
  grok_base_url?: string | null
  anthropic_base_url?: string | null
  openai_base_url?: string | null
}

/** Resolve the active base_url value (mirrors legacy `getProviderBaseUrl`). */
export function getProviderBaseUrl(config: BaseUrlSource): string {
  if (config.llm_provider === 'grok') return config.grok_base_url || ''
  if (config.llm_provider === 'anthropic') return config.anthropic_base_url || ''
  return config.openai_base_url || ''
}
