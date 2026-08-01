/**
 * Unit tests for the auth store (src/stores/auth.ts).
 *
 * Covers the bootstrap fail path — in particular M2: when the
 * /api/auth/status request times out (10s AbortController in client.ts),
 * fetchWithAuth rejects and init() must mark the bootstrap as failed so
 * App.vue leaves the full-screen loader and MainLayout renders the
 * banner + retry button instead of hanging forever.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const clientMocks = vi.hoisted(() => ({
  fetchWithAuth: vi.fn(),
  storeApiKey: vi.fn(),
}))

vi.mock('@/api/client', () => clientMocks)

import { useAuthStore } from '@/stores/auth'

describe('auth store — bootstrap (M2 fail path)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    clientMocks.fetchWithAuth.mockReset()
    clientMocks.storeApiKey.mockReset()
  })

  it('marks the bootstrap as failed when the auth request times out', async () => {
    // client.ts fetchWithAuth rejects with this after the 10s abort fires.
    clientMocks.fetchWithAuth.mockRejectedValue(
      new Error('Auth request timed out after 10000ms'),
    )
    const store = useAuthStore()

    await store.init()

    expect(store.status).toBe('fail')
    expect(store.error).toBe('Auth request timed out after 10000ms')
  })

  it('marks the bootstrap as failed on any other rejection', async () => {
    clientMocks.fetchWithAuth.mockRejectedValue(new Error('network down'))
    const store = useAuthStore()

    await store.init()

    expect(store.status).toBe('fail')
    expect(store.error).toBe('network down')
  })

  it('bootstraps to ok and persists the key when the backend responds', async () => {
    clientMocks.fetchWithAuth.mockResolvedValue({ api_secret_key: 'fresh-key' })
    const store = useAuthStore()

    await store.init()

    expect(store.status).toBe('ok')
    expect(store.error).toBeNull()
    expect(clientMocks.storeApiKey).toHaveBeenCalledWith('fresh-key')
  })
})
