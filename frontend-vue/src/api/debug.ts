/**
 * Debug API — simulate, capture inspection, and DSML/thinking sanitize.
 *
 * Backend contract (backend/app/routers/debug.py):
 *   POST /api/debug/simulate                    → DebugSimulateResult
 *   GET  /api/debug/captures?limit=&channel_id= → DebugCaptureSummary[]
 *   GET  /api/debug/captures/{id}               → DebugCaptureDetail
 *   POST /api/debug/sanitize                    → DebugSanitizeResult
 */

import { fetchWithAuth } from './client'

/** Payload for POST /api/debug/simulate (bot_id optional → per-bot config). */
export interface DebugSimulateRequest {
  user_id: string
  channel_id: string
  guild_id?: string | null
  role_id?: string | null
  message_content: string
  bot_id?: string | null
}

export interface DebugSimulateResult {
  generated_system_prompt: string
  formatted_user_request: string
  llm_response: string
  active_directives_log: string[]
}

export interface DebugCaptureSummary {
  id: string
  captured_at: string
  trigger_message_id: string
  channel_id: string
  guild_id: string | null
  user_id: string
  user_name: string
  user_display_name: string
  trigger_sources: string[]
  raw_user_message: string
  provider: string
  model: string
}

export interface DebugCaptureDetail extends DebugCaptureSummary {
  plugin_outputs: string[]
  formatted_user_request: string
  system_prompt: string
  history_for_llm: Record<string, unknown>[]
  llm_messages: Record<string, unknown>[]
  intermediate_llm_responses: string[]
  raw_llm_response: string
  cleaned_llm_response: string
  usage: Record<string, unknown> | null
}

export interface DebugSanitizeResult {
  original_text: string
  sanitized_text: string
}

/** Run the debug simulation against a bot (or the global config when no botId). */
export async function simulate(
  payload: DebugSimulateRequest,
): Promise<DebugSimulateResult> {
  return fetchWithAuth<DebugSimulateResult>('/api/debug/simulate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** List captured debug conversations (default limit 50). */
export async function listCaptures(
  limit = 50,
  channelId?: string,
): Promise<DebugCaptureSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (channelId && channelId.trim()) params.set('channel_id', channelId.trim())
  return fetchWithAuth<DebugCaptureSummary[]>(`/api/debug/captures?${params.toString()}`)
}

/** Fetch the full detail of one capture. */
export async function getCapture(captureId: string): Promise<DebugCaptureDetail> {
  return fetchWithAuth<DebugCaptureDetail>(
    `/api/debug/captures/${encodeURIComponent(captureId)}`,
  )
}

/** Strip DSML tool blocks + thinking sections from raw model output. */
export async function sanitize(text: string): Promise<DebugSanitizeResult> {
  return fetchWithAuth<DebugSanitizeResult>('/api/debug/sanitize', {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}
