<script setup lang="ts">
/**
 * SearchSettingsCard — Tavily search plugin settings (`config.plugins.search`).
 *
 * The backend consumes search settings from the built-in `search` plugin
 * (bot_instance.py discover_and_load reads `config["plugins"]`); the legacy
 * frontend mirrored that by storing them under `plugins.search`.
 * Bindings mirror the legacy frontend/src/components/SearchSettings.svelte:
 * api_key/api_url, enabled, trigger_mode (command|keyword), command/keywords,
 * include_date/require_main_trigger/rewrite_query_with_llm, max_results,
 * compression_strategy, exclude_domains list + usage guide modal.
 *
 * `plugins.search` may be absent on old configs — reads apply the same
 * defaults as the legacy component, writes create the group on demand.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton,
  NFormItem,
  NGrid,
  NGi,
  NInput,
  NInputNumber,
  NModal,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
  NSwitch,
  NText,
} from 'naive-ui'

import type { SearchSettings } from '@/api/config'
import { useConfigsStore } from '@/stores/configs'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const configsStore = useConfigsStore()

const config = computed(() => configsStore.config)
const markDirty = (): void => configsStore.markDirty()

const newDomain = ref('')
const showUsageGuide = ref(false)

/** Legacy default search config (same values as the old component). */
const DEFAULT_SEARCH: Required<SearchSettings> = {
  enabled: false,
  api_key: '',
  api_url: 'https://api.tavily.com',
  command: '!search',
  trigger_mode: 'command',
  keywords: [],
  require_main_trigger: true,
  rewrite_query_with_llm: true,
  search_depth: 'basic',
  max_results: 5,
  include_date: true,
  exclude_domains: [],
  compression_strategy: 'none',
}

/** Read a search field with the legacy default fallback. */
function getSearch<K extends keyof SearchSettings>(key: K): SearchSettings[K] {
  const value = config.value?.plugins?.search?.[key]
  return value === undefined ? DEFAULT_SEARCH[key] : (value as SearchSettings[K])
}

/** Write a search field, creating the `plugins.search` group when missing. */
function setSearch<K extends keyof SearchSettings>(key: K, value: SearchSettings[K]): void {
  if (!config.value) return
  if (!config.value.plugins) config.value.plugins = {}
  const search = config.value.plugins.search ?? (config.value.plugins.search = {})
  ;(search as SearchSettings)[key] = value
  markDirty()
}

const triggerModeOptions = [
  { label: t('searchSettings.triggerMode.command'), value: 'command' },
  { label: t('searchSettings.triggerMode.keyword'), value: 'keyword' },
]

const compressionOptions = [
  { label: t('searchSettings.compressionNone'), value: 'none' },
  { label: t('searchSettings.compressionTruncate'), value: 'truncate' },
  { label: t('searchSettings.compressionRAG'), value: 'rag' },
]

function addDomain(): void {
  const domain = newDomain.value.trim()
  if (!domain) return
  const domains = [...getSearch('exclude_domains'), domain]
  setSearch('exclude_domains', domains)
  newDomain.value = ''
}

function removeDomain(index: number): void {
  const domains = [...getSearch('exclude_domains')]
  domains.splice(index, 1)
  setSearch('exclude_domains', domains)
}

function handleDomainChange(index: number, value: string): void {
  const domains = [...getSearch('exclude_domains')]
  domains[index] = value
  setSearch('exclude_domains', domains)
}

/** keywords input is a comma-separated string in the UI, an array in config. */
function keywordsText(): string {
  return getSearch('keywords').join(', ')
}

function setKeywordsText(value: string): void {
  setSearch(
    'keywords',
    value.split(',').map((k) => k.trim()).filter(Boolean),
  )
}

/** max_results is clamped to >= 1 like the legacy component. */
function setMaxResults(value: number | null): void {
  setSearch('max_results', Math.max(1, value ?? 1))
}
</script>

