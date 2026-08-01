<script setup lang="ts">
/**
 * LogPanel — footer log viewer.
 *
 * Toolbar: level filter button group (6 literals, click forces auto-scroll),
 * max-line select (persisted in `logPanel.maxLines`), auto-scroll switch,
 * pause/refresh/clear. A 6px resize handle at the top drags the panel height
 * (clamped 120–500) and emits `resize` for the layout to persist.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NScrollbar, NButton, NSwitch, NEmpty, NSpace, NSelect } from 'naive-ui'
import { useLogsStore, type LogRow } from '@/stores/logs'

const emit = defineEmits<{
  resize: [height: number]
  'resize-end': [height: number]
}>()

const { t } = useI18n()
const logsStore = useLogsStore()

const scrollbarRef = ref<InstanceType<typeof NScrollbar> | null>(null)

type LevelFilter = 'ALL' | LogRow['level']
const LEVEL_FILTERS: LevelFilter[] = ['ALL', 'ERROR', 'WARN', 'INFO', 'DEBUG', 'OTHER']
const MAX_LINE_OPTIONS = [200, 500, 1000, 2000]

/** Level filter state is local to the panel (store stays polling-agnostic). */
const levelFilter = ref<LevelFilter>('ALL')
const maxLineOptions = MAX_LINE_OPTIONS.map((n) => ({ label: String(n), value: n }))

const filteredRows = computed<LogRow[]>(() => {
  if (levelFilter.value === 'ALL') return logsStore.rows
  return logsStore.rows.filter((row) => row.level === levelFilter.value)
})

function setLevelFilter(level: LevelFilter): void {
  levelFilter.value = level
  logsStore.autoScroll = true
  void scrollToBottom()
}

function setMaxLines(n: number): void {
  logsStore.setMaxLines(n)
}

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

// --- resize handle (drag up/down, clamp 120–500) ---
let dragging = false
let lastHeight: number | null = null

function onHandlePointerDown(e: PointerEvent): void {
  e.preventDefault()
  dragging = true
  lastHeight = null
  document.body.style.userSelect = 'none'
  document.addEventListener('pointermove', onHandlePointerMove)
  document.addEventListener('pointerup', onHandlePointerUp)
}

function onHandlePointerMove(e: PointerEvent): void {
  if (!dragging) return
  const height = Math.max(120, Math.min(500, window.innerHeight - e.clientY))
  lastHeight = height
  emit('resize', height)
}

function onHandlePointerUp(): void {
  dragging = false
  if (lastHeight !== null) emit('resize-end', lastHeight)
  document.body.style.userSelect = ''
  document.removeEventListener('pointermove', onHandlePointerMove)
  document.removeEventListener('pointerup', onHandlePointerUp)
}

onBeforeUnmount(() => {
  if (dragging) onHandlePointerUp()
})
</script>

<template>
  <div class="log-panel">
    <div
      class="resize-handle"
      role="separator"
      aria-orientation="horizontal"
      @pointerdown="onHandlePointerDown"
    ></div>
    <div class="log-panel-toolbar">
      <span class="log-panel-title">{{ t('logPanel.logs') }}</span>
      <n-space :size="8" align="center">
        <div class="log-filter-group" role="group" aria-label="log level filter">
          <button
            v-for="level in LEVEL_FILTERS"
            :key="level"
            type="button"
            class="log-filter-btn"
            :class="{ active: levelFilter === level }"
            @click="setLevelFilter(level)"
          >
            {{ level }}
          </button>
        </div>
        <n-select
          v-model:value="logsStore.maxLines"
          :options="maxLineOptions"
          size="tiny"
          :style="{ width: '88px' }"
          @update:value="setMaxLines"
        />
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
      <n-empty v-if="filteredRows.length === 0" size="small" description="—" class="log-empty" />
      <div v-else class="log-lines">
        <div
          v-for="(row, index) in filteredRows"
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

/* Drag strip on top; physically separate from the layout's toggle bar. */
.resize-handle {
  height: 6px;
  flex-shrink: 0;
  cursor: ns-resize;
  background: transparent;
}

.resize-handle::after {
  content: '';
  display: block;
  height: 2px;
  margin: 2px 0;
  background: var(--log-border);
}

.resize-handle:hover::after {
  background: rgba(69, 163, 230, 0.5);
}

.log-panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--log-border);
}

.log-panel-title {
  font-weight: 600;
  font-size: 13px;
}

.log-filter-group {
  display: flex;
  gap: 2px;
  background: rgba(148, 163, 184, 0.1);
  border-radius: 6px;
  padding: 2px;
}

.log-filter-btn {
  border: none;
  background: transparent;
  color: #90a4ae;
  padding: 2px 6px;
  font-size: 11px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.log-filter-btn:hover {
  color: #b8c8da;
}

.log-filter-btn.active {
  background: rgba(69, 163, 230, 0.35);
  color: #88d1ff;
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
