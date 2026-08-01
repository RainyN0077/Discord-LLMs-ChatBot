/**
 * Providers API — LLM provider list, health and dynamic switching.
 *
 * Backend contract (backend/app/routers/providers.py):
 *   GET  /api/bots/{bot_id}/providers      → ProviderListResponse
 *   POST /api/bots/{bot_id}/providers/switch → ProviderSwitchResponse
 */

import { fetchWithAuth } from './client'

export interface ProviderInfo {
  name: string
  model: string
  configured: boolean
  healthy: boolean | null
  latency_ms: number | null
  is_current: boolean
}

export interface ProviderListResponse {
  current_provider: string
  current_model: string
  providers: ProviderInfo[]
}

export interface ProviderSwitchRequest {
  provider: string
  model: string
  api_key: string
  base_url?: string
}

export interface ProviderSwitchResponse {
  message: string
  previous_provider: string
  current_provider: string
  current_model: string
  status: string
}

/** List providers (with cached health) for a bot. */
export async function fetchProviders(botId: string): Promise<ProviderListResponse> {
  // Trailing slash avoids the backend's 307 redirect (GET / → /).
  return fetchWithAuth<ProviderListResponse>(
    `/api/bots/${encodeURIComponent(botId)}/providers/`,
  )
}

/** Switch the bot's LLM provider (two-phase commit on the backend). */
export async function switchProvider(
  botId: string,
  payload: ProviderSwitchRequest,
): Promise<ProviderSwitchResponse> {
  return fetchWithAuth<ProviderSwitchResponse>(
    `/api/bots/${encodeURIComponent(botId)}/providers/switch`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}
