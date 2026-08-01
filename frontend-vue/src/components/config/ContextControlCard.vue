<script setup lang="ts">
/**
 * ContextControlCard — context mode (channel/memory) plus per-mode
 * message/char limits with their "unlimited" switches.
 *
 * `unlimited_message_count` disables `message_limit`; `unlimited_context_length`
 * disables `char_limit` (mirrors the legacy ConfigPanel.svelte bindings).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NCheckbox, NFormItem, NGrid, NGi, NInputNumber, NRadioButton, NRadioGroup, NText } from 'naive-ui'

import { useConfigsStore } from '@/stores/configs'
import type { ContextSettings } from '@/api/config'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const configsStore = useConfigsStore()

const config = computed(() => configsStore.config)
const markDirty = (): void => configsStore.markDirty()

const modeOptions = [
  { label: t('contextControl.modes.none'), value: 'none' },
  { label: t('contextControl.modes.channel'), value: 'channel' },
  { label: t('contextControl.modes.memory'), value: 'memory' },
]

const activeSettings = computed<ContextSettings | null>(() => {
  if (!config.value) return null
  if (config.value.context_mode === 'none') return null
  const key = `${config.value.context_mode}_context_settings`
  return ((config.value as Record<string, unknown>)[key] as ContextSettings) ?? null
})

const modeInfo = computed(() => t(`contextControl.${config.value?.context_mode ?? 'channel'}ModeInfo`))

function setContextMode(value: string): void {
  if (config.value) config.value.context_mode = value as 'none' | 'channel' | 'memory'
  markDirty()
}

function setUnlimitedFlag(field: 'unlimited_message_count' | 'unlimited_context_length', value: boolean): void {
  if (activeSettings.value) {
    activeSettings.value[field] = value
    markDirty()
  }
}
</script>

<template>
  <div v-if="config">
    <SectionCard :title="t('contextControl.title')">
      <n-form-item :label="t('contextControl.contextMode')" label-placement="top">
      <n-radio-group
        :value="config.context_mode"
        @update:value="setContextMode"
      >
        <n-radio-button v-for="opt in modeOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </n-radio-button>
      </n-radio-group>
    </n-form-item>

    <n-text depth="3" class="mode-info">{{ modeInfo }}</n-text>

    <div v-if="activeSettings">
      <n-grid :cols="2" :x-gap="16" responsive="screen" item-responsive class="context-grid">
      <n-gi :span="1">
        <n-form-item :label="t('contextControl.historyLimit')" label-placement="top">
          <n-input-number
            v-model:value="activeSettings.message_limit"
            :min="0"
            :step="1"
            :disabled="activeSettings.unlimited_message_count === true"
            class="full-width"
            @update:value="markDirty"
          />
        </n-form-item>
        <n-checkbox
          :checked="activeSettings.unlimited_message_count === true"
          @update:checked="(v: boolean) => setUnlimitedFlag('unlimited_message_count', v)"
        >
          {{ t('contextControl.unlimitedHistoryMessages') }}
        </n-checkbox>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t('contextControl.charLimit')" label-placement="top">
          <n-input-number
            v-model:value="activeSettings.char_limit"
            :min="0"
            :placeholder="t('contextControl.charLimitPlaceholder')"
            :disabled="activeSettings.unlimited_context_length === true"
            class="full-width"
            @update:value="markDirty"
          />
        </n-form-item>
        <n-checkbox
          :checked="activeSettings.unlimited_context_length === true"
          @update:checked="(v: boolean) => setUnlimitedFlag('unlimited_context_length', v)"
        >
          {{ t('contextControl.unlimitedContextLength') }}
        </n-checkbox>
      </n-gi>
      </n-grid>
    </div>
  </SectionCard>
  </div>
</template>

<style scoped>
.mode-info {
  display: block;
  margin: -4px 0 12px;
  font-size: 13px;
}

.context-grid {
  margin-top: 4px;
}

.full-width {
  width: 100%;
}
</style>
