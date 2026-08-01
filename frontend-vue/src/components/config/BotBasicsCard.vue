<script setup lang="ts">
/**
 * BotBasicsCard - core tab: bot identity, LLM provider + inference params,
 * custom headers, and API secret key display.
 *
 * All fields bind DIRECTLY to the store's reactive config object; edits call
 * `configsStore.markDirty()` (full round-trip save happens on the page).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton,
  NCheckbox,
  NFormItem,
  NGrid,
  NGi,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NSwitch,
  NText,
  useMessage,
} from 'naive-ui'

import { getStoredApiKey } from '@/api/client'
import type { BotConfig } from '@/api/config'
import { useConfigsStore } from '@/stores/configs'
import SectionCard from '@/components/common/SectionCard.vue'
import { providerOptions } from './providerOptions'

const { t } = useI18n()
const configsStore = useConfigsStore()
const message = useMessage()

const config = computed(() => configsStore.config)
const markDirty = (): void => configsStore.markDirty()

const providerOpts = providerOptions((key) => t(key))

const platformOpts = [
  { label: 'Discord', value: 'discord' },
  { label: 'QQ', value: 'qq' },
]

/** Map each provider to its dedicated base-url config slot. */
const baseUrlFieldByProvider: Record<string, keyof BotConfig> = {
  openai: 'openai_base_url',
  openai_compatible: 'openai_base_url',
  gemini: 'openai_base_url',
  anthropic: 'anthropic_base_url',
  anthropic_compatible: 'anthropic_base_url',
  grok: 'grok_base_url',
  deepseek: 'deepseek_base_url',
  siliconflow: 'siliconflow_base_url',
  volcengine: 'volcengine_base_url',
  dashscope: 'dashscope_base_url',
  moonshot: 'moonshot_base_url',
  zhipu: 'zhipu_base_url',
  stepfun: 'stepfun_base_url',
}

const currentBaseUrlField = computed<string>(() => {
  const provider = config.value?.llm_provider ?? 'openai'
  return (baseUrlFieldByProvider[provider] ?? 'openai_base_url') as string
})

/** Read the active provider's base-url config slot (string form). */
const currentBaseUrl = computed<string>(() => {
  if (!config.value) return ''
  const value = (config.value as Record<string, unknown>)[currentBaseUrlField.value]
  return typeof value === 'string' ? value : ''
})

/** Write the active provider's base-url config slot. */
function setCurrentBaseUrl(value: string): void {
  if (!config.value) return
  ;(config.value as Record<string, unknown>)[currentBaseUrlField.value] = value
  markDirty()
}

/** Map providers without a dedicated placeholder to their closest alias. */
function placeholderFor(provider: string): string {
  if (provider === 'openai_compatible') return 'openai'
  if (provider === 'gemini') return 'google'
  if (provider === 'anthropic_compatible') return 'anthropic'
  return provider
}

const modelPlaceholder = computed(() =>
  t(`defaultBehavior.modelPlaceholders.${placeholderFor(config.value?.llm_provider ?? 'openai')}`),
)

const inferencePlaceholder = computed(() =>
  t(`inferenceParams.placeholders.${placeholderFor(config.value?.llm_provider ?? 'openai')}`),
)

const intents = computed(() => config.value?.discord_intents ?? null)
/** Config field key → i18n key (locale uses camelCase labels). */
const intentKeys = [
  { key: 'guilds', labelKey: 'guilds' },
  { key: 'guild_messages', labelKey: 'guildMessages' },
  { key: 'direct_messages', labelKey: 'directMessages' },
  { key: 'message_content', labelKey: 'messageContent' },
  { key: 'members', labelKey: 'members' },
] as const

function setPlatform(value: string): void {
  if (config.value) config.value.platform = value as 'discord' | 'qq'
  markDirty()
}

function setIntent(key: (typeof intentKeys)[number]['key'], value: boolean): void {
  if (config.value?.discord_intents) {
    config.value.discord_intents[key] = value
    markDirty()
  }
}

