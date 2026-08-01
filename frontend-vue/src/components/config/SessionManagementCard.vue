<script setup lang="ts">
/**
 * SessionManagementCard — clear per-channel conversation memory
 * (POST /api/memory/clear with the channel id, behind a confirm dialog).
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDialog, useMessage } from 'naive-ui'
import { NButton, NFormItem, NInput, NText } from 'naive-ui'

import { clearMemories } from '@/api/memory'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()

const channelId = ref('')
const clearing = ref(false)

const canClear = computed(() => channelId.value.trim().length > 0 && !clearing.value)

async function handleClear(): Promise<void> {
  const id = channelId.value.trim()
  if (!id) {
    message.error(t('sessionManagement.errorNoId'))
    return
  }
  dialog.warning({
    title: t('sessionManagement.title'),
    content: t('sessionManagement.info'),
    positiveText: t('sessionManagement.clearButton'),
    negativeText: t('knowledge.memory.cancel'),
    onPositiveClick: async () => {
      clearing.value = true
      try {
        await clearMemories(id)
        message.success(t('sessionManagement.clearSuccess'))
        channelId.value = ''
      } catch (err) {
        message.error(
          t('sessionManagement.clearFailed') +
            (err instanceof Error ? err.message : String(err)),
        )
      } finally {
        clearing.value = false
      }
    },
  })
}
</script>

<template>
  <SectionCard :title="t('sessionManagement.title')">
    <n-text depth="3" class="section-hint">{{ t('sessionManagement.info') }}</n-text>
    <n-form-item :label="t('debugger.channelId')" label-placement="top">
      <n-input
        v-model:value="channelId"
        :placeholder="t('sessionManagement.channelIdPlaceholder')"
      />
    </n-form-item>
    <n-button type="error" :loading="clearing" :disabled="!canClear" @click="handleClear">
      {{ clearing ? t('sessionManagement.clearing') : t('sessionManagement.clearButton') }}
    </n-button>
  </SectionCard>
</template>

<style scoped>
.section-hint {
  display: block;
  margin-bottom: 12px;
  font-size: 13px;
}
</style>
