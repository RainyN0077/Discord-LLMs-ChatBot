<script setup lang="ts">
/**
 * CapturesTab — debug capture list + full-detail drawer.
 *
 * Limit dropdown (20/50/100, default 50) + optional channel_id filter →
 * listCaptures; clicking a row loads the detail (getCapture) into a right
 * drawer showing every field (system_prompt / history_for_llm / llm_messages
 * / intermediate responses / raw vs cleaned output / usage / plugin_outputs).
 *
 * S2 (docs/full-implementation-design.md §3/§4):
 *  - row container is a `div[role=button]` (a <button> cannot legally nest
 *    the row delete button) with Enter/Space keyboard activation
 *  - per-row delete + toolbar "Clear All" (n-popconfirm)
 *  - the intermediate-outputs block renders parseTraceSteps' three states:
 *    empty hint / texts list (degraded → fallback alert + raw JSON fold) /
 *    self-drawn timeline with stage labels and collapsible reasoning
 *  - every raw payload is rendered with plain-text interpolation only
 *    (no v-html — XSS double-guard, design §3.4 L4)
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import {
  NAlert,
  NButton,
  NCard,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NInput,
  NPopconfirm,
  NSelect,
  NSpin,
  NTag,
} from 'naive-ui'

import {
  clearCaptures,
  deleteCapture,
  getCapture,
  listCaptures,
  type DebugCaptureDetail,
  type DebugCaptureSummary,
} from '@/api/debug'
import { parseTraceSteps, type TraceNode } from './trace'

const { t } = useI18n()
const message = useMessage()

const limit = ref(50)
const channelId = ref('')
const captures = ref<DebugCaptureSummary[]>([])
const loading = ref(false)
const error = ref('')
const clearing = ref(false)

const detail = ref<DebugCaptureDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
const drawerVisible = ref(false)
const deletingId = ref<string | null>(null)

const limitOptions = [
  { label: '20', value: 20 },
  { label: '50', value: 50 },
  { label: '100', value: 100 },
]

/**
 * Guards out-of-order list responses when the user refreshes quickly.
 * (perf LOW-2: split from detailSeq so a refresh never invalidates an open
 * detail, and vice versa — previously a shared counter left the list
 * `loading` stuck when a detail was opened mid-refresh.)
 */
let listSeq = 0

/** Guards out-of-order detail responses when the user clicks rows fast. */
let detailSeq = 0

async function loadCaptures(): Promise<void> {
  const seq = ++listSeq
  loading.value = true
  error.value = ''
  try {
    const data = await listCaptures(limit.value, channelId.value)
    if (seq !== listSeq) return
    captures.value = data
  } catch (err) {
    if (seq !== listSeq) return
    error.value = err instanceof Error ? err.message : String(err)
    captures.value = []
  } finally {
    if (seq === listSeq) loading.value = false
  }
}

onMounted(loadCaptures)

// Re-query automatically when the page-size limit changes (legacy parity).
watch(limit, () => loadCaptures())

async function openDetail(capture: DebugCaptureSummary): Promise<void> {
  const seq = ++detailSeq
  drawerVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  detail.value = null
  try {
    const data = await getCapture(capture.id)
    if (seq !== detailSeq) return
    detail.value = data
  } catch (err) {
    if (seq !== detailSeq) return
    detailError.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (seq === detailSeq) detailLoading.value = false
  }
}

/**
 * perf LOW-1: closing the drawer releases the multi-hundred-KB detail
 * immediately instead of keeping it referenced until the next open (the
 * next `openDetail` would otherwise be the only point that freed it).
 */
function onDrawerShowChange(show: boolean): void {
  if (!show) {
    detail.value = null
    detailError.value = ''
  }
}

function formatBytes(usage: Record<string, unknown> | null): string {
  if (!usage) return ''
  const promptTokens = usage.prompt_tokens ?? usage.prompt ?? 0
  const completionTokens = usage.completion_tokens ?? usage.completion ?? 0
  return `${promptTokens} + ${completionTokens}`
}

