<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { RefreshOutline, SettingsOutline } from '@vicons/ionicons5'
import {
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NForm,
  NFormItem,
  NGrid,
  NGi,
  NIcon,
  NInput,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  type FormInst,
  type FormRules,
} from 'naive-ui'

import { useBotsStore } from '@/stores/bots'
import { useProvidersStore } from '@/stores/providers'
import { PROVIDER_DEFAULTS } from './model-settings/providerDefaults'

const { t } = useI18n()
const message = useMessage()
const router = useRouter()
const botsStore = useBotsStore()
const providersStore = useProvidersStore()

const formRef = ref<FormInst | null>(null)

const form = reactive({
  provider: '',
  model: '',
  api_key: '',
  base_url: '',
})

/** Front-end validation aligned with backend ProviderSwitchRequest (P1-6). */
const formRules: FormRules = {
  model: [{ required: true, message: () => t('providersPage.modelRequired') }],
  api_key: [
    { required: true, message: () => t('providersPage.apiKeyRequired') },
    { min: 8, message: () => t('providersPage.apiKeyTooShort') },
  ],
  base_url: [
    {
      validator: (_rule, value: string) => {
        if (!value) return true
        return /^https?:\/\//.test(value)
          ? true
          : new Error(t('providersPage.baseUrlInvalid'))
      },
      message: () => t('providersPage.baseUrlInvalid'),
    },
  ],
}

const selectedBot = computed(() => botsStore.selectedBot)

const providerOptions = computed(() =>
  providersStore.providers.map((p) => ({ label: p.name, value: p.name })),
)

/** Health display state for the three-state badge. */
function healthType(p: { healthy: boolean | null; configured: boolean }) {
  if (!p.configured) return 'default'
  if (p.healthy === null) return 'warning'
  return p.healthy ? 'success' : 'error'
}

/** Jump to Model Settings with this provider pre-selected (link only). */
function openModelSettings(provider: string): void {
  void router.push({ name: 'model-settings', query: { provider } })
}

function healthLabel(p: { healthy: boolean | null; configured: boolean }): string {
  if (!p.configured) return t('providersPage.notConfigured')
  if (p.healthy === null) return t('providersPage.unknown')
  return p.healthy ? t('providersPage.healthy') : t('providersPage.unhealthy')
}

async function submitSwitch(): Promise<void> {
  if (!selectedBot.value || providersStore.switching || providersStore.rateLimited) {
    return
  }
  try {
    await formRef.value?.validate()
  } catch {
    return // validation errors are shown inline by n-form-item
  }
  const ok = await providersStore.switchTo(selectedBot.value.bot_id, {
    provider: form.provider,
    model: form.model,
    api_key: form.api_key,
    base_url: form.base_url || undefined,
  })
  if (ok) {
    form.api_key = ''
  }
}

/**
 * Default pre-fill (UI-only initial values, user-editable): when a provider
 * is picked and a field is still empty, fill model/base_url from
 * PROVIDER_DEFAULTS. Fields the user already typed are left untouched.
 */
watch(
  () => form.provider,
  (provider) => {
    const defaults = PROVIDER_DEFAULTS[provider]
    if (!defaults) return
    if (!form.model) form.model = defaults.defaultModel ?? ''
    if (!form.base_url) form.base_url = defaults.baseUrl
  },
)

/** Manual refresh of the provider list (loading state + failure toast). */
async function handleRefresh(): Promise<void> {
  const botId = selectedBot.value?.bot_id
  if (!botId || providersStore.loading) return
  await providersStore.fetch(botId)
  if (providersStore.error) {
    message.error(t('providersPage.loadFailed', { error: providersStore.error }))
  }
}

watch(
  () => selectedBot.value?.bot_id,
  (botId) => {
    form.provider = ''
    form.model = ''
    form.api_key = ''
    form.base_url = ''
    // Clear the previous bot's transient state (error / rate limit / message)
    // before fetching — stale state from bot A must not leak into bot B.
    providersStore.reset()
    if (botId) void providersStore.fetch(botId)
  },
  { immediate: true },
)

onMounted(() => {
  if (!botsStore.bots.length) void botsStore.fetchBotsList()
})
</script>

