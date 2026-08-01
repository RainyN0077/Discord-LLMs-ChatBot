<script setup lang="ts">
/**
 * DebuggerPage — container: 4 tabs (simulate / history / captures / sanitize).
 *
 * The config store is loaded per selected bot so the simulate tab can offer
 * the role_based_config dropdown; `bot_id` is always sent to the backend.
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NButton, NTabs, NTabPane, NSpin } from 'naive-ui'

import { useBotsStore } from '@/stores/bots'
import { useConfigsStore } from '@/stores/configs'
import EmptyState from '@/components/common/EmptyState.vue'
import SimulateTab from './SimulateTab.vue'
import HistoryTab from './HistoryTab.vue'
import CapturesTab from './CapturesTab.vue'
import SanitizeTab from './SanitizeTab.vue'

const { t } = useI18n()
const botsStore = useBotsStore()
const configsStore = useConfigsStore()

const activeTab = ref('simulate')

watch(
  () => botsStore.selectedBotId,
  (botId) => {
    configsStore.reset()
    if (botId) void configsStore.load(botId)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  configsStore.reset()
})

onMounted(() => {
  if (!botsStore.bots.length) void botsStore.fetchBotsList()
})

/** Page-level retry for the config load (the tabs handle their own errors). */
function handleRetry(): void {
  const botId = botsStore.selectedBotId
  if (botId) void configsStore.load(botId)
}
</script>

<template>
  <div class="debugger-page">
    <template v-if="!botsStore.selectedBot">
      <EmptyState :description="t('configPanel.selectBot')" />
    </template>

    <template v-else>
      <n-alert v-if="configsStore.error" type="error" class="debugger-alert">
        <div class="debugger-alert-body">
          <span class="debugger-alert-text">{{ configsStore.error }}</span>
          <n-button v-if="!configsStore.config" size="small" @click="handleRetry">
            {{ t('generic.retry') }}
          </n-button>
        </div>
      </n-alert>

      <n-spin :show="configsStore.loading">
        <n-tabs v-model:value="activeTab" type="line" animated>
          <n-tab-pane name="simulate" :tab="t('debugger.simulateTab')">
            <SimulateTab :bot-id="botsStore.selectedBotId ?? ''" />
          </n-tab-pane>
          <n-tab-pane name="history" :tab="t('debugger.historyTab')">
            <HistoryTab :active="activeTab === 'history'" />
          </n-tab-pane>
          <n-tab-pane name="captures" :tab="t('debugger.capturesTab')">
            <CapturesTab />
          </n-tab-pane>
          <n-tab-pane name="sanitize" :tab="t('debugger.sanitizeTab')">
            <SanitizeTab />
          </n-tab-pane>
        </n-tabs>
      </n-spin>
    </template>
  </div>
</template>

<style scoped>
.debugger-page {
  max-width: 1000px;
  margin: 0 auto;
}

.debugger-alert {
  margin-bottom: 12px;
}

.debugger-alert-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.debugger-alert-text {
  flex: 1;
  min-width: 0;
}
</style>
