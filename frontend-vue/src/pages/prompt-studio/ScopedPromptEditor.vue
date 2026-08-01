<script setup lang="ts">
/**
 * ScopedPromptEditor — guilds/channels scoped prompt CRUD (legacy parity:
 * id / enabled / mode(append|override) / prompt). Edits the config store
 * directly and marks it dirty — saving happens via the sticky page bar.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NButton, NInput, NRadio, NRadioGroup, NSwitch, NCard } from 'naive-ui'

import type { ScopedPromptEntry } from '@/api/config'
import { useConfigsStore } from '@/stores/configs'

const props = defineProps<{
  /** 'guilds' | 'channels' */
  type: 'guilds' | 'channels'
  title: string
}>()

const { t } = useI18n()
const message = useMessage()
const configsStore = useConfigsStore()

const entries = computed<Record<string, ScopedPromptEntry>>(() => {
  const scoped = configsStore.config?.scoped_prompts?.[props.type] ?? {}
  return scoped as Record<string, ScopedPromptEntry>
})

const entryKeys = computed(() => Object.keys(entries.value))

function updateItem(key: string, field: keyof ScopedPromptEntry, value: unknown): void {
  const scoped = configsStore.config?.scoped_prompts?.[props.type]
  const item = scoped?.[key]
  if (!scoped || !item) return
  scoped[key] = { ...item, [field]: value }
  configsStore.markDirty()
}

function updateItemId(oldKey: string, newId: string): void {
  const trimmed = newId.trim()
  if (!trimmed || oldKey === trimmed) return
  const scoped = configsStore.config?.scoped_prompts?.[props.type]
  if (!scoped) return
  if (scoped[trimmed]) {
    message.error(t('errors.duplicateId', { id: trimmed }))
    return
  }
  const item = scoped[oldKey]
  if (!item) return
  const next = { ...scoped }
  delete next[oldKey]
  next[trimmed] = { ...item, id: trimmed }
  if (configsStore.config) {
    configsStore.config.scoped_prompts = {
      ...configsStore.config.scoped_prompts,
      [props.type]: next,
    }
  }
  configsStore.markDirty()
}

function addItem(): void {
  const key = `new-${props.type}-${Date.now()}`
  const scoped = configsStore.config?.scoped_prompts?.[props.type] ?? {}
  const next = { ...scoped }
  next[key] = { id: '', enabled: true, mode: 'append', prompt: '' }
  if (configsStore.config) {
    configsStore.config.scoped_prompts = {
      ...configsStore.config.scoped_prompts,
      [props.type]: next,
    }
  }
  configsStore.markDirty()
}

function removeItem(key: string): void {
  const scoped = configsStore.config?.scoped_prompts?.[props.type]
  if (!scoped) return
  const next = { ...scoped }
  delete next[key]
  if (configsStore.config) {
    configsStore.config.scoped_prompts = {
      ...configsStore.config.scoped_prompts,
      [props.type]: next,
    }
  }
  configsStore.markDirty()
}
</script>

<template>
  <n-card class="scoped-editor" size="small" :bordered="true">
    <template #header>
      <span class="scoped-editor-title">{{ title }}</span>
    </template>
    <p class="scoped-editor-info">{{ t(`scopedPrompts.${type}.info`) }}</p>

    <div class="scoped-editor-list">
      <div v-for="key in entryKeys" :key="key" class="scoped-editor-item">
        <div class="scoped-editor-grid">
          <div class="cell">
            <label class="cell-label">{{ t(`scopedPrompts.${type}.id`) }}</label>
            <n-input
              :value="entries[key].id ?? ''"
              :placeholder="t(`scopedPrompts.${type}.idPlaceholder`)"
              @blur="(e: FocusEvent) => updateItemId(key, (e.target as HTMLInputElement).value)"
            />
          </div>
          <div class="cell">
            <label class="cell-label">{{ t('scopedPrompts.enabled') }}</label>
            <n-switch
              :value="entries[key].enabled"
              @update:value="(v: boolean) => updateItem(key, 'enabled', v)"
            />
          </div>
          <div class="cell">
            <label class="cell-label">{{ t('scopedPrompts.mode.title') }}</label>
            <n-radio-group
              :value="entries[key].mode"
              @update:value="(v: 'append' | 'override') => updateItem(key, 'mode', v)"
            >
              <n-radio value="override">{{ t('scopedPrompts.mode.override') }}</n-radio>
              <n-radio value="append">{{ t('scopedPrompts.mode.append') }}</n-radio>
            </n-radio-group>
          </div>
          <div class="cell cell-prompt">
            <label class="cell-label">{{ t(`scopedPrompts.${type}.prompt`) }}</label>
            <n-input
              type="textarea"
              :value="entries[key].prompt"
              :placeholder="
                entries[key].mode === 'override'
                  ? t(`scopedPrompts.${type}.overridePlaceholder`)
                  : t(`scopedPrompts.${type}.appendPlaceholder`)
              "
              :autosize="{ minRows: 3, maxRows: 6 }"
              @update:value="(v: string) => updateItem(key, 'prompt', v)"
            />
          </div>
        </div>
        <n-button size="small" type="error" secondary class="scoped-editor-remove" @click="removeItem(key)">
          ×
        </n-button>
      </div>
    </div>

    <n-button size="small" class="scoped-editor-add" @click="addItem">
      {{ t(`scopedPrompts.${type}.add`) }}
    </n-button>
  </n-card>
</template>

<style scoped>
.scoped-editor {
  margin-bottom: 16px;
}

.scoped-editor-title {
  font-weight: 600;
  font-size: 15px;
}

.scoped-editor-info {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-color-3);
}

.scoped-editor-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.scoped-editor-item {
  position: relative;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.scoped-editor-grid {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 12px;
  align-items: start;
}

.cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cell-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-color-3);
}

.cell-prompt {
  grid-column: 1 / -1;
}

.scoped-editor-remove {
  position: absolute;
  top: 10px;
  right: 10px;
}

.scoped-editor-add {
  margin-top: 12px;
}
</style>
