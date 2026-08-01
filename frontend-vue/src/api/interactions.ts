/**
 * Interactions API — interaction-history tree, messages, usage, delete/prune,
 * and raw-context reconstruction.
 *
 * Signatures + query params ported verbatim from the legacy frontend
 * `frontend/src/lib/api.js` (fetchInteractionTree / fetchInteractionMessages /
 * fetchInteractionUsage / deleteInteractionRecords / pruneInteractions /
 * reconstructContext) and the call sites in `frontend/src/pages/Debugger.svelte`.
 *
 * Backend contract (backend/app/routers/interactions.py):
 *   GET    /api/interactions/{bot_id}/tree?guild_id=&role_id=&channel_id=&member_id=
 *   GET    /api/interactions/{bot_id}/messages?guild_id=&role_id=&channel_id=&member_id=&date=
 *   GET    /api/interactions/{bot_id}/usage
 *   DELETE /api/interactions/{bot_id}/delete?guild_id=&channel_id=&member_id=&date=
 *   POST   /api/interactions/{bot_id}/prune
 *   POST   /api/interactions/{bot_id}/context?guild_id=&role_id=&channel_id=&member_id=&date=
 */

import { fetchWithAuth } from './client'

/** One node of the interaction tree (role/channel/member/date combination). */
export interface InteractionTreeItem {
  role_id: string
  channel_id: string
  member_id: string
  date: string
  [key: string]: unknown
}

export interface InteractionTreeResponse {
  items: InteractionTreeItem[]
}

export interface InteractionMessage {
  message_id?: string
  timestamp?: string
  author_name?: string
  content?: string
  is_bot_reply?: boolean
  trigger_source?: string
  [key: string]: unknown
}

export interface InteractionMessagesResponse {
  messages: InteractionMessage[]
}

export interface InteractionUsage {
  used_bytes: number
  max_bytes: number
  percent: number
}

export interface DeleteInteractionFilters {
  guild_id?: string | null
  channel_id?: string | null
  member_id?: string | null
  date?: string | null
}

export interface ReconstructedMessage {
  timestamp?: string
  author_id?: string
  author_name?: string
  formatted_content?: string
  original_content?: string
}

export interface ReconstructedContext {
  system_prompt: string
  messages: ReconstructedMessage[]
}

/** Fetch the interaction tree, optionally filtered by guild/channel/member. */
export async function getInteractionTree(
  botId: string,
  filters: {
    guild_id?: string | null
    role_id?: string | null
    channel_id?: string | null
    member_id?: string | null
  } = {},
): Promise<InteractionTreeResponse> {
  const params = new URLSearchParams()
  if (filters.guild_id) params.set('guild_id', filters.guild_id)
  if (filters.role_id) params.set('role_id', filters.role_id)
  if (filters.channel_id) params.set('channel_id', filters.channel_id)
  if (filters.member_id) params.set('member_id', filters.member_id)
  const qs = params.toString()
  return fetchWithAuth<InteractionTreeResponse>(
    `/api/interactions/${encodeURIComponent(botId)}/tree${qs ? `?${qs}` : ''}`,
  )
}

/** Fetch the recorded messages for an exact role/channel/member/date slot. */
export async function getInteractionMessages(
  botId: string,
  guildId: string,
  roleId: string,
  channelId: string,
  memberId: string,
  date: string,
): Promise<InteractionMessagesResponse> {
  const params = new URLSearchParams({
    guild_id: guildId,
    role_id: roleId,
    channel_id: channelId,
    member_id: memberId,
    date,
  })
  return fetchWithAuth<InteractionMessagesResponse>(
    `/api/interactions/${encodeURIComponent(botId)}/messages?${params.toString()}`,
  )
}

/** Fetch the storage usage for one bot's interaction history. */
export async function getInteractionUsage(botId: string): Promise<InteractionUsage> {
  return fetchWithAuth<InteractionUsage>(
    `/api/interactions/${encodeURIComponent(botId)}/usage`,
  )
}

/** Delete records matching the (optional) filters; returns { deleted }. */
export async function deleteInteraction(
  botId: string,
  filters: DeleteInteractionFilters = {},
): Promise<{ deleted: number }> {
  const params = new URLSearchParams()
  if (filters.guild_id) params.set('guild_id', filters.guild_id)
  if (filters.channel_id) params.set('channel_id', filters.channel_id)
  if (filters.member_id) params.set('member_id', filters.member_id)
  if (filters.date) params.set('date', filters.date)
  const qs = params.toString()
  return fetchWithAuth<{ deleted: number }>(
    `/api/interactions/${encodeURIComponent(botId)}/delete${qs ? `?${qs}` : ''}`,
    { method: 'DELETE' },
  )
}

/** Prune the oldest records until the bot's storage budget is respected. */
export async function pruneInteractions(botId: string): Promise<{ pruned: number }> {
  return fetchWithAuth<{ pruned: number }>(
    `/api/interactions/${encodeURIComponent(botId)}/prune`,
    { method: 'POST' },
  )
}

/** Rebuild the raw context (system prompt + formatted messages) for a slot. */
export async function getInteractionContext(
  botId: string,
  guildId: string,
  roleId: string,
  channelId: string,
  memberId: string,
  date: string,
): Promise<ReconstructedContext> {
  const params = new URLSearchParams({
    guild_id: guildId,
    role_id: roleId,
    channel_id: channelId,
    member_id: memberId,
    date,
  })
  return fetchWithAuth<ReconstructedContext>(
    `/api/interactions/${encodeURIComponent(botId)}/context?${params.toString()}`,
    { method: 'POST' },
  )
}
