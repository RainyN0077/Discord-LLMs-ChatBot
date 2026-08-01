<script setup lang="ts">
/**
 * RoleConfigEditor — role_based_config CRUD (legacy parity with the old
 * RoleConfigEditor.svelte: id / title / prompt / message & char quotas /
 * output budget / display color + quota preview). Edits the config store
 * directly; saving happens via the sticky page bar.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NButton, NInput, NInputNumber, NSwitch, NCard } from 'naive-ui'

import type { RoleConfigEntry } from '@/api/config'
import { useConfigsStore } from '@/stores/configs'

const { t } = useI18n()
const message = useMessage()
const configsStore = useConfigsStore()

const entries = computed<Record<string, RoleConfigEntry>>(
  () => (configsStore.config?.role_based_config ?? {}) as Record<string, RoleConfigEntry>,
)

const entryKeys = computed(() => Object.keys(entries.value))

/** Numeric fields are coerced to numbers on edit ('' → 0), legacy parity. */
const NUMERIC_FIELDS = new Set<keyof RoleConfigEntry>([
  'message_limit',
  'message_refresh_minutes',
  'char_limit',
  'char_refresh_minutes',
  'char_output_budget',
])

function updateField(key: string, field: keyof RoleConfigEntry, value: unknown): void {
  const entry = entries.value[key]
  if (!entry) return
  let nextValue = value
  if (NUMERIC_FIELDS.has(field)) {
    nextValue = value === '' || value === null || value === undefined ? 0 : Number(value)
  }
  if (configsStore.config) {
    configsStore.config.role_based_config = {
      ...configsStore.config.role_based_config,
      [key]: { ...entry, [field]: nextValue },
    }
  }
  configsStore.markDirty()
}

function updateId(oldKey: string, newId: string): void {
  const trimmed = newId.trim()
  if (!trimmed || oldKey === trimmed) return
  const rc = configsStore.config?.role_based_config
  if (!rc) return
  if (rc[trimmed]) {
    message.error(t('errors.duplicateId', { id: trimmed }))
    return
  }
  const entry = rc[oldKey]
  if (!entry) return
  const next = { ...rc }
  delete next[oldKey]
  next[trimmed] = { ...entry, id: trimmed }
  if (configsStore.config) configsStore.config.role_based_config = next
  configsStore.markDirty()
}

function addRoleConfig(): void {
  const key = `new-role-${Date.now()}`
  const next = {
    ...(configsStore.config?.role_based_config ?? {}),
    [key]: {
      id: '',
      title: '',
      prompt: '',
      enable_message_limit: false,
      message_limit: 0,
      message_refresh_minutes: 60,
      message_output_budget: 1,
      enable_char_limit: false,
      char_limit: 0,
      char_refresh_minutes: 60,
      char_output_budget: 300,
      display_color: '#ffffff',
    } satisfies RoleConfigEntry,
  }
  if (configsStore.config) configsStore.config.role_based_config = next
  configsStore.markDirty()
}

function removeRoleConfig(key: string): void {
  const rc = configsStore.config?.role_based_config
  if (!rc) return
  const next = { ...rc }
  delete next[key]
  if (configsStore.config) configsStore.config.role_based_config = next
  configsStore.markDirty()
}
</script>

