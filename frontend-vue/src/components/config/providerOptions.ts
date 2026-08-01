/**
 * Shared LLM provider option list (13 providers) for the main select and the
 * ocr/embedding/rerank selects. Labels reuse the `modelProviders.*` i18n keys
 * which already exist for all 13 values.
 */

export const PROVIDER_VALUES = [
  'openai',
  'grok',
  'openai_compatible',
  'gemini',
  'anthropic',
  'anthropic_compatible',
  'deepseek',
  'siliconflow',
  'volcengine',
  'dashscope',
  'moonshot',
  'zhipu',
  'stepfun',
] as const

export type ProviderValue = (typeof PROVIDER_VALUES)[number]

/** Build naive-ui select options for the current locale. */
export function providerOptions(t: (key: string) => string) {
  return PROVIDER_VALUES.map((value) => ({
    label: t(`modelProviders.${value}`),
    value,
  }))
}
