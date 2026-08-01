<script setup lang="ts">
/**
 * BlocklistTab — blocklist/whitelist rules (legacy parity with the old
 * UserOptions.svelte blocklist tab):
 *
 * - global enabled toggle + member_search_timeout_ms
 * - rule cards: scope editor (global/guild+refresh+diagnostics/manual ID /
 *   channel / dm), mode segmented, whitelist_behavior segmented
 * - users: add/edit/remove, blacklist_mode radio, negative_portrait
 * - member search (Enter/button) with the 200+error three-state special-case
 * - diagnostics modal (online / guild_count / intents / warnings)
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NAlert, NButton, NCard, NInput, NInputNumber, NModal, NSwitch, NTag } from 'naive-ui'

import {
  getChannels,
  getDiagnostics,
  getGuilds,
  searchMembers,
  type BotDiagnostics,
  type ChannelInfo,
  type GuildInfo,
  type MemberInfo,
} from '@/api/bots'
import type { ScopeUserRule, UserBlocklistEntry, UserOptionsConfig } from '@/api/config'
import { makeKey } from './scopeKeys'

const props = defineProps<{
  botId: string
  userOptions: UserOptionsConfig
}>()

const { t } = useI18n()
const message = useMessage()

// --- guild / channel lists ---
const guildList = ref<GuildInfo[]>([])
const guildListLoaded = ref(false)
const isRefreshingGuilds = ref(false)
const channelListCache = reactive<Record<string, ChannelInfo[]>>({})

/** Resolved scope names keyed by makeKey(scopeType, scopeId), e.g. '*' or 'guild:123'. */
const scopeNameCache = reactive<Record<string, string>>({})

function cacheGuildNames(guilds: GuildInfo[]): void {
  for (const g of guilds) scopeNameCache[makeKey('guild', g.id)] = g.name
}

function cacheChannelNames(channels: ChannelInfo[]): void {
  for (const c of channels) scopeNameCache[makeKey('channel', c.id)] = c.name
}

// --- per-rule transient state (keyed by rule key) ---
interface RuleSearchState {
  input: string
  results: MemberInfo[]
  error: string
  searching: boolean
}
const memberSearch = reactive<Record<string, RuleSearchState>>({})

interface ManualGuildState {
  input: string
  resolving: boolean
}
const manualGuild = reactive<Record<string, ManualGuildState>>({})

// --- diagnostics modal ---
const showDiagnostics = ref(false)
const diagnosticsData = ref<BotDiagnostics | null>(null)
const diagnosticsLoading = ref(false)

const ruleKeys = computed(() => Object.keys(props.userOptions.rules ?? {}))

function ensureRuleState(key: string): void {
  if (!memberSearch[key]) {
    memberSearch[key] = { input: '', results: [], error: '', searching: false }
  }
  if (!manualGuild[key]) {
    manualGuild[key] = { input: '', resolving: false }
  }
}

function updateRule(key: string, patch: Partial<ScopeUserRule>): void {
  const rule = props.userOptions.rules[key]
  if (!rule) return
  // Scope change → member search results from the previous scope are stale;
  // clear them so they can never leak across scopes.
  if (patch.scope_type !== undefined || patch.scope_id !== undefined) {
    const searchState = memberSearch[key]
    if (searchState) {
      searchState.results = []
      searchState.error = ''
    }
  }
  props.userOptions.rules = { ...props.userOptions.rules, [key]: { ...rule, ...patch } }
}

function addRule(): void {
  const key = `rule-${Date.now()}`
  props.userOptions.rules = {
    ...(props.userOptions.rules ?? {}),
    [key]: {
      scope_type: 'global',
      scope_id: '',
      mode: 'blacklist',
      whitelist_behavior: 'triggers_only',
      users: {},
    },
  }
}

function removeRule(key: string): void {
  const next = { ...props.userOptions.rules }
  delete next[key]
  props.userOptions.rules = next
}

function addUserToRule(ruleKey: string): void {
  const rule = props.userOptions.rules[ruleKey]
  if (!rule) return
  const uid = `u-${Date.now()}`
  const users = { ...(rule.users || {}) }
  users[uid] = {
    user_id: '',
    user_display_name: '',
    blacklist_mode: 'deny_response',
    negative_portrait: '',
  }
  updateRule(ruleKey, { users })
}

