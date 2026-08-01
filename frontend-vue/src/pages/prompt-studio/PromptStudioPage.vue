<script setup lang="ts">
/**
 * PromptStudioPage — container: 4 tabs (global templates / scope overrides /
 * plugin integration / role strategies) with a sticky save bar.
 *
 * `currentTemplates` is a local reactive copy of the config's
 * `prompt_templates` (falling back to DEFAULT_TEMPLATES); the save bar
 * writes it back into the config before the full-config round-trip.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NTabs, NTabPane, NButton, NSpin, NAlert, NTag } from 'naive-ui'

import { useBotsStore } from '@/stores/bots'
import { useConfigsStore } from '@/stores/configs'
import type { PromptTemplate } from '@/api/prompts'
import EmptyState from '@/components/common/EmptyState.vue'
import PluginEditor from '@/components/config/PluginEditor.vue'
import PresetManager from './PresetManager.vue'
import TemplateEditor from './TemplateEditor.vue'
import ScenarioSimulator from './ScenarioSimulator.vue'
import ScopedPromptEditor from './ScopedPromptEditor.vue'
import RoleConfigEditor from './RoleConfigEditor.vue'
import { DEFAULT_TEMPLATES, normalizeTemplates } from './defaultTemplates'

const { t } = useI18n()
const message = useMessage()
const botsStore = useBotsStore()
const configsStore = useConfigsStore()

const activeTab = ref('global')
const currentTemplates = ref<PromptTemplate>({ ...DEFAULT_TEMPLATES })

/** Serialized snapshot of the last-synced templates (config load / save). */
const templatesBaseline = ref('')

function baselineKey(templates: PromptTemplate): string {
  return JSON.stringify(normalizeTemplates(templates))
}

// Anchor the baseline to the initial defaults so the dirty badge never
// flashes before the config finishes loading.
templatesBaseline.value = baselineKey(currentTemplates.value)

/** Page-level dirty flag: template edits / preset load / import vs. baseline. */
const templatesDirty = computed(() => baselineKey(currentTemplates.value) !== templatesBaseline.value)

/** Bot-scoped preset storage target; undefined → global presets. */
const presetBotId = computed<string | undefined>(() => botsStore.selectedBotId ?? undefined)

// Sync the local template copy when a (different) config finishes loading.
// Baseline is re-anchored here so a config reload never marks templates dirty.
watch(
  () => configsStore.config,
  (config) => {
    if (config) {
      currentTemplates.value = normalizeTemplates(config.prompt_templates)
    } else {
      currentTemplates.value = { ...DEFAULT_TEMPLATES }
    }
    templatesBaseline.value = baselineKey(currentTemplates.value)
  },
)

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
  if (!botsStore.bots.length) void botsStore.fetchBotsList()
})

/** Apply a template payload (preset load / import). */
function applyTemplates(templates: PromptTemplate): void {
  currentTemplates.value = normalizeTemplates(templates)
}

async function handleSave(): Promise<void> {
  const botId = botsStore.selectedBotId
  if (!botId || configsStore.saving || !configsStore.config) return
  // Write the local template copy into the config before the full PUT.
  configsStore.config.prompt_templates = JSON.parse(JSON.stringify(currentTemplates.value))
  configsStore.markDirty()
  const ok = await configsStore.save(botId)
  // Re-anchor the baseline only on success — a failed save keeps the dirty mark.
  if (ok) templatesBaseline.value = baselineKey(currentTemplates.value)
}

async function handleReset(): Promise<void> {
  const botId = botsStore.selectedBotId
  if (!botId) return
  await configsStore.load(botId)
  message.info(t('promptStudio.reset'))
}
</script>

<template>
  <div class="prompt-studio-page">
    <template v-if="!botsStore.selectedBot">
      <EmptyState :description="t('configPanel.selectBot')" />
    </template>

    <template v-else>
      <div class="prompt-studio-head">
        <div>
          <h2 class="prompt-studio-title">{{ t('promptStudio.title') }}</h2>
          <p class="prompt-studio-desc">{{ t('promptStudio.description') }}</p>
        </div>
      </div>

      <n-alert v-if="configsStore.error" type="error" class="prompt-studio-alert">
        {{ configsStore.error }}
      </n-alert>

      <n-spin :show="configsStore.loading">
        <template v-if="configsStore.config">
          <n-tabs v-model:value="activeTab" type="line" animated>
            <n-tab-pane name="global" :tab="t('promptStudio.tabs.global')">
              <PresetManager
                :templates="currentTemplates"
                :bot-id="presetBotId"
                @apply="applyTemplates"
              />
              <TemplateEditor v-model:templates="currentTemplates" />
              <ScenarioSimulator
                :templates="currentTemplates"
                :bot-id="presetBotId"
              />
            </n-tab-pane>

            <n-tab-pane name="scopes" :tab="t('promptStudio.tabs.scopes')">
              <ScopedPromptEditor type="guilds" :title="t('promptStudio.scopeServerOverride')" />
              <ScopedPromptEditor type="channels" :title="t('promptStudio.scopeChannelOverride')" />
            </n-tab-pane>

            <n-tab-pane name="plugins" :tab="t('promptStudio.tabs.plugins')">
              <PluginEditor />
            </n-tab-pane>

            <n-tab-pane name="roles" :tab="t('promptStudio.tabs.roles')">
              <RoleConfigEditor />
            </n-tab-pane>
          </n-tabs>
        </template>
      </n-spin>

      <!-- Sticky save bar (legacy parity: full round-trip save + reload reset) -->
      <div class="prompt-studio-bar">
        <n-tag v-if="templatesDirty || configsStore.dirty" type="warning" size="small">
          {{ t('promptStudio.unsavedChanges') }}
        </n-tag>
        <span v-else class="prompt-studio-bar-spacer" />
        <n-button :loading="configsStore.loading" @click="handleReset">
          {{ t('promptStudio.reset') }}
        </n-button>
        <n-button
          type="success"
          :loading="configsStore.saving"
          :disabled="!botsStore.selectedBotId"
          @click="handleSave"
        >
          {{ configsStore.saving ? t('promptStudio.saving') : t('promptStudio.save') }}
        </n-button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.prompt-studio-page {
  max-width: 1200px;
  margin: 0 auto;
}

.prompt-studio-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
}

.prompt-studio-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.prompt-studio-desc {
  margin: 4px 0 0;
  color: var(--text-color-3);
  font-size: 13px;
}

.prompt-studio-alert {
  margin-bottom: 12px;
}

.prompt-studio-bar {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 16px;
  margin-top: 16px;
  background: var(--card-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  z-index: 10;
}

.prompt-studio-bar-spacer {
  flex: 1;
}
</style>
