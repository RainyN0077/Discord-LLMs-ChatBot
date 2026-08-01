/**
 * Bots store — bot list, selection and the selectedBot getter.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { fetchBots, type BotSummary } from '@/api/bots'

export const useBotsStore = defineStore('bots', () => {
  const bots = ref<BotSummary[]>([])
  const selectedBotId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedBot = computed<BotSummary | null>(() => {
    if (!selectedBotId.value) return null
    return bots.value.find((b) => b.bot_id === selectedBotId.value) ?? null
  })

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

  return { bots, selectedBotId, selectedBot, loading, error, fetchBotsList, selectBot }
})