function removeUserFromRule(ruleKey: string, userKey: string): void {
  const rule = props.userOptions.rules[ruleKey]
  if (!rule) return
  const users = { ...rule.users }
  delete users[userKey]
  updateRule(ruleKey, { users })
}

function updateUserField(
  ruleKey: string,
  userKey: string,
  field: keyof UserBlocklistEntry,
  value: string,
): void {
  const rule = props.userOptions.rules[ruleKey]
  const user = rule?.users?.[userKey]
  if (!rule || !user) return
  const users = { ...rule.users, [userKey]: { ...user, [field]: value } }
  updateRule(ruleKey, { users })
}

async function loadGuildList(): Promise<void> {
  if (!props.botId || guildListLoaded.value) return
  try {
    const data = await getGuilds(props.botId)
    guildList.value = data.guilds || []
    cacheGuildNames(guildList.value)
    guildListLoaded.value = true
  } catch {
    guildList.value = []
    guildListLoaded.value = true
  }
}

onMounted(loadGuildList)

async function refreshGuilds(): Promise<void> {
  guildList.value = []
  guildListLoaded.value = false
  isRefreshingGuilds.value = true
  await loadGuildList()
  isRefreshingGuilds.value = false
  message.success(t('userOptions.guildListRefreshed'))
}

async function loadChannelsForGuild(guildId: string): Promise<void> {
  if (!guildId || !props.botId) return
  if (channelListCache[guildId]) return
  try {
    const data = await getChannels(props.botId, guildId)
    channelListCache[guildId] = data.channels || []
    cacheChannelNames(channelListCache[guildId])
  } catch {
    channelListCache[guildId] = []
  }
}

async function handleMemberSearch(ruleKey: string, guildId: string): Promise<void> {
  ensureRuleState(ruleKey)
  const state = memberSearch[ruleKey]
  const query = state.input.trim()
  if (!props.botId || !guildId || !query) return
  state.searching = true
  state.error = ''
  state.results = []
  try {
    const data = await searchMembers(
      props.botId,
      guildId,
      query,
      props.userOptions.member_search_timeout_ms || 5000,
    )
    // 200 + error special-case (rate_limited / api_error / search_timeout).
    if (data.error) {
      state.error = data.message || data.error
    } else {
      state.results = data.members || []
      if (state.results.length === 0) {
        state.error = t('userOptions.blocklist.noMembersFound')
      }
    }
  } catch (err) {
    state.error = err instanceof Error ? err.message : String(err)
  } finally {
    state.searching = false
  }
}

function selectSearchedMember(ruleKey: string, member: MemberInfo): void {
  const rule = props.userOptions.rules[ruleKey]
  if (!rule) return
  const uid = `u-${Date.now()}`
  const users = { ...(rule.users || {}) }
  users[uid] = {
    user_id: member.id,
    user_display_name: member.display_name || member.username,
    blacklist_mode: 'deny_response',
    negative_portrait: '',
  }
  updateRule(ruleKey, { users })
  const state = memberSearch[ruleKey]
  state.input = ''
  state.results = []
}

async function resolveManualGuild(ruleKey: string): Promise<void> {
  const gid = manualGuild[ruleKey]?.input?.trim()
  if (!gid || !props.botId) return
  manualGuild[ruleKey].resolving = true
  try {
    const data = await getGuilds(props.botId)
    guildList.value = data.guilds || []
    cacheGuildNames(guildList.value)
    guildListLoaded.value = true
    const match = guildList.value.find((g) => g.id === gid || g.name === gid)
    if (match) {
      updateRule(ruleKey, { scope_id: match.id })
      await loadChannelsForGuild(match.id)
      message.success(t('userOptions.guildResolved', { name: match.name }))
    } else {
      message.error(t('userOptions.guildNotFound', { id: gid }))
    }
  } catch (err) {
    message.error(
      t('userOptions.guildResolveFailed', {
        error: err instanceof Error ? err.message : String(err),
      }),
    )
  } finally {
    manualGuild[ruleKey].resolving = false
  }
}

async function loadDiagnostics(): Promise<void> {
  if (!props.botId) return
  diagnosticsLoading.value = true
  try {
    diagnosticsData.value = await getDiagnostics(props.botId)
    showDiagnostics.value = true
  } catch (err) {
    message.error(
      t('userOptions.diagnosticsFailed', {
        error: err instanceof Error ? err.message : String(err),
      }),
    )
  } finally {
    diagnosticsLoading.value = false
  }
}

