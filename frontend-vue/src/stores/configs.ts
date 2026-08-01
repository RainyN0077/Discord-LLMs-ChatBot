/**
 * Configs store — full per-bot config loading, editing and saving.
 *
 * Editing model: the component tree mutates the reactive `config` object
 * directly (field assignment = edit) and calls `markDirty()`. `save()`
 * round-trips the FULL config (never a partial patch — the backend's PUT
 * merges shallowly, so missing fields would silently drop data):
 *   deep copy → custom_parameters type coercion → trigger_keywords array
 *   fallback → recursive `_key` strip → force bot_id → full PUT.
 *
 * `fetchSeq` guards out-of-order loads when the user switches bots while a
 * request is in flight (stale results from bot A must not overwrite bot B);
 * `reset()` also bumps the sequence so a stale in-flight response cannot land
 * in the window between reset and the next load.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  fetchBotConfig,
  updateBotConfig,
  type BotConfig,
  type CustomParameter,
} from '@/api/config'
import { i18n } from '@/locales'
import { getMessageApi } from '@/utils/feedback'

export const useConfigsStore = defineStore('configs', () => {
  const config = ref<BotConfig | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const dirty = ref(false)
  const error = ref<string | null>(null)

  /** Bot whose config is currently loaded (null after reset/switch). */
  const currentBotId = ref<string | null>(null)

  // Guards against out-of-order fetches when the bot changes mid-flight.
  let fetchSeq = 0

  /** Coerce custom_parameters values to the declared type for the backend. */
  function convertCustomParameter(p: CustomParameter): CustomParameter {
    if (p.type === 'number') {
      const raw = String(p.value)
      // LOW-2: the UI clears number fields to '' — normalize empty input to 0
      // so a string never lands in the JSON for a number-typed parameter.
      if (raw.trim() === '') return { ...p, value: 0 }
      const n = parseFloat(raw)
      // Non-finite results (e.g. NaN input) keep the raw string.
      return { ...p, value: Number.isFinite(n) ? n : raw }
    }
    if (p.type === 'boolean') {
      // UI edits produce strings; case-insensitive compare (True/TRUE too).
      return { ...p, value: String(p.value).toLowerCase() === 'true' }
    }
    return { ...p, value: String(p.value) }
  }

  /** Recursively delete underscore-prefixed keys (naive-ui table `_key`). */
  function stripUnderscoreKeys(node: unknown): void {
    if (Array.isArray(node)) {
      for (const item of node) stripUnderscoreKeys(item)
      return
    }
    if (node === null || typeof node !== 'object') return
    for (const key of Object.keys(node as Record<string, unknown>)) {
      const value = (node as Record<string, unknown>)[key]
      if (key.startsWith('_')) {
        delete (node as Record<string, unknown>)[key]
      } else {
        stripUnderscoreKeys(value)
      }
    }
  }

  /** Load the full config for a bot (seq-guarded against bot switches). */
  async function load(botId: string): Promise<void> {
    const seq = ++fetchSeq
    loading.value = true
    error.value = null
    try {
      const data = await fetchBotConfig(botId)
      if (seq !== fetchSeq) return // stale response — bot switched mid-flight
      config.value = data
      currentBotId.value = botId
      dirty.value = false
    } catch (err) {
      if (seq !== fetchSeq) return
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      if (seq === fetchSeq) loading.value = false
    }
  }

  /** Save the full config; on success the bot restarts on the backend. */
  async function save(botId: string): Promise<boolean> {
    if (saving.value || !config.value) return false
    saving.value = true
    error.value = null
    const message = getMessageApi()
    try {
      // 1. Deep copy the current (edited) config as the baseline.
      const snapshot = JSON.parse(JSON.stringify(config.value)) as BotConfig
      // 2. Type-coerce custom_parameters rows (UI keeps raw strings).
      if (Array.isArray(snapshot.custom_parameters)) {
        snapshot.custom_parameters = snapshot.custom_parameters.map(
          convertCustomParameter,
        )
      }
      // 3. Backward compatibility: keep the legacy base_url aligned with the
      //    OpenAI custom endpoint (mirrors legacy stores.js saveConfig).
      snapshot.base_url = snapshot.openai_base_url || ''
      // 4. trigger_keywords string ↔ array fallback.
      if (typeof snapshot.trigger_keywords === 'string') {
        snapshot.trigger_keywords = (
          snapshot.trigger_keywords as unknown as string
        )
          .split(',')
          .map((k) => k.trim())
          .filter(Boolean)
      }
      // 5. Strip naive-ui table `_key` artifacts recursively.
      stripUnderscoreKeys(snapshot)
      // 6. Force the bot id (imported/renamed configs must not leak theirs).
      snapshot.bot_id = botId
      // 7. Full-body PUT.
      await updateBotConfig(botId, snapshot)
      // Only clear the dirty flag if the user is still editing the bot that
      // was saved — otherwise a stale success would silently drop the dirty
      // marker of a bot the user switched to and edited mid-flight.
      if (botId === currentBotId.value) dirty.value = false
      message?.success(i18n.global.t('status.saveSuccess'))
      return true
    } catch (err) {
      const e = err as { message?: string; status?: number }
      error.value = e.message || String(err)
      // Keep dirty — the user's edits must survive a failed save.
      message?.error(
        i18n.global.t('status.saveFailed', {
          error: e.message || String(err),
        }),
      )
      return false
    } finally {
      saving.value = false
    }
  }

  /** Apply a partial patch to the live config and mark it dirty. */
  function update(patch: Partial<BotConfig>): void {
    if (!config.value) return
    config.value = { ...config.value, ...patch }
    dirty.value = true
  }

  /** Mark the config dirty after a direct field edit. */
  function markDirty(): void {
    dirty.value = true
  }

  /** Reset transient state (bot switched / unmount). Bumps the fetch seq so
   * a stale in-flight load can never land after the reset. */
  function reset(): void {
    fetchSeq++
    config.value = null
    currentBotId.value = null
    loading.value = false
    saving.value = false
    dirty.value = false
    error.value = null
  }

  return {
    config,
    loading,
    saving,
    dirty,
    error,
    load,
    save,
    update,
    markDirty,
    reset,
  }
})
