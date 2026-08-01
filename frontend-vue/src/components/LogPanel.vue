<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NScrollbar, NButton, NSwitch, NEmpty, NSpace } from 'naive-ui'
import { useLogsStore } from '@/stores/logs'

const { t } = useI18n()
const logsStore = useLogsStore()

const scrollbarRef = ref<InstanceType<typeof NScrollbar> | null>(null)

/** Scroll the log container to the bottom when autoScroll is on. */
async function scrollToBottom(): Promise<void> {
  await nextTick()
  const container = scrollbarRef.value
  if (!container) return
  try {
    const el = container.$el?.querySelector('.n-scrollbar-container') as HTMLElement | null
    if (el) el.scrollTop = el.scrollHeight
  } catch {
    // ignore scroll failures
  }
}

watch(
  () => logsStore.rows,
  () => {
    if (logsStore.autoScroll && !logsStore.paused) void scrollToBottom()
  },
  { deep: false },
)

watch(
  () => logsStore.botId,
  () => {
    void scrollToBottom()
  },
)
</script>

<template>
  <div class="log-panel">
    <div class="log-panel-toolbar">
      <span class="log-panel-title">{{ t('logPanel.logs') }}</span>
      <n-space :size="8" align="center">
        <span class="log-panel-label">{{ t('logPanel.auto') }}</span>
        <n-switch v-model:value="logsStore.autoScroll" size="small" />
        <n-button
          size="tiny"
          :type="logsStore.paused ? 'primary' : 'default'"
          @click="logsStore.paused = !logsStore.paused"
        >
          {{ logsStore.paused ? '▶' : '⏸' }}
        </n-button>
        <n-button size="tiny" @click="logsStore.refresh()">
          ↻
        </n-button>
        <n-button size="tiny" @click="logsStore.clear()">✕</n-button>
      </n-space>
    </div>
    <div v-if="logsStore.error" class="log-panel-error">{{ logsStore.error }}</div>
    <NScrollbar ref="scrollbarRef" class="log-scroll">
      <n-empty v-if="logsStore.rows.length === 0" size="small" description="—" class="log-empty" />
      <div v-else class="log-lines">
        <div
          v-for="(row, index) in logsStore.rows"
          :key="index"
          class="log-line"
          :class="`log-${row.level.toLowerCase()}`"
        >
          {{ row.raw }}
        </div>
      </div>
    </NScrollbar>
  </div>
</template>

<style scoped>
.log-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.log-panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  border-bottom: 1px solid var(--log-border);
}

.log-panel-title {
  font-weight: 600;
  font-size: 13px;
}

.log-panel-label {
  font-size: 12px;
  opacity: 0.7;
}

.log-panel-error {
  padding: 4px 12px;
  font-size: 12px;
  color: var(--log-error);
  background: var(--log-error-bg);
}

.log-scroll {
  flex: 1;
  min-height: 0;
}

.log-lines {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  padding: 6px 12px;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}

.log-empty {
  padding-top: 24px;
}

.log-error {
  color: var(--log-error);
}

.log-warn {
  color: var(--log-warn);
}

.log-info {
  color: var(--log-info);
}

.log-debug {
  color: var(--log-debug);
}

.log-other {
  color: var(--log-other);
}
</style>
