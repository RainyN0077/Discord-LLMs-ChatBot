<script setup lang="ts">
/**
 * UserOptionsPage — container: 5 tabs (user portraits / blocklist /
 * server portraits / channel portraits / role portraits).
 *
 * Shared editing model: local deep copies of the four config sections
 * (user_personas / user_options / scoped_prompts / role_based_config).
 * Children mutate the local reactive copies directly; the save button
 * writes them back into the config store and round-trips the FULL config.
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NSpin, NAlert, NTabs, NTabPane } from 'naive-ui'

import type { RoleConfigEntry, ScopedPromptEntry, UserOptionsConfig, UserPersona } from '@/api/config'
import { useBotsStore } from '@/stores/bots'
import { useConfigsStore } from '@/stores/configs'
import EmptyState from '@/components/common/EmptyState.vue'
import PortraitTab from './PortraitTab.vue'
import BlocklistTab from './BlocklistTab.vue'
import GuildPortraitTab from './GuildPortraitTab.vue'
import ChannelPortraitTab from './ChannelPortraitTab.vue'
import RolePortraitTab from './RolePortraitTab.vue'

const { t } = useI18n()
const botsStore = useBotsStore()
const configsStore = useConfigsStore()

const activeTab = ref('portrait')

// --- local editable copies (shared editing model) ---
const userPersonas = ref<Record<string, UserPersona>>({})
const userOptions = ref<UserOptionsConfig>({ enabled: false, rules: {} })
const scopedGuilds = ref<Record<string, ScopedPromptEntry>>({})
const scopedChannels = ref<Record<string, ScopedPromptEntry>>({})
const roleConfigs = ref<Record<string, RoleConfigEntry>>({})

function syncLocalCopies(): void {
  const config = configsStore.config
  if (!config) return
  userPersonas.value = JSON.parse(JSON.stringify(config.user_personas ?? {}))
  userOptions.value = JSON.parse(
    JSON.stringify(config.user_options ?? { enabled: false, rules: {} }),
  )
  scopedGuilds.value = JSON.parse(JSON.stringify(config.scoped_prompts?.guilds ?? {}))
  scopedChannels.value = JSON.parse(JSON.stringify(config.scoped_prompts?.channels ?? {}))
  roleConfigs.value = JSON.parse(JSON.stringify(config.role_based_config ?? {}))
}

watch(
  () => configsStore.config,
  (config) => {
    if (config) syncLocalCopies()
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

async function handleSave(): Promise<void> {
  const botId = botsStore.selectedBotId
  if (!botId || configsStore.saving || !configsStore.config) return
  // Write the local edit copies back into the config, then full PUT.
  configsStore.config.user_personas = JSON.parse(JSON.stringify(userPersonas.value))
  configsStore.config.user_options = JSON.parse(JSON.stringify(userOptions.value))
  configsStore.config.scoped_prompts = {
    guilds: JSON.parse(JSON.stringify(scopedGuilds.value)),
    channels: JSON.parse(JSON.stringify(scopedChannels.value)),
  }
  configsStore.config.role_based_config = JSON.parse(JSON.stringify(roleConfigs.value))
  configsStore.markDirty()
  await configsStore.save(botId)
}
</script>

<template>
  <div class="user-options-page">
    <template v-if="!botsStore.selectedBot">
      <EmptyState :description="t('configPanel.selectBot')" />
    </template>

    <template v-else>
      <div class="user-options-head">
        <h2 class="user-options-title">
          {{ t('userOptions.titleFor', { botId: botsStore.selectedBot.bot_id }) }}
        </h2>
        <n-button type="success" :loading="configsStore.saving" @click="handleSave">
          {{ configsStore.saving ? t('configPanel.saving') : t('configPanel.saveAndRestart') }}
        </n-button>
      </div>

      <n-alert v-if="configsStore.error" type="error" class="user-options-alert">
        {{ configsStore.error }}
      </n-alert>

      <n-spin :show="configsStore.loading">
        <template v-if="configsStore.config">
          <n-tabs v-model:value="activeTab" type="line" animated>
            <n-tab-pane name="portrait" :tab="t('userOptions.tabs.portrait')">
              <PortraitTab :user-personas="userPersonas" />
            </n-tab-pane>
            <n-tab-pane name="blocklist" :tab="t('userOptions.tabs.blocklist')">
              <BlocklistTab
                :bot-id="botsStore.selectedBotId ?? ''"
                :user-options="userOptions"
              />
            </n-tab-pane>
            <n-tab-pane name="guildPortrait" :tab="t('userOptions.tabs.guildPortrait')">
              <GuildPortraitTab
                :bot-id="botsStore.selectedBotId ?? ''"
                :scoped-items="scopedGuilds"
              />
            </n-tab-pane>
            <n-tab-pane name="channelPortrait" :tab="t('userOptions.tabs.channelPortrait')">
              <ChannelPortraitTab
                :bot-id="botsStore.selectedBotId ?? ''"
                :scoped-items="scopedChannels"
              />
            </n-tab-pane>
            <n-tab-pane name="rolePortrait" :tab="t('userOptions.tabs.rolePortrait')">
              <RolePortraitTab :role-configs="roleConfigs" />
            </n-tab-pane>
          </n-tabs>
        </template>
      </n-spin>
    </template>
  </div>
</template>

<style scoped>
.user-options-page {
  max-width: 1100px;
  margin: 0 auto;
}

.user-options-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.user-options-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.user-options-alert {
  margin-bottom: 12px;
}
</style>