<template>
  <n-card class="role-config-editor" size="small" :bordered="true">
    <template #header>
      <span class="role-config-title">{{ t('roleConfig.title') }}</span>
    </template>
    <p class="role-config-info">{{ t('roleConfig.info') }}</p>

    <div class="role-config-list">
      <div v-for="key in entryKeys" :key="key" class="role-config-item">
        <div class="role-config-grid">
          <n-input
            :value="entries[key].id ?? ''"
            :placeholder="t('roleConfig.roleId')"
            @blur="(e: FocusEvent) => updateId(key, (e.target as HTMLInputElement).value)"
          />
          <n-input
            :value="entries[key].title"
            :placeholder="t('roleConfig.roleTitle')"
            @update:value="(v: string) => updateField(key, 'title', v)"
          />
          <n-input
            type="textarea"
            :value="entries[key].prompt"
            :placeholder="t('roleConfig.rolePrompt')"
            :autosize="{ minRows: 3, maxRows: 6 }"
            class="role-config-prompt"
            @update:value="(v: string) => updateField(key, 'prompt', v)"
          />

          <div class="limit-control">
            <n-switch
              :value="entries[key].enable_message_limit"
              @update:value="(v: boolean) => updateField(key, 'enable_message_limit', v)"
            />
            <span class="limit-label">{{ t('roleConfig.enableMsgLimit') }}</span>
            <div class="limit-row" :class="{ disabled: !entries[key].enable_message_limit }">
              <span>{{ t('roleConfig.totalQuota') }}:</span>
              <n-input-number
                size="small"
                :min="0"
                :disabled="!entries[key].enable_message_limit"
                :value="entries[key].message_limit"
                @update:value="(v: number | null) => updateField(key, 'message_limit', v ?? 0)"
              />
              <span>/</span>
              <n-input-number
                size="small"
                :min="1"
                :disabled="!entries[key].enable_message_limit"
                :value="entries[key].message_refresh_minutes"
                @update:value="(v: number | null) => updateField(key, 'message_refresh_minutes', v ?? 60)"
              />
              <span class="unit">{{ t('roleConfig.minutes') }}</span>
            </div>
          </div>

          <div class="limit-control">
            <n-switch
              :value="entries[key].enable_char_limit"
              @update:value="(v: boolean) => updateField(key, 'enable_char_limit', v)"
            />
            <span class="limit-label">{{ t('roleConfig.enableTokenLimit') }}</span>
            <div class="limit-row" :class="{ disabled: !entries[key].enable_char_limit }">
              <span>{{ t('roleConfig.totalQuota') }}:</span>
              <n-input-number
                size="small"
                :min="0"
                :disabled="!entries[key].enable_char_limit"
                :value="entries[key].char_limit"
                @update:value="(v: number | null) => updateField(key, 'char_limit', v ?? 0)"
              />
              <span>/</span>
              <n-input-number
                size="small"
                :min="1"
                :disabled="!entries[key].enable_char_limit"
                :value="entries[key].char_refresh_minutes"
                @update:value="(v: number | null) => updateField(key, 'char_refresh_minutes', v ?? 60)"
              />
              <span class="unit">{{ t('roleConfig.minutes') }}</span>
            </div>
            <div class="limit-row" :class="{ disabled: !entries[key].enable_char_limit }">
              <span>{{ t('roleConfig.outputBudget') }}:</span>
              <n-input-number
                size="small"
                :min="0"
                :disabled="!entries[key].enable_char_limit"
                :value="entries[key].char_output_budget"
                @update:value="(v: number | null) => updateField(key, 'char_output_budget', v ?? 0)"
              />
            </div>
          </div>

          <div class="quota-preview">
            <div class="preview-header" :style="{ color: entries[key].display_color }">
              {{ t('roleConfig.previewHeader') }}
            </div>
            <div class="preview-row">
              <span>{{ t('roleConfig.msgLimit') }}</span>
              <span :style="{ color: entries[key].display_color }">
                {{
                  entries[key].enable_message_limit
                    ? `${entries[key].message_limit - Math.floor(entries[key].message_limit / 3)}/${entries[key].message_limit > 0 ? entries[key].message_limit : '∞'}`
                    : t('roleConfig.disabled')
                }}
              </span>
            </div>
            <div class="preview-row">
              <span>{{ t('roleConfig.tokenLimit') }}</span>
              <span :style="{ color: entries[key].display_color }">
                {{
                  entries[key].enable_char_limit
                    ? `${entries[key].char_limit - Math.floor(entries[key].char_limit / 4)}/${entries[key].char_limit > 0 ? entries[key].char_limit : '∞'}`
                    : t('roleConfig.disabled')
                }}
              </span>
            </div>
          </div>

          <div class="color-row">
            <label>{{ t('roleConfig.displayColor') }}</label>
            <input
              type="color"
              :value="entries[key].display_color"
              @input="(e: Event) => updateField(key, 'display_color', (e.target as HTMLInputElement).value)"
            />
          </div>
        </div>
        <n-button
          size="small"
          type="error"
          secondary
          class="role-config-remove"
          :title="t('roleConfig.remove')"
          @click="removeRoleConfig(key)"
        >
          ×
        </n-button>
      </div>
    </div>

    <n-button size="small" class="role-config-add" @click="addRoleConfig">
      {{ t('roleConfig.add') }}
    </n-button>
  </n-card>
</template>

<style scoped>
.role-config-editor {
  margin-bottom: 16px;
}

.role-config-title {
  font-weight: 600;
  font-size: 15px;
}

.role-config-info {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-color-3);
}

.role-config-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.role-config-item {
  position: relative;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.role-config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}

.role-config-prompt {
  grid-column: 1 / -1;
}

.limit-control {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  grid-column: 1 / -1;
}

.limit-label {
  font-size: 13px;
  font-weight: 500;
}

.limit-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.limit-row.disabled {
  opacity: 0.5;
}

.unit {
  font-size: 12px;
  color: var(--text-color-3);
}

.quota-preview {
  border: 1px dashed var(--border-color);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-header {
  font-size: 13px;
  font-weight: 600;
}

.preview-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.color-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.role-config-remove {
  position: absolute;
  top: 10px;
  right: 10px;
}

.role-config-add {
  margin-top: 12px;
}
</style>
