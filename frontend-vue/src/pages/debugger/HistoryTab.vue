<script setup lang="ts">
/**
 * HistoryTab — interaction history browsing (legacy parity with the old
 * Debugger.svelte history tab):
 *
 *   5-level cascade: Bot(botsStore) → Guild(getGuilds) → Channel(getChannels)
 *   → Member(searchMembers, 200+error special-case) → Date(tree items, desc).
 *
 * requestSeq guards out-of-order responses when the user clicks fast (same
 * pattern as the legacy page). prune / delete require confirmation; the raw
 * context is reconstructed via the context endpoint and shown in a modal.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDialog, useMessage } from 'naive-ui'
import {
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NModal,
  NSelect,
  NSpin,
} from 'naive-ui'

import {
  deleteInteraction,
  getInteractionContext,
  getInteractionMessages,
  getInteractionTree,
  getInteractionUsage,
  pruneInteractions,
  type InteractionMessage,
  type InteractionTreeItem,
  type InteractionUsage,
  type ReconstructedContext,
} from '@/api/interactions'
import {
  getChannels,
  getGuilds,
  searchMembers,
  type ChannelInfo,
  type GuildInfo,
  type MemberInfo,
} from '@/api/bots'
import { useBotsStore } from '@/stores/bots'

const props = defineProps<{
  /** Only fetch when the history tab is actually visible (legacy parity). */
  active: boolean
}>()

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()
const botsStore = useBotsStore()

// --- cascade state ---
const selectedBotId = ref<string | null>(null)
const selectedGuild = ref<string | null>(null)
const selectedChannel = ref<string | null>(null)
const selectedMember = ref<string | null>(null)
const selectedDate = ref<string | null>(null)

const guildList = ref<GuildInfo[]>([])
const guildListLoading = ref(false)
const channelList = ref<ChannelInfo[]>([])
const channelListLoading = ref(false)
const memberList = ref<MemberInfo[]>([])
const memberListLoading = ref(false)
const memberSearchError = ref('')

const treeItems = ref<InteractionTreeItem[]>([])
const treeLoading = ref(false)
const messages = ref<InteractionMessage[]>([])
const messagesLoading = ref(false)
const usage = ref<InteractionUsage>({ used_bytes: 0, max_bytes: 524288000, percent: 0 })

const rawContext = ref<ReconstructedContext | null>(null)
const rawContextLoading = ref(false)
const rawContextError = ref('')
const rawContextVisible = ref(false)

let requestSeq = 0

const botOptions = computed(() =>
  botsStore.bots.map((b) => ({ label: b.bot_name || b.bot_id, value: b.bot_id })),
)
const guildOptions = computed(() => guildList.value.map((g) => ({ label: g.name, value: g.id })))
const channelOptions = computed(() =>
  channelList.value.map((c) => ({ label: `#${c.name}`, value: c.id })),
)
const memberOptions = computed(() =>
  memberList.value.map((m) => ({ label: m.display_name || m.username, value: m.id })),
)

// Date options: unique dates from the tree, descending (legacy parity).
const dateStrings = computed(() =>
  [...new Set(treeItems.value.map((item) => item.date))].sort().reverse(),
)
const dateOptions = computed(() => dateStrings.value.map((d) => ({ label: d, value: d })))

async function loadGuilds(seq: number): Promise<void> {
  if (!selectedBotId.value) return
  guildListLoading.value = true
  try {
    const data = await getGuilds(selectedBotId.value)
    if (seq !== requestSeq) return
    guildList.value = data.guilds || []
  } catch {
    if (seq !== requestSeq) return
    guildList.value = []
  } finally {
    if (seq === requestSeq) guildListLoading.value = false
  }
}

async function loadChannels(seq: number): Promise<void> {
  if (!selectedBotId.value || !selectedGuild.value) return
  channelListLoading.value = true
  try {
    const data = await getChannels(selectedBotId.value, selectedGuild.value)
    if (seq !== requestSeq) return
    channelList.value = data.channels || []
  } catch {
    if (seq !== requestSeq) return
    channelList.value = []
  } finally {
    if (seq === requestSeq) channelListLoading.value = false
  }
}

