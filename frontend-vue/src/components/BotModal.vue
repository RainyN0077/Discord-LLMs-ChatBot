<script setup lang="ts">
/**
 * BotModal — create-bot dialog (7 fields, no enabled toggle).
 *
 * Validation is manual: bot_id is required and must match ^[a-z0-9_-]+$;
 * errors render inline (frontend validation or the backend's message).
 * The form is decoupled from the selected bot and resets on every open.
 */
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NButton, NForm, NFormItem, NInput, NModal, NSelect } from 'naive-ui'
import { LLM_PROVIDER_VALUES } from '@/pages/model-settings/providerDefaults'
import { useBotsStore } from '@/stores/bots'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ 'update:show': [value: boolean] }>()

const { t } = useI18n()
const botsStore = useBotsStore()

const BOT_ID_RE = /^[a-z0-9_-]+$/

const form = reactive({
  bot_id: '',
  bot_name: '',
  platform: 'discord' as 'discord' | 'qq',
  discord_token: '',
  llm_provider: 'openai',
  api_key: '',
  model_name: 'gpt-4o',
})

const creating = ref(false)
const error = ref('')

const providerOptions = computed(() =>
  LLM_PROVIDER_VALUES.map((value) => ({
    label: t(`llmProvider.providers.${value}`),
    value,
  })),
)

const platformOptions = [
  { label: 'Discord', value: 'discord' },
  { label: 'QQ', value: 'qq' },
]

function resetForm(): void {
  form.bot_id = ''
  form.bot_name = ''
  form.platform = 'discord'
  form.discord_token = ''
  form.llm_provider = 'openai'
  form.api_key = ''
  form.model_name = 'gpt-4o'
  error.value = ''
}

// Clean slate every time the modal opens.
watch(
  () => props.show,
  (visible) => {
    if (visible) resetForm()
  },
)

/** Enter submits; IME composition (e.g. Chinese) is ignored. */
function onBotIdKeydown(e: KeyboardEvent): void {
  if (e.isComposing) return
  if (e.key === 'Enter') {
    e.preventDefault()
    void handleCreate()
  }
}

async function handleCreate(): Promise<void> { if (creating.value) return
  error.value = ''
  const botId = form.bot_id.trim()
  if (!botId || !BOT_ID_RE.test(botId)) {
    error.value = t('sidebar.createIdError')
    return
  }
  creating.value = true
  try {
    const refreshed = await botsStore.createBot({
      bot_id: botId,
      bot_name: form.bot_name.trim() || botId,
      platform: form.platform,
      discord_token: form.discord_token,
      llm_provider: form.llm_provider,
      api_key: form.api_key,
      model_name: form.model_name.trim() || 'gpt-4o',
    })
    if (!refreshed) {
      // L3: the bot WAS created — closing silently would hide that the
      // sidebar list is stale; show the refresh failure and let the user
      // decide (cancel, or retry once the backend recovers).
      error.value = t('botManager.createRefreshFailed', {
        error: botsStore.error ?? '',
      })
      return
    }
    emit('update:show', false)
    resetForm()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <n-modal
    preset="card"
    :show="props.show"
    :title="t('botManager.createBot')"
    :style="{ width: '540px', maxWidth: '92vw' }"
    @update:show="emit('update:show', $event)"
  >
    <n-form label-placement="top" :show-feedback="false">
      <div class="modal-grid">
        <n-form-item :label="t('sidebar.botIdPlaceholder')">
          <n-input
            v-model:value="form.bot_id"
            :placeholder="t('sidebar.botIdPlaceholder')"
            @keydown="onBotIdKeydown"
          />
        </n-form-item>
        <n-form-item :label="t('configPanel.botName')">
          <n-input
            v-model:value="form.bot_name"
            :placeholder="t('sidebar.botNamePlaceholder')"
          />
        </n-form-item>
        <n-form-item :label="t('configPanel.platform')">
          <n-select v-model:value="form.platform" :options="platformOptions" />
        </n-form-item>
        <n-form-item :label="t('llmProvider.title')">
          <n-select v-model:value="form.llm_provider" :options="providerOptions" />
        </n-form-item>
        <n-form-item :label="t('globalConfig.token')">
          <n-input
            v-model:value="form.discord_token"
            type="password"
            show-password-on="click"
            :placeholder="t('sidebar.discordTokenPlaceholder')"
          />
        </n-form-item>
        <n-form-item :label="t('llmProvider.apiKey')">
          <n-input
            v-model:value="form.api_key"
            type="password"
            show-password-on="click"
            :placeholder="t('sidebar.llmApiKeyPlaceholder')"
          />
        </n-form-item>
        <n-form-item :label="t('defaultBehavior.modelName')" class="modal-grid-full">
          <n-input
            v-model:value="form.model_name"
            :placeholder="t('sidebar.modelNamePlaceholder')"
          />
        </n-form-item>
      </div>

      <n-alert v-if="error" type="error" class="modal-error">
        {{ error }}
      </n-alert>

      <div class="modal-actions">
        <n-button
          type="primary"
          :loading="creating"
          :disabled="creating"
          @click="handleCreate"
        >
          {{ creating ? t('botManager.creating') : t('botManager.createBot') }}
        </n-button>
        <n-button quaternary @click="emit('update:show', false)">
          {{ t('botManager.cancel') }}
        </n-button>
      </div>
    </n-form>
  </n-modal>
</template>

<style scoped>
.modal-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 16px;
}

.modal-grid-full {
  grid-column: 1 / -1;
}

.modal-error {
  margin-bottom: 16px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 4px;
}
</style>
