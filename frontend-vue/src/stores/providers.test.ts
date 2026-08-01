/**
 * Unit tests for the providers store (src/stores/providers.ts).
 *
 * Focus: the rate-limit/throttle state machine — a 429 response arms a 30s
 * countdown, blocks further switches, and auto-resets when it expires —
 * plus the fetch/switch happy paths and error handling.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiMocks = vi.hoisted(() => ({
  fetchProviders: vi.fn(),
  switchProvider: vi.fn(),
}))

vi.mock('@/api/providers', () => ({
  fetchProviders: apiMocks.fetchProviders,
  switchProvider: apiMocks.switchProvider,
}))

import { useProvidersStore } from '@/stores/providers'
import type { ProviderListResponse, ProviderSwitchResponse } from '@/api/providers'

const LIST_RESPONSE: ProviderListResponse = {
  current_provider: 'openai',
  current_model: 'gpt-4o',
  providers: [
    { name: 'openai', model: 'gpt-4o', configured: true, healthy: true, latency_ms: 100, is_current: true },
    { name: 'anthropic', model: 'claude-3.5', configured: true, healthy: true, latency_ms: 90, is_current: false },
  ],
}

const SWITCH_RESPONSE: ProviderSwitchResponse = {
  message: 'Provider switched',
  previous_provider: 'openai',
  current_provider: 'anthropic',
  current_model: 'claude-3.5',
  status: 'ok',
}

function makeStore() {
  setActivePinia(createPinia())
  return useProvidersStore()
}

beforeEach(() => {
  apiMocks.fetchProviders.mockReset()
  apiMocks.switchProvider.mockReset()
})

describe('providers store — fetch', () => {
  it('loads the provider list and current selection', async () => {
    apiMocks.fetchProviders.mockResolvedValueOnce(LIST_RESPONSE)
    const store = makeStore()

    await store.fetch('bot1')

    expect(store.providers).toHaveLength(2)
    expect(store.currentProvider).toBe('openai')
    expect(store.currentModel).toBe('gpt-4o')
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
    expect(apiMocks.fetchProviders).toHaveBeenCalledWith('bot1')
  })

  it('records fetch errors without leaving loading stuck', async () => {
    apiMocks.fetchProviders.mockRejectedValueOnce(new Error('backend down'))
    const store = makeStore()

    await store.fetch('bot1')

    expect(store.error).toBe('backend down')
    expect(store.loading).toBe(false)
  })

  it('ignores stale responses when the bot changed mid-flight', async () => {
    const store = makeStore()
    let resolveFirst!: (v: ProviderListResponse) => void
    apiMocks.fetchProviders
      .mockImplementationOnce(
        () =>
          new Promise<ProviderListResponse>((resolve) => {
            resolveFirst = resolve
          }),
      )
      .mockResolvedValueOnce(LIST_RESPONSE)

    const first = store.fetch('bot1')
    await store.fetch('bot2') // newer sequence number
    resolveFirst({
      current_provider: 'old',
      current_model: 'old-model',
      providers: [],
    })
    await first

    // bot1's stale result must not overwrite bot2's.
    expect(store.currentProvider).toBe('openai')
    expect(store.loading).toBe(false)
  })
})

describe('providers store — switching (rate-limit state machine)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('switches successfully, stores the message and refetches the list', async () => {
    apiMocks.switchProvider.mockResolvedValueOnce(SWITCH_RESPONSE)
    apiMocks.fetchProviders.mockResolvedValueOnce(LIST_RESPONSE)
    const store = makeStore()

    const ok = await store.switchTo('bot1', {
      provider: 'anthropic',
      model: 'claude-3.5',
      api_key: 'sk-test',
    })

    expect(ok).toBe(true)
    expect(store.lastSwitchMessage).toBe('Provider switched')
    expect(store.currentProvider).toBe('openai') // from the refetched list
    expect(store.rateLimited).toBe(false)
    expect(apiMocks.switchProvider).toHaveBeenCalledTimes(1)
  })

  it('arms the 30s countdown on 429 and clears it when it expires', async () => {
    apiMocks.switchProvider.mockRejectedValueOnce({
      status: 429,
      message: 'Too many switches — wait 30s',
    })
    const store = makeStore()

    const ok = await store.switchTo('bot1', {
      provider: 'anthropic',
      model: 'claude-3.5',
      api_key: 'k',
    })

    expect(ok).toBe(false)
    expect(store.rateLimited).toBe(true)
    expect(store.rateLimitRemaining).toBe(30)
    expect(store.error).toBe('Too many switches — wait 30s')

    // 29s in: still limited, countdown ticking.
    vi.advanceTimersByTime(29_000)
    expect(store.rateLimited).toBe(true)
    expect(store.rateLimitRemaining).toBe(1)

    // 30s total: the countdown finishes and resets the state.
    vi.advanceTimersByTime(1_000)
    expect(store.rateLimited).toBe(false)
    expect(store.rateLimitRemaining).toBe(0)
  })

  it('falls back to the default message when the 429 carries none', async () => {
    apiMocks.switchProvider.mockRejectedValueOnce({ status: 429 })
    const store = makeStore()

    await store.switchTo('bot1', {
      provider: 'anthropic',
      model: 'claude-3.5',
      api_key: 'k',
    })

    expect(store.rateLimited).toBe(true)
    expect(store.error).toBe('Rate limited — please wait before switching again')
  })

  it('rejects further switches while rate limited', async () => {
    apiMocks.switchProvider.mockRejectedValueOnce({ status: 429 })
    const store = makeStore()
    await store.switchTo('bot1', { provider: 'a', model: 'm', api_key: 'k' })
    expect(store.rateLimited).toBe(true)

    const ok = await store.switchTo('bot1', { provider: 'b', model: 'n', api_key: 'k' })

    expect(ok).toBe(false)
    expect(apiMocks.switchProvider).toHaveBeenCalledTimes(1) // no new API call
  })

  it('rejects concurrent switches while one is in flight', async () => {
    let resolveSwitch!: (v: ProviderSwitchResponse) => void
    apiMocks.switchProvider.mockImplementationOnce(
      () =>
        new Promise<ProviderSwitchResponse>((resolve) => {
          resolveSwitch = resolve
        }),
    )
    apiMocks.fetchProviders.mockResolvedValueOnce(LIST_RESPONSE)
    const store = makeStore()

    const first = store.switchTo('bot1', { provider: 'a', model: 'm', api_key: 'k' })
    const second = await store.switchTo('bot1', { provider: 'b', model: 'n', api_key: 'k' })

    expect(second).toBe(false)
    resolveSwitch(SWITCH_RESPONSE)
    await expect(first).resolves.toBe(true)
    expect(apiMocks.switchProvider).toHaveBeenCalledTimes(1)
  })

  it('records non-429 errors without arming the countdown', async () => {
    apiMocks.switchProvider.mockRejectedValueOnce(new Error('provider rejected'))
    const store = makeStore()

    const ok = await store.switchTo('bot1', { provider: 'a', model: 'm', api_key: 'k' })

    expect(ok).toBe(false)
    expect(store.error).toBe('provider rejected')
    expect(store.rateLimited).toBe(false)
    expect(store.rateLimitRemaining).toBe(0)
  })

  it('reset() clears the rate-limit state', async () => {
    apiMocks.switchProvider.mockRejectedValueOnce({ status: 429, message: 'nope' })
    const store = makeStore()
    await store.switchTo('bot1', { provider: 'a', model: 'm', api_key: 'k' })
    expect(store.rateLimited).toBe(true)

    store.reset()

    expect(store.rateLimited).toBe(false)
    expect(store.rateLimitRemaining).toBe(0)
    expect(store.error).toBeNull()
    expect(store.lastSwitchMessage).toBeNull()
  })

  it('clears lastSwitchMessage and error before each switch attempt', async () => {
    apiMocks.switchProvider.mockRejectedValueOnce({ status: 429 })
    apiMocks.switchProvider.mockResolvedValueOnce(SWITCH_RESPONSE)
    apiMocks.fetchProviders.mockResolvedValueOnce(LIST_RESPONSE)
    const store = makeStore()

    await store.switchTo('bot1', { provider: 'a', model: 'm', api_key: 'k' })
    expect(store.error).not.toBeNull()

    // Let the 30s countdown finish so the second attempt is allowed.
    vi.advanceTimersByTime(30_000)
    expect(store.rateLimited).toBe(false)

    // Second attempt starts with a clean slate and succeeds.
    const ok = await store.switchTo('bot1', { provider: 'a', model: 'm', api_key: 'k' })
    expect(ok).toBe(true)
    expect(store.error).toBeNull()
    expect(store.rateLimited).toBe(false)
  })
})
