<script setup lang="ts">
/**
 * SanitizeTab — DSML/thinking-section cleaning test.
 *
 * Paste raw model output → POST /api/debug/sanitize → two-column comparison
 * (original vs sanitized).
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NButton, NCard, NInput } from 'naive-ui'

import { sanitize, type DebugSanitizeResult } from '@/api/debug'

const { t } = useI18n()

const inputText = ref('')
const result = ref<DebugSanitizeResult | null>(null)
const error = ref('')
const sanitizing = ref(false)

async function handleSanitize(): Promise<void> {
  sanitizing.value = true
  error.value = ''
  try {
    result.value = await sanitize(inputText.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    sanitizing.value = false
  }
}
</script>

<template>
  <div class="sanitize-tab">
    <n-card :title="t('debugger.sanitizeTitle')" size="small">
      <n-input
        v-model:value="inputText"
        type="textarea"
        :placeholder="t('debugger.sanitizeInputPlaceholder')"
        :autosize="{ minRows: 8, maxRows: 16 }"
      />
      <n-button
        type="primary"
        class="sanitize-run"
        :loading="sanitizing"
        :disabled="!inputText.trim()"
        @click="handleSanitize"
      >
        {{ sanitizing ? t('debugger.sanitizing') : t('debugger.sanitizeRun') }}
      </n-button>

      <n-alert v-if="error" type="error" class="sanitize-error">
        {{ t('debugger.sanitizeFailed') }}{{ error }}
      </n-alert>
    </n-card>

    <template v-if="result">
      <div class="sanitize-grid">
        <n-card :title="t('debugger.captureRawOutput')" size="small">
          <pre class="sanitize-code">{{ result.original_text }}</pre>
        </n-card>
        <n-card :title="t('debugger.sanitizeOutput')" size="small">
          <pre class="sanitize-code">{{ result.sanitized_text }}</pre>
        </n-card>
      </div>
    </template>
  </div>
</template>

<style scoped>
.sanitize-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 900px;
}

.sanitize-run {
  margin-top: 12px;
}

.sanitize-error {
  margin-top: 12px;
}

.sanitize-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.sanitize-code {
  margin: 0;
  padding: 12px;
  background: var(--log-shell-bg);
  color: var(--log-text-color);
  border-radius: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 420px;
  overflow-y: auto;
}
</style>
