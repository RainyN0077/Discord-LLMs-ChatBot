<script setup lang="ts">
/**
 * SimulateTab — debug simulation form + results.
 *
 * Legacy parity: user_id and channel_id required, guild_id and role_id
 * optional (role dropdown from config.role_based_config), message_content;
 * result renders 2 cards (generated system prompt / LLM response) plus the
 * active_directives_log list (defensively JSON-rendered).
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NButton, NCard, NInput, NSelect, NAlert, NEmpty } from 'naive-ui'

import { simulate, type DebugSimulateResult } from '@/api/debug'
import { useConfigsStore } from '@/stores/configs'

const props = defineProps<{
  botId: string
}>()

const { t } = useI18n()
const message = useMessage()
const configsStore = useConfigsStore()

const payload = ref({
  user_id: '',
  channel_id: '',
  guild_id: '',
  role_id: '',
  message_content: '',
})

const result = ref<DebugSimulateResult | null>(null)
const error = ref('')
const isSimulating = ref(false)

const roleOptions = computed(() =>
  Object.entries(configsStore.config?.role_based_config ?? {}).map(([id, cfg]) => ({
    label: cfg.title || id,
    value: id,
  })),
)

async function handleSimulate(): Promise<void> {
  if (!payload.value.user_id.trim() || !payload.value.channel_id.trim() || !payload.value.message_content.trim()) {
    message.error(t('debugger.errorIncomplete'))
    return
  }
  isSimulating.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await simulate({
      user_id: payload.value.user_id.trim(),
      channel_id: payload.value.channel_id.trim(),
      guild_id: payload.value.guild_id.trim() || null,
      role_id: payload.value.role_id || null,
      message_content: payload.value.message_content,
      bot_id: props.botId,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isSimulating.value = false
  }
}

/** Defensive rendering: entries may arrive as non-strings from older captures. */
function renderDirective(directive: string): string {
  return typeof directive === 'string' ? directive : JSON.stringify(directive)
}
</script>

<template>
  <div class="simulate-tab">
    <n-card :title="t('debugger.title')" size="small">
      <p class="simulate-info">{{ t('debugger.info') }}</p>
      <div class="simulate-grid">
        <label>{{ t('debugger.userId') }}</label>
        <n-input
          v-model:value="payload.user_id"
          :placeholder="t('debugger.userIdPlaceholder')"
        />

        <label>{{ t('debugger.roleId') }}</label>
        <n-select
          v-model:value="payload.role_id"
          :options="roleOptions"
          :placeholder="`-- ${t('debugger.roleId')} --`"
          clearable
        />

        <label>{{ t('debugger.channelId') }}</label>
        <n-input
          v-model:value="payload.channel_id"
          :placeholder="t('debugger.channelIdPlaceholder')"
        />

        <label>{{ t('debugger.guildId') }}</label>
        <n-input
          v-model:value="payload.guild_id"
          :placeholder="t('debugger.guildIdPlaceholder')"
        />
      </div>
      <div class="simulate-message">
        <label>{{ t('debugger.message') }}</label>
        <n-input
          v-model:value="payload.message_content"
          type="textarea"
          :placeholder="t('debugger.messagePlaceholder')"
          :autosize="{ minRows: 4, maxRows: 10 }"
        />
      </div>
      <n-button type="primary" class="simulate-run" :loading="isSimulating" @click="handleSimulate">
        {{ isSimulating ? t('debugger.simulating') : t('debugger.button') }}
      </n-button>

      <n-alert v-if="error" type="error" class="simulate-error">
        {{ t('debugger.error') }}{{ error }}
      </n-alert>
    </n-card>

    <template v-if="result">
      <n-card :title="t('debugger.generatedPrompt')" size="small">
        <pre class="simulate-result">{{ result.generated_system_prompt }}</pre>
      </n-card>
      <n-card :title="t('debugger.llmResponse')" size="small">
        <div class="simulate-result simulate-response">{{ result.llm_response }}</div>
      </n-card>
      <n-card :title="t('debugger.activeDirectives')" size="small">
        <template v-if="result.active_directives_log && result.active_directives_log.length">
          <ul class="simulate-directives">
            <li v-for="(directive, i) in result.active_directives_log" :key="i">
              {{ renderDirective(directive) }}
            </li>
          </ul>
        </template>
        <n-empty v-else :description="t('debugger.noMessages')" />
      </n-card>
    </template>
  </div>
</template>

<style scoped>
.simulate-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 860px;
}

.simulate-info {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-color-3);
}

.simulate-grid {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px 14px;
  align-items: center;
}

.simulate-grid label {
  font-size: 13px;
  font-weight: 500;
}

.simulate-message {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
}

.simulate-message label {
  font-size: 13px;
  font-weight: 500;
}

.simulate-run {
  margin-top: 14px;
}

.simulate-error {
  margin-top: 12px;
}

.simulate-result {
  margin: 0;
  padding: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
}

.simulate-response {
  font-family: inherit;
  white-space: normal;
}

.simulate-directives {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--text-color-2);
  line-height: 1.8;
}
</style>
