<script setup lang="ts">
/**
 * ModelSettingsPage — full migration of the legacy ModelSettings.svelte
 * (4 cards: LLM provider / inference params / custom headers / custom
 * parameters). Route `/model-settings` is kept unchanged.
 *
 * State model: a page-local `draft` (deep copy of the loaded config). The
 * single "Save & Restart Bot" button is the ONLY path that writes the store:
 * draft → `configsStore.update(pick)` → `configsStore.save(botId)` (reuses
 * the 7-step save pipeline) → reload to rebuild the draft on success; on
 * failure the draft is preserved and the store error is shown.
 *
 * All async flows are seq-guarded (loadSeq / fetchSeq / testSeq) against
 * out-of-order landings.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NSpace, NSpin } from 'naive-ui'

import { useBotsStore } from '@/stores/bots'
import { useConfigsStore } from '@/stores/configs'
import { fetchModelList, testModel, type ModelTestResponse } from '@/api/models'
import type { BotConfig } from '@/api/config'
import EmptyState from '@/components/common/EmptyState.vue'
import LLMProviderCard from './model-settings/LLMProviderCard.vue'
import InferenceParamsCard from './model-settings/InferenceParamsCard.vue'
import CustomHeadersCard from './model-settings/CustomHeadersCard.vue'
import CustomParamsCard from './model-settings/CustomParamsCard.vue'
import PlaygroundCard from './model-settings/PlaygroundCard.vue'
import {
  KNOWN_PROVIDERS,
  LLM_PROVIDER_VALUES,
  PROVIDER_DEFAULTS,
  getProviderBaseUrl,
} from './model-settings/providerDefaults'

const { t } = useI18n()
const message = useMessage()
const route = useRoute()
const router = useRouter()
const botsStore = useBotsStore()
const configsStore = useConfigsStore()

const draft = ref<BotConfig | null>(null)
const availableModels = ref<string[]>([])
const useManualInput = ref(false)
const fetchingModels = ref(false)
const testing = ref(false)
const testResult = ref<ModelTestResponse | null>(null)
const saving = ref(false)

let loadSeq = 0
let fetchSeq = 0
let testSeq = 0

/**
 * The api_key value applied by the most recent loadConfig. Used to tell the
 * load-induced api_key watch fire apart from a genuine user edit (MED-2).
 */
let appliedApiKey: string | undefined

const selectedBot = computed(() => botsStore.selectedBot)

/** Three-state model selector: fetched list / single default / manual text. */
const modelMode = computed<'list' | 'default' | 'manual'>(() => {
  if (!useManualInput.value && availableModels.value.length > 0) return 'list'
  if (!useManualInput.value) {
    const defaults = draft.value ? PROVIDER_DEFAULTS[draft.value.llm_provider] : undefined
    if (defaults?.defaultModel) return 'default'
  }
  return 'manual'
})

// ---------------------------------------------------------------------------
// Load / three-state
// ---------------------------------------------------------------------------

watch(
  () => botsStore.selectedBotId,
  (botId) => {
    loadSeq++
    resetTransient()
    draft.value = null
    configsStore.reset()
    if (botId) void loadConfig(botId)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  loadSeq++
  configsStore.reset()
})

onMounted(() => {
  if (!botsStore.bots.length) void botsStore.fetchBotsList()
})

async function loadConfig(botId: string): Promise<void> {
  const seq = ++loadSeq
  await configsStore.load(botId)
  if (seq !== loadSeq) return
  const cfg = configsStore.config
  if (cfg) {
    appliedApiKey = cfg.api_key
    draft.value = JSON.parse(JSON.stringify(cfg)) as BotConfig
    applyQueryPreSelect()
  }
}

function handleRetry(): void {
  const botId = botsStore.selectedBotId
  if (botId) void loadConfig(botId)
}

/** Clear all fetch/test transient state (legacy page side effects). */
function resetTransient(): void {
  fetchSeq++
  testSeq++
  availableModels.value = []
  useManualInput.value = false
  fetchingModels.value = false
  testing.value = false
  testResult.value = null
}

// API key edits invalidate the fetched model list / test result (legacy).
// Loading the draft (draft transitions null → object) fires this watch once
// with oldKey === undefined and key === the value load just applied; that
// fire is skipped, otherwise resetTransient() bumps fetchSeq and silently
// discards the query pre-select's in-flight fetchModels response (MED-2).
watch(
  () => draft.value?.api_key,
  (key, oldKey) => {
    if (oldKey === undefined && key === appliedApiKey) return
    resetTransient()
  },
)

// ---------------------------------------------------------------------------
// Provider / base URL / model list / connection test
// ---------------------------------------------------------------------------

/**
 * Provider change side effects (shared by the select and the query
 * pre-select): fill the CN default base URL when empty, clear fetched
 * models / test result and auto-fetch the model list when an API key is set.
 */
function handleProviderChange(provider: string): void {
  const cfg = draft.value
  if (!cfg) return
  cfg.llm_provider = provider
  if (KNOWN_PROVIDERS.includes(provider)) {
    const defaults = PROVIDER_DEFAULTS[provider]
    if (defaults && !cfg.openai_base_url) {
      cfg.openai_base_url = defaults.baseUrl
    }
  }
  resetTransient()
  if (cfg.api_key) void fetchModels()
}

