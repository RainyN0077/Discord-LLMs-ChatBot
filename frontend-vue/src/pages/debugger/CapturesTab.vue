<script setup lang="ts">
/**
 * CapturesTab — debug capture list + full-detail drawer.
 *
 * Limit dropdown (20/50/100, default 50) + optional channel_id filter →
 * listCaptures; clicking a row loads the detail (getCapture) into a right
 * drawer showing every field (system_prompt / history_for_llm / llm_messages
 * / intermediate responses / raw vs cleaned output / usage / plugin_outputs).
 */
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NAlert,
  NButton,
  NCard,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NInput,
  NSelect,
  NSpin,
  NTag,
} from 'naive-ui'

import {
  getCapture,
  listCaptures,
  type DebugCaptureDetail,
  type DebugCaptureSummary,
} from '@/api/debug'

const { t } = useI18n()

const limit = ref(50)
const channelId = ref('')
const captures = ref<DebugCaptureSummary[]>([])
const loading = ref(false)
const error = ref('')

const detail = ref<DebugCaptureDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
const drawerVisible = ref(false)

const limitOptions = [
  { label: '20', value: 20 },
  { label: '50', value: 50 },
  { label: '100', value: 100 },
]

/** Guards out-of-order list/detail responses when the user clicks fast. */
let requestSeq = 0

async function loadCaptures(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const data = await listCaptures(limit.value, channelId.value)
    if (seq !== requestSeq) return
    captures.value = data
  } catch (err) {
    if (seq !== requestSeq) return
    error.value = err instanceof Error ? err.message : String(err)
    captures.value = []
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

onMounted(loadCaptures)

// Re-query automatically when the page-size limit changes (legacy parity).
watch(limit, () => loadCaptures())

async function openDetail(capture: DebugCaptureSummary): Promise<void> {
  const seq = ++requestSeq
  drawerVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  detail.value = null
  try {
    const data = await getCapture(capture.id)
    if (seq !== requestSeq) return
    detail.value = data
  } catch (err) {
    if (seq !== requestSeq) return
    detailError.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (seq === requestSeq) detailLoading.value = false
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
          <button
            v-for="capture in captures"
            :key="capture.id"
            type="button"
            class="captures-row"
            @click="openDetail(capture)"
          >
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
          </button>
        </div>
      </n-spin>
    </n-card>

    <!-- Detail drawer -->
    <n-drawer v-model:show="drawerVisible" :width="640" placement="right">
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
              <h4>History ({{ detail.history_for_llm.length }})</h4>
              <pre class="capture-code">{{ safeJson(detail.history_for_llm) }}</pre>
            </div>
            <div v-if="detail.llm_messages && detail.llm_messages.length" class="capture-section">
              <h4>{{ t('debugger.captureLlmMessages') }}</h4>
              <pre class="capture-code">{{ safeJson(detail.llm_messages) }}</pre>
            </div>
            <div
              v-if="detail.intermediate_llm_responses && detail.intermediate_llm_responses.length"
              class="capture-section"
            >
              <h4>{{ t('debugger.captureIntermediateOutputs') }}</h4>
              <pre class="capture-code">{{ safeJson(detail.intermediate_llm_responses) }}</pre>
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
</style>
