/**
 * Prompt Studio shared constants — same-source port of the backend defaults
 * (`backend/app/routers/prompts.py`). Keep both in sync when editing.
 */

import type { PromptTemplate } from '@/api/prompts'

/** Default preset name (readonly on the backend — cannot save/delete).
 * Half-width parentheses, matching the legacy i18n value exactly. */
export const DEFAULT_PRESET_NAME = '(默认)开箱即用'

/** The 4 required template keys (import validation list, legacy parity). */
export const REQUIRED_TEMPLATE_KEYS = [
  'message_format',
  'user_request_block',
  'system_prompt_foundation_header',
  'operational_instructions',
] as const

/** 14-key default templates: 4 required + 10 optional + instruction list. */
export const DEFAULT_TEMPLATES: PromptTemplate = {
  // Required (4) — non-empty defaults
  message_format: '「{author_name}」说：\n{content}',
  user_request_block: '<user_request>\n{parts}\n</user_request>',
  system_prompt_foundation_header: '你是一个乐于助人的 AI 助手，请根据以下信息回答用户的问题。',
  operational_instructions: [],
  // Optional (10) — empty strings
  image_note: '',
  reply_context: '',
  deleted_reply_context: '',
  tool_context: '',
  memory_context: '',
  worldbook_context: '',
  system_prompt_persona_header: '',
  system_prompt_situation_header: '',
  system_prompt_participants_header: '',
  system_prompt_security_header: '',
}

/**
 * Left-nav grouping of the 14 keys (legacy parity: message context /
 * knowledge injection / system prompt structure / core instructions).
 * Keys are i18n paths resolved at render time via `promptStudio.nav.*`.
 */
export interface TemplateSection {
  titleKey: string
  items: { key: string; labelKey: string }[]
}

export const TEMPLATE_SECTIONS: TemplateSection[] = [
  {
    titleKey: 'promptStudio.nav.messageContext',
    items: [
      { key: 'message_format', labelKey: 'promptStudio.nav.messageFormat' },
      { key: 'image_note', labelKey: 'promptStudio.nav.imageNote' },
      { key: 'reply_context', labelKey: 'promptStudio.nav.replyContext' },
      { key: 'deleted_reply_context', labelKey: 'promptStudio.nav.deletedReplyContext' },
      { key: 'user_request_block', labelKey: 'promptStudio.nav.userRequestBlock' },
    ],
  },
  {
    titleKey: 'promptStudio.nav.knowledgeInjection',
    items: [
      { key: 'tool_context', labelKey: 'promptStudio.nav.toolContext' },
      { key: 'memory_context', labelKey: 'promptStudio.nav.memoryContext' },
      { key: 'worldbook_context', labelKey: 'promptStudio.nav.worldbookContext' },
    ],
  },
  {
    titleKey: 'promptStudio.nav.systemPromptStructure',
    items: [
      { key: 'system_prompt_foundation_header', labelKey: 'promptStudio.nav.foundationHeader' },
      { key: 'system_prompt_persona_header', labelKey: 'promptStudio.nav.personaHeader' },
      { key: 'system_prompt_situation_header', labelKey: 'promptStudio.nav.situationHeader' },
      { key: 'system_prompt_participants_header', labelKey: 'promptStudio.nav.participantsHeader' },
      { key: 'system_prompt_security_header', labelKey: 'promptStudio.nav.securityHeader' },
    ],
  },
  {
    titleKey: 'promptStudio.nav.coreInstructions',
    items: [{ key: 'operational_instructions', labelKey: 'promptStudio.nav.operationalInstructions' }],
  },
]

/** Placeholder hints per template key (legacy parity). */
export const TEMPLATE_PLACEHOLDERS: Record<string, string[]> = {
  message_format: ['{author_id}', '{content}', '{image_note}'],
  image_note: ['{count}'],
  reply_context: ['{author_info}', '{replied_content}'],
  tool_context: ['{data}'],
  memory_context: ['{data}'],
  worldbook_context: ['{data}'],
  user_request_block: ['{parts}'],
}

/** Deep-merge imported/loaded template JSON over the defaults (shape guard). */
export function normalizeTemplates(raw: unknown): PromptTemplate {
  const data = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const out: Record<string, unknown> = { ...DEFAULT_TEMPLATES }
  for (const key of Object.keys(out)) {
    if (key === 'operational_instructions') {
      out[key] = Array.isArray(data.operational_instructions)
        ? (data.operational_instructions as unknown[]).filter((i): i is string => typeof i === 'string')
        : []
    } else if (typeof data[key] === 'string') {
      out[key] = data[key]
    }
  }
  return out as unknown as PromptTemplate
}
