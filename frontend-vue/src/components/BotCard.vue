<script setup lang="ts">
/**
 * BotCard — sidebar bot entry: status dot, name, platform/model meta,
 * trigger keywords, hover action buttons (start/stop/restart/delete) and an
 * inline double-click rename state machine.
 */
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton,
  NIcon,
  NInput,
  useDialog,
  useMessage,
} from 'naive-ui'
import {
  PlayOutline,
  RefreshOutline,
  StopOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import type { BotSummary } from '@/api/bots'
import { useBotsStore } from '@/stores/bots'

const props = defineProps<{ bot: BotSummary; active: boolean }>()
const emit = defineEmits<{ select: [botId: string] }>()

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()
const botsStore = useBotsStore()

const BOT_ID_RE = /^[a-z0-9_-]+$/

/** Which button is currently running an operation on this card. */
const pendingAction = ref<'start' | 'stop' | 'restart' | 'delete' | null>(null)

/** Guards against stacking a second delete dialog while one is open. */
const deleteDialogOpen = ref(false)

// --- inline rename state machine (view ↔ editing) ---
const editing = ref(false)
const editValue = ref('')
const renaming = ref(false)
const renameError = ref('')
const editInputRef = ref<InstanceType<typeof NInput> | null>(null)

/** IME composition in progress (e.g. Chinese pinyin) — see onRenameBlur. */
const isComposing = ref(false)
/** A blur arrived mid-composition; commit once the composition ends. */
let blurDuringComposition = false

const operating = computed(() =>
  botsStore.operatingBotIds.includes(props.bot.bot_id),
)
const status = computed(() => props.bot.status)

const startDisabled = computed(
  () =>
    operating.value ||
    pendingAction.value !== null ||
    status.value === 'running' ||
    status.value === 'starting',
)
const stopDisabled = computed(
  () =>
    operating.value ||
    pendingAction.value !== null ||
    status.value === 'stopped' ||
    status.value === 'stopping',
)
const restartDisabled = computed(
  () =>
    operating.value ||
    pendingAction.value !== null ||
    status.value === 'stopped' ||
    status.value === 'stopping',
)
const deleteDisabled = computed(
  () => operating.value || pendingAction.value === 'delete',
)

const metaText = computed(() =>
  [props.bot.model_name, props.bot.llm_provider]
    .filter((v) => !!v)
    .join(' · '),
)

/**
 * Secondary info row text — nickname first (F8), falling back to the bot id
 * so the row always opens with a name-like label; then model · provider.
 */
const secondaryText = computed(() =>
  [props.bot.bot_nickname || props.bot.bot_id, metaText.value]
    .filter((v) => !!v)
    .join(' · '),
)

function errMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

async function runAction(
  action: 'start' | 'stop' | 'restart',
): Promise<void> {
  if (pendingAction.value) return
  pendingAction.value = action
  try {
    if (action === 'start') await botsStore.startBot(props.bot.bot_id)
    else if (action === 'stop') await botsStore.stopBot(props.bot.bot_id)
    else await botsStore.restartBot(props.bot.bot_id)
  } catch (err) {
    message.error(errMessage(err))
  } finally {
    pendingAction.value = null
  }
}

function confirmDelete(): void {
  if (pendingAction.value || deleteDialogOpen.value || editing.value) return
  deleteDialogOpen.value = true
  dialog.warning({
    title: t('botManager.title'),
    content: t('botManager.deleteConfirm', { botId: props.bot.bot_id }),
    positiveText: t('actionBtn.delete'),
    negativeText: t('botManager.cancel'),
    // Reset the guard on every close path (confirm / cancel / mask / Esc).
    onAfterLeave: () => {
      deleteDialogOpen.value = false
    },
    onPositiveClick: async () => {
      pendingAction.value = 'delete'
      try {
        await botsStore.deleteBot(props.bot.bot_id)
        return true
      } catch (err) {
        message.error(errMessage(err))
        // Keep the dialog open on failure so the user can retry (naive-ui
        // hides the dialog unless the handler resolves `false`).
        return false
      } finally {
        pendingAction.value = null
      }
    },
  })
}

// --- rename ---
function startEdit(): void {
  // NEW-8: mutual exclusion — the delete dialog must not open rename, and a
  // pending delete must not be interrupted by entering the edit state.
  if (deleteDialogOpen.value || pendingAction.value === 'delete') return
  editing.value = true
  editValue.value = props.bot.bot_id
  renameError.value = ''
  void nextTick(() => {
    editInputRef.value?.focus()
    editInputRef.value?.select()
  })
}

function cancelRename(): void {
  editing.value = false
  renameError.value = ''
}

/** Enter commits, Escape cancels; IME composition (e.g. Chinese) is ignored. */
function onRenameKeydown(e: KeyboardEvent): void {
  if (e.isComposing) return
  if (e.key === 'Enter') {
    e.preventDefault()
    void commitRename()
  } else if (e.key === 'Escape') {
    cancelRename()
  }
}

/**
 * NEW-3: blur must not commit half-composed IME text. While a composition is
 * active the commit is deferred to compositionend (the input already lost
 * focus, so the composition event may fire before or after blur — both
 * orders are handled); the full text is committed once composition ends.
 */
function onCompositionStart(): void {
  isComposing.value = true
}

function onCompositionEnd(): void {
  isComposing.value = false
  if (blurDuringComposition) {
    blurDuringComposition = false
    void commitRename()
  }
}

function onRenameBlur(): void {
  if (isComposing.value) {
    blurDuringComposition = true
    return
  }
  void commitRename()
}

/**
 * Keyboard activation (F11): Enter and Space both select the card — Space
 * with preventDefault so the page does not scroll. While the rename input is
 * editing, keys bubble up from it and must stay owned by the input (Enter
 * commits, Space types); the guard returns before touching the event.
 */
function onCardKeydown(e: KeyboardEvent): void {
  if (editing.value) return
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    emit('select', props.bot.bot_id)
  }
}