function scopeDisplayName(scopeType: string): string {
  if (scopeType === 'global') return t('userOptions.scopeGlobal')
  if (scopeType === 'guild') return t('userOptions.scopeGuild')
  if (scopeType === 'channel') return t('userOptions.scopeChannel')
  return t('userOptions.scopeDm', { id: '' })
}

function resolveScopeDetail(scopeType: string, scopeId?: string): string {
  if (!scopeId) return ''
  if (scopeType === 'guild') return scopeNameCache[makeKey('guild', scopeId)] || scopeId
  if (scopeType === 'channel') return `#${scopeNameCache[makeKey('channel', scopeId)] || scopeId}`
  if (scopeType === 'dm') return `@${scopeId}`
  return scopeId
}
</script>

<template>
  <div class="blocklist-tab">
    <n-card :title="t('userOptions.blocklist.title')" size="small">
      <p class="blocklist-info">{{ t('userOptions.blocklist.info') }}</p>
      <div class="blocklist-top">
        <n-switch
          :value="userOptions.enabled"
          @update:value="(v: boolean) => (userOptions.enabled = v)"
        />
        <span class="blocklist-enable-label">{{ t('userOptions.blocklist.enable') }}</span>
        <span class="blocklist-timeout-label">{{ t('userOptions.blocklist.memberSearchTimeout') }}</span>
        <n-input-number
          :value="userOptions.member_search_timeout_ms ?? 5000"
          :min="1000"
          :max="30000"
          :step="500"
          style="width: 110px"
          @update:value="(v: number | null) => (userOptions.member_search_timeout_ms = v ?? 5000)"
        />
        <span class="blocklist-unit">ms</span>
      </div>
    </n-card>

    <n-alert v-if="guildListLoaded && guildList.length === 0" type="warning" class="blocklist-warning">
      <span>⚠ {{ t('userOptions.blocklist.noGuildsWarning') }}</span>
      <n-button size="small" text type="primary" @click="loadDiagnostics">
        {{ t('userOptions.blocklist.diagnostics') }}
      </n-button>
    </n-alert>

    <n-card :title="t('userOptions.blocklist.rules')" size="small">
      <div class="blocklist-rules">
        <div
          v-for="(ruleKey, idx) in ruleKeys"
          :key="ruleKey"
          class="blocklist-rule"
          :class="userOptions.rules[ruleKey].mode === 'blacklist' ? 'rule-blacklist' : 'rule-whitelist'"
        >
          <div class="rule-topbar">
            <span class="rule-index">#{{ idx + 1 }}</span>
            <n-tag
              size="small"
              :type="userOptions.rules[ruleKey].scope_type === 'global' ? 'warning' : 'info'"
            >
              {{ scopeDisplayName(userOptions.rules[ruleKey].scope_type) }}
            </n-tag>
            <span
              v-if="userOptions.rules[ruleKey].scope_id"
              class="rule-scope-detail"
            >
              {{ resolveScopeDetail(userOptions.rules[ruleKey].scope_type, userOptions.rules[ruleKey].scope_id) }}
            </span>

            <div class="rule-spacer" />

            <div class="rule-mode-segmented">
              <n-button
                size="tiny"
                :type="userOptions.rules[ruleKey].mode === 'blacklist' ? 'error' : 'default'"
                :secondary="userOptions.rules[ruleKey].mode === 'blacklist'"
                @click="updateRule(ruleKey, { mode: 'blacklist' })"
              >
                {{ t('userOptions.blocklist.modeBlacklist') }}
              </n-button>
              <n-button
                size="tiny"
                :type="userOptions.rules[ruleKey].mode === 'whitelist' ? 'success' : 'default'"
                :secondary="userOptions.rules[ruleKey].mode === 'whitelist'"
                @click="updateRule(ruleKey, { mode: 'whitelist' })"
              >
                {{ t('userOptions.blocklist.modeWhitelist') }}
              </n-button>
            </div>

            <n-button size="tiny" type="error" secondary :title="t('userOptions.remove')" @click="removeRule(ruleKey)">
              ×
            </n-button>
          </div>

          <div class="rule-body">
            <template v-if="userOptions.rules[ruleKey].mode === 'whitelist'">
              <div class="rule-whitelist-row">
                <span class="rule-sub-label">{{ t('userOptions.blocklist.whitelistBehavior') }}:</span>
                <n-button
                  size="tiny"
                  :type="userOptions.rules[ruleKey].whitelist_behavior === 'triggers_only' ? 'primary' : 'default'"
                  @click="updateRule(ruleKey, { whitelist_behavior: 'triggers_only' })"
                >
                  {{ t('userOptions.blocklist.wlTriggersOnly') }}
                </n-button>
                <n-button
                  size="tiny"
                  :type="userOptions.rules[ruleKey].whitelist_behavior === 'messages_only' ? 'primary' : 'default'"
                  @click="updateRule(ruleKey, { whitelist_behavior: 'messages_only' })"
                >
                  {{ t('userOptions.blocklist.wlMessagesOnly') }}
                </n-button>
              </div>
            </template>

            <!-- Scope editor -->
            <div class="rule-scope-editor">
              <n-select
                :value="userOptions.rules[ruleKey].scope_type"
                :options="[
                  { label: t('userOptions.scopeGlobal'), value: 'global' },
                  { label: t('userOptions.scopeGuild'), value: 'guild' },
                  { label: t('userOptions.scopeChannel'), value: 'channel' },
                  { label: t('userOptions.scopeDm', { id: '' }), value: 'dm' },
                ]"
                class="rule-scope-type"
                @update:value="(v: string) => updateRule(ruleKey, { scope_type: v as ScopeUserRule['scope_type'] })"
              />

              <template v-if="userOptions.rules[ruleKey].scope_type === 'guild'">
                <n-select
                  :value="userOptions.rules[ruleKey].scope_id || null"
                  :options="guildList.map((g) => ({ label: g.name, value: g.id }))"
                  :placeholder="t('userOptions.blocklist.selectPlaceholder')"
                  class="rule-scope-id"
                  @update:value="(v: string) => updateRule(ruleKey, { scope_id: v })"
                />
                <n-button size="small" :loading="isRefreshingGuilds" :title="t('userOptions.blocklist.refreshGuilds')" @click="refreshGuilds">
                  ⟳
                </n-button>
                <n-button size="small" :loading="diagnosticsLoading" :title="t('userOptions.blocklist.diagnostics')" @click="loadDiagnostics">
                  ?
                </n-button>
                <div class="rule-manual-row">
                  <n-input
                    :value="manualGuild[ruleKey]?.input ?? ''"
                    :placeholder="t('userOptions.blocklist.manualGuildPlaceholder')"
                    size="small"
                    @update:value="(v: string) => { ensureRuleState(ruleKey); manualGuild[ruleKey].input = v }"
                    @keyup.enter="resolveManualGuild(ruleKey)"
                  />
                  <n-button
                    size="small"
                    :loading="manualGuild[ruleKey]?.resolving"
                    @click="resolveManualGuild(ruleKey)"
                  >
                    {{ t('userOptions.blocklist.resolve') }}
                  </n-button>
                </div>
              </template>

              <template v-else-if="userOptions.rules[ruleKey].scope_type === 'channel'">
                <n-select
                  :options="guildList.map((g) => ({ label: g.name, value: g.id }))"
                  :placeholder="t('userOptions.blocklist.selectPlaceholder')"
                  class="rule-scope-id"
                  @update:value="(v: string) => loadChannelsForGuild(v)"
                />
                <n-input
                  :value="userOptions.rules[ruleKey].scope_id"
                  :placeholder="t('userOptions.blocklist.channelIdPlaceholder')"
                  class="rule-scope-id"
                  @update:value="(v: string) => updateRule(ruleKey, { scope_id: v })"
                />
              </template>

              <template v-else-if="userOptions.rules[ruleKey].scope_type === 'dm'">
                <n-input
                  :value="userOptions.rules[ruleKey].scope_id"
                  :placeholder="t('userPortrait.userId')"
                  class="rule-scope-id"
                  @update:value="(v: string) => updateRule(ruleKey, { scope_id: v })"
                />
              </template>
            </div>
          </div>

          <!-- Users section -->
          <div class="rule-users">
            <div class="rule-users-header">
              <span>
                {{ t('userOptions.blocklist.users') }}
                <strong>{{ Object.keys(userOptions.rules[ruleKey].users || {}).length }}</strong>
              </span>
              <div v-if="userOptions.rules[ruleKey].scope_type === 'guild' && userOptions.rules[ruleKey].scope_id" class="rule-member-search">
                <n-input
                  :value="memberSearch[ruleKey]?.input ?? ''"
                  :placeholder="t('userOptions.blocklist.searchMembers')"
                  size="small"
                  style="width: 220px"
                  @update:value="(v: string) => { ensureRuleState(ruleKey); memberSearch[ruleKey].input = v }"
                  @keyup.enter="handleMemberSearch(ruleKey, userOptions.rules[ruleKey].scope_id)"
                />
                <n-button
                  size="small"
                  :loading="memberSearch[ruleKey]?.searching"
                  @click="handleMemberSearch(ruleKey, userOptions.rules[ruleKey].scope_id)"
                >
                  {{ t('userOptions.blocklist.search') }}
                </n-button>
              </div>
            </div>

            <n-alert
              v-if="memberSearch[ruleKey]?.error"
              type="warning"
              size="small"
              class="rule-search-error"
            >
              {{ memberSearch[ruleKey].error }}
            </n-alert>

            <div v-if="memberSearch[ruleKey]?.results?.length" class="rule-search-results">
              <n-button
                v-for="m in memberSearch[ruleKey].results"
                :key="m.id"
                size="small"
                quaternary
                class="rule-search-result"
                @click="selectSearchedMember(ruleKey, m)"
              >
                {{ m.display_name }} @{{ m.username }}
              </n-button>
            </div>

            <div class="rule-user-grid">
              <div
                v-for="userKey in Object.keys(userOptions.rules[ruleKey].users || {})"
                :key="userKey"
                class="rule-user-card"
              >
                <div class="rule-user-top">
                  <span class="rule-user-avatar">
                    {{ userOptions.rules[ruleKey].users[userKey].user_display_name?.[0] || '?' }}
                  </span>
                  <n-input
                    :value="userOptions.rules[ruleKey].users[userKey].user_id"
                    :placeholder="t('userPortrait.userId')"
                    size="small"
                    @update:value="(v: string) => updateUserField(ruleKey, userKey, 'user_id', v)"
                  />
                  <n-input
                    :value="userOptions.rules[ruleKey].users[userKey].user_display_name"
                    :placeholder="t('userOptions.blocklist.displayName')"
                    size="small"
                    @update:value="(v: string) => updateUserField(ruleKey, userKey, 'user_display_name', v)"
                  />
                  <n-button
                    size="tiny"
                    type="error"
                    secondary
                    :title="t('userOptions.remove')"
                    @click="removeUserFromRule(ruleKey, userKey)"
                  >
                    ×
                  </n-button>
                </div>
                <template v-if="userOptions.rules[ruleKey].mode === 'blacklist'">
                  <div class="rule-user-mode">
                    <n-button
                      size="tiny"
                      :type="userOptions.rules[ruleKey].users[userKey].blacklist_mode === 'deny_response' ? 'primary' : 'default'"
                      @click="updateUserField(ruleKey, userKey, 'blacklist_mode', 'deny_response')"
                    >
                      {{ t('userOptions.blocklist.denyResponse') }}
                    </n-button>
                    <n-button
                      size="tiny"
                      :type="userOptions.rules[ruleKey].users[userKey].blacklist_mode === 'block_messages' ? 'primary' : 'default'"
                      @click="updateUserField(ruleKey, userKey, 'blacklist_mode', 'block_messages')"
                    >
                      {{ t('userOptions.blocklist.blockMessages') }}
                    </n-button>
                    <n-button
                      size="tiny"
                      :type="userOptions.rules[ruleKey].users[userKey].blacklist_mode === 'negative_portrait' ? 'primary' : 'default'"
                      @click="updateUserField(ruleKey, userKey, 'blacklist_mode', 'negative_portrait')"
                    >
                      {{ t('userOptions.blocklist.negativePortrait') }}
                    </n-button>
                  </div>
                  <n-input
                    v-if="userOptions.rules[ruleKey].users[userKey].blacklist_mode === 'negative_portrait'"
                    v-model:value="userOptions.rules[ruleKey].users[userKey].negative_portrait"
                    type="textarea"
                    :placeholder="t('userOptions.blocklist.negativePortraitPlaceholder')"
                    size="small"
                  />
                </template>
              </div>
            </div>

            <n-button size="small" class="rule-add-user" @click="addUserToRule(ruleKey)">
              + {{ t('userOptions.blocklist.addUser') }}
            </n-button>
          </div>
        </div>
      </div>

      <n-button size="small" class="blocklist-add-rule" @click="addRule">
        + {{ t('userOptions.blocklist.addRule') }}
      </n-button>
    </n-card>

    <!-- Diagnostics modal -->
    <n-modal
      v-model:show="showDiagnostics"
      preset="card"
      :title="t('userOptions.blocklist.diagnosticsTitle')"
      style="width: 480px; max-width: 92vw;"
    >
      <template v-if="diagnosticsData">
        <div class="diag-row">
          <span class="diag-label">{{ t('userOptions.blocklist.diagOnline') }}</span>
          <n-tag :type="diagnosticsData.online ? 'success' : 'error'" size="small">
            {{ diagnosticsData.online ? t('userOptions.blocklist.diagYes') : t('userOptions.blocklist.diagNo') }}
          </n-tag>
        </div>
        <div class="diag-row">
          <span class="diag-label">{{ t('userOptions.blocklist.diagGuildCount') }}</span>
          <span>{{ diagnosticsData.guild_count }}</span>
        </div>
        <div v-for="(enabled, intent) in diagnosticsData.intents" :key="intent" class="diag-row">
          <span class="diag-label">Intent: {{ intent }}</span>
          <n-tag :type="enabled ? 'success' : 'error'" size="small">
            {{ enabled ? t('userOptions.blocklist.diagEnabled') : t('userOptions.blocklist.diagDisabled') }}
          </n-tag>
        </div>
        <div v-if="diagnosticsData.warnings && diagnosticsData.warnings.length" class="diag-warnings">
          <strong>{{ t('userOptions.blocklist.diagWarnings') }}:</strong>
          <p v-for="(w, i) in diagnosticsData.warnings" :key="i" class="diag-warning">⚠ {{ w }}</p>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.blocklist-info {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-color-3);
}

