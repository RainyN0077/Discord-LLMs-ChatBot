<script setup lang="ts">
/**
 * AdvancedProviderCard — ocr / embedding / rerank provider config card.
 *
 * The `config` prop is the store's reactive config object (mutations persist
 * into the store); fields are the flat `{prefix}_*` config slots. Fetching
 * the model list switches the model input between text (TXT) and select (SEL).
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NButton, NFormItem, NInput, NInputNumber, NSelect, NSpace } from 'naive-ui'

import { fetchModelList, testModel, type ModelTask } from '@/api/models'
import type { BotConfig } from '@/api/config'
import { useConfigsStore } from '@/stores/configs'
import SectionCard from '@/components/common/SectionCard.vue'
import { providerOptions } from './providerOptions'

const props = defineProps<{
  /** Config field prefix: 'ocr' | 'embedding' | 'rerank'. */
  prefix: 'ocr' | 'embedding' | 'rerank'
  /** The store's reactive config object (direct field mutation persists). */
  config: BotConfig | null
}>()

const { t } = useI18n()
const message = useMessage()
const configsStore = useConfigsStore()

const task = computed<ModelTask>(() => props.prefix)
const providerOpts = providerOptions((key) => t(key))

const availableModels = ref<string[]>([])
const isLoadingModels = ref(false)
const isTesting = ref(false)
const useManualInput = ref(false)

/** Read a flat `{prefix}_{field}` slot as string. */
function getField(field: string): string {
  const value = (props.config as unknown as Record<string, unknown> | null)?.[`${props.prefix}_${field}`]
  return typeof value === 'string' ? value : value == null ? '' : String(value)
}

/** Write a flat `{prefix}_{field}` slot. */
function setField(field: string, value: unknown): void {
  if (!props.config) return
  ;(props.config as unknown as Record<string, unknown>)[`${props.prefix}_${field}`] = value
  configsStore.markDirty()
}

const apiKey = computed(() => getField('api_key'))

/** Combine base_url + port into a single endpoint (mirrors old frontend). */
function buildEndpoint(): string {
  const baseUrl = getField('base_url').trim()
  const port = getField('port').trim()
  if (!baseUrl) return ''
  if (!port) return baseUrl
  try {
    const parsed = new URL(baseUrl)
    parsed.port = port
    return parsed.toString().replace(/\/$/, '')
  } catch {
    const normalized = baseUrl.replace(/\/$/, '')
    if (/:\d+$/.test(normalized)) return normalized
    return `${normalized}:${port}`
  }
}

async function loadModels(): Promise<void> {
  if (!apiKey.value) {
    message.error(t('llmProvider.noApiKey'))
    return
  }
  isLoadingModels.value = true
  try {
    const result = await fetchModelList(getField('provider'), apiKey.value, buildEndpoint(), task.value)
    availableModels.value = result.models || []
    useManualInput.value = false
    message.success(t('llmProvider.modelsLoaded'))
  } catch (err) {
    availableModels.value = []
    useManualInput.value = true
    message.error(t('llmProvider.modelsLoadFailed') + (err instanceof Error ? err.message : String(err)))
  } finally {
    isLoadingModels.value = false
  }
}

async function handleTest(): Promise<void> {
  const modelName = getField('model_name')
  if (!modelName) {
    message.error(t('llmProvider.selectModelFirst'))
    return
  }
  isTesting.value = true
  try {
    const extra =
      props.prefix === 'ocr'
        ? {
            ocr_timeout_seconds: (props.config as unknown as Record<string, unknown>).ocr_timeout_seconds,
            ocr_timeout_disabled: !!(props.config as unknown as Record<string, unknown>).ocr_timeout_disabled,
          }
        : {}
    const result = await testModel(
      getField('provider'),
      apiKey.value,
      buildEndpoint(),
      modelName,
      task.value,
      extra,
    )
    if (result.success) {
      message.success(t('llmProvider.testSuccess'))
    } else {
      message.error(t('llmProvider.testFailed') + (result.error || ''))
    }
  } catch (err) {
    message.error(t('llmProvider.testError') + (err instanceof Error ? err.message : String(err)))
  } finally {
    isTesting.value = false
  }
}

// Provider change resets the fetched model list and TXT/SEL state, but KEEPS
// the model_name value (legacy AdvancedProviderCard.svelte behavior — the
// design doc had this inverted, the old component is the source of truth).
watch(
  () => getField('provider'),
  () => {
    availableModels.value = []
    useManualInput.value = false
  },
)

// API key / endpoint change invalidates the fetched model list (keeps model).
watch(
  [apiKey, () => getField('base_url'), () => getField('port')],
  () => {
    availableModels.value = []
    useManualInput.value = false
  },
)

const modelInputMode = computed(() => !useManualInput.value && availableModels.value.length > 0)
</script>

