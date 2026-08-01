<script setup lang="ts">
/**
 * GuildPortraitTab — scoped_prompts.guilds CRUD with a guild dropdown
 * (getGuilds) to fill new entry ids.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NButton, NCard, NInput, NRadio, NRadioGroup, NSelect, NSwitch } from 'naive-ui'

import { getGuilds, type GuildInfo } from '@/api/bots'
import type { ScopedPromptEntry } from '@/api/config'

const props = defineProps<{
  botId: string
  scopedItems: Record<string, ScopedPromptEntry>
}>()

const { t } = useI18n()
const message = useMessage()

const guilds = ref<GuildInfo[]>([])
const selectedGuildId = ref<string | null>(null)

const itemKeys = computed(() => Object.keys(props.scopedItems))

onMounted(async () => {
  try {
    const data = await getGuilds(props.botId)
    guilds.value = data.guilds || []
  } catch {
    guilds.value = []
  }
})

function updateItem(key: string, field: keyof ScopedPromptEntry, value: unknown): void {
  const item = props.scopedItems[key]
  if (!item) return
  props.scopedItems[key] = { ...item, [field]: value }
}

function updateId(oldKey: string, newId: string): void {
  const trimmed = newId.trim()
  if (!trimmed || oldKey === trimmed) return
  if (props.scopedItems[trimmed]) {
    message.error(t('errors.duplicateId', { id: trimmed }))
    return
  }
  const item = props.scopedItems[oldKey]
  if (!item) return
  const next = { ...props.scopedItems }
  delete next[oldKey]
  next[trimmed] = { ...item, id: trimmed }
  Object.keys(props.scopedItems).forEach((k) => delete props.scopedItems[k])
  Object.assign(props.scopedItems, next)
}

function addItem(): void {
  const key = `new-guilds-${Date.now()}`
  props.scopedItems[key] = {
    id: selectedGuildId.value ?? '',
    enabled: true,
    mode: 'append',
    prompt: '',
  }
  selectedGuildId.value = null
}

function removeItem(key: string): void {
  delete props.scopedItems[key]
}
</script>

<template>
  <n-card :title="t('scopedPrompts.guilds.title')" size="small">
    <p class="scoped-info">{{ t('scopedPrompts.guilds.info') }}</p>

    <div class="scoped-list">
      <div v-for="key in itemKeys" :key="key" class="scoped-item">
        <div class="scoped-grid">
          <div class="cell">
            <label class="cell-label">{{ t('scopedPrompts.guilds.id') }}</label>
            <n-input
              :value="scopedItems[key].id ?? ''"
              :placeholder="t('scopedPrompts.guilds.idPlaceholder')"
              @blur="(e: FocusEvent) => updateId(key, (e.target as HTMLInputElement).value)"
            />
          </div>
          <div class="cell">
            <label class="cell-label">{{ t('scopedPrompts.enabled') }}</label>
            <n-switch
              :value="scopedItems[key].enabled"
              @update:value="(v: boolean) => updateItem(key, 'enabled', v)"
            />
          </div>
          <div class="cell">
            <label class="cell-label">{{ t('scopedPrompts.mode.title') }}</label>
            <n-radio-group
              :value="scopedItems[key].mode"
              @update:value="(v: 'append' | 'override') => updateItem(key, 'mode', v)"
            >
              <n-radio value="override">{{ t('scopedPrompts.mode.override') }}</n-radio>
              <n-radio value="append">{{ t('scopedPrompts.mode.append') }}</n-radio>
            </n-radio-group>
          </div>
          <div class="cell cell-prompt">
            <label class="cell-label">{{ t('scopedPrompts.guilds.prompt') }}</label>
            <n-input
              type="textarea"
              :value="scopedItems[key].prompt"
              :placeholder="
                scopedItems[key].mode === 'override'
                  ? t('scopedPrompts.guilds.overridePlaceholder')
                  : t('scopedPrompts.guilds.appendPlaceholder')
              "
              :autosize="{ minRows: 3, maxRows: 6 }"
              @update:value="(v: string) => updateItem(key, 'prompt', v)"
            />
          </div>
        </div>
        <n-button size="small" type="error" secondary class="scoped-remove" @click="removeItem(key)">
          ×
        </n-button>
      </div>
    </div>

    <div class="scoped-add-row">
      <n-select
        v-model:value="selectedGuildId"
        :options="guilds.map((g) => ({ label: g.name, value: g.id }))"
        :placeholder="t('userOptions.blocklist.selectGuild')"
        clearable
        style="width: 260px"
      />
      <n-button size="small" @click="addItem">{{ t('scopedPrompts.guilds.add') }}</n-button>
    </div>
  </n-card>
</template>

<style scoped>
.scoped-info {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-color-3);
}

.scoped-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.scoped-item {
  position: relative;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.scoped-grid {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 12px;
  align-items: start;
}

/* Narrow screens: single column (matches the sider breakpoint). */
@media (max-width: 768px) {
  .scoped-grid {
    grid-template-columns: 1fr;
  }
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

.scoped-remove {
  position: absolute;
  top: 10px;
  right: 10px;
}

.scoped-add-row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 12px;
}
</style>