.blocklist-top {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.blocklist-enable-label {
  font-size: 13px;
}

.blocklist-timeout-label {
  font-size: 13px;
  color: var(--text-color-3);
  margin-left: 12px;
}

.blocklist-unit {
  font-size: 12px;
  color: var(--text-color-3);
}

.blocklist-warning {
  margin: 12px 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.blocklist-rules {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.blocklist-rule {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
}

.rule-blacklist {
  border-left: 4px solid #ef4444;
}

.rule-whitelist {
  border-left: 4px solid #22c55e;
}

.rule-topbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--fill-color);
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.rule-index {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-color-3);
}

.rule-scope-detail {
  font-size: 12px;
  color: var(--text-color-3);
  font-family: monospace;
}

.rule-spacer {
  flex: 1;
}

.rule-mode-segmented {
  display: flex;
  gap: 4px;
}

.rule-body {
  padding: 12px;
}

.rule-whitelist-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.rule-sub-label {
  font-size: 13px;
}

.rule-scope-editor {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.rule-scope-type {
  width: 140px;
}

.rule-scope-id {
  width: 220px;
}

.rule-manual-row {
  display: flex;
  gap: 6px;
  width: 100%;
  margin-top: 8px;
}

.rule-manual-row .n-input {
  flex: 1;
}

.rule-users {
  border-top: 1px dashed var(--border-color);
  padding: 12px;
}

.rule-users-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 13px;
  margin-bottom: 10px;
}

.rule-member-search {
  display: flex;
  gap: 6px;
  align-items: center;
}

.rule-search-error {
  margin-bottom: 8px;
}

.rule-search-results {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.rule-user-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rule-user-card {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rule-user-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rule-user-avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--primary-color);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}

.rule-user-mode {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.rule-add-user {
  margin-top: 10px;
}

.blocklist-add-rule {
  margin-top: 14px;
}

.diag-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
}

.diag-label {
  color: var(--text-color-3);
}

.diag-warnings {
  margin-top: 10px;
  border-top: 1px dashed var(--border-color);
  padding-top: 10px;
}

.diag-warning {
  font-size: 12px;
  color: var(--warning-color);
  margin: 4px 0;
}
</style>
