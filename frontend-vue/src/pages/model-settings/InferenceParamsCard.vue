<script setup lang="ts">
/**
 * InferenceParamsCard — 6 optional inference parameters with per-field
 * clear buttons (mirrors the legacy ModelSettings.svelte Card 2).
 *
 * Presentational: values come from props, edits bubble up via
 * `update-field` / `clear-field` emits.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NFormItem, NInputNumber, NSpace } from 'naive-ui'

import SectionCard from '@/components/common/SectionCard.vue'

export interface InferenceParams {
  temperature: number | null
  top_p: number | null
  max_tokens: number | null
  top_k: number | null
  frequency_penalty: number | null
  presence_penalty: number | null
}

const props = defineProps<{
  params: InferenceParams
  /** Current provider — drives the temperature placeholder. */
  llm_provider: string
}>()

const emit = defineEmits<{
  (e: 'update-field', key: keyof InferenceParams, value: number | null): void
  (e: 'clear-field', key: keyof InferenceParams): void
}>()

const { t, te } = useI18n()

interface ParamField {
  key: keyof InferenceParams
  label: string
  min: number
  max?: number
  step: number
  placeholder: string
}

const fields = computed<ParamField[]>(() => {
  // Provider-specific recommendation falls back to the generic default
  // (mirrors the legacy page's placeholder lookup chain).
  const temperatureKey = `inferenceParams.placeholders.${props.llm_provider}`
  const temperaturePlaceholder = te(temperatureKey)
    ? t(temperatureKey)
    : t('inferenceParams.placeholders.default')
  return [
    {
      key: 'temperature',
      label: 'inferenceParams.temperature',
      min: 0,
      max: 2,
      step: 0.1,
      placeholder: temperaturePlaceholder,
    },
    {
      key: 'top_p',
      label: 'inferenceParams.topP',
      min: 0,
      max: 1,
      step: 0.05,
      placeholder: t('inferenceParams.placeholders.topP'),
    },
    {
      key: 'max_tokens',
      label: 'inferenceParams.maxTokens',
      min: 1,
      step: 1,
      placeholder: t('inferenceParams.maxTokensHint'),
    },
    {
      key: 'top_k',
      label: 'inferenceParams.topK',
      min: 1,
      step: 1,
      placeholder: t('inferenceParams.placeholders.topK'),
    },
    {
      key: 'frequency_penalty',
      label: 'inferenceParams.frequencyPenalty',
      min: -2,
      max: 2,
      step: 0.1,
      placeholder: t('inferenceParams.placeholders.frequencyPenalty'),
    },
    {
      key: 'presence_penalty',
      label: 'inferenceParams.presencePenalty',
      min: -2,
      max: 2,
      step: 0.1,
      placeholder: t('inferenceParams.placeholders.presencePenalty'),
    },
  ]
})
</script>

<template>
  <SectionCard :title="t('inferenceParams.title')">
    <p class="inference-hint">{{ t('inferenceParams.hint') }}</p>
    <n-grid :cols="2" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
      <n-gi v-for="f in fields" :key="f.key" :span="1">
        <n-form-item :label="t(f.label)" label-placement="top" class="param-field">
          <n-space :size="8" class="param-row">
            <n-input-number
              class="param-input"
              :value="params[f.key]"
              :min="f.min"
              :max="f.max"
              :step="f.step"
              :placeholder="f.placeholder"
              @update:value="(v: number | null) => emit('update-field', f.key, v)"
            />
            <n-button
              size="small"
              quaternary
              :title="t('inferenceParams.clear')"
              @click="emit('clear-field', f.key)"
            >
              ×
            </n-button>
          </n-space>
        </n-form-item>
      </n-gi>
    </n-grid>
  </SectionCard>
</template>

<style scoped>
.inference-hint {
  margin: 0 0 12px;
  font-size: 13px;
  opacity: 0.7;
}

.param-row {
  width: 100%;
}

.param-input {
  flex: 1;
}
</style>
