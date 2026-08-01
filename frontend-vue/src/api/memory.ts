/**
 * Knowledge base API — memory / world book / candidates / clear.
 *
 * Backend contract (backend/app/routers/memory.py):
 *   GET    /api/memory                          → MemoryItem[]
 *   POST   /api/memory                          → MemoryItem (created)
 *   PUT    /api/memory/{id}                     → 204 {content}
 *   DELETE /api/memory/{id}                     → 204
 *   GET    /api/memory/candidates               → MemoryCandidateItem[]
 *   POST   /api/memory/candidates/{id}/promote  → {candidate_id, memory_id}
 *   DELETE /api/memory/candidates/{id}          → 204
 *   GET    /api/worldbook                       → WorldBookItem[]
 *   POST   /api/worldbook                       → WorldBookItem (created)
 *   PUT    /api/worldbook/{id}                  → WorldBookItem
 *   DELETE /api/worldbook/{id}                  → 204
 *   POST   /api/memory/clear                    → {message}
 *
 * Endpoints are NOT bot-scoped (single active bot), matching the legacy
 * frontend's calls in frontend/src/lib/api.js.
 */

import { fetchWithAuth } from './client'

export interface MemoryItem {
  id?: number
  content: string
  timestamp?: string | null
  user_id?: string | null
  user_name?: string | null
  source?: string | null
  timezone?: string | null
}

export interface UpdateMemoryRequest {
  content: string
}

export interface WorldBookItem {
  id?: number
  keywords: string
  content: string
  enabled: boolean
  linked_user_id?: string | null
}

export interface MemoryCandidateItem {
  id: number
  content_sample: string
  first_seen: string
  last_seen: string
  seen_count: number
  distinct_user_count: number
  promoted: number
  promoted_memory_id?: number | null
  promoted_at?: string | null
  last_reason?: string | null
  user_ids: string[]
  channel_ids: string[]
  source_types: string[]
}

export interface PromoteCandidateResponse {
  candidate_id: number
  memory_id: number
}

/** List all memory items. */
export async function fetchMemoryItems(): Promise<MemoryItem[]> {
  return fetchWithAuth<MemoryItem[]>('/api/memory')
}

/** Add a memory item (user-supplied content/user/time/source). */
export async function addMemoryItem(item: MemoryItem): Promise<MemoryItem> {
  return fetchWithAuth<MemoryItem>('/api/memory', {
    method: 'POST',
    body: JSON.stringify(item),
  })
}

/** Update a memory item's content (204 on success). */
export async function updateMemoryItem(
  itemId: number,
  content: string,
): Promise<void> {
  const body: UpdateMemoryRequest = { content }
  await fetchWithAuth<void>(`/api/memory/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

/** Delete a memory item (204 on success). */
export async function deleteMemoryItem(itemId: number): Promise<void> {
  await fetchWithAuth<void>(`/api/memory/${itemId}`, { method: 'DELETE' })
}

/** List memory candidates, optionally including promoted ones. */
export async function fetchMemoryCandidates(
  includePromoted = false,
  limit = 200,
): Promise<MemoryCandidateItem[]> {
  const params = new URLSearchParams({
    include_promoted: includePromoted ? 'true' : 'false',
    limit: String(limit),
  })
  return fetchWithAuth<MemoryCandidateItem[]>(
    `/api/memory/candidates?${params.toString()}`,
  )
}

/** Promote a candidate into a full memory item. */
export async function promoteMemoryCandidate(
  candidateId: number,
): Promise<PromoteCandidateResponse> {
  return fetchWithAuth<PromoteCandidateResponse>(
    `/api/memory/candidates/${candidateId}/promote`,
    { method: 'POST' },
  )
}

/** Delete a memory candidate (204 on success). */
export async function deleteMemoryCandidate(candidateId: number): Promise<void> {
  await fetchWithAuth<void>(`/api/memory/candidates/${candidateId}`, {
    method: 'DELETE',
  })
}

/** List all world book entries. */
export async function fetchWorldBookItems(): Promise<WorldBookItem[]> {
  return fetchWithAuth<WorldBookItem[]>('/api/worldbook')
}

/** Add a world book entry. */
export async function addWorldBookItem(item: WorldBookItem): Promise<WorldBookItem> {
  return fetchWithAuth<WorldBookItem>('/api/worldbook', {
    method: 'POST',
    body: JSON.stringify(item),
  })
}

/** Update a world book entry. */
export async function updateWorldBookItem(
  itemId: number,
  item: WorldBookItem,
): Promise<WorldBookItem> {
  return fetchWithAuth<WorldBookItem>(`/api/worldbook/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify(item),
  })
}

/** Delete a world book entry (204 on success). */
export async function deleteWorldBookItem(itemId: number): Promise<void> {
  await fetchWithAuth<void>(`/api/worldbook/${itemId}`, { method: 'DELETE' })
}

/** Clear conversation memory for a channel (sets a memory cutoff). */
export async function clearMemories(channelId: string): Promise<{ message: string }> {
  return fetchWithAuth<{ message: string }>('/api/memory/clear', {
    method: 'POST',
    body: JSON.stringify({ channel_id: channelId }),
  })
}
