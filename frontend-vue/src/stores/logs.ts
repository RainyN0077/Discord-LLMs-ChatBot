/**
 * Logs store — periodic polling of backend logs with backoff and buffering.
 *
 * Polling: 5s base interval ×2 backoff on failure, capped at 60s.
 * Buffer: rows are trimmed to `maxLines` (default 500, persisted under
 * `logPanel.maxLines`). Switching bots resets state.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import { fetchWithAuth } from '@/api/client'

const BASE_INTERVAL_MS = 5000
const MAX_INTERVAL_MS = 60_000
const DEFAULT_MAX_LINES = 500
const MAX_LINE_OPTIONS = [200, 500, 1000, 2000]

export interface LogRow {
  raw: string
  level: 'ERROR' | 'WARN' | 'INFO' | 'DEBUG' | 'OTHER'
}

/** Read the persisted max line count, validated against the allowed set. */
function readMaxLines(): number {
  try {
    const n = Number(localStorage.getItem('logPanel.maxLines'))
    if (MAX_LINE_OPTIONS.includes(n)) return n
  } catch {
    // storage unavailable — fall back to the default
  }
  return DEFAULT_MAX_LINES
}

/** Classify a raw log line into a severity level. */
export function classifyLevel(line: string): LogRow['level'] {
  if (/\b(ERROR|CRITICAL|FATAL)\b/i.test(line)) return 'ERROR'
  if (/\bWARN(ING)?\b/i.test(line)) return 'WARN'
  if (/\bINFO\b/i.test(line)) return 'INFO'
  if (/\bDEBUG\b/i.test(line)) return 'DEBUG'
  return 'OTHER'
}

export const useLogsStore = defineStore('logs', () => {
  const rows = ref<LogRow[]>([])
  const maxLines = ref(readMaxLines())
  const botId = ref<string | null>(null)
  const polling = ref(false)
  const autoScroll = ref(true)
  const paused = ref(false)
  const error = ref<string | null>(null)

  let timer: ReturnType<typeof setTimeout> | null = null
  let intervalMs = BASE_INTERVAL_MS

  /** Start polling logs for the given bot. Resets state on botId change. */
  function start(targetBotId: string): void {
    if (botId.value !== targetBotId) {
      stop()
      rows.value = []
      botId.value = targetBotId
      intervalMs = BASE_INTERVAL_MS
      error.value = null
    }
    if (polling.value) return
    polling.value = true
    void pollOnce()
    scheduleNext()
  }

  /** Stop polling and cancel any pending timer. */
  function stop(): void {
    polling.value = false
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  /** Clear buffered rows (botId stays, polling keeps running). */
  function clear(): void {
    rows.value = []
  }

  /** Update the row cap: persist, then trim the current buffer immediately. */
  function setMaxLines(n: number): void {
    maxLines.value = n
    try {
      localStorage.setItem('logPanel.maxLines', String(n))
    } catch {
      // ignore persistence failures (storage may be disabled/blocked)
    }
    rows.value = rows.value.slice(-n)
  }

  /** Single fetch of the latest log tail (used by refresh button too). */
  async function pollOnce(): Promise<void> {
    if (!botId.value) return
    const id = botId.value
    try {
      const body = await fetchWithAuth<{ logs?: string[] }>(
        `/api/bots/${encodeURIComponent(id)}/logs`,
        { _noRetry: true },
      )
      // Discard stale responses: the bot may have been switched while this
      // request was in flight — bot A's logs must not overwrite bot B's.
      if (id !== botId.value) return
      const lines = Array.isArray(body?.logs) ? body.logs : []
      const newRows: LogRow[] = lines.map((raw) => ({
        raw,
        level: classifyLevel(raw),
      }))
      rows.value = [...newRows].slice(-maxLines.value)
      intervalMs = BASE_INTERVAL_MS
      error.value = null
    } catch (err) {
      if (id !== botId.value) return
      error.value = err instanceof Error ? err.message : String(err)
      // Backoff ×2 on failure, capped at 60s.
      intervalMs = Math.min(intervalMs * 2, MAX_INTERVAL_MS)
    }
  }

  /** Fetch immediately (refresh button) and keep the polling schedule ticking. */
  async function refresh(): Promise<void> {
    if (!botId.value) return
    await pollOnce()
    scheduleNext()
  }

  function scheduleNext(): void {
    if (timer !== null) clearTimeout(timer)
    if (!polling.value) return
    timer = setTimeout(() => {
      void pollOnce().then(scheduleNext)
    }, intervalMs)
  }

  return {
    rows,
    maxLines,
    botId,
    polling,
    autoScroll,
    paused,
    error,
    setMaxLines,
    start,
    stop,
    clear,
    refresh,
  }
})