/** Defensive rendering for raw array/dict fields from older captures. */
function safeJson(value: unknown): string {
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

// ---------------------------------------------------------------------------
// S2: trace three-state block (replaces the hardcoded intermediate section)
// ---------------------------------------------------------------------------

/**
 * The intermediate payload is passed to the parser as `unknown` — the
 * component deliberately does not guess its shape (design §3.4). The parser
 * never throws; every input collapses into one of the three states.
 */
const trace = computed(() =>
  parseTraceSteps(detail.value?.intermediate_llm_responses as unknown),
)

/** `tool_call` → `tool_call`, used by stageLabel's i18n key mapping. */
function pascalCase(value: string): string {
  return value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('')
}

/** Whitelisted stages map onto debugger.trace* keys; 'other' shows a
 *  generic label (falling back to the raw stage name when present). */
function stageLabel(node: TraceNode): string {
  if (node.stage === 'other') return node.label || node.raw || t('debugger.traceOther')
  return t(`debugger.trace${pascalCase(node.stage)}`)
}

// ---------------------------------------------------------------------------
// S2: delete / clear
// ---------------------------------------------------------------------------

function errMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

async function handleDeleteCapture(capture: DebugCaptureSummary): Promise<void> {
  if (deletingId.value !== null) return
  deletingId.value = capture.id
  try {
    await deleteCapture(capture.id)
    message.success(t('debugger.capDeleted'))
    if (detail.value?.id === capture.id) {
      drawerVisible.value = false
      detail.value = null
    }
    await loadCaptures()
  } catch (err) {
    message.error(t('debugger.capDelFailed', { error: errMessage(err) }))
  } finally {
    deletingId.value = null
  }
}

async function handleClearCaptures(): Promise<void> {
  clearing.value = true
  try {
    await clearCaptures()
    message.success(t('debugger.capClearSuccess'))
    drawerVisible.value = false
    detail.value = null
    await loadCaptures()
  } catch (err) {
    message.error(t('debugger.capClearFailed', { error: errMessage(err) }))
  } finally {
    clearing.value = false
  }
}
</script>

<template>
  <div class="captures-tab">
    <n-card size="small">
      <div class="captures-toolbar">
        <span class="captures-label">{{ t('debugger.captureLimit') }}:</span>
        <n-select v-model:value="limit" :options="limitOptions" class="captures-limit" />
        <n-input
          v-model:value="channelId"
          :placeholder="t('debugger.captureChannelFilter')"
          class="captures-channel"
          clearable
          @keyup.enter="loadCaptures"
        />
        <n-button type="primary" :loading="loading" @click="loadCaptures">
          {{ t('debugger.captureRefresh') }}
        </n-button>
        <n-popconfirm
          :disabled="captures.length === 0 || loading || clearing"
          @positive-click="handleClearCaptures"
        >
          <template #trigger>
            <n-button
              secondary
              class="captures-clear-btn"
              :disabled="captures.length === 0 || loading || clearing"
              :loading="clearing"
            >
              {{ t('debugger.capClear') }}
            </n-button>
          </template>
          {{ t('debugger.capClearConfirm') }}
        </n-popconfirm>
      </div>

      <n-alert v-if="error" type="error" class="captures-error">
        {{ t('debugger.captureLoadFailed') }}{{ error }}
      </n-alert>

      <n-spin :show="loading">
        <n-empty
          v-if="!loading && captures.length === 0"
          :description="t('debugger.captureEmpty')"
        />
        <div v-else class="captures-list">
          <div
            v-for="capture in captures"
            :key="capture.id"
            role="button"
            tabindex="0"
            class="captures-row"
            @click="openDetail(capture)"
            @keydown.enter="openDetail(capture)"
            @keydown.space.prevent="openDetail(capture)"
          >
            <div class="captures-row-body">
              <div class="captures-row-main">
                <span class="captures-time">{{ capture.captured_at }}</span>
                <span class="captures-user">{{ capture.user_display_name || capture.user_name }}</span>
                <n-tag size="small" type="info" class="captures-channel-tag">
                  #{{ capture.channel_id }}
                </n-tag>
              </div>
              <div class="captures-row-msg">{{ capture.raw_user_message }}</div>
              <div class="captures-row-meta">
                <span v-for="src in capture.trigger_sources" :key="src" class="captures-source">
                  [{{ src }}]
                </span>
                <span v-if="capture.provider || capture.model">
                  {{ capture.provider }} / {{ capture.model }}
                </span>
              </div>
            </div>
            <n-button
              size="tiny"
              quaternary
              circle
              class="captures-delete"
              :title="t('debugger.capDel')"
              :aria-label="t('debugger.capDel')"
              :loading="deletingId === capture.id"
              @click.stop="handleDeleteCapture(capture)"
              @keydown.stop
            >
              ×
            </n-button>
          </div>
        </div>
      </n-spin>
    </n-card>

    <!-- Detail drawer -->
    <n-drawer
      v-model:show="drawerVisible"
      :width="640"
      placement="right"
      @update:show="onDrawerShowChange"
    >
      <n-drawer-content :title="detail?.id ?? ''" closable>
        <n-spin :show="detailLoading">
          <n-alert v-if="detailError" type="error" class="captures-detail-error">
            {{ t('debugger.captureDetailFailed') }}{{ detailError }}
          </n-alert>

          <template v-if="detail">
            <div class="capture-section">
              <h4>{{ t('debugger.captureRawInput') }}</h4>
              <pre class="capture-code">{{ detail.raw_user_message }}</pre>
            </div>
            <div class="capture-section">
              <h4>{{ t('debugger.captureFormattedInput') }}</h4>
              <pre class="capture-code">{{ detail.formatted_user_request }}</pre>
            </div>
            <div v-if="detail.plugin_outputs && detail.plugin_outputs.length" class="capture-section">
              <h4>{{ t('debugger.capturePluginOutputs') }}</h4>
              <pre class="capture-code">{{ safeJson(detail.plugin_outputs) }}</pre>
            </div>
            <div class="capture-section">
              <h4>{{ t('debugger.captureSystemPrompt') }}</h4>
              <pre class="capture-code">{{ detail.system_prompt }}</pre>
            </div>
            <div v-if="detail.history_for_llm && detail.history_for_llm.length" class="capture-section">
              <h4>{{ t('debugger.detailHistory', { count: detail.history_for_llm.length }) }}</h4>
              <pre class="capture-code">{{ safeJson(detail.history_for_llm) }}</pre>
            </div>
            <div v-if="detail.llm_messages && detail.llm_messages.length" class="capture-section">
              <h4>{{ t('debugger.captureLlmMessages') }}</h4>
              <pre class="capture-code">{{ safeJson(detail.llm_messages) }}</pre>
            </div>
            <div class="capture-section">
              <h4>{{ t('debugger.trace') }}</h4>
              <p v-if="trace.kind === 'empty'" class="trace-empty">{{ t('debugger.traceEmpty') }}</p>
              <div v-else-if="trace.kind === 'texts'" class="trace-texts">
                <n-alert
                  v-if="trace.degraded"
                  type="warning"
                  role="alert"
                  class="trace-degraded"
                >
                  {{ t('debugger.detailFallback') }}
                </n-alert>
                <details v-if="trace.degraded" class="trace-raw-fold">
                  <summary>{{ t('debugger.detailRaw') }}</summary>
                  <pre class="capture-code">{{ safeJson(detail.intermediate_llm_responses) }}</pre>
                </details>
                <pre v-for="(item, i) in trace.items" :key="i" class="capture-code">{{ item }}</pre>
              </div>
              <div v-else class="timeline">
                <div
                  v-for="(node, i) in trace.items"
                  :key="i"
                  class="tl-node"
                  :data-stage="node.stage"
                >
                  <span class="tl-dot" :class="{ warn: node.stage === 'tool_call' }"></span>
                  <div class="tl-body">
                    <div class="tl-head">{{ stageLabel(node) }}</div>
                    <div v-if="node.stage === 'tool_call'" class="tl-meta">
                      {{ node.name }}{{ node.args ? ' · ' + node.args : '' }}
                    </div>
                    <details
                      v-if="node.stage === 'reasoning' && node.content"
                      class="reasoning-fold"
                    >
                      <summary>{{ t('debugger.traceReasoning') }}</summary>
                      <div class="reasoning-content">{{ node.content }}</div>
                    </details>
                    <div v-else-if="node.content" class="tl-meta">{{ node.content }}</div>
                  </div>
                </div>
              </div>
            </div>
            <div class="capture-section">
              <h4>{{ t('debugger.captureRawOutput') }}</h4>
              <pre class="capture-code">{{ detail.raw_llm_response }}</pre>
            </div>
            <div class="capture-section">
              <h4>{{ t('debugger.captureCleanedOutput') }}</h4>
              <pre class="capture-code">{{ detail.cleaned_llm_response }}</pre>
            </div>
            <div v-if="detail.usage" class="capture-section">
              <h4>{{ t('debugger.captureUsage') }}</h4>
              <pre class="capture-code">{{ formatBytes(detail.usage) }}</pre>
            </div>
          </template>
        </n-spin>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.captures-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.captures-label {
  font-size: 13px;
  color: var(--text-color-3);
}

.captures-limit {
  width: 90px;
}

.captures-channel {
  width: 240px;
}

.captures-error {
  margin-bottom: 10px;
}

.captures-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 560px;
  overflow-y: auto;
}