async function commitRename(): Promise<void> {
  if (!editing.value || renaming.value) return
  const newId = editValue.value.trim()
  if (!newId || newId === props.bot.bot_id) {
    cancelRename()
    return
  }
  if (!BOT_ID_RE.test(newId)) {
    renameError.value = t('sidebar.renameError')
    return
  }
  renaming.value = true
  renameError.value = ''
  try {
    await botsStore.renameBot(props.bot.bot_id, newId)
    editing.value = false
  } catch (err) {
    // Keep editing so the user can fix the value.
    renameError.value = errMessage(err)
  } finally {
    renaming.value = false
  }
}
</script>

<template>
  <div
    class="bot-card"
    :class="{ active, operating }"
    role="button"
    tabindex="0"
    @click="emit('select', bot.bot_id)"
    @keydown="onCardKeydown"
  >
    <div class="card-actions" @click.stop>
      <n-button
        size="tiny"
        quaternary
        :disabled="startDisabled"
        :loading="pendingAction === 'start'"
        @click="runAction('start')"
      >
        <template #icon>
          <n-icon><PlayOutline /></n-icon>
        </template>
        {{ t('actionBtn.start') }}
      </n-button>
      <n-button
        size="tiny"
        quaternary
        :disabled="stopDisabled"
        :loading="pendingAction === 'stop'"
        @click="runAction('stop')"
      >
        <template #icon>
          <n-icon><StopOutline /></n-icon>
        </template>
        {{ t('actionBtn.stop') }}
      </n-button>
      <n-button
        size="tiny"
        quaternary
        :disabled="restartDisabled"
        :loading="pendingAction === 'restart'"
        @click="runAction('restart')"
      >
        <template #icon>
          <n-icon><RefreshOutline /></n-icon>
        </template>
        {{ t('actionBtn.restart') }}
      </n-button>
      <n-button
        size="tiny"
        quaternary
        :disabled="deleteDisabled"
        :loading="pendingAction === 'delete'"
        @click="confirmDelete"
      >
        <template #icon>
          <n-icon><TrashOutline /></n-icon>
        </template>
        {{ t('actionBtn.delete') }}
      </n-button>
    </div>

    <div class="card-row card-row-main">
      <span class="status-dot" :class="status"></span>
      <span class="bot-name">{{ bot.bot_name || bot.bot_id }}</span>
      <span v-if="bot.enabled === false" class="disabled-badge">
        {{ t('sidebar.disabled') }}
      </span>
    </div>

    <div class="card-row card-row-id">
      <template v-if="editing">
        <div class="rename-edit-row">
          <n-input
            ref="editInputRef"
            v-model:value="editValue"
            size="tiny"
            class="rename-input"
            :disabled="renaming"
            @click.stop
            @dblclick.stop
            @compositionstart="onCompositionStart"
            @compositionend="onCompositionEnd"
            @keydown="onRenameKeydown"
            @blur="onRenameBlur"
          />
          <button
            type="button"
            class="rename-btn rename-btn-confirm"
            :disabled="renaming"
            :title="t('sidebar.saveTitle')"
            @mousedown.prevent
            @click.stop="() => void commitRename()"
          >✓</button>
          <button
            type="button"
            class="rename-btn rename-btn-cancel"
            :disabled="renaming"
            :title="t('sidebar.cancelTitle')"
            @mousedown.prevent
            @click.stop="cancelRename"
          >×</button>
        </div>
        <span v-if="renameError" class="rename-error">{{ renameError }}</span>
      </template>
      <span
        v-else
        class="card-id"
        :title="t('sidebar.renameTitle')"
        @dblclick.stop="startEdit"
      >{{ bot.bot_id }}</span>
    </div>

    <div class="card-row card-row-meta">
      <span class="platform-badge" :class="bot.platform === 'qq' ? 'qq' : 'discord'">
        {{ bot.platform }}
      </span>
      <span v-if="secondaryText" class="card-meta">{{ secondaryText }}</span>
    </div>

    <div v-if="bot.trigger_keywords && bot.trigger_keywords.length > 0" class="card-tags">
      <span
        v-for="kw in bot.trigger_keywords.slice(0, 4)"
        :key="kw"
        class="keyword-tag"
      >{{ kw }}</span>
      <span v-if="bot.trigger_keywords.length > 4" class="keyword-tag more">
        +{{ bot.trigger_keywords.length - 4 }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.bot-card {
  position: relative;
  padding: 8px 10px;
  margin: 4px 8px;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    opacity 0.2s ease;
}

.bot-card:hover {
  background: rgba(148, 163, 184, 0.12);
}

.bot-card.active {
  background: rgba(69, 163, 230, 0.16);
  border-color: var(--n-primary-color, #45a3e6);
}

.bot-card.operating {
  opacity: 0.75;
}

/* --- hover action buttons (top-right corner) --- */
.card-actions {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 2px;
  max-width: 55%;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.bot-card:hover .card-actions,
.bot-card:focus-visible .card-actions,
.bot-card.active .card-actions,
.bot-card.operating .card-actions {
  opacity: 1;
  pointer-events: auto;
}

/* --- rows --- */
.card-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.card-row-main {
  padding-right: clamp(12px, 4vw, 100px);
}

.card-row-id {
  margin-top: 2px;
  padding-right: clamp(12px, 4vw, 100px);
}

.card-row-meta {
  margin-top: 6px;
  gap: 8px;
}

/* --- status dot --- */
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.status-dot.running {
  background: var(--success-text);
  animation: dot-pulse 1.5s ease-in-out infinite;
}

.status-dot.starting {
  background: var(--primary-color);
  animation: dot-pulse 0.8s ease-in-out infinite;
}

@keyframes dot-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.45;
  }
}

/* --- name / badges --- */
.bot-name {
  font-weight: 600;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.disabled-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(255, 51, 102, 0.12);
  color: var(--log-error, #ff8bb4);
  font-weight: 600;
  flex-shrink: 0;
}

/* --- bot id + rename --- */
.card-id {
  font-size: 12px;
  font-family: var(--font-mono);
  opacity: 0.65;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: text;
}

.card-id:hover {
  opacity: 1;
  color: var(--n-primary-color, #45a3e6);
}

.rename-edit-row {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.rename-input {
  flex: 1;
  min-width: 0;
}

.rename-btn {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #94a3b8;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  transition:
    color 0.15s ease,
    background-color 0.15s ease;
}

.rename-btn:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.15);
}

.rename-btn-confirm:hover:not(:disabled) {
  color: var(--success-text);
}

.rename-btn-cancel:hover:not(:disabled) {
  color: #ff8bb4;
}

.rename-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.rename-error {
  font-size: 11px;
  color: var(--log-error, #ff8bb4);
}

/* --- platform / meta --- */
.platform-badge {
  font-size: 10px;
  text-transform: uppercase;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
  flex-shrink: 0;
}

.platform-badge.discord {
  background: rgba(88, 101, 242, 0.15);
  color: var(--sidebar-discord-text);
}

.platform-badge.qq {
  background: rgba(18, 183, 106, 0.15);
  color: var(--sidebar-qq-text);
}

.card-meta {
  font-size: 12px;
  opacity: 0.7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* --- trigger keywords --- */
.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.keyword-tag {
  font-size: 11px;
  background: rgba(148, 163, 184, 0.12);
  border-radius: 3px;
  padding: 1px 6px;
  line-height: 1.5;
  opacity: 0.85;
}

.keyword-tag.more {
  opacity: 0.6;
}
</style>