async function loadMembers(seq: number): Promise<void> {
  if (!selectedBotId.value || !selectedGuild.value) return
  memberListLoading.value = true
  memberSearchError.value = ''
  try {
    const data = await searchMembers(selectedBotId.value, selectedGuild.value, '', 5000)
    if (seq !== requestSeq) return
    if (data.error) {
      // 200 + error special-case (rate_limited / api_error / search_timeout).
      memberSearchError.value = data.message || data.error
      memberList.value = []
    } else {
      memberList.value = data.members || []
    }
  } catch (err) {
    if (seq !== requestSeq) return
    memberSearchError.value = err instanceof Error ? err.message : String(err)
    memberList.value = []
  } finally {
    if (seq === requestSeq) memberListLoading.value = false
  }
}

async function loadInteractionTree(seq: number): Promise<void> {
  if (!selectedBotId.value) return
  treeLoading.value = true
  try {
    const filters: { guild_id?: string; channel_id?: string; member_id?: string } = {}
    if (selectedGuild.value) filters.guild_id = selectedGuild.value
    if (selectedChannel.value) filters.channel_id = selectedChannel.value
    if (selectedMember.value) filters.member_id = selectedMember.value
    const data = await getInteractionTree(selectedBotId.value, filters)
    if (seq !== requestSeq) return
    treeItems.value = data.items || []
  } catch {
    if (seq !== requestSeq) return
    treeItems.value = []
  } finally {
    if (seq === requestSeq) treeLoading.value = false
  }
}

async function loadMessages(seq: number): Promise<void> {
  if (
    !selectedBotId.value || !selectedGuild.value || !selectedChannel.value ||
    !selectedMember.value || !selectedDate.value
  ) return
  if (seq !== requestSeq) return
  messagesLoading.value = true
  try {
    const tree = await getInteractionTree(selectedBotId.value, {
      guild_id: selectedGuild.value,
      channel_id: selectedChannel.value,
      member_id: selectedMember.value,
    })
    if (seq !== requestSeq) return
    const items = tree.items || []
    if (items.length > 0) {
      const item = items[0]
      const data = await getInteractionMessages(
        selectedBotId.value,
        selectedGuild.value,
        item.role_id,
        selectedChannel.value,
        selectedMember.value,
        selectedDate.value,
      )
      if (seq !== requestSeq) return
      messages.value = data.messages || []
    } else {
      messages.value = []
    }
  } catch {
    if (seq !== requestSeq) return
    messages.value = []
  } finally {
    if (seq === requestSeq) messagesLoading.value = false
  }
}

async function loadUsage(seq: number): Promise<void> {
  if (!selectedBotId.value) return
  try {
    const data = await getInteractionUsage(selectedBotId.value)
    if (seq !== requestSeq) return
    usage.value = data
  } catch {
    // ignore — usage bar stays at defaults
  }
}

async function handleShowRawContext(): Promise<void> {
  if (!selectedBotId.value || !selectedGuild.value || !selectedChannel.value ||
      !selectedMember.value || !selectedDate.value) return
  const seq = ++requestSeq
  rawContextLoading.value = true
  rawContextError.value = ''
  rawContext.value = null
  rawContextVisible.value = true
  try {
    const tree = await getInteractionTree(selectedBotId.value, {
      guild_id: selectedGuild.value,
      channel_id: selectedChannel.value,
      member_id: selectedMember.value,
    })
    if (seq !== requestSeq) return
    const items = tree.items || []
    const roleId = items.length > 0 ? items[0].role_id : 'default'
    rawContext.value = await getInteractionContext(
      selectedBotId.value,
      selectedGuild.value,
      roleId,
      selectedChannel.value,
      selectedMember.value,
      selectedDate.value,
    )
  } catch (err) {
    if (seq !== requestSeq) return
    rawContextError.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (seq === requestSeq) rawContextLoading.value = false
  }
}

async function handleDeleteRecords(): Promise<void> {
  if (!selectedBotId.value) return
  dialog.warning({
    title: t('debugger.confirmDelete'),
    content: '',
    positiveText: t('debugger.deleteSelected'),
    negativeText: t('importExport.cancel'),
    onPositiveClick: async () => {
      try {
        const filters: Record<string, string> = {}
        if (selectedGuild.value) filters.guild_id = selectedGuild.value
        if (selectedChannel.value) filters.channel_id = selectedChannel.value
        if (selectedMember.value) filters.member_id = selectedMember.value
        if (selectedDate.value) filters.date = selectedDate.value
        await deleteInteraction(selectedBotId.value!, filters)
        message.success(t('debugger.deleted'))
        const seq = ++requestSeq
        await loadInteractionTree(seq)
        await loadUsage(seq)
        messages.value = []
      } catch (err) {
        message.error(
          t('debugger.deleteFailed', {
            error: err instanceof Error ? err.message : String(err),
          }),
        )
      }
    },
  })
}

