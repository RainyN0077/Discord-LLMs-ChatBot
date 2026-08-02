<script setup lang="ts">
/**
 * PlaygroundCard — stateless direct-LLM test conversation for the current
 * bot's provider/model (docs/full-implementation-design.md §2).
 *
 * Contract notes (design §2.2 / §2.4):
 *  - props carry only provider / modelName / botId from the page draft
 *    (no params prop — /api/chat/direct has no parameter slot; inference
 *    params are driven by the bot's SAVED config server-side)
 *  - single-turn requests: `[{ role: 'user', content }]`, always with
 *    include_system_prompt: true, debug_mode: false, bot_id
 *  - api_key never leaves the backend (read per bot_id server-side)
 *  - H2 guard: `watch(botId)` bumps pgSeq + clears the chat so an in-flight
 *    response from the old bot can never land in the new bot's session
 *  - four states: empty guide / sending (thinking bubble) / reply (usage
 *    line) / failure (error bubble with retry)
 *  - every message renders with plain-text interpolation only — no v-html
 *    (XSS double-guard on top of the backend's encode_output, §2.5)
 */
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NButton, NInput } from 'naive-ui'

import { sendDirectChat, type DirectChatUsage } from '@/api/chat'
import { PROVIDER_ERROR_PREFIX } from '@/api/client'
import SectionCard from '@/components/common/SectionCard.vue'

const props = withDefaults(
  defineProps<{
    provider: string
    modelName: string
    botId: string
    disabled?: boolean
  }>(),
  { disabled: false },
)

const { t } = useI18n()
const message = useMessage()

interface PlaygroundMessage {
  id: number
  role: 'user' | 'assistant' | 'error'
  text: string
  thinking?: boolean
}

const messages = ref<PlaygroundMessage[]>([])
const input = ref('')
const sending = ref(false)
const lastUsage = ref<{ p: number; c: number; t: number } | null>(null)

/**
 * H2 seq guard: bumped on every send AND on every bot switch. `sending`
 * already blocks same-bot concurrent sends; pgSeq exists to invalidate
 * responses that resolve after the user switched to another bot.
 */
let pgSeq = 0
let nextId = 1

const MAX_MESSAGES = 50

/**
 * sec-M1: client.ts's toApiError replaces 500 `LLM_PROVIDER_ERROR:` details
 * with the generic message below (raw detail goes to console only). This
 * component maps that normalized error onto the i18n providerError text —
 * the match prefix is the shared `PROVIDER_ERROR_PREFIX` exported by
 * client.ts (qa LOW-4: single source of truth, no duplicated strings).
 */

function clearChat(): void {
  messages.value = []
  lastUsage.value = null
}

/** Bot switch: invalidate in-flight responses, reset sending and drop the
 *  old session. `sending` must be reset here — the stale request's finally
 *  block skips its reset because its seq no longer matches pgSeq. */
watch(
  () => props.botId,
  () => {
    pgSeq++
    sending.value = false
    clearChat()
  },
)

function pushMessage(msg: Omit<PlaygroundMessage, 'id'>): PlaygroundMessage {
  const entry: PlaygroundMessage = { ...msg, id: nextId++ }
  messages.value.push(entry)
  if (messages.value.length > MAX_MESSAGES) {
    messages.value.splice(0, messages.value.length - MAX_MESSAGES)
  }
  return entry
}

function replaceMessage(id: number, patch: Partial<PlaygroundMessage>): void {
  const idx = messages.value.findIndex((m) => m.id === id)
  if (idx !== -1) {
    messages.value[idx] = { ...messages.value[idx], ...patch }
  }
}

/** Defensive usage read (design §12): supports input/output/total naming
 *  variants; `total` falls back to prompt + completion (LOW-16). */
function readUsage(usage: DirectChatUsage | null | undefined): {
  p: number
  c: number
  t: number
} {
  const u = (usage ?? {}) as unknown as Record<string, unknown>
  const num = (v: unknown): number =>
    typeof v === 'number' && Number.isFinite(v) ? v : 0
  const p = num(u.input_tokens ?? u.prompt_tokens ?? u.prompt)
  const c = num(u.output_tokens ?? u.completion_tokens ?? u.completion)
  const t = num(u.total_tokens ?? u.total) || p + c
  return { p, c, t }
}

function errorText(err: unknown): string {
  const detail = err instanceof Error ? err.message : String(err)
  const status = (err as { status?: unknown }).status
  if (status === 500 && detail.startsWith(PROVIDER_ERROR_PREFIX)) {
    return t('modelSettings.playground.providerError')
  }
  return detail
}

/** Shared send core (used by the send button and the retry button).
 *  `appendUser` is false on retry — the user message is already in the
 *  list and must not be duplicated. */
