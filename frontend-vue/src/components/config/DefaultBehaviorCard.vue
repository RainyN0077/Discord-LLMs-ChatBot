<script setup lang="ts">
/**
 * DefaultBehaviorCard — trigger keywords, match mode, case sensitivity and
 * streaming response mode. Direct store binding with dirty marking.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NDynamicTags, NFormItem, NGrid, NGi, NSelect, NSwitch } from 'naive-ui'

import { useConfigsStore } from '@/stores/configs'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const configsStore = useConfigsStore()

const config = computed(() => configsStore.config)
const markDirty = (): void => configsStore.markDirty()

const matchModeOptions = [
  { label: t('defaultBehavior.triggerMatchModes.contains'), value: 'contains' },
  // Backend (backend/app/utils.py) only recognizes contains/starts_with/exact/regex.
  { label: t('defaultBehavior.triggerMatchModes.startsWith'), value: 'starts_with' },
  { label: t('defaultBehavior.triggerMatchModes.exact'), value: 'exact' },
  { label: t('defaultBehavior.triggerMatchModes.regex'), value: 'regex' },
]

function setTriggerKeywords(value: string[]): void {
  if (config.value) config.value.trigger_keywords = value
  markDirty()
}

function setMatchMode(value: string): void {
  if (config.value) config.value.trigger_match_mode = value
  markDirty()
}
</script>

<template>
  <div v-if="config">
    <SectionCard :title="t('defaultBehavior.title')">
      <n-grid :cols="2" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
        <n-gi :span="2">
          <n-form-item :label="t('defaultBehavior.triggerKeywords')" label-placement="top">
            <n-dynamic-tags
              :value="config.trigger_keywords"
              :placeholder="t('defaultBehavior.triggerKeywordsPlaceholder')"
              @update:value="setTriggerKeywords"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('defaultBehavior.triggerMatchMode')" label-placement="top">
            <n-select
              :value="config.trigger_match_mode"
              :options="matchModeOptions"
              @update:value="setMatchMode"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('defaultBehavior.triggerCaseSensitive')" label-placement="top">
            <n-switch v-model:value="config.trigger_case_sensitive" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('defaultBehavior.responseMode')" label-placement="top">
            <n-switch
              v-model:value="config.stream_response"
              @update:value="markDirty"
            />
            <template #feedback>
              {{ config.stream_response
                ? t('defaultBehavior.modes.stream')
                : t('defaultBehavior.modes.nonStream') }}
            </template>
          </n-form-item>
        </n-gi>
      </n-grid>
    </SectionCard>
  </div>
</template>
