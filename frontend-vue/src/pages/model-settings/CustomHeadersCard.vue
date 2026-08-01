<script setup lang="ts">
/**
 * CustomHeadersCard — `custom_headers` list editor ({ name, value } rows,
 * mirrors the legacy ModelSettings.svelte Card 3).
 *
 * Presentational: rows come from props, edits bubble up via emits.
 */
import { useI18n } from 'vue-i18n'
import { NButton, NInput, NSpace } from 'naive-ui'

import SectionCard from '@/components/common/SectionCard.vue'
import type { CustomHeader } from '@/api/config'

defineProps<{
  headers: CustomHeader[]
}>()

const emit = defineEmits<{
  (e: 'add'): void
  (e: 'remove', index: number): void
  (e: 'update-field', index: number, field: 'name' | 'value', value: string): void
}>()

const { t } = useI18n()
</script>

<template>
  <SectionCard :title="t('customHeaders.title')">
    <n-space vertical :size="8" class="headers-list">
      <n-space
        v-for="(header, i) in headers"
        :key="i"
        :size="8"
        align="center"
        class="header-row"
      >
        <n-input
          class="header-name"
          :value="header.name"
          :placeholder="t('customHeaders.namePlaceholder')"
          @update:value="(v: string) => emit('update-field', i, 'name', v)"
        />
        <n-input
          class="header-value"
          :value="header.value"
          :placeholder="t('customHeaders.valuePlaceholder')"
          @update:value="(v: string) => emit('update-field', i, 'value', v)"
        />
        <n-button
          size="small"
          quaternary
          type="error"
          :title="t('customHeaders.remove')"
          @click="emit('remove', i)"
        >
          ×
        </n-button>
      </n-space>
    </n-space>
    <n-button size="small" dashed class="add-btn" @click="emit('add')">
      {{ t('customHeaders.add') }}
    </n-button>
  </SectionCard>
</template>

<style scoped>
.header-row {
  width: 100%;
}

.header-name {
  flex: 1;
}

.header-value {
  flex: 2;
}

.add-btn {
  margin-top: 12px;
}
</style>
