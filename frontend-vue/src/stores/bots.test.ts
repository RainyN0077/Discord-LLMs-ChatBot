/**
 * Unit tests for the bots store (src/stores/bots.ts).
 *
 * Focus: withOperating coverage for delete/rename (F9), the delete
 * selection fallback, the rename selection sync (incl. the mid-flight
 * click guard) and the createBot "ghost selection" fix (NEW-4).
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiMocks = vi.hoisted(() => ({
  fetchBots: vi.fn(),
  createBot: vi.fn(),
  deleteBot: vi.fn(),
  renameBot: vi.fn(),
  startBot: vi.fn(),
  stopBot: vi.fn(),
  restartBot: vi.fn(),
}))

vi.mock('@/api/bots', () => apiMocks)

import { useBotsStore } from '@/stores/bots'
import type { BotSummary } from '@/api/bots'

function makeBot(bot_id: string): BotSummary {
  return {
    bot_id,
    bot_name: bot_id,
    platform: 'discord',
    enabled: true,
    status: 'stopped',
    uptime_seconds: null,
    bot_nickname: '',
    model_name: 'gpt-4o',
    llm_provider: 'openai',
    trigger_keywords: [],
  }
}

const alpha = makeBot('alpha')
const bravo = makeBot('bravo')
const newbie = makeBot('newbie')

describe('bots store — withOperating covers delete/rename (F9)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    for (const fn of Object.values(apiMocks)) fn.mockReset()
  })

  it('marks the bot operating during delete and clears the marker after', async () => {
    let release!: (v: { message: string }) => void
    apiMocks.deleteBot.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve
        }),
    )
    const store = useBotsStore()
    store.bots = [alpha, bravo]

    const pending = store.deleteBot('alpha')
    // Let withOperating push the marker before the API resolves.
    await Promise.resolve()
    expect(store.operatingBotIds).toEqual(['alpha'])

    release({ message: 'ok' })
    await pending
    expect(store.operatingBotIds).toEqual([])
  })

  it('clears the operating marker when delete fails (finally)', async () => {
    apiMocks.deleteBot.mockRejectedValueOnce(new Error('boom'))
    const store = useBotsStore()
    store.bots = [alpha, bravo]

    await expect(store.deleteBot('alpha')).rejects.toThrow('boom')
    expect(store.operatingBotIds).toEqual([])
  })

  it('marks the bot operating during rename and clears it after', async () => {
    let release!: (v: { message: string; bot_id: string }) => void
    apiMocks.renameBot.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve
        }),
    )
    const store = useBotsStore()
    store.bots = [alpha, bravo]
    store.selectedBotId = 'alpha'

    const pending = store.renameBot('alpha', 'alice')
    await Promise.resolve()
    expect(store.operatingBotIds).toEqual(['alpha'])

    release({ message: 'ok', bot_id: 'alice' })
    await pending
    expect(store.operatingBotIds).toEqual([])
    expect(store.bots[0].bot_id).toBe('alice')
    expect(store.selectedBotId).toBe('alice')
  })

  it('falls back to the first bot when the selected bot is deleted', async () => {
    apiMocks.deleteBot.mockResolvedValue({ message: 'ok' })
    const store = useBotsStore()
    store.bots = [alpha, bravo]
    store.selectedBotId = 'alpha'

    await store.deleteBot('alpha')
    expect(store.bots.map((b) => b.bot_id)).toEqual(['bravo'])
    expect(store.selectedBotId).toBe('bravo')
  })

  it('does not clobber a selection made while the rename was in flight', async () => {
    let release!: (v: { message: string; bot_id: string }) => void
    apiMocks.renameBot.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve
        }),
    )
    const store = useBotsStore()
    store.bots = [alpha, bravo]
    store.selectedBotId = 'alpha'

    const pending = store.renameBot('alpha', 'alice')
    store.selectedBotId = 'bravo' // user clicked another card mid-flight
    release({ message: 'ok', bot_id: 'alice' })
    await pending

    expect(store.bots[0].bot_id).toBe('alice')
    expect(store.selectedBotId).toBe('bravo')
  })
})

describe('bots store — createBot selection (NEW-4 ghost fix)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    for (const fn of Object.values(apiMocks)) fn.mockReset()
  })

  it('selects the newly created bot after a successful refresh', async () => {
    apiMocks.createBot.mockResolvedValue({ message: 'ok', bot_id: 'newbie' })
    apiMocks.fetchBots.mockResolvedValue([alpha, bravo, newbie])
    const store = useBotsStore()

    await store.createBot({ bot_id: 'newbie', bot_name: 'New' })
    expect(store.selectedBotId).toBe('newbie')
    expect(store.selectedBot?.bot_id).toBe('newbie')
  })

  it('keeps the current selection when the list refresh fails (no ghost id)', async () => {
    apiMocks.createBot.mockResolvedValue({ message: 'ok', bot_id: 'newbie' })
    apiMocks.fetchBots.mockRejectedValue(new Error('list down'))
    const store = useBotsStore()
    store.bots = [alpha, bravo]
    store.selectedBotId = 'alpha'

    await store.createBot({ bot_id: 'newbie', bot_name: 'New' })
    expect(store.error).toBe('list down')
    // The ghost id must NOT be selected — the list still holds the old bots.
    expect(store.selectedBotId).toBe('alpha')
    expect(store.selectedBot?.bot_id).toBe('alpha')
  })

  it('keeps selection null when the refresh failed and nothing was selected', async () => {
    apiMocks.createBot.mockResolvedValue({ message: 'ok', bot_id: 'newbie' })
    apiMocks.fetchBots.mockRejectedValue(new Error('list down'))
    const store = useBotsStore()

    await store.createBot({ bot_id: 'newbie', bot_name: 'New' })
    expect(store.selectedBotId).toBeNull()
    expect(store.selectedBot).toBeNull()
  })
})
