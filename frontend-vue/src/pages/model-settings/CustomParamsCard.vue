<script setup lang="ts">
/**
 * CustomParamsCard — `custom_parameters` list editor ({ name, type, value }
 * rows, mirrors the legacy ModelSettings.svelte Card 4).
 *
 * Type switching coerces the row value (number→0, boolean→'true',
 * text/json→''). Booleans are edited via a 'true'/'false' string select and
 * JSON values via a textarea; the final number/boolean coercion happens in
 * the configs store's save pipeline.
 *
 * Presentational: rows come from props, edits bubble up via emits.
 */
import { useI18n } from 'vue-i18n'
import { NButton, NInput, NInputNumber, NSelect, NSpace } from 'naive-ui'

import SectionCard from '@/components/common/SectionCard.vue'
import type { CustomParameter } from '@/api/config'

const props = defineProps<{
  params: CustomParameter[]
}>()

const emit = defineEmits<{
  (e: 'add'): void
  (e: 'remove', index: number): void
  (e: 'update-field', index: number, field: 'name' | 'value', value: string | number): void
  /** Type changed — the coerced value is emitted right after. */
  (e: 'change-type', index: number, type: string): void
}>()

const { t } = useI18n()

const typeOptions = [
  { label: t('customParams.types.text'), value: 'text' },
  { label: t('customParams.types.number'), value: 'number' },
  { label: t('customParams.types.boolean'), value: 'boolean' },
  { label: t('customParams.types.json'), value: 'json' },
]

const boolOptions = [
  { label: 'True', value: 'true' },
  { label: 'False', value: 'false' },
]

/** Coerce a freshly-switched type (mirrors the legacy page). */
function coercedValueFor(type: string): string | number {
  if (type === 'number') return 0
  if (type === 'boolean') return 'true'
  return ''
}

function handleTypeChange(index: number, type: string): void {
  if (props.params[index].type === type) return
  emit('change-type', index, type)
  emit('update-field', index, 'value', coercedValueFor(type))
}

/** Normalize a possibly-string number for NInputNumber. */
function numberValue(row: CustomParameter): number | null {
  const v = row.value
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}
</script>

<template>
  <SectionCard :title="t('customParams.title')">
    <n-space vertical :size="8" class="params-list">
      <n-space
        v-for="(param, i) in params"
        :key="i"
        :size="8"
        align="center"
        class="param-row"
      >
        <n-input
          class="param-name"
          :value="param.name"
          :placeholder="t('customParams.paramName')"
          @update:value="(v: string) => emit('update-field', i, 'name', v)"
        />
        <n-select
          class="param-type"
          :value="param.type"
          :options="typeOptions"
          @update:value="(v: string) => handleTypeChange(i, v)"
        />
        <n-input
          v-if="param.type === 'text'"
          class="param-value"
          :value="String(param.value)"
          :placeholder="t('customParams.paramValue')"
          @update:value="(v: string) => emit('update-field', i, 'value', v)"
        />
        <n-input-number
          v-else-if="param.type === 'number'"
          class="param-value"
          :value="numberValue(param)"
          :step="0.01"
          :placeholder="t('customParams.paramValue')"
          @update:value="(v: number | null) => emit('update-field', i, 'value', v ?? '')"
        />
        <n-select
          v-else-if="param.type === 'boolean'"
          class="param-value"
          :value="String(param.value)"
          :options="boolOptions"
          @update:value="(v: string) => emit('update-field', i, 'value', v)"
        />
        <n-input
          v-else
          class="param-value param-textarea"
          type="textarea"
          :rows="1"
          :value="String(param.value)"
          :placeholder="t('customParams.paramValue')"
          @update:value="(v: string) => emit('update-field', i, 'value', v)"
        />
        <n-button
          size="small"
          quaternary
          type="error"
          :title="t('customParams.remove')"
          @click="emit('remove', i)"
        >
          ×
        </n-button>
      </n-space>
    </n-space>
    <n-button size="small" dashed class="add-btn" @click="emit('add')">
      {{ t('customParams.add') }}
    </n-button>
  </SectionCard>
</template>

<style scoped>
.param-row {
  width: 100%;
}

.param-name {
  flex: 1.5;
}

.param-type {
  flex: 1;
}

.param-value {
  flex: 2;
}

.param-textarea :deep(textarea) {
  resize: vertical;
  font-family: var(--font-mono, monospace);
}

.add-btn {
  margin-top: 12px;
}
</style>
