/**
 * Auth store — backend authentication bootstrap state.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import { fetchWithAuth, storeApiKey } from '@/api/client'

export type AuthStatus = 'idle' | 'ok' | 'fail'

export const useAuthStore = defineStore('auth', () => {
  const status = ref<AuthStatus>('idle')
  const error = ref<string | null>(null)

  /** Bootstrap the API key from /api/auth/status (localhost only). */
  async function init(): Promise<void> {
    reset()
    try {
      const body = await fetchWithAuth<{ api_secret_key?: string }>(
        '/api/auth/status',
        { _noRetry: true },
      )
      if (body?.api_secret_key) {
        storeApiKey(body.api_secret_key)
        status.value = 'ok'
      } else {
        markFail('Backend returned no api_secret_key (non-localhost request?)')
      }
    } catch (err) {
      markFail(err instanceof Error ? err.message : String(err))
    }
  }

  /** Mark the auth bootstrap as failed (with a user-visible message). */
  function markFail(message: string): void {
    status.value = 'fail'
    error.value = message
  }

  /** Reset to the initial idle state (used before re-bootstrapping). */
  function reset(): void {
    status.value = 'idle'
    error.value = null
  }

  return { status, error, init, markFail, reset }
})
