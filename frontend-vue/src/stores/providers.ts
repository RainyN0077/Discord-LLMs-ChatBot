/**
 * Providers store — provider list, health and switching for the selected bot.
 *
 * 429 (backend rate limit: one switch per bot per 30s) → rateLimited state
 * with a 30s countdown and a warning message; auto-refetches the list on
 * successful switches.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  fetchProviders,
  switchProvider,
  type ProviderInfo,
  type ProviderListResponse,
  type ProviderSwitchRequest,
} from '@/api/providers'

const RATE_LIMIT_WINDOW_S = 30

export const useProvidersStore = defineStore('providers', () => {
  const providers = ref<ProviderInfo[]>([])
  const currentProvider = ref('')
  const currentModel = ref('')
  const loading = ref(false)
  const switching = ref(false)
  const error = ref<string | null>(null)
  const rateLimited = ref(false)
  const rateLimitRemaining = ref(0)
  const lastSwitchMessage = ref<string | null>(null)

  let countdownTimer: ReturnType<typeof setInterval> | null = null
  // Guards against out-of-order fetches when the user switches bots while a
  // request is in flight (stale results from bot A must not overwrite bot B).
  let fetchSeq = 0

  /** Clear the countdown interval only — does NOT touch rate-limit state. */
  function clearCountdownTimer(): void {
    if (countdownTimer !== null) {
      clearInterval(countdownTimer)
      countdownTimer = null
    }
  }

  /** Clear the timer AND reset the rate-limit state (countdown reached 0). */
  function resetRateLimit(): void {
    clearCountdownTimer()
    rateLimited.value = false
    rateLimitRemaining.value = 0
  }

  /** Reset all transient per-bot view state (called when the bot changes). */
  function reset(): void {
    resetRateLimit()
    error.value = null
    lastSwitchMessage.value = null
  }

  /** Fetch the provider list (with cached health) for a bot. */
  async function fetch(botId: string): Promise<void> {
    const seq = ++fetchSeq
    loading.value = true
    error.value = null
    try {
      const data: ProviderListResponse = await fetchProviders(botId)
      if (seq !== fetchSeq) return // stale response — bot was switched mid-flight
      providers.value = data.providers
      currentProvider.value = data.current_provider
      currentModel.value = data.current_model
    } catch (err) {
      if (seq !== fetchSeq) return
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      if (seq === fetchSeq) loading.value = false
    }
  }

  /** Switch the bot's provider; on 429 starts the 30s rate-limit countdown. */
  async function switchTo(
    botId: string,
    payload: ProviderSwitchRequest,
  ): Promise<boolean> {
    if (switching.value || rateLimited.value) return false
    switching.value = true
    error.value = null
    lastSwitchMessage.value = null
    try {
      const res = await switchProvider(botId, payload)
      lastSwitchMessage.value = res.message
      await fetch(botId)
      return true
    } catch (err) {
      const e = err as { status?: number; message?: string }
      if (e.status === 429) {
        // Stop any previous countdown timer FIRST, then arm the new one.
        // clearCountdownTimer() must not reset rateLimited/rateLimitRemaining
        // (that would clear the state we are about to set).
        clearCountdownTimer()
        rateLimited.value = true
        rateLimitRemaining.value = RATE_LIMIT_WINDOW_S
        countdownTimer = setInterval(() => {
          rateLimitRemaining.value -= 1
          if (rateLimitRemaining.value <= 0) {
            // Countdown finished naturally — now it is safe to reset state.
            resetRateLimit()
          }
        }, 1000)
        error.value = e.message || 'Rate limited — please wait before switching again'
      } else {
        error.value = e.message || String(err)
      }
      return false
    } finally {
      switching.value = false
    }
  }

  return {
    providers,
    currentProvider,
    currentModel,
    loading,
    switching,
    error,
    rateLimited,
    rateLimitRemaining,
    lastSwitchMessage,
    reset,
    fetch,
    switchTo,
  }
})