const maskDisplay = computed(() => {
  const key = getStoredApiKey()
  return key ? '\u2022'.repeat(16) : t('globalConfig.apiKeyUnavailable')
})

async function copyApiSecret(): Promise<void> {
  try {
    await navigator.clipboard.writeText(getStoredApiKey() ?? '')
    message.success(t('globalConfig.copied'))
  } catch {
    message.error(t('globalConfig.copyFailed'))
  }
}

// --- custom_headers rows ---------------------------------------------------

function addHeader(): void {
  if (!config.value) return
  config.value.custom_headers = [...config.value.custom_headers, { name: '', value: '' }]
  markDirty()
}

function removeHeader(index: number): void {
  if (!config.value) return
  config.value.custom_headers = config.value.custom_headers.filter((_, i) => i !== index)
  markDirty()
}
</script>

<template>
  <div v-if="config">
    <SectionCard :title="t('configPanel.botIdentity')">
      <n-grid :cols="2" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
        <n-gi :span="1">
          <n-form-item :label="t('configPanel.botName')" label-placement="top">
            <n-input v-model:value="config.bot_name" :placeholder="t('sidebar.botNamePlaceholder')" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('defaultBehavior.botNickname')" label-placement="top">
            <n-input
              v-model:value="config.bot_nickname"
              :placeholder="t('defaultBehavior.botNicknamePlaceholder')"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('configPanel.platform')" label-placement="top">
            <n-select
              :value="config.platform"
              :options="platformOpts"
              @update:value="setPlatform"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('configPanel.enabled')" label-placement="top">
            <n-switch v-model:value="config.enabled" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="2">
          <n-form-item :label="t('globalConfig.token')" label-placement="top">
            <n-input
              v-model:value="config.discord_token"
              type="password"
              show-password-on="click"
              :placeholder="t('globalConfig.tokenPlaceholder')"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
      </n-grid>

      <div v-if="intents" class="intent-block">
        <n-text depth="3" class="intent-info">{{ t('globalConfig.intents.info') }}</n-text>
        <n-space :size="16" wrap class="intent-grid">
          <n-checkbox
            v-for="item in intentKeys"
            :key="item.key"
            :checked="intents[item.key] !== false"
            @update:checked="(v: boolean) => setIntent(item.key, v)"
          >
            {{ t(`globalConfig.intents.${item.labelKey}`) }}
          </n-checkbox>
        </n-space>
      </div>
    </SectionCard>

    <SectionCard :title="t('configPanel.llmSettings')">
      <n-grid :cols="2" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
        <n-gi :span="1">
          <n-form-item :label="t('llmProvider.select')" label-placement="top">
            <n-select v-model:value="config.llm_provider" :options="providerOpts" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('llmProvider.apiKey')" label-placement="top">
            <n-input
              v-model:value="config.api_key"
              type="password"
              show-password-on="click"
              :placeholder="t('llmProvider.apiKeyPlaceholder')"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="2">
          <n-form-item :label="t('llmProvider.baseUrl')" label-placement="top">
            <n-input
              :value="currentBaseUrl"
              :placeholder="t('llmProvider.baseUrlPlaceholder')"
              @update:value="setCurrentBaseUrl"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('defaultBehavior.modelName')" label-placement="top">
            <n-input v-model:value="config.model_name" :placeholder="modelPlaceholder" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('llmProvider.multimodalLabel')" label-placement="top">
            <n-switch v-model:value="config.llm_is_multimodal" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
      </n-grid>
    </SectionCard>

    <SectionCard :title="t('inferenceParams.title')">
      <n-text depth="3" class="section-hint">{{ t('inferenceParams.hint') }}</n-text>
      <n-grid :cols="3" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
        <n-gi :span="1">
          <n-form-item :label="t('inferenceParams.temperature')" label-placement="top">
            <n-input-number
              v-model:value="config.temperature"
              :min="0"
              :max="2"
              :step="0.1"
              :placeholder="inferencePlaceholder"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('inferenceParams.maxTokens')" label-placement="top">
            <n-input-number
              v-model:value="config.max_tokens"
              :min="1"
              :placeholder="t('inferenceParams.maxTokensHint')"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('inferenceParams.topP')" label-placement="top">
            <n-input-number
              v-model:value="config.top_p"
              :min="0"
              :max="1"
              :step="0.05"
              :placeholder="t('inferenceParams.placeholders.topP')"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('inferenceParams.topK')" label-placement="top">
            <n-input-number
              v-model:value="config.top_k"
              :min="1"
              :placeholder="t('inferenceParams.placeholders.topK')"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('inferenceParams.frequencyPenalty')" label-placement="top">
            <n-input-number
              v-model:value="config.frequency_penalty"
              :min="-2"
              :max="2"
              :step="0.1"
              :placeholder="t('inferenceParams.placeholders.frequencyPenalty')"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('inferenceParams.presencePenalty')" label-placement="top">
            <n-input-number
              v-model:value="config.presence_penalty"
              :min="-2"
              :max="2"
              :step="0.1"
              :placeholder="t('inferenceParams.placeholders.presencePenalty')"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
      </n-grid>

      <n-form-item :label="t('customHeaders.title')" label-placement="top" class="headers-block">
        <div class="headers-list">
          <div v-for="(header, index) in config.custom_headers" :key="index" class="header-row">
            <n-input
              v-model:value="header.name"
              :placeholder="t('customHeaders.namePlaceholder')"
              @update:value="markDirty"
            />
            <n-input
              v-model:value="header.value"
              :placeholder="t('customHeaders.valuePlaceholder')"
              @update:value="markDirty"
            />
            <n-button size="small" quaternary type="error" @click="removeHeader(index)">
              {{ t('customHeaders.remove') }}
            </n-button>
          </div>
          <n-button size="small" dashed @click="addHeader">
            {{ t('customHeaders.add') }}
          </n-button>
        </div>
      </n-form-item>
    </SectionCard>

    <SectionCard :title="t('configPanel.systemPromptTitle')">
      <n-form-item :label="t('defaultBehavior.systemPrompt')" label-placement="top">
        <n-input
          v-model:value="config.system_prompt"
          type="textarea"
          :rows="5"
          :placeholder="t('defaultBehavior.systemPromptPlaceholder')"
          @update:value="markDirty"
        />
      </n-form-item>
      <n-form-item :label="t('defaultBehavior.blockedResponse')" label-placement="top">
        <n-input
          v-model:value="config.blocked_prompt_response"
          type="textarea"
          :rows="3"
          @update:value="markDirty"
        />
      </n-form-item>
      <n-text depth="3">{{ t('defaultBehavior.blockedResponseInfo') }}</n-text>
    </SectionCard>

    <SectionCard :title="t('globalConfig.apiKey')">
      <n-space :size="12" align="center" class="secret-row">
        <n-input :value="maskDisplay" readonly :placeholder="t('globalConfig.apiKeyUnavailable')" class="secret-input" />
        <n-button size="small" secondary @click="copyApiSecret">
          {{ t('globalConfig.copy') }}
        </n-button>
      </n-space>
      <n-text depth="3">{{ t('globalConfig.apiKeyInfo') }}</n-text>
    </SectionCard>
  </div>
</template>

<style scoped>
.section-hint {
  display: block;
  margin-bottom: 12px;
  font-size: 13px;
}

.intent-block {
  margin-top: 4px;
}

.intent-info {
  display: block;
  margin-bottom: 10px;
  font-size: 12px;
}

.intent-grid {
  gap: 4px 20px;
}

.full-width {
  width: 100%;
}

.headers-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.header-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 8px;
  align-items: center;
}

.secret-row {
  width: 100%;
  margin-bottom: 8px;
}

.secret-input {
  flex: 1;
}
</style>