async function sendChatWith(text: string, appendUser = true): Promise<void> {
  if (sending.value || props.disabled) return
  if (!props.modelName) {
    message.error(t('modelSettings.playground.noModel'))
    return
  }
  const seq = ++pgSeq
  if (appendUser) pushMessage({ role: 'user', text })
  const thinkingMsg = pushMessage({
    role: 'assistant',
    text: t('modelSettings.playground.thinking'),
    thinking: true,
  })
  sending.value = true
  try {
    const resp = await sendDirectChat({
      messages: [{ role: 'user', content: text }],
      include_system_prompt: true,
      // debug_mode is omitted on purpose (D1): the backend defaults it to
      // false, which keeps the Playground on the non-debug path.
      bot_id: props.botId,
    })
    if (seq !== pgSeq) return
    replaceMessage(thinkingMsg.id, {
      role: 'assistant',
      text: resp.response,
      thinking: false,
    })
    // qa LOW-2: a null/empty usage means the backend reported no token
    // stats — leave lastUsage null so the usage line is not rendered as
    // 「输入 0 · 输出 0 · 总计 0」.
    const usage = resp.usage
    lastUsage.value =
      usage != null && Object.keys(usage).length > 0 ? readUsage(usage) : null
  } catch (err) {
    if (seq !== pgSeq) return
    replaceMessage(thinkingMsg.id, { role: 'error', text: errorText(err), thinking: false })
  } finally {
    if (seq === pgSeq) sending.value = false
  }
}

function handleSend(): void {
  const text = input.value.trim()
  if (!text) {
    message.warning(t('modelSettings.playground.emptyInput'))
    return
  }
  input.value = ''
  void sendChatWith(text)
}

/**
 * qa LOW-4: Enter while an IME composition is active (Chinese/Japanese
 * input confirming a candidate) must not send — `isComposing` guards it.
 */
function onKeydownEnter(e: KeyboardEvent): void {
  if (e.isComposing) return
  handleSend()
}

/** Retry reuses the last user message: drop everything after it, re-send
 *  without duplicating the user message. */
function handleRetry(): void {
  const lastUser = [...messages.value].reverse().find((m) => m.role === 'user')
  if (!lastUser) return
  const idx = messages.value.findIndex((m) => m.id === lastUser.id)
  messages.value = messages.value.slice(0, idx + 1)
  lastUsage.value = null
  void sendChatWith(lastUser.text, false)
}
</script>

<template>
  <SectionCard :title="t('modelSettings.playground.title')">
    <template #extra>
      <n-button
        size="small"
        quaternary
        class="pg-clear-btn"
        :disabled="messages.length === 0 || sending || disabled"
        @click="clearChat"
      >
        {{ t('modelSettings.playground.clear') }}
      </n-button>
    </template>

    <p class="pg-hint">{{ t('modelSettings.playground.hint') }}</p>

    <div v-if="messages.length === 0" class="pg-empty">
      {{ t('modelSettings.playground.empty') }}
    </div>

    <div v-else class="pg-messages">
      <div v-for="msg in messages" :key="msg.id" class="pg-message" :data-role="msg.role">
        <div
          class="pg-bubble"
          :class="[`pg-${msg.role}`, { 'pg-thinking': msg.thinking }]"
        >
          <template v-if="msg.thinking">
            {{ msg.text }}
          </template>
          <template v-else-if="msg.role === 'error'">
            <div class="pg-error-text">
              {{ t('modelSettings.playground.error', { error: msg.text }) }}
            </div>
            <n-button size="tiny" type="error" class="pg-retry-btn" @click="handleRetry">
              {{ t('modelSettings.playground.retry') }}
            </n-button>
          </template>
          <template v-else>
            {{ msg.text }}
          </template>
        </div>
      </div>
    </div>

    <div v-if="lastUsage" class="pg-usage" data-testid="pg-usage">
      {{
        t('modelSettings.playground.usage', {
          p: lastUsage.p,
          c: lastUsage.c,
          t: lastUsage.t,
        })
      }}
      <span v-if="provider || modelName" class="pg-usage-model">
        {{ provider }} / {{ modelName }}
      </span>
    </div>

    <div class="pg-input-row">
      <n-input
        v-model:value="input"
        type="textarea"
        :rows="2"
        class="pg-input"
        :placeholder="t('modelSettings.playground.placeholder')"
        :disabled="sending || disabled"
        @keydown.enter.exact.prevent="onKeydownEnter"
      />
      <n-button
        type="primary"
        class="pg-send-btn"
        :loading="sending"
        :disabled="sending || disabled"
        @click="handleSend"
      >
        {{ sending ? t('modelSettings.playground.sending') : t('modelSettings.playground.send') }}
      </n-button>
    </div>
  </SectionCard>
</template>

<style scoped>
.pg-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--text-color-3);
}

.pg-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--text-color-3);
  border: 1px dashed var(--border-color);
  border-radius: 8px;
  margin-bottom: 12px;
}

.pg-messages {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.pg-message {
  display: flex;
}

.pg-message[data-role='user'] {
  justify-content: flex-end;
}

.pg-message[data-role='assistant'],
.pg-message[data-role='error'] {
  justify-content: flex-start;
}

.pg-bubble {
  max-width: 80%;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
}

.pg-user {
  background: var(--primary-color);
  color: var(--primary-color-suppl, #fff);
}

.pg-assistant {
  background: var(--card-color, var(--log-shell-bg));
  border: 1px solid var(--border-color);
}

.pg-thinking {
  opacity: 0.6;
  font-style: italic;
}

.pg-error {
  background: var(--error-color);
  color: #fff;
}

.pg-error-text {
  margin-bottom: 6px;
}

.pg-usage {
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--text-color-3);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.pg-usage-model {
  font-family: 'Fira Code', 'Consolas', monospace;
}

.pg-input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.pg-input {
  flex: 1;
}
</style>
