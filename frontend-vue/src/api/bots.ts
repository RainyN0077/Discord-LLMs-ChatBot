/**
 * Bots API — bot list and per-bot status.
 *
 * Mirrors `BotInstance.to_status_dict` (backend/app/bot_instance.py), which
 * returns exactly these 10 fields.
 */

import { fetchWithAuth } from './client'

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