async function handlePrune(): Promise<void> {
  if (!selectedBotId.value) return
  dialog.warning({
    title: t('debugger.prune'),
    content: '',
    positiveText: t('debugger.prune'),
    negativeText: t('importExport.cancel'),
    onPositiveClick: async () => {
      try {
        await pruneInteractions(selectedBotId.value!)
        message.success(t('debugger.pruned'))
        const seq = ++requestSeq
        await loadInteractionTree(seq)
        await loadUsage(seq)
      } catch (err) {
        message.error(
          t('debugger.pruneFailed', {
            error: err instanceof Error ? err.message : String(err),
          }),
        )
      }
    },
  })
}

function resetHistoryFilters(): void {
  selectedGuild.value = null
  selectedChannel.value = null
  selectedMember.value = null
  selectedDate.value = null
  channelList.value = []
  memberList.value = []
  treeItems.value = []
  messages.value = []
}

function onBotChange(): void {
  resetHistoryFilters()
  const seq = ++requestSeq
  guildList.value = []
  loadGuilds(seq)
}

function onGuildChange(): void {
  selectedChannel.value = null
  selectedMember.value = null
  selectedDate.value = null
  messages.value = []
  treeItems.value = []
  const seq = ++requestSeq
  loadChannels(seq)
  loadMembers(seq)
}

function onChannelChange(): void {
  selectedMember.value = null
  selectedDate.value = null
  messages.value = []
  const seq = ++requestSeq
  loadInteractionTree(seq)
}

function onMemberChange(): void {
  selectedDate.value = null
  messages.value = []
  const seq = ++requestSeq
  loadInteractionTree(seq)
}

// Legacy parity: fetch the tree only when the history tab is visible.
watch(
  () => props.active,
  (active) => {
    if (active && selectedBotId.value && selectedGuild.value) {
      const seq = ++requestSeq
      loadInteractionTree(seq)
      loadUsage(seq)
    }
  },
)

// Full 5-level selection → messages.
watch(
  [selectedChannel, selectedMember, selectedDate],
  ([channel, member, date]) => {
    if (channel && member && date) {
      const seq = ++requestSeq
      loadMessages(seq)
    }
  },
)