<template>
  <SectionCard v-if="config" :title="t(`${props.prefix}Settings.title`)">
    <n-grid :cols="2" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
      <n-gi :span="1">
        <n-form-item :label="t(`${props.prefix}Settings.provider`)" label-placement="top">
          <n-select :value="getField('provider')" :options="providerOpts" @update:value="(v: string) => setField('provider', v)" />
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t(`${props.prefix}Settings.apiKey`)" label-placement="top">
          <n-input
            :value="apiKey"
            type="password"
            show-password-on="click"
            :placeholder="t('llmProvider.apiKeyPlaceholder')"
            @update:value="(v: string) => setField('api_key', v)"
          />
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t(`${props.prefix}Settings.baseUrl`)" label-placement="top">
          <n-input
            :value="getField('base_url')"
            :placeholder="t('llmProvider.baseUrlPlaceholder')"
            @update:value="(v: string) => setField('base_url', v)"
          />
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t(`${props.prefix}Settings.port`)" label-placement="top">
          <n-input
            :value="getField('port')"
            placeholder="443"
            @update:value="(v: string) => setField('port', v)"
          />
        </n-form-item>
      </n-gi>
      <n-gi :span="2">
        <n-form-item :label="t(`${props.prefix}Settings.modelName`)" label-placement="top">
          <n-space vertical :size="8" class="full-width">
            <n-select
              v-if="modelInputMode"
              :value="getField('model_name')"
              :options="availableModels.map((m) => ({ label: m, value: m }))"
              :placeholder="t('llmProvider.selectModel')"
              @update:value="(v: string) => setField('model_name', v)"
            />
            <n-input
              v-else
              :value="getField('model_name')"
              @update:value="(v: string) => setField('model_name', v)"
            />
            <n-space :size="8">
              <n-button size="small" :loading="isLoadingModels" @click="loadModels">
                {{ isLoadingModels ? t('llmProvider.loading') : t('llmProvider.fetchModels') }}
              </n-button>
              <n-button
                v-if="availableModels.length > 0"
                size="small"
                :title="t('llmProvider.toggleInputMode')"
                @click="useManualInput = !useManualInput"
              >
                {{ useManualInput ? 'SEL' : 'TXT' }}
              </n-button>
              <n-button
                size="small"
                type="primary"
                :loading="isTesting"
                :disabled="!getField('model_name')"
                @click="handleTest"
              >
                {{ isTesting ? t('llmProvider.testing') : t('llmProvider.testConnection') }}
              </n-button>
            </n-space>
          </n-space>
        </n-form-item>
      </n-gi>

      <template v-if="props.prefix === 'embedding'">
        <n-gi :span="1">
          <n-form-item :label="t('embeddingSettings.dimensions')" label-placement="top">
            <n-input-number
              :value="Number(getField('dimensions')) || 1536"
              :min="1"
              :step="1"
              class="full-width"
              @update:value="(v: number | null) => setField('dimensions', v ?? 1536)"
            />
          </n-form-item>
        </n-gi>
      </template>

      <template v-if="props.prefix === 'ocr'">
        <n-gi :span="2">
          <n-form-item :label="t('ocrSettings.promptTemplate')" label-placement="top">
            <n-input
              :value="getField('prompt_template')"
              type="textarea"
              :rows="4"
              :placeholder="t('ocrSettings.promptTemplatePlaceholder')"
              @update:value="(v: string) => setField('prompt_template', v)"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('ocrSettings.maxOutputChars')" label-placement="top">
            <n-input-number
              :value="Number(getField('max_output_chars')) || 4000"
              :min="200"
              :max="20000"
              :step="100"
              class="full-width"
              @update:value="(v: number | null) => setField('max_output_chars', v ?? 4000)"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('ocrSettings.timeoutSeconds')" label-placement="top">
            <n-input-number
              :value="Number(getField('timeout_seconds')) || 15"
              :min="1"
              :max="86400"
              :step="1"
              :disabled="getField('timeout_disabled') === 'true'"
              class="full-width"
              @update:value="(v: number | null) => setField('timeout_seconds', v ?? 15)"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('ocrSettings.timeoutMode')" label-placement="top">
            <n-select
              :value="getField('timeout_disabled') === 'true' ? 'disabled' : 'enabled'"
              :options="[
                { label: t('ocrSettings.timeoutEnabledOption'), value: 'enabled' },
                { label: t('ocrSettings.timeoutDisabledOption'), value: 'disabled' },
              ]"
              @update:value="(v: string) => setField('timeout_disabled', v === 'disabled')"
            />
          </n-form-item>
        </n-gi>
      </template>
    </n-grid>
  </SectionCard>
</template>

<style scoped>
.full-width {
  width: 100%;
}
</style>
