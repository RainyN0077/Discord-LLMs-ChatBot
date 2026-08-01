<script setup lang="ts">
/**
 * LLMProviderCard — Card 1 of Model Settings (mirrors the legacy
 * ModelSettings.svelte Card 1): provider select, API key, Base URL, the
 * three-state model selector, connection test result and multimodal /
 * response-mode controls.
 *
 * Presentational: all state (draft, model lists, fetch/test in-flight
 * flags, test results) lives in the parent page; this card only emits
 * `update:*` / action events.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NAlert,
  NButton,
  NCheckbox,
  NFormItem,
  NInput,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
} from 'naive-ui'

import SectionCard from '@/components/common/SectionCard.vue'
import type { BotConfig } from '@/api/config'
import type { ModelTestResponse } from '@/api/models'
import {
  KNOWN_PROVIDERS,
  LLM_PROVIDER_VALUES,
  PROVIDER_DEFAULTS,
  getProviderBaseUrl,
} from './providerDefaults'

const props = defineProps<{
  draft: BotConfig
  availableModels: string[]
  modelMode: 'list' | 'default' | 'manual'
  fetchLoading: boolean
  testing: boolean
  testResult: ModelTestResponse | null
}>()

const emit = defineEmits<{
  (e: 'update-llm-provider', value: string): void
  (e: 'update-api-key', value: string): void
  (e: 'update-base-url', value: string): void
  (e: 'update-model-name', value: string): void
  (e: 'update-multimodal', value: boolean): void
  (e: 'update-stream-response', value: boolean): void
  (e: 'fetch-models'): void
  (e: 'toggle-manual'): void
  (e: 'test-connection'): void
}>()

const { t } = useI18n()

const providerOptions = LLM_PROVIDER_VALUES.map((value) => ({
  label: t(`llmProvider.providers.${value}`),
  value,
}))

/** Base URL input is only shown for providers outside the 7 CN defaults. */
const isKnownProvider = computed(() =>
  KNOWN_PROVIDERS.includes(props.draft.llm_provider),
)

/** Display value of the active base_url slot (read-only mapping). */
const baseUrlValue = computed(() => getProviderBaseUrl(props.draft))

/** Legacy label suffixes: (Grok) / (Anthropic) / (API Base). */
const baseUrlLabel = computed(() => {
  const provider = props.draft.llm_provider
  if (provider === 'grok') return `${t('llmProvider.baseUrl')} (Grok)`
  if (provider === 'anthropic') return `${t('llmProvider.baseUrl')} (Anthropic)`
  return `${t('llmProvider.baseUrl')} (API Base)`
})

const defaultModel = computed(
  () => PROVIDER_DEFAULTS[props.draft.llm_provider]?.defaultModel,
)

/** Toggle-able only when at least one of list / default models is present. */
const hasModelSource = computed(
  () => props.availableModels.length > 0 || Boolean(defaultModel.value),
)

/** Options for the "default model only" single-value select. */
const defaultModelOptions = computed(() => {
  const options: { label: string; value: string }[] = []
  if (defaultModel.value) options.push({ label: defaultModel.value, value: defaultModel.value })
  // Keep a loaded model_name visible even when it differs from the default.
  const current = props.draft.model_name
  if (current && current !== defaultModel.value) {
    options.push({ label: current, value: current })
  }
  return options
})

const manualPlaceholder = computed(
  () => t(`defaultBehavior.modelPlaceholders.${props.draft.llm_provider}`),
)

const usage = computed(() => props.testResult?.model_info?.usage)
</script>