.captures-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  text-align: left;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  transition: border-color 0.15s;
}

.captures-row:hover {
  border-color: var(--primary-color);
}

.captures-row:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.captures-row-body {
  flex: 1;
  min-width: 0;
}

.captures-delete {
  flex-shrink: 0;
}

.captures-row-main {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.captures-time {
  font-size: 12px;
  color: var(--text-color-3);
}

.captures-user {
  font-weight: 600;
  font-size: 13px;
}

.captures-row-msg {
  font-size: 13px;
  color: var(--text-color-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.captures-row-meta {
  font-size: 12px;
  color: var(--text-color-3);
  display: flex;
  gap: 6px;
}

.capture-section {
  margin-bottom: 16px;
}

.capture-section h4 {
  font-size: 13px;
  margin: 0 0 6px;
}

.capture-code {
  margin: 0;
  padding: 10px;
  background: var(--log-shell-bg);
  color: var(--log-text-color);
  border-radius: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.captures-detail-error {
  margin-bottom: 12px;
}

.trace-empty {
  margin: 0;
  font-size: 13px;
  color: var(--text-color-3);
}

.trace-degraded {
  margin-bottom: 10px;
}

.trace-raw-fold {
  margin-bottom: 10px;
  font-size: 13px;
}

.trace-raw-fold summary {
  cursor: pointer;
  color: var(--text-color-2);
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tl-node {
  display: flex;
  gap: 10px;
}

.tl-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary-color);
  margin-top: 6px;
  flex-shrink: 0;
}

.tl-dot.warn {
  background: var(--warning-color, #f0a020);
}

.tl-body {
  flex: 1;
  min-width: 0;
}

.tl-head {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}

.tl-meta {
  font-size: 12px;
  color: var(--text-color-2);
  white-space: pre-wrap;
  word-break: break-all;
}

.reasoning-content {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-color-2);
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
