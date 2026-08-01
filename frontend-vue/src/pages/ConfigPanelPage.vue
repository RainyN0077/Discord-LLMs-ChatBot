<script setup lang="ts">
/**
 * ConfigPanelPage — Phase 1 vertical slice: shell + 4 tabs of the config
 * editor. Header holds export / import / save actions; the save button
 * round-trips the FULL config through the configs store.
 */
import { h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDialog, useMessage } from 'naive-ui'
import {
  NAlert,
  NButton,
  NCheckbox,
  NSpin,
  NTabs,
  NTabPane,
} from 'naive-ui'

import { exportBotConfig, importBotConfig } from '@/api/bots'
import { useBotsStore } from '@/stores/bots'
import { useConfigsStore } from '@/stores/configs'
import EmptyState from '@/components/common/EmptyState.vue'
import BotBasicsCard from '@/components/config/BotBasicsCard.vue'
import ContextControlCard from '@/components/config/ContextControlCard.vue'
import AdvancedProviderCard from '@/components/config/AdvancedProviderCard.vue'
import AutomationSettingsCard from '@/components/config/AutomationSettingsCard.vue'
import DefaultBehaviorCard from '@/components/config/DefaultBehaviorCard.vue'
import KnowledgeEditor from '@/components/config/KnowledgeEditor.vue'
import PluginEditor from '@/components/config/PluginEditor.vue'
import SearchSettingsCard from '@/components/config/SearchSettingsCard.vue'
import CustomParamsCard from '@/components/config/CustomParamsCard.vue'
import SessionManagementCard from '@/components/config/SessionManagementCard.vue'
import UiSettingsCard from '@/components/config/UiSettingsCard.vue'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()
const botsStore = useBotsStore()
const configsStore = useConfigsStore()

const activeTab = ref('core')
const fileInputRef = ref<HTMLInputElement | null>(null)

watch(
  () => botsStore.selectedBotId,
  (botId) => {
    configsStore.reset()
    if (botId) void configsStore.load(botId)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  configsStore.reset()
})

onMounted(() => {
  // Landing directly on this page must still populate the sidebar bot list
  // (P0 pages fetch it on mount; auto-selects the first bot afterwards).
  if (!botsStore.bots.length) void botsStore.fetchBotsList()
})

async function handleSave(): Promise<void> {
  const botId = botsStore.selectedBotId
  if (!botId || configsStore.saving) return
  await configsStore.save(botId)
}

async function handleExport(): Promise<void> {
  const botId = botsStore.selectedBotId
  if (!botId) return
  try {
    const { blob, filename } = await exportBotConfig(botId)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    message.success(t('importExport.exportSuccess'))
  } catch (err) {
    message.error(
      t('importExport.exportFailed', {
        error: err instanceof Error ? err.message : String(err),
      }),
    )
  }
}

function handleImportClick(): void {
  fileInputRef.value?.click()
}

async function handleFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // allow re-selecting the same file
  if (!file) return

  if (!file.name.toLowerCase().endsWith('.json')) {
    message.error(t('importExport.invalidFileType'))
    return
  }
  try {
    JSON.parse(await file.text())
  } catch (err) {
    message.error(
      t('importExport.invalidJson', {
        error: err instanceof Error ? err.message : String(err),
      }),
    )
    return
  }

  const overwrite = ref(false)
  dialog.warning({
    title: t('importExport.importTitle_Dialog'),
    content: () =>
      h('div', { style: 'display: flex; gap: 8px; align-items: center;' }, [
        h(NCheckbox, {
          label: t('importExport.overwriteExisting'),
          'onUpdate:checked': (v: boolean) => {
            overwrite.value = v
          },
        }),
      ]),
    positiveText: t('importExport.confirmImport'),
    negativeText: t('importExport.cancel'),
    onPositiveClick: async () => {
      try {
        const result = await importBotConfig(file, overwrite.value)
        message.success(t('importExport.importSuccess'))
        await botsStore.fetchBotsList()
        // If the imported bot is the currently selected one, reload it.
        if (botsStore.selectedBotId === result.bot_id) {
          void configsStore.load(result.bot_id)
        }
      } catch (err) {
        const e = err as { status?: number; message?: string }
        message.error(e.message || String(err))
      }
    },
  })
}
</script>

<template>
  <div class="config-panel-page">
    <template v-if="!botsStore.selectedBot">
      <EmptyState :description="t('configPanel.selectBot')" />
    </template>

    <template v-else>
      <div class="config-panel-head">
        <h2 class="config-panel-title">
          {{ t('configPanel.configFor', { botId: botsStore.selectedBot.bot_id }) }}
        </h2>
        <div class="config-panel-actions">
          <n-button :disabled="!botsStore.selectedBotId" @click="handleExport">
            {{ t('importExport.export') }}
          </n-button>
          <n-button @click="handleImportClick">
            {{ t('importExport.import') }}
          </n-button>
          <n-button
            type="success"
            :loading="configsStore.saving"
            :disabled="!botsStore.selectedBotId"
            @click="handleSave"
          >
            {{ configsStore.saving ? t('configPanel.saving') : t('configPanel.saveAndRestart') }}
          </n-button>
        </div>
      </div>

      <n-alert v-if="configsStore.error" type="error" class="config-panel-alert">
        {{ configsStore.error }}
      </n-alert>

      <n-spin :show="configsStore.loading">
        <template v-if="configsStore.config">
          <n-tabs v-model:value="activeTab" type="line" animated>
            <n-tab-pane name="core" :tab="t('tabs.core')">
              <BotBasicsCard />
              <ContextControlCard />
              <!-- OCR config is irrelevant when the main model reads images -->
              <AdvancedProviderCard
                v-if="!configsStore.config.llm_is_multimodal"
                prefix="ocr"
                :config="configsStore.config"
              />
              <AdvancedProviderCard prefix="embedding" :config="configsStore.config" />
              <AdvancedProviderCard prefix="rerank" :config="configsStore.config" />
            </n-tab-pane>
            <n-tab-pane name="directives" :tab="t('tabs.directives')">
              <DefaultBehaviorCard />
              <KnowledgeEditor @save="handleSave" />
            </n-tab-pane>
            <n-tab-pane name="automation" :tab="t('tabs.automation')">
              <AutomationSettingsCard />
            </n-tab-pane>
            <n-tab-pane name="advanced" :tab="t('tabs.advanced')">
              <PluginEditor />
              <SearchSettingsCard />
              <CustomParamsCard />
              <SessionManagementCard />
              <UiSettingsCard />
            </n-tab-pane>
          </n-tabs>
        </template>
      </n-spin>
    </template>

    <input
      ref="fileInputRef"
      type="file"
      accept=".json"
      class="hidden-file-input"
      @change="handleFileChange"
    />
  </div>
</template>

<style scoped>
.config-panel-page {
  max-width: 1100px;
  margin: 0 auto;
}

.config-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.config-panel-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.config-panel-actions {
  display: flex;
  gap: 8px;
}

.config-panel-alert {
  margin-bottom: 12px;
}

.hidden-file-input {
  display: none;
}
</style>