<template>
  <SectionCard :title="t('llmProvider.title')">
    <n-grid :cols="2" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
      <n-gi :span="1">
        <n-form-item :label="t('llmProvider.select')" label-placement="top">
          <n-select
            :value="draft.llm_provider"
            :options="providerOptions"
            @update:value="(v: string) => emit('update-llm-provider', v)"
          />
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t('llmProvider.apiKey')" label-placement="top">
          <n-input
            :value="draft.api_key"
            type="password"
            show-password-on="click"
            :placeholder="t('llmProvider.apiKeyPlaceholder')"
            @update:value="(v: string) => emit('update-api-key', v)"
          />
        </n-form-item>
      </n-gi>

      <n-gi v-if="!isKnownProvider" :span="2">
        <n-form-item :label="baseUrlLabel" label-placement="top">
          <n-input
            :value="baseUrlValue"
            :placeholder="t('llmProvider.baseUrlPlaceholder')"
            @update:value="(v: string) => emit('update-base-url', v)"
          />
        </n-form-item>
      </n-gi>

      <n-gi :span="2">
        <n-form-item :label="t('defaultBehavior.modelName')" label-placement="top">
          <n-space vertical :size="8" class="full-width">
            <n-select
              v-if="modelMode === 'list'"
              :value="draft.model_name"
              :options="availableModels.map((m) => ({ label: m, value: m }))"
              :placeholder="t('llmProvider.selectModel')"
              @update:value="(v: string) => emit('update-model-name', v)"
            />
            <n-select
              v-else-if="modelMode === 'default'"
              :value="draft.model_name"
              :options="defaultModelOptions"
              :placeholder="t('llmProvider.selectModel')"
              @update:value="(v: string) => emit('update-model-name', v)"
            />
            <n-input
              v-else
              :value="draft.model_name"
              :placeholder="manualPlaceholder"
              @update:value="(v: string) => emit('update-model-name', v)"
            />
            <n-space :size="8">
              <n-button
                size="small"
                :loading="fetchLoading"
                :disabled="!draft.api_key"
                :title="t('llmProvider.fetchModelsTooltip')"
                @click="emit('fetch-models')"
              >
                {{ fetchLoading ? t('llmProvider.loading') : t('llmProvider.fetchModels') }}
              </n-button>
              <n-button
                v-if="hasModelSource"
                size="small"
                :title="t('llmProvider.toggleInputMode')"
                @click="emit('toggle-manual')"
              >
                {{ modelMode === 'manual' ? '📋' : '✏️' }}
              </n-button>
              <n-button
                size="small"
                type="primary"
                :loading="testing"
                :disabled="!draft.api_key || !draft.model_name"
                @click="emit('test-connection')"
              >
                {{ testing ? t('llmProvider.testing') : t('llmProvider.testConnection') }}
              </n-button>
            </n-space>
            <p v-if="modelMode === 'list'" class="model-list-info">
              {{ t('llmProvider.modelListInfo', { count: availableModels.length }) }}
            </p>
          </n-space>
        </n-form-item>
      </n-gi>
    </n-grid>

    <n-alert
      v-if="testResult"
      class="test-result"
      :type="testResult.success ? 'success' : 'error'"
      :bordered="false"
    >
      <strong>{{ t('llmProvider.testResult') }}:</strong>
      <template v-if="testResult.success">
        <p class="test-line">
          {{ t('llmProvider.modelResponded') }}: "{{ testResult.response }}"
        </p>
        <p v-if="usage" class="usage-info">
          {{
            t('llmProvider.usageInfo', {
              total: usage.total_tokens ?? 0,
              prompt: usage.prompt_tokens ?? 0,
              completion: usage.completion_tokens ?? 0,
            })
          }}
        </p>
      </template>
      <p v-else class="test-line">{{ testResult.error }}</p>
    </n-alert>

    <div class="multimodal-block">
      <n-checkbox
        :checked="draft.llm_is_multimodal"
        @update:checked="(v: boolean) => emit('update-multimodal', v)"
      >
        {{ t('llmProvider.multimodalLabel') }}
      </n-checkbox>
      <p class="info-text">{{ t('llmProvider.multimodalInfo') }}</p>
      <p v-if="draft.llm_is_multimodal" class="info-text ocr-hint">
        {{ t('llmProvider.ocrHiddenHint') }}
      </p>
    </div>

    <div class="response-mode-block">
      <div class="group-label">{{ t('defaultBehavior.responseMode') }}</div>
      <n-radio-group
        :value="draft.stream_response"
        @update:value="(v: string | number | boolean) => emit('update-stream-response', v === true)"
      >
        <n-space :size="16">
          <n-radio :value="true">{{ t('defaultBehavior.modes.stream') }}</n-radio>
          <n-radio :value="false">{{ t('defaultBehavior.modes.nonStream') }}</n-radio>
        </n-space>
      </n-radio-group>
    </div>
  </SectionCard>
</template>

<style scoped>
.full-width {
  width: 100%;
}

.model-list-info {
  margin: 0;
  font-size: 12px;
  opacity: 0.7;
}

.test-result {
  margin-top: 12px;
}

.test-line {
  margin: 4px 0 0;
}

.usage-info {
  margin: 4px 0 0;
  font-size: 12px;
  opacity: 0.8;
}

.multimodal-block {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--n-border-color, rgba(128, 128, 128, 0.2));
  border-radius: 8px;
}

.info-text {
  margin: 6px 0 0;
  font-size: 12px;
  opacity: 0.7;
}

.ocr-hint {
  opacity: 1;
}

.response-mode-block {
  margin-top: 16px;
}

.group-label {
  margin-bottom: 8px;
  font-weight: 500;
  opacity: 0.75;
}
</style>
