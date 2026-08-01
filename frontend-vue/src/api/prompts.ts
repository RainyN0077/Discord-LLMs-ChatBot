/**
 * Prompts API — Prompt Studio preset management + backend preview.
 *
 * Backend contract (backend/app/routers/prompts.py):
 *   GET    /api/prompts/presets?bot_id=           → PresetItem[] (default first, readonly)
 *   GET    /api/prompts/presets/{name}?bot_id=    → PromptTemplate (default name → synthesized)
 *   PUT    /api/prompts/presets/{name}?bot_id=    → { message, name } (validates 4 required keys)
 *   DELETE /api/prompts/presets/{name}?bot_id=    → 204
 *   POST   /api/prompts/preview?bot_id=           → PromptPreviewResult
 *
 * Every call accepts an optional `botId` query param (undefined → global presets).
 */

import { fetchWithAuth } from './client'

/** 14-key prompt template structure (4 required + 10 optional). */
export interface PromptTemplate {
  message_format: string
  image_note: string
  reply_context: string
  deleted_reply_context: string
  user_request_block: string
  tool_context: string
  memory_context: string
  worldbook_context: string
  system_prompt_foundation_header: string
  system_prompt_persona_header: string
  system_prompt_situation_header: string
  system_prompt_participants_header: string
  system_prompt_security_header: string
  operational_instructions: string[]
}

/** List entry: default preset is synthesized server-side with readonly=true. */
export interface PresetItem {
  name: string
  readonly: boolean
}

export type PresetListResponse = PresetItem[]

/** Scenario simulator payload (mirrors preview_builder._create_mock_objects). */
export interface PromptPreviewScenario {
  user_id?: string
  user_roles?: string[]
  channel_id?: string
  guild_id?: string
  message_content?: string
  is_reply?: boolean
  replied_message?: { author_id?: string; content?: string }
  image_count?: number
  triggered_plugins?: { name: string; simulated_output: string }[]
  [key: string]: unknown
}

export interface PromptPreviewRequest {
  templates: PromptTemplate
  scenario: PromptPreviewScenario
}

export interface PromptPreviewResult {
  final_system_prompt: string
  final_user_request: string
  construction_log: string[]
}

function withBotId(path: string, botId?: string): string {
  if (!botId) return path
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}bot_id=${encodeURIComponent(botId)}`
}

/** List presets; the default readonly preset is always first. */
export async function listPresets(botId?: string): Promise<PresetListResponse> {
  return fetchWithAuth<PresetListResponse>(withBotId('/api/prompts/presets', botId))
}

/** Fetch one preset's templates (default name returns the synthesized defaults). */
export async function getPreset(name: string, botId?: string): Promise<PromptTemplate> {
  return fetchWithAuth<PromptTemplate>(
    withBotId(`/api/prompts/presets/${encodeURIComponent(name)}`, botId),
  )
}

/** Save (create/overwrite) a custom preset. */
export async function savePreset(
  name: string,
  templates: PromptTemplate,
  botId?: string,
): Promise<{ message: string; name: string }> {
  return fetchWithAuth<{ message: string; name: string }>(
    withBotId(`/api/prompts/presets/${encodeURIComponent(name)}`, botId),
    { method: 'PUT', body: JSON.stringify(templates) },
  )
}

/** Delete a custom preset (204). */
export async function deletePreset(name: string, botId?: string): Promise<void> {
  await fetchWithAuth<void>(
    withBotId(`/api/prompts/presets/${encodeURIComponent(name)}`, botId),
    { method: 'DELETE' },
  )
}

/** Ask the backend to build a live preview from templates + scenario. */
export async function preview(
  payload: PromptPreviewRequest,
  botId?: string,
): Promise<PromptPreviewResult> {
  return fetchWithAuth<PromptPreviewResult>(withBotId('/api/prompts/preview', botId), {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
