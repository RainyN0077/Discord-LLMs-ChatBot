<script setup lang="ts">
/**
 * CustomParamsCard — `custom_parameters` table (name / type / value).
 *
 * Four types (text / number / boolean / json) mirror the legacy ConfigPanel;
 * the backend stores `type` as a free string, so legacy `text`/`json` rows
 * must render. Switching type resets the row value (number→0, boolean→'true',
 * text/json→''). Rows are kept as raw strings in the UI; the type conversion
 * to number / boolean happens in the store's save() step.
 */
import { computed, h } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton,
  NDataTable,
  NInput,
  NSelect,
  type DataTableColumns,
} from 'naive-ui'

import type { CustomParameter } from '@/api/config'
import { useConfigsStore } from '@/stores/configs'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const configsStore = useConfigsStore()

const config = computed(() => configsStore.config)
const markDirty = (): void => configsStore.markDirty()

const typeOptions = [
  { label: t('customParams.types.text'), value: 'text' },
  { label: t('customParams.types.number'), value: 'number' },
  { label: t('customParams.types.boolean'), value: 'boolean' },
  { label: t('customParams.types.json'), value: 'json' },
]

/** Default value for a freshly-switched type (mirrors legacy ConfigPanel). */
function resetValueForType(type: string): string | number {
  if (type === 'number') return 0
  if (type === 'boolean') return 'true'
  return ''
}

function addParameter(): void {
  if (!config.value) return
  config.value.custom_parameters = [
    ...config.value.custom_parameters,
    { name: '', type: 'text', value: '' },
  ]
  markDirty()
}

function changeType(row: CustomParameter, type: string): void {
  if (row.type === type) return
  row.type = type
  row.value = resetValueForType(type)
  markDirty()
}

function removeParameter(index: number): void {
  if (!config.value) return
  config.value.custom_parameters = config.value.custom_parameters.filter((_, i) => i !== index)
  markDirty()
}

function rowKey(row: CustomParameter): number {
  return config.value?.custom_parameters.indexOf(row) ?? 0
}

const columns = computed<DataTableColumns<CustomParameter>>(() => [
  {
    title: t('customParams.paramName'),
    key: 'name',
    render: (row) =>
      h(NInput, {
        value: row.name,
        size: 'small',
        placeholder: t('customParams.paramName'),
        onUpdateValue: (v: string) => {
          row.name = v
          markDirty()
        },
      }),
  },
  {
    title: t('customParams.paramValue'),
    key: 'value',
    render: (row) =>
      h(NInput, {
        value: String(row.value),
        size: 'small',
        placeholder: t('customParams.paramValue'),
        onUpdateValue: (v: string) => {
          row.value = v
          markDirty()
        },
      }),
  },
  {
    title: t('customParams.types.text'),
    key: 'type',
    width: 140,
    render: (row) =>
      h(NSelect, {
        value: row.type,
        options: typeOptions,
        size: 'small',
        onUpdateValue: (v: string) => changeType(row, v),
      }),
  },
  {
    title: '',
    key: 'actions',
    width: 80,
    render: (_row, index) =>
      h(
        NButton,
        {
          size: 'tiny',
          quaternary: true,
          type: 'error',
          onClick: () => removeParameter(index),
        },
        { default: () => t('customParams.remove') },
      ),
  },
])</script>

<template>
  <SectionCard v-if="config" :title="t('customParams.title')">
    <n-data-table
      :columns="columns"
      :data="config.custom_parameters"
      :row-key="rowKey"
      :bordered="false"
      size="small"
      class="params-table"
    />
    <n-button size="small" dashed class="add-btn" @click="addParameter">
      {{ t('customParams.add') }}
    </n-button>
  </SectionCard>
</template>

<style scoped>
.add-btn {
  margin-top: 12px;
}
</style>