// Bot defaults to the sidebar selection when the tab first opens.
watch(
  () => botsStore.selectedBotId,
  (botId) => {
    if (botId && !selectedBotId.value) {
      selectedBotId.value = botId
      const seq = ++requestSeq
      loadGuilds(seq)
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="history-tab">
    <n-card :title="t('debugger.historyTitle')" size="small">
      <div class="ih-filters">
        <n-select
          v-model:value="selectedBotId"
          :options="botOptions"
          :placeholder="t('debugger.selectBot')"
          class="ih-filter"
          @update:value="onBotChange"
        />
        <n-select
          v-model:value="selectedGuild"
          :options="guildOptions"
          :placeholder="t('debugger.selectServer')"
          :loading="guildListLoading"
          :disabled="!selectedBotId"
          class="ih-filter"
          @update:value="onGuildChange"
        />
        <n-select
          v-model:value="selectedChannel"
          :options="channelOptions"
          :placeholder="t('debugger.selectChannel')"
          :loading="channelListLoading"
          :disabled="!selectedGuild"
          class="ih-filter"
          @update:value="onChannelChange"
        />
        <n-select
          v-model:value="selectedMember"
          :options="memberOptions"
          :placeholder="t('debugger.selectMember')"
          :loading="memberListLoading"
          :disabled="!selectedGuild"
          class="ih-filter"
          @update:value="onMemberChange"
        />
        <n-select
          v-model:value="selectedDate"
          :options="dateOptions"
          :placeholder="t('debugger.selectDate')"
          :disabled="!selectedMember"
          class="ih-filter"
        />
      </div>

      <n-alert v-if="memberSearchError" type="warning" class="ih-member-error">
        {{ memberSearchError }}
      </n-alert>

      <template v-if="selectedBotId">
        <div class="ih-usage-bar">
          <span>
            {{ t('debugger.storageUsage') }}:
            {{ Math.round((usage.used_bytes / 1024 / 1024) * 100) / 100 }}MB /
            {{ Math.round(usage.max_bytes / 1024 / 1024) }}MB ({{ usage.percent }}%)
          </span>
          <div class="ih-bar-track">
            <div class="ih-bar-fill" :style="{ width: `${Math.min(usage.percent, 100)}%` }" />
          </div>
          <n-button size="small" @click="handlePrune">{{ t('debugger.prune') }}</n-button>
          <n-button size="small" type="error" secondary @click="handleDeleteRecords">
            {{ t('debugger.deleteSelected') }}
          </n-button>
        </div>
      </template>
    </n-card>

    <n-spin :show="messagesLoading">
      <template v-if="messages.length > 0">
        <n-card :title="`${t('debugger.messagesFor')} ${selectedDate}`" size="small">
          <div class="ih-msg-actions">
            <n-button size="small" :loading="rawContextLoading" @click="handleShowRawContext">
              {{ rawContextLoading ? '...' : t('debugger.showRawContext') }}
            </n-button>
          </div>
          <div class="ih-messages">
            <div
              v-for="(msg, i) in messages"
              :key="msg.message_id || i"
              class="ih-msg"
              :class="{ 'ih-bot-msg': msg.is_bot_reply }"
            >
              <div class="ih-msg-meta">
                <span class="ih-msg-time">{{ msg.timestamp ? msg.timestamp.substring(11, 19) : '' }}</span>
                <span class="ih-msg-author">{{ msg.author_name }}</span>
                <span
                  v-if="msg.trigger_source && msg.trigger_source !== 'none'"
                  class="ih-msg-trigger"
                >
                  [{{ msg.trigger_source }}]
                </span>
              </div>
              <div class="ih-msg-content">{{ msg.content }}</div>
            </div>
          </div>
        </n-card>
      </template>
      <n-empty v-else-if="selectedDate" :description="t('debugger.noMessages')" />
    </n-spin>

    <!-- Raw context modal -->
    <n-modal
      v-model:show="rawContextVisible"
      preset="card"
      :title="t('debugger.rawContext')"
      class="ih-context-modal"
      style="width: 720px; max-width: 92vw;"
    >
      <n-spin :show="rawContextLoading">
        <template v-if="rawContext">
          <div class="ih-context-section">
            <h4>{{ t('debugger.systemPrompt') }}</h4>
            <pre class="ih-context-code">{{ rawContext.system_prompt }}</pre>
          </div>
          <div v-if="rawContext.messages && rawContext.messages.length" class="ih-context-section">
            <h4>{{ t('debugger.formattedMessages') }}</h4>
            <div v-for="(fm, i) in rawContext.messages" :key="i" class="ih-context-msg">
              <span class="ih-msg-author">{{ fm.author_name }}</span>
              <pre class="ih-context-code">{{ fm.formatted_content }}</pre>
            </div>
          </div>
        </template>
        <n-alert v-else-if="rawContextError" type="error">
          {{ t('debugger.contextError') }}: {{ rawContextError }}
        </n-alert>
      </n-spin>
    </n-modal>
  </div>
</template>

<style scoped>
.ih-filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.ih-filter {
  width: 180px;
}

.ih-member-error {
  margin-bottom: 10px;
}

.ih-usage-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-color-3);
  flex-wrap: wrap;
  padding: 6px 0;
}

.ih-bar-track {
  flex: 1;
  min-width: 120px;
  height: 8px;
  background: var(--fill-color);
  border-radius: 4px;
  overflow: hidden;
}

.ih-bar-fill {
  height: 100%;
  background: var(--primary-color);
  border-radius: 4px;
  transition: width 0.3s;
}

.ih-msg-actions {
  margin-bottom: 10px;
}

.ih-messages {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ih-msg {
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--fill-color);
  border-left: 3px solid var(--border-color);
}

.ih-bot-msg {
  border-left-color: var(--primary-color);
}

.ih-msg-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-color-3);
  margin-bottom: 4px;
}

.ih-msg-author {
  font-weight: 600;
  color: var(--text-color);
}

.ih-msg-trigger {
  color: var(--primary-color);
  font-size: 12px;
}

.ih-msg-content {
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
}

.ih-context-section {
  margin-bottom: 14px;
}

.ih-context-section h4 {
  font-size: 13px;
  margin: 0 0 6px;
}

.ih-context-code {
  margin: 0;
  padding: 10px;
  background: var(--log-shell-bg);
  color: var(--log-text-color);
  border-radius: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 240px;
  overflow-y: auto;
}

.ih-context-msg {
  margin-bottom: 8px;
}
</style>