<template>
  <SectionCard v-if="config" :title="t('searchSettings.title')">
    <n-grid :cols="2" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
      <n-gi :span="1">
        <n-form-item :label="t('searchSettings.apiKey')" label-placement="top">
          <n-input
            :value="getSearch('api_key')"
            type="password"
            show-password-on="click"
            placeholder="sk-..."
            @update:value="(v: string) => setSearch('api_key', v)"
          />
          <template #feedback>
            <a
              href="https://app.tavily.com/home"
              target="_blank"
              rel="noopener noreferrer"
              class="api-help-link"
            >
              {{ t('searchSettings.getApiKey') }}
            </a>
          </template>
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t('searchSettings.apiUrl')" label-placement="top">
          <n-input
            :value="getSearch('api_url')"
            @update:value="(v: string) => setSearch('api_url', v)"
          />
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t('searchSettings.enable')" label-placement="top">
          <n-switch :value="getSearch('enabled')" @update:value="(v: boolean) => setSearch('enabled', v)" />
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t('searchSettings.triggerMode.title')" label-placement="top">
          <n-radio-group
            :value="getSearch('trigger_mode')"
            @update:value="(v: string) => setSearch('trigger_mode', v as 'command' | 'keyword')"
          >
            <n-radio v-for="opt in triggerModeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </n-radio>
          </n-radio-group>
        </n-form-item>
      </n-gi>

      <template v-if="getSearch('trigger_mode') === 'command'">
        <n-gi :span="2">
          <n-form-item :label="t('searchSettings.commandLabel')" label-placement="top">
            <n-input :value="getSearch('command')" @update:value="(v: string) => setSearch('command', v)" />
            <template #feedback>{{ t('searchSettings.commandInfo') }}</template>
          </n-form-item>
        </n-gi>
      </template>
      <template v-else>
        <n-gi :span="2">
          <n-form-item :label="t('searchSettings.keywordsLabel')" label-placement="top">
            <n-input :value="keywordsText()" @update:value="setKeywordsText" />
            <template #feedback>{{ t('searchSettings.keywordsInfo') }}</template>
          </n-form-item>
        </n-gi>
      </template>

      <n-gi :span="1">
        <n-form-item :label="t('searchSettings.includeDate')" label-placement="top">
          <n-switch :value="getSearch('include_date')" @update:value="(v: boolean) => setSearch('include_date', v)" />
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t('searchSettings.requireMainTrigger')" label-placement="top">
          <n-switch :value="getSearch('require_main_trigger')" @update:value="(v: boolean) => setSearch('require_main_trigger', v)" />
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t('searchSettings.rewriteQueryWithLlm')" label-placement="top">
          <n-switch :value="getSearch('rewrite_query_with_llm')" @update:value="(v: boolean) => setSearch('rewrite_query_with_llm', v)" />
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item :label="t('searchSettings.maxResults')" label-placement="top">
          <n-input-number
            :value="getSearch('max_results')"
            :min="1"
            :step="1"
            class="full-width"
            @update:value="setMaxResults"
          />
        </n-form-item>
      </n-gi>
      <n-gi :span="2">
        <n-form-item :label="t('searchSettings.compression')" label-placement="top">
          <n-select
            :value="getSearch('compression_strategy')"
            :options="compressionOptions"
            class="full-width"
            @update:value="(v: string) => setSearch('compression_strategy', v as 'none' | 'truncate' | 'rag')"
          />
        </n-form-item>
      </n-gi>

      <n-gi :span="2">
        <n-form-item :label="t('searchSettings.blacklist.title')" label-placement="top">
          <div class="domains-list">
            <div v-for="(domain, index) in getSearch('exclude_domains')" :key="index" class="domain-row">
              <n-input
                :value="domain"
                placeholder="example.com/*"
                @update:value="(v: string) => handleDomainChange(index, v)"
              />
              <n-button size="small" quaternary type="error" @click="removeDomain(index)">×</n-button>
            </div>
            <n-text v-if="getSearch('exclude_domains').length === 0" depth="3">
              {{ t('searchSettings.blacklist.empty') }}
            </n-text>
            <n-space :size="8" class="domain-add">
              <n-input
                :value="newDomain"
                :placeholder="t('searchSettings.blacklist.addPlaceholder')"
                @update:value="(v: string) => { newDomain = v }"
              />
              <n-button size="small" @click="addDomain">
                {{ t('searchSettings.blacklist.add') }}
              </n-button>
            </n-space>
          </div>
        </n-form-item>
      </n-gi>
    </n-grid>

    <n-button text type="primary" size="small" @click="showUsageGuide = true">
      {{ t('searchSettings.usageGuide.link') }}
    </n-button>

    <n-modal
      v-model:show="showUsageGuide"
      :title="t('searchSettings.usageGuide.title')"
      preset="card"
      class="usage-guide-modal"
    >
      <n-text depth="2">{{ t('searchSettings.usageGuide.intro') }}</n-text>

      <h4 class="guide-heading">{{ t('searchSettings.usageGuide.commandTitle') }}</h4>
      <ul class="guide-list">
        <li>{{ t('searchSettings.usageGuide.command1') }}</li>
        <li>{{ t('searchSettings.usageGuide.command2') }}</li>
        <li>{{ t('searchSettings.usageGuide.command3') }}</li>
      </ul>

      <h4 class="guide-heading">{{ t('searchSettings.usageGuide.keywordTitle') }}</h4>
      <ul class="guide-list">
        <li>{{ t('searchSettings.usageGuide.keyword1') }}</li>
        <li>{{ t('searchSettings.usageGuide.keyword2') }}</li>
        <li>{{ t('searchSettings.usageGuide.keyword3') }}</li>
      </ul>

      <h4 class="guide-heading">{{ t('searchSettings.usageGuide.troubleshootTitle') }}</h4>
      <ol class="guide-list">
        <li>{{ t('searchSettings.usageGuide.troubleshoot1') }}</li>
        <li>{{ t('searchSettings.usageGuide.troubleshoot2') }}</li>
        <li>{{ t('searchSettings.usageGuide.troubleshoot3') }}</li>
        <li>{{ t('searchSettings.usageGuide.troubleshoot4') }}</li>
      </ol>

      <template #footer>
        <n-space justify="end">
          <n-button size="small" @click="showUsageGuide = false">
            {{ t('searchSettings.usageGuide.close') }}
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </SectionCard>
</template>

<style scoped>
.full-width {
  width: 100%;
}

.api-help-link {
  font-size: 12px;
}

.domains-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.domain-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: center;
}

.domain-add {
  width: 100%;
}

.domain-add .n-input {
  flex: 1;
}

.usage-guide-modal {
  width: min(640px, 94vw);
}

.guide-heading {
  margin: 16px 0 8px;
  font-size: 14px;
}

.guide-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.85;
}
</style>
