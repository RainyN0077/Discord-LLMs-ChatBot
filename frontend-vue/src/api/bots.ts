/**
 * Bots API — bot list, per-bot status, and config export/import.
 *
 * Status mirrors `BotInstance.to_status_dict` (backend/app/bot_instance.py),
 * which returns exactly these 10 fields.
 */

import { fetchWithAuth, getStoredApiKey, toApiError } from './client'

export interface BotSummary {
  bot_id: string
  bot_name: string
  platform: string
  enabled: boolean
  status: string
  uptime_seconds: number | null
  bot_nickname: string
  model_name: string
  llm_provider: string
  trigger_keywords: string[]
}

/** Fetch the list of registered bots. */
export async function fetchBots(): Promise<BotSummary[]> {
  // Trailing slash avoids the backend's 307 redirect (GET / → /).
  return fetchWithAuth<BotSummary[]>('/api/bots/')
}

/** Payload for POST /api/bots/ (mirrors backend `CreateBotRequest`). */
export interface CreateBotRequest {
  bot_id: string
  bot_name?: string
  platform?: 'discord' | 'qq'
  discord_token?: string
  llm_provider?: string
  api_key?: string
  model_name?: string
}

export interface BotOperationResult {
  message: string
  bot_id?: string
  status?: string
}

/** Create a new bot (POST /api/bots/ — trailing slash, mirrors GET). */
export async function createBot(payload: CreateBotRequest): Promise<BotOperationResult> {
  return fetchWithAuth<BotOperationResult>('/api/bots/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** Delete a bot and all its data (no trailing slash). */
export async function deleteBot(botId: string): Promise<BotOperationResult> {
  return fetchWithAuth<BotOperationResult>(`/api/bots/${encodeURIComponent(botId)}`, {
    method: 'DELETE',
  })
}

/** Rename a bot (PUT /api/bots/{id}/rename, body { new_id }). */
export async function renameBot(botId: string, newId: string): Promise<BotOperationResult> {
  return fetchWithAuth<BotOperationResult>(`/api/bots/${encodeURIComponent(botId)}/rename`, {
    method: 'PUT',
    body: JSON.stringify({ new_id: newId }),
  })
}

export async function startBot(botId: string): Promise<BotOperationResult> {
  return fetchWithAuth<BotOperationResult>(`/api/bots/${encodeURIComponent(botId)}/start`, {
    method: 'POST',
  })
}

export async function stopBot(botId: string): Promise<BotOperationResult> {
  return fetchWithAuth<BotOperationResult>(`/api/bots/${encodeURIComponent(botId)}/stop`, {
    method: 'POST',
  })
}

export async function restartBot(botId: string): Promise<BotOperationResult> {
  return fetchWithAuth<BotOperationResult>(`/api/bots/${encodeURIComponent(botId)}/restart`, {
    method: 'POST',
  })
}

export interface ExportResult {
  blob: Blob
  /** Filename parsed from the Content-Disposition header. */
  filename: string
}

export interface ImportResult {
  message: string
  bot_id: string
  status: string
}

/**
 * Export a bot's config as a JSON download (blob + filename).
 *
 * Blob endpoints bypass `fetchWithAuth` (JSON parsing would corrupt the
 * payload) and use a plain fetch with the stored API key; errors are still
 * normalized through `toApiError`.
 */
export async function exportBotConfig(botId: string): Promise<ExportResult> {
  const key = getStoredApiKey()
  const headers = new Headers()
  if (key) headers.set('X-API-Key', key)
  const res = await fetch(`/api/bots/${encodeURIComponent(botId)}/export`, {
    headers,
  })
  if (!res.ok) {
    const err = await toApiError(res)
    throw Object.assign(new Error(err.message || `HTTP ${res.status}`), {
      status: err.status ?? res.status,
    })
  }
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') || ''
  const filenameMatch = disposition.match(/filename="?(.+?)"?$/)
  const filename = filenameMatch ? filenameMatch[1] : `${botId}-config.json`
  return { blob, filename }
}

/**
 * Import a bot config from a JSON file (multipart form).
 *
 * The FormData body is NOT a string, so `fetchWithAuth` never injects a JSON
 * Content-Type — the browser sets the correct multipart boundary. The backend
 * returns 409 when the bot already exists and `overwrite` is false; callers
 * can inspect `err.status === 409` for the conflict feedback.
 */
export async function importBotConfig(
  file: File,
  overwrite: boolean,
): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('overwrite', String(overwrite))
  return fetchWithAuth<ImportResult>('/api/bots/import', {
    method: 'POST',
    body: formData,
  })
}
