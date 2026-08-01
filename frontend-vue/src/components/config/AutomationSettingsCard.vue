<script setup lang="ts">
/**
 * AutomationSettingsCard — auto interject + repeat parrot settings.
 * Direct store binding; every edit marks the config dirty.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NFormItem, NGrid, NGi, NInputNumber, NSwitch, NText } from 'naive-ui'

import { useConfigsStore } from '@/stores/configs'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const configsStore = useConfigsStore()

const config = computed(() => configsStore.config)
const markDirty = (): void => configsStore.markDirty()
</script>

<template>
  <div v-if="config">
    <SectionCard :title="t('automation.title')">
      <n-text depth="3" class="section-hint">{{ t('automation.description') }}</n-text>
    </SectionCard>

    <SectionCard :title="t('automation.autoInterjectTitle')">
      <n-text depth="3" class="section-hint">{{ t('automation.autoInterjectInfo') }}</n-text>
      <n-grid :cols="3" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
        <n-gi :span="1">
          <n-form-item :label="t('automation.autoInterjectEnabled')" label-placement="top">
            <n-switch v-model:value="config.auto_interject_enabled" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('automation.autoInterjectInterval')" label-placement="top">
            <n-input-number
              v-model:value="config.auto_interject_interval"
              :min="1"
              :step="1"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('automation.autoInterjectMinLength')" label-placement="top">
            <n-input-number
              v-model:value="config.auto_interject_min_length"
              :min="0"
              :step="1"
              class="full-width"
              @update:value="markDirty"
            />
            <template #feedback>{{ t('automation.autoInterjectMinLengthHint') }}</template>
          </n-form-item>
        </n-gi>
      </n-grid>
    </SectionCard>

    <SectionCard :title="t('automation.repeatParrotTitle')">
      <n-text depth="3" class="section-hint">{{ t('automation.repeatParrotInfo') }}</n-text>
      <n-grid :cols="3" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
        <n-gi :span="1">
          <n-form-item :label="t('automation.repeatParrotEnabled')" label-placement="top">
            <n-switch v-model:value="config.repeat_parrot_enabled" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('automation.repeatParrotThreshold')" label-placement="top">
            <n-input-number
              v-model:value="config.repeat_parrot_threshold"
              :min="2"
              :step="1"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('automation.repeatParrotMinLength')" label-placement="top">
            <n-input-number
              v-model:value="config.repeat_parrot_min_length"
              :min="0"
              :step="1"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('automation.repeatParrotCaseSensitive')" label-placement="top">
            <n-switch v-model:value="config.repeat_parrot_case_sensitive" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('automation.repeatParrotTrimWhitespace')" label-placement="top">
            <n-switch v-model:value="config.repeat_parrot_trim_whitespace" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('automation.repeatParrotRequireMultipleUsers')" label-placement="top">
            <n-switch v-model:value="config.repeat_parrot_require_multiple_users" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
      </n-grid>
    </SectionCard>
  </div>
</template>

<style scoped>
.section-hint {
  display: block;
  margin-bottom: 12px;
  font-size: 13px;
}

.full-width {
  width: 100%;
}
</style>
