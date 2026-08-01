/**
 * Unit tests for the logs store (src/stores/logs.ts).
 *
 * Focus: classifyLevel severity mapping plus the store's row-cap
 * persistence (readMaxLines / setMaxLines) and basic polling lifecycle
 * (start/stop/clear/pollOnce) with a mocked API client.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const clientMocks = vi.hoisted(() => ({
  fetchWithAuth: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  fetchWithAuth: clientMocks.fetchWithAuth,
}))

import { classifyLevel, useLogsStore } from '@/stores/logs'
import type { LogRow } from '@/stores/logs'

describe('classifyLevel — severity mapping', () => {
  it('maps ERROR / CRITICAL / FATAL to ERROR (case-insensitive)', () => {
    expect(classifyLevel('10:00:00 | ERROR | boom')).toBe('ERROR')
    expect(classifyLevel('10:00:00 | CRITICAL | boom')).toBe('ERROR')
    expect(classifyLevel('10:00:00 | FATAL | boom')).toBe('ERROR')
    expect(classifyLevel('fatal: disk full')).toBe('ERROR')
    expect(classifyLevel('error: connection lost')).toBe('ERROR')
  })

  it('maps WARN / WARNING to WARN', () => {
    expect(classifyLevel('WARN low disk')).toBe('WARN')
    expect(classifyLevel('warning: slow query')).toBe('WARN')
    expect(classifyLevel('Connection WARNING logged')).toBe('WARN')
  })

  it('maps INFO to INFO', () => {
    expect(classifyLevel('INFO: bot started')).toBe('INFO')
    expect(classifyLevel('info: ready')).toBe('INFO')
  })

  it('maps DEBUG to DEBUG', () => {
    expect(classifyLevel('DEBUG: trace 123')).toBe('DEBUG')
    expect(classifyLevel('debug: payload')).toBe('DEBUG')
  })

  it('maps unknown lines to OTHER', () => {
    expect(classifyLevel('just some plain text')).toBe('OTHER')
    expect(classifyLevel('')).toBe('OTHER')
    expect(classifyLevel('2026-08-01 10:00:00')).toBe('OTHER')
  })

  it('respects word boundaries (embedded keywords are not matched)', () => {
    expect(classifyLevel('SOMETHING_ERROR_IS_HERE')).toBe('OTHER')
    expect(classifyLevel('debugging_info')).toBe('OTHER')
    expect(classifyLevel('WARNINGLIGHTS')).toBe('OTHER')
  })

  it('gives ERROR precedence over lower severities', () => {
    expect(classifyLevel('INFO then ERROR happened')).toBe('ERROR')
    expect(classifyLevel('DEBUG then WARNING here')).toBe('WARN')
    expect(classifyLevel('WARNING and INFO both')).toBe('WARN')
  })
})

describe('logs store — maxLines persistence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    clientMocks.fetchWithAuth.mockReset()
  })

  it('defaults to 500 lines', () => {
    const store = useLogsStore()
    expect(store.maxLines).toBe(500)
  })

  it('reads a persisted valid option from localStorage', () => {
    localStorage.setItem('logPanel.maxLines', '1000')
    const store = useLogsStore()
    expect(store.maxLines).toBe(1000)
  })

  it('falls back to the default for invalid persisted values', () => {
    localStorage.setItem('logPanel.maxLines', '999')
    const store = useLogsStore()
    expect(store.maxLines).toBe(500)
    localStorage.setItem('logPanel.maxLines', 'not-a-number')
    const store2 = useLogsStore()
    expect(store2.maxLines).toBe(500)
  })

  it('persists setMaxLines and trims the current buffer', async () => {
    clientMocks.fetchWithAuth.mockResolvedValueOnce({ logs: ['INFO a', 'INFO b', 'WARN c'] })
    const store = useLogsStore()
    await store.start('bot1')
    expect(store.rows).toHaveLength(3)

    store.setMaxLines(200)
    expect(store.maxLines).toBe(200)
    expect(localStorage.getItem('logPanel.maxLines')).toBe('200')

    store.setMaxLines(1)
    expect(store.rows).toHaveLength(1)
    expect(store.rows[0].raw).toBe('WARN c')
  })
})

describe('logs store — polling lifecycle', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    clientMocks.fetchWithAuth.mockReset()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts polling, classifies rows and stops cleanly', async () => {
    clientMocks.fetchWithAuth.mockResolvedValueOnce({
      logs: ['INFO started', 'ERROR crash', 'plain line'],
    })
    const store = useLogsStore()

    await store.start('bot1')

    expect(store.botId).toBe('bot1')
    expect(store.polling).toBe(true)
    expect(store.rows.map((r: LogRow) => r.level)).toEqual(['INFO', 'ERROR', 'OTHER'])

    store.stop()
    expect(store.polling).toBe(false)
  })

  it('resets rows and error state when switching bots', async () => {
    clientMocks.fetchWithAuth.mockResolvedValueOnce({ logs: ['INFO a'] })
    const store = useLogsStore()
    await store.start('bot1')
    expect(store.rows).toHaveLength(1)

    clientMocks.fetchWithAuth.mockResolvedValueOnce({ logs: ['DEBUG b'] })
    await store.start('bot2')

    expect(store.rows).toHaveLength(1)
    expect(store.rows[0].raw).toBe('DEBUG b')
    expect(store.botId).toBe('bot2')
    expect(store.error).toBeNull()
  })

  it('records the error message and keeps rows on failure', async () => {
    clientMocks.fetchWithAuth.mockRejectedValueOnce(new Error('backend down'))
    const store = useLogsStore()

    await store.start('bot1')

    expect(store.error).toBe('backend down')
    expect(store.polling).toBe(true)
    store.stop()
  })

  it('ignores a stale poll response after the bot was switched', async () => {
    const store = useLogsStore()
    let resolveFirst!: (v: { logs: string[] }) => void
    clientMocks.fetchWithAuth
      .mockImplementationOnce(
        () =>
          new Promise<{ logs: string[] }>((resolve) => {
            resolveFirst = resolve
          }),
      )
      .mockResolvedValueOnce({ logs: ['INFO b'] })

    const first = store.start('bot1')
    await store.start('bot2') // switches botId before the first response lands
    resolveFirst({ logs: ['INFO stale-a'] })
    await first

    expect(store.rows).toHaveLength(1)
    expect(store.rows[0].raw).toBe('INFO b')
  })

  it('clears buffered rows without stopping polling', async () => {
    clientMocks.fetchWithAuth.mockResolvedValueOnce({ logs: ['INFO a', 'INFO b'] })
    const store = useLogsStore()
    await store.start('bot1')
    expect(store.rows).toHaveLength(2)

    store.clear()
    expect(store.rows).toHaveLength(0)
    expect(store.polling).toBe(true)
    store.stop()
  })

  it('refresh() fetches immediately and keeps polling alive', async () => {
    clientMocks.fetchWithAuth.mockResolvedValue({ logs: ['INFO x'] })
    const store = useLogsStore()
    await store.start('bot1')
    expect(clientMocks.fetchWithAuth).toHaveBeenCalledTimes(1)

    await store.refresh()
    expect(clientMocks.fetchWithAuth).toHaveBeenCalledTimes(2)
    expect(store.rows[0].raw).toBe('INFO x')
    store.stop()
  })
})