function handleUpdateBaseUrl(value: string): void {
  const cfg = draft.value
  if (!cfg) return
  if (cfg.llm_provider === 'grok') cfg.grok_base_url = value
  else if (cfg.llm_provider === 'anthropic') cfg.anthropic_base_url = value
  else cfg.openai_base_url = value
}

async function fetchModels(): Promise<void> {
  const cfg = draft.value
  if (!cfg) return
  if (!cfg.api_key) {
    message.error(t('llmProvider.noApiKey'))
    return
  }
  const seq = ++fetchSeq
  fetchingModels.value = true
  try {
    const result = await fetchModelList(
      cfg.llm_provider,
      cfg.api_key,
      getProviderBaseUrl(cfg),
      'chat',
    )
    if (seq !== fetchSeq) return
    availableModels.value = result.models || []
    useManualInput.value = false
    message.success(t('llmProvider.modelsLoaded'))
  } catch (err) {
    if (seq !== fetchSeq) return
    availableModels.value = []
    useManualInput.value = true
    message.error(
      t('llmProvider.modelsLoadFailed') +
        (err instanceof Error ? err.message : String(err)),
    )
  } finally {
    if (seq === fetchSeq) fetchingModels.value = false
  }
}

async function handleTestConnection(): Promise<void> {
  const cfg = draft.value
  if (!cfg) return
  if (!cfg.api_key) {
    message.error(t('llmProvider.noApiKey'))
    return
  }
  if (!cfg.model_name) {
    message.error(t('llmProvider.selectModelFirst'))
    return
  }
  const seq = ++testSeq
  testing.value = true
  testResult.value = null
  try {
    const result = await testModel(
      cfg.llm_provider,
      cfg.api_key,
      getProviderBaseUrl(cfg),
      cfg.model_name,
      'chat',
    )
    if (seq !== testSeq) return
    // Success is judged by body.success, not the HTTP status.
    testResult.value = result
    if (result.success) {
      message.success(t('llmProvider.testSuccess'))
    } else {
      message.error(t('llmProvider.testFailed') + (result.error || ''))
    }
  } catch (err) {
    if (seq !== testSeq) return
    message.error(
      t('llmProvider.testError') + (err instanceof Error ? err.message : String(err)),
    )
  } finally {
    if (seq === testSeq) testing.value = false
  }
}

// ---------------------------------------------------------------------------
// Save (the only path that writes the store)
// ---------------------------------------------------------------------------

/** The config keys owned by this page (design §4.1 mapping table). */
const MODEL_SETTINGS_KEYS = [
  'llm_provider',
  'api_key',
  'openai_base_url',
  'grok_base_url',
  'anthropic_base_url',
  'model_name',
  'llm_is_multimodal',
  'stream_response',
  'temperature',
  'top_p',
  'max_tokens',
  'top_k',
  'frequency_penalty',
  'presence_penalty',
  'custom_headers',
  'custom_parameters',
] as const

function pickModelSettingsKeys(src: BotConfig): Partial<BotConfig> {
  const pick: Record<string, unknown> = {}
  for (const key of MODEL_SETTINGS_KEYS) {
    pick[key] = (src as unknown as Record<string, unknown>)[key]
  }
  return pick as Partial<BotConfig>
}

async function handleSave(): Promise<void> {
  const botId = botsStore.selectedBotId
  if (!botId || saving.value || !draft.value) return
  saving.value = true
  try {
    configsStore.update(pickModelSettingsKeys(draft.value))
    const ok = await configsStore.save(botId)
    // Re-sync the draft from the server response — but only if the user is
    // still editing the same bot (a mid-save bot switch already started its
    // own load; reloading the old bot would clobber the new one's data).
    if (ok && botsStore.selectedBotId === botId) {
      await loadConfig(botId)
    }
    // On failure the store error surfaces in the NAlert and the draft is
    // preserved so the user can retry.
  } finally {
    saving.value = false
  }
}

// ---------------------------------------------------------------------------
// Providers page link: query pre-select (no store writes, no save)
// ---------------------------------------------------------------------------

function clearProviderQuery(): void {
  if (route.query.provider !== undefined) {
    void router.replace({ name: 'model-settings' })
  }
}

/**
 * After a successful load, pre-select the provider requested via
 * `?provider=` from the Providers page. Invalid values are silently
 * ignored; the query is always cleared afterwards.
 */
function applyQueryPreSelect(): void {
  const q = route.query.provider
  if (typeof q === 'string' && q) clearProviderQuery()
  if (typeof q !== 'string' || !q) return
  const cfg = draft.value
  if (!cfg) return
  if (!LLM_PROVIDER_VALUES.includes(q)) return
  if (q === cfg.llm_provider) return
  handleProviderChange(q)
}

// ---------------------------------------------------------------------------
// Card edit handlers (draft mutations only)
// ---------------------------------------------------------------------------

function onUpdateInferenceField(key: string, value: number | null): void {
  if (!draft.value) return
  ;(draft.value as unknown as Record<string, unknown>)[key] = value
}