<template>
  <div class="providers-page">
    <template v-if="!selectedBot">
      <n-empty
        :description="t('configPanel.selectBot')"
        class="no-bot-empty"
      />
    </template>

    <template v-else>
      <div class="providers-head">
        <h2 class="providers-title">
          {{ t('providersPage.title', { botId: selectedBot.bot_id }) }}
        </h2>
        <n-space :size="12" align="center">
          <span class="providers-label">{{ t('providersPage.current') }}:</span>
          <n-tag type="primary" size="small" :bordered="false">
            {{ providersStore.currentProvider || '—' }}
          </n-tag>
          <span class="providers-label">{{ t('providersPage.currentModel') }}:</span>
          <n-tag size="small" :bordered="false">
            {{ providersStore.currentModel || '—' }}
          </n-tag>
        </n-space>
      </div>

      <n-alert v-if="providersStore.error" type="error" class="providers-alert">
        {{ providersStore.error }}
      </n-alert>
      <n-alert v-if="providersStore.rateLimited" type="warning" class="providers-alert">
        {{ providersStore.error }}
        <span v-if="providersStore.rateLimitRemaining > 0">
          （{{ providersStore.rateLimitRemaining }}s）
        </span>
      </n-alert>
      <n-alert v-if="providersStore.lastSwitchMessage" type="success" class="providers-alert">
        {{ providersStore.lastSwitchMessage }}
      </n-alert>

      <n-spin :show="providersStore.loading">
        <n-grid :cols="3" :x-gap="12" :y-gap="12" responsive="screen" item-responsive class="providers-grid">
          <n-gi v-for="p in providersStore.providers" :key="p.name" :span="1">
            <n-card size="small" class="provider-card" :class="{ 'is-current': p.is_current }">
              <template #header>
                <n-space justify="space-between" align="center" :size="6">
                  <span class="provider-name">{{ p.name }}</span>
                  <n-space :size="4" align="center">
                    <n-tag v-if="p.is_current" type="primary" size="tiny" :bordered="false">
                      {{ t('providersPage.currentTag') }}
                    </n-tag>
                    <n-button
                      quaternary
                      circle
                      size="tiny"
                      :title="t('modelSettings.openSettings')"
                      :aria-label="t('modelSettings.openSettings')"
                      @click="openModelSettings(p.name)"
                    >
                      <template #icon>
                        <n-icon><SettingsOutline /></n-icon>
                      </template>
                    </n-button>
                  </n-space>
                </n-space>
              </template>
              <n-space vertical :size="8">
                <div class="provider-model">{{ p.model || '—' }}</div>
                <n-space :size="6" align="center">
                  <n-tag :type="healthType(p)" size="small" :bordered="false">
                    {{ healthLabel(p) }}
                  </n-tag>
                  <span v-if="p.latency_ms !== null" class="provider-latency">
                    {{ t('providersPage.latency', { ms: p.latency_ms }) }}
                  </span>
                </n-space>
              </n-space>
            </n-card>
          </n-gi>
        </n-grid>
      </n-spin>

      <n-card class="switch-card" size="small">
        <template #header>
          <n-space justify="space-between" align="center" :size="12">
            <span>{{ t('providersPage.switchTitle') }}</span>
            <n-button
              size="small"
              :loading="providersStore.loading"
              :disabled="providersStore.rateLimited"
              @click="handleRefresh"
            >
              <template #icon>
                <n-icon><RefreshOutline /></n-icon>
              </template>
              {{
                providersStore.loading
                  ? t('providersPage.refreshing')
                  : t('providersPage.refresh')
              }}
            </n-button>
          </n-space>
        </template>
        <n-form
          ref="formRef"
          :model="form"
          :rules="formRules"
          label-placement="top"
          class="switch-form"
          @submit.prevent="submitSwitch"
        >
          <n-grid :cols="2" :x-gap="12" responsive="screen" item-responsive>
            <n-gi :span="1">
              <n-form-item :label="t('providersPage.formProvider')" required>
                <n-select
                  v-model:value="form.provider"
                  :options="providerOptions"
                  :placeholder="t('providersPage.formProviderPlaceholder')"
                  :disabled="providersStore.switching || providersStore.rateLimited"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="1">
              <n-form-item :label="t('providersPage.modelLabel')" required>
                <n-input
                  v-model:value="form.model"
                  :placeholder="t('providersPage.modelPlaceholder')"
                  :disabled="providersStore.switching || providersStore.rateLimited"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="1">
              <n-form-item :label="t('providersPage.apiKeyLabel')" required>
                <n-input
                  v-model:value="form.api_key"
                  type="password"
                  show-password-on="click"
                  :placeholder="t('providersPage.formApiKeyPlaceholder')"
                  :disabled="providersStore.switching || providersStore.rateLimited"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="1">
              <n-form-item :label="t('providersPage.baseUrlLabel')">
                <n-input
                  v-model:value="form.base_url"
                  :placeholder="t('providersPage.formBaseUrlPlaceholder')"
                  :disabled="providersStore.switching || providersStore.rateLimited"
                />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-space :size="12" align="center">
            <n-button
              type="primary"
              :loading="providersStore.switching"
              :disabled="!form.provider || providersStore.rateLimited"
              @click="submitSwitch"
            >
              {{ t('providersPage.switchBtn') }}
            </n-button>
            <span v-if="providersStore.rateLimited" class="rate-limit-hint">
              {{ t('providersPage.rateLimited') }}
              <span v-if="providersStore.rateLimitRemaining > 0">
                ({{ providersStore.rateLimitRemaining }}s)
              </span>
            </span>
          </n-space>
        </n-form>
      </n-card>
    </template>
  </div>
</template>

<style scoped>
.providers-page {
  max-width: 1100px;
  margin: 0 auto;
}

.no-bot-empty {
  padding-top: 96px;
}

.providers-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.providers-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.providers-label {
  font-size: 13px;
  opacity: 0.7;
}

.providers-alert {
  margin-bottom: 12px;
}

.providers-grid {
  margin-bottom: 16px;
}

.provider-card.is-current {
  outline: 1px solid var(--n-primary-color, #45a3e6);
}

.provider-name {
  font-weight: 600;
}

.provider-model {
  font-family: var(--font-mono);
  font-size: 13px;
  opacity: 0.85;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.provider-latency {
  font-size: 12px;
  opacity: 0.7;
}

.switch-card {
  margin-bottom: 16px;
}

.switch-form {
  margin-top: 4px;
}

.rate-limit-hint {
  font-size: 13px;
  color: var(--log-warn);
}
</style>
