/**
 * Bots store — bot list, selection and per-bot operations.
 *
 * Delete/rename update the local list optimistically; start/stop/restart and
 * create refetch the list afterwards. All actions re-throw API errors so the
 * calling component decides how to surface them.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  createBot as apiCreateBot,
  deleteBot as apiDeleteBot,
  fetchBots,
  renameBot as apiRenameBot,
  restartBot as apiRestartBot,
  startBot as apiStartBot,
  stopBot as apiStopBot,
  type BotSummary,
  type CreateBotRequest,
} from '@/api/bots'

export const useBotsStore = defineStore('bots', () => {
  const bots = ref<BotSummary[]>([])
  const selectedBotId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const operatingBotIds = ref<string[]>([])

  const selectedBot = computed<BotSummary | null>(() => {
    if (!selectedBotId.value) return null
    return bots.value.find((b) => b.bot_id === selectedBotId.value) ?? null
  })

  /**
   * Run an operation with the bot marked as operating (guards re-entry).
   * The marker is removed in `finally` so it survives failures.
   */
  async function withOperating<T>(botId: string, fn: () => Promise<T>): Promise<T> {
    operatingBotIds.value = [...operatingBotIds.value, botId]
    try {
      return await fn()
    } finally {
      operatingBotIds.value = operatingBotIds.value.filter((id) => id !== botId)
    }
  }

  /** Fetch the bot list; auto-select the first bot when nothing is selected. */
  async function fetchBotsList(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      bots.value = await fetchBots()
      if (!selectedBotId.value && bots.value.length > 0) {
        selectedBotId.value = bots.value[0].bot_id
      } else if (selectedBotId.value) {
        // Drop selection if the bot disappeared from the list.
        const stillExists = bots.value.some(
          (b) => b.bot_id === selectedBotId.value,
        )
        if (!stillExists) {
          selectedBotId.value = bots.value[0]?.bot_id ?? null
        }
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      loading.value = false
    }
  }

  function selectBot(botId: string): void {
    selectedBotId.value = botId
  }

  /** Create a bot, refetch the list and select the new bot. */
  async function createBot(payload: CreateBotRequest): Promise<void> {
    const { bot_id } = await apiCreateBot(payload)
    const newId = bot_id ?? payload.bot_id
    await fetchBotsList()
    // NEW-4: only select the new bot when the refresh succeeded and the bot
    // is actually in the list. Selecting a bot that failed to refresh would
    // leave the store pointing at a ghost id — `selectedBot` resolves to
    // null (no card highlight, header tag gone, log polling dead) while the
    // list still shows the old selection.
    if (!bots.value.some((b) => b.bot_id === newId)) {
      if (!selectedBotId.value) {
        selectedBotId.value = bots.value[0]?.bot_id ?? null
      }
      return
    }
    selectBot(newId)
  }

  /** Delete a bot; drop it locally and fall back to the first bot. */
  async function deleteBot(botId: string): Promise<void> {
    await withOperating(botId, async () => {
      await apiDeleteBot(botId)
      bots.value = bots.value.filter((b) => b.bot_id !== botId)
      if (selectedBotId.value === botId) {
        selectedBotId.value = bots.value[0]?.bot_id ?? null
      }
    })
  }

  /**
   * Rename a bot; update the local id and keep the selection in sync.
   *
   * The selection is only re-pointed when it still references the OLD id —
   * a click that landed on another card while the rename was in flight must
   * not be clobbered (NEW-4 race).
   */
  async function renameBot(botId: string, newId: string): Promise<void> {
    await withOperating(botId, async () => {
      const result = await apiRenameBot(botId, newId)
      const nextId = result.bot_id ?? newId
      const idx = bots.value.findIndex((b) => b.bot_id === botId)
      if (idx >= 0) {
        bots.value[idx] = { ...bots.value[idx], bot_id: nextId }
      }
      if (selectedBotId.value === botId) {
        selectedBotId.value = nextId
      }
    })
  }

  async function startBot(botId: string): Promise<void> {
    await withOperating(botId, async () => {
      await apiStartBot(botId)
      await fetchBotsList()
    })
  }

  async function stopBot(botId: string): Promise<void> {
    await withOperating(botId, async () => {
      await apiStopBot(botId)
      await fetchBotsList()
    })
  }

  async function restartBot(botId: string): Promise<void> {
    await withOperating(botId, async () => {
      await apiRestartBot(botId)
      await fetchBotsList()
    })
  }

  return {
    bots,
    selectedBotId,
    selectedBot,
    loading,
    error,
    operatingBotIds,
    fetchBotsList,
    selectBot,
    createBot,
    deleteBot,
    renameBot,
    startBot,
    stopBot,
    restartBot,
  }
})