function onClearInferenceField(key: string): void {
  if (!draft.value) return
  ;(draft.value as unknown as Record<string, unknown>)[key] = null
}

function addHeader(): void {
  if (!draft.value) return
  draft.value.custom_headers = [
    ...draft.value.custom_headers,
    { name: '', value: '' },
  ]
}

function removeHeader(index: number): void {
  if (!draft.value) return
  draft.value.custom_headers = draft.value.custom_headers.filter(
    (_, i) => i !== index,
  )
}

function onUpdateHeader(index: number, field: 'name' | 'value', value: string): void {
  const row = draft.value?.custom_headers[index]
  if (row) row[field] = value
}

function addParameter(): void {
  if (!draft.value) return
  draft.value.custom_parameters = [
    ...draft.value.custom_parameters,
    { name: '', type: 'text', value: '' },
  ]
}

function removeParameter(index: number): void {
  if (!draft.value) return
  draft.value.custom_parameters = draft.value.custom_parameters.filter(
    (_, i) => i !== index,
  )
}

function onUpdateParameter(index: number, field: 'name' | 'value', value: string | number): void {
  const row = draft.value?.custom_parameters[index]
  if (row) (row as unknown as Record<string, unknown>)[field] = value
}

function onChangeParameterType(index: number, type: string): void {
  const row = draft.value?.custom_parameters[index]
  if (row) row.type = type
}

function goBack(): void {
  if (window.history.length <= 1) {
    void router.push('/config-panel')
  } else {
    router.back()
  }
}
</script>

<template>
  <div class="model-settings-page">
    <div class="ms-head">
      <h2 class="ms-title">
        {{
          selectedBot
            ? t('modelSettings.title', { botId: selectedBot.bot_id })
            : t('modelSettings.selectBotFirst')
        }}
      </h2>
      <n-space :size="8">
        <n-button @click="goBack">{{ t('modelSettings.backToConfig') }}</n-button>
        <n-button
          type="success"
          :loading="saving"
          :disabled="!botsStore.selectedBotId"
          @click="handleSave"
        >
          {{ saving ? t('status.saving') : t('modelSettings.saveAndRestart') }}
        </n-button>
      </n-space>
    </div>

    <n-alert v-if="configsStore.error" type="error" class="ms-alert">
      <div class="ms-alert-body">
        <span class="ms-alert-text">{{ configsStore.error }}</span>
        <n-button v-if="!configsStore.config" size="small" @click="handleRetry">
          {{ t('generic.retry') }}
        </n-button>
      </div>
    </n-alert>

    <template v-if="!selectedBot">
      <EmptyState :description="t('configPanel.selectBot')">
        <template #action>
          <n-button size="small" @click="goBack">{{ t('modelSettings.backToConfig') }}</n-button>
        </template>
      </EmptyState>
    </template>

    <n-spin
      v-else
      :show="configsStore.loading"
      :description="t('modelSettings.loading')"
    >
      <template v-if="configsStore.config && draft">
        <LLMProviderCard
          :draft="draft"
          :available-models="availableModels"
          :model-mode="modelMode"
          :fetch-loading="fetchingModels"
          :testing="testing"
          :test-result="testResult"
          @update-llm-provider="handleProviderChange"
          @update-api-key="(v: string) => { if (draft) draft.api_key = v }"
          @update-base-url="handleUpdateBaseUrl"
          @update-model-name="(v: string) => { if (draft) draft.model_name = v }"
          @update-multimodal="(v: boolean) => { if (draft) draft.llm_is_multimodal = v }"
          @update-stream-response="(v: boolean) => { if (draft) draft.stream_response = v }"
          @fetch-models="fetchModels"
          @toggle-manual="useManualInput = !useManualInput"
          @test-connection="handleTestConnection"
        />

        <InferenceParamsCard
          :params="{
            temperature: draft.temperature,
            top_p: draft.top_p,
            max_tokens: draft.max_tokens,
            top_k: draft.top_k,
            frequency_penalty: draft.frequency_penalty,
            presence_penalty: draft.presence_penalty,
          }"
          :llm_provider="draft.llm_provider"
          @update-field="onUpdateInferenceField"
          @clear-field="onClearInferenceField"
        />

        <CustomHeadersCard
          :headers="draft.custom_headers"
          @add="addHeader"
          @remove="removeHeader"
          @update-field="onUpdateHeader"
        />

        <CustomParamsCard
          :params="draft.custom_parameters"
          @add="addParameter"
          @remove="removeParameter"
          @update-field="onUpdateParameter"
          @change-type="onChangeParameterType"
        />

        <PlaygroundCard
          :provider="draft.llm_provider"
          :model-name="draft.model_name"
          :bot-id="selectedBot!.bot_id"
          :disabled="!!configsStore.loading"
        />
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.model-settings-page {
  max-width: 1100px;
  margin: 0 auto;
}

.ms-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.ms-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.ms-alert {
  margin-bottom: 12px;
}

.ms-alert-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ms-alert-text {
  flex: 1;
  min-width: 0;
}
</style>
