<script setup lang="ts">
/**
 * RolePortraitTab — role_based_config CRUD (legacy parity with the old
 * UserOptions.svelte rolePortrait tab + RoleConfigEditor fields: id / title /
 * prompt / message & char quotas / output budget / display color).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NButton, NCard, NInput, NInputNumber, NSwitch } from 'naive-ui'

import type { RoleConfigEntry } from '@/api/config'

const props = defineProps<{
  roleConfigs: Record<string, RoleConfigEntry>
}>()

const { t } = useI18n()
const message = useMessage()

const entryKeys = computed(() => Object.keys(props.roleConfigs))

const NUMERIC_FIELDS = new Set<keyof RoleConfigEntry>([
  'message_limit',
  'message_refresh_minutes',
  'char_limit',
  'char_refresh_minutes',
  'char_output_budget',
])

function updateField(key: string, field: keyof RoleConfigEntry, value: unknown): void {
  const entry = props.roleConfigs[key]
  if (!entry) return
  let nextValue = value
  if (NUMERIC_FIELDS.has(field)) {
    nextValue = value === '' || value === null || value === undefined ? 0 : Number(value)
  }
  props.roleConfigs[key] = { ...entry, [field]: nextValue }
}

function updateId(oldKey: string, newId: string): void {
  const trimmed = newId.trim()
  if (!trimmed || oldKey === trimmed) return
  if (props.roleConfigs[trimmed]) {
    message.error(t('errors.duplicateId', { id: trimmed }))
    return
  }
  const entry = props.roleConfigs[oldKey]
  if (!entry) return
  const next = { ...props.roleConfigs }
  delete next[oldKey]
  next[trimmed] = { ...entry, id: trimmed }
  Object.keys(props.roleConfigs).forEach((k) => delete props.roleConfigs[k])
  Object.assign(props.roleConfigs, next)
}

function addRoleConfig(): void {
  const key = `new-role-${Date.now()}`
  props.roleConfigs[key] = {
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
  }
}

function removeRoleConfig(key: string): void {
  delete props.roleConfigs[key]
}
</script>

<template>
  <n-card :title="t('roleConfig.title')" size="small">
    <p class="role-info">{{ t('roleConfig.info') }}</p>

    <div class="role-list">
      <div v-for="key in entryKeys" :key="key" class="role-item">
        <div class="role-grid">
          <n-input
            :value="roleConfigs[key].id ?? ''"
            :placeholder="t('roleConfig.roleId')"
            @blur="(e: FocusEvent) => updateId(key, (e.target as HTMLInputElement).value)"
          />
          <n-input
            :value="roleConfigs[key].title"
            :placeholder="t('roleConfig.roleTitle')"
            @update:value="(v: string) => updateField(key, 'title', v)"
          />
          <n-input
            type="textarea"
            :value="roleConfigs[key].prompt"
            :placeholder="t('roleConfig.rolePrompt')"
            :autosize="{ minRows: 3, maxRows: 6 }"
            class="role-prompt"
            @update:value="(v: string) => updateField(key, 'prompt', v)"
          />

          <div class="limit-control">
            <n-switch
              :value="roleConfigs[key].enable_message_limit"
              @update:value="(v: boolean) => updateField(key, 'enable_message_limit', v)"
            />
            <span class="limit-label">{{ t('roleConfig.enableMsgLimit') }}</span>
            <div class="limit-row" :class="{ disabled: !roleConfigs[key].enable_message_limit }">
              <span>{{ t('roleConfig.totalQuota') }}:</span>
              <n-input-number
                size="small"
                :min="0"
                :disabled="!roleConfigs[key].enable_message_limit"
                :value="roleConfigs[key].message_limit"
                @update:value="(v: number | null) => updateField(key, 'message_limit', v ?? 0)"
              />
              <span>/</span>
              <n-input-number
                size="small"
                :min="1"
                :disabled="!roleConfigs[key].enable_message_limit"
                :value="roleConfigs[key].message_refresh_minutes"
                @update:value="(v: number | null) => updateField(key, 'message_refresh_minutes', v ?? 60)"
              />
              <span class="unit">{{ t('roleConfig.minutes') }}</span>
            </div>
          </div>

          <div class="limit-control">
            <n-switch
              :value="roleConfigs[key].enable_char_limit"
              @update:value="(v: boolean) => updateField(key, 'enable_char_limit', v)"
            />
            <span class="limit-label">{{ t('roleConfig.enableTokenLimit') }}</span>
            <div class="limit-row" :class="{ disabled: !roleConfigs[key].enable_char_limit }">
              <span>{{ t('roleConfig.totalQuota') }}:</span>
              <n-input-number
                size="small"
                :min="0"
                :disabled="!roleConfigs[key].enable_char_limit"
                :value="roleConfigs[key].char_limit"
                @update:value="(v: number | null) => updateField(key, 'char_limit', v ?? 0)"
              />
              <span>/</span>
              <n-input-number
                size="small"
                :min="1"
                :disabled="!roleConfigs[key].enable_char_limit"
                :value="roleConfigs[key].char_refresh_minutes"
                @update:value="(v: number | null) => updateField(key, 'char_refresh_minutes', v ?? 60)"
              />
              <span class="unit">{{ t('roleConfig.minutes') }}</span>
            </div>
            <div class="limit-row" :class="{ disabled: !roleConfigs[key].enable_char_limit }">
              <span>{{ t('roleConfig.outputBudget') }}:</span>
              <n-input-number
                size="small"
                :min="0"
                :disabled="!roleConfigs[key].enable_char_limit"
                :value="roleConfigs[key].char_output_budget"
                @update:value="(v: number | null) => updateField(key, 'char_output_budget', v ?? 0)"
              />
            </div>
          </div>

          <div class="color-row">
            <label>{{ t('roleConfig.displayColor') }}</label>
            <input
              type="color"
              :value="roleConfigs[key].display_color"
              @input="(e: Event) => updateField(key, 'display_color', (e.target as HTMLInputElement).value)"
            />
          </div>
        </div>
        <n-button
          size="small"
          type="error"
          secondary
          class="role-remove"
          :title="t('roleConfig.remove')"
          @click="removeRoleConfig(key)"
        >
          ×
        </n-button>
      </div>
    </div>

    <n-button size="small" class="role-add" @click="addRoleConfig">
      {{ t('roleConfig.add') }}
    </n-button>
  </n-card>
</template>

<style scoped>
.role-info {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-color-3);
}

.role-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.role-item {
  position: relative;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.role-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}

.role-prompt {
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

.color-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.role-remove {
  position: absolute;
  top: 10px;
  right: 10px;
}

.role-add {
  margin-top: 12px;
}
</style>
