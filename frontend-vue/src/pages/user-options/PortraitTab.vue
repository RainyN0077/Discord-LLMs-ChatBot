<script setup lang="ts">
/**
 * PortraitTab — user_personas CRUD (legacy parity):
 * id (blur rename + duplicate guard) / nickname / prompt / trigger_keywords
 * (comma-separated ↔ array).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NButton, NCard, NInput } from 'naive-ui'

import type { UserPersona } from '@/api/config'

const props = defineProps<{
  userPersonas: Record<string, UserPersona>
}>()

const { t } = useI18n()
const message = useMessage()

const personaKeys = computed(() => Object.keys(props.userPersonas))

function updateField(key: string, field: keyof UserPersona, value: unknown): void {
  const persona = props.userPersonas[key]
  if (!persona) return
  props.userPersonas[key] = { ...persona, [field]: value }
}

function updateId(oldKey: string, newId: string): void {
  const trimmed = newId.trim()
  if (!trimmed || oldKey === trimmed) return
  if (props.userPersonas[trimmed]) {
    message.error(t('errors.duplicateId', { id: trimmed }))
    return
  }
  const persona = props.userPersonas[oldKey]
  if (!persona) return
  const next = { ...props.userPersonas }
  delete next[oldKey]
  next[trimmed] = { ...persona, id: trimmed }
  Object.keys(props.userPersonas).forEach((k) => delete props.userPersonas[k])
  Object.assign(props.userPersonas, next)
}

function updateKeywords(key: string, value: string): void {
  updateField(key, 'trigger_keywords', value.split(',').map((k) => k.trim()).filter(Boolean))
}

function addPersona(): void {
  props.userPersonas[`new-${Date.now()}`] = {
    id: '',
    nickname: '',
    prompt: '',
    trigger_keywords: [],
  }
}

function removePersona(key: string): void {
  delete props.userPersonas[key]
}
</script>

<template>
  <n-card :title="t('userPortrait.title')" size="small">
    <p class="portrait-info">{{ t('userPortrait.info') }}</p>

    <div class="portrait-list">
      <div v-for="key in personaKeys" :key="key" class="portrait-item">
        <div class="portrait-grid">
          <n-input
            :value="userPersonas[key].id ?? ''"
            :placeholder="t('userPortrait.userId')"
            @blur="(e: FocusEvent) => updateId(key, (e.target as HTMLInputElement).value)"
          />
          <n-input
            :value="userPersonas[key].nickname ?? ''"
            :placeholder="t('userPortrait.customNicknamePlaceholder')"
            @update:value="(v: string) => updateField(key, 'nickname', v)"
          />
          <n-input
            type="textarea"
            :value="userPersonas[key].prompt ?? ''"
            :placeholder="t('userPortrait.personaPrompt')"
            :autosize="{ minRows: 3, maxRows: 6 }"
            class="portrait-prompt"
            @update:value="(v: string) => updateField(key, 'prompt', v)"
          />
          <n-input
            :value="(userPersonas[key].trigger_keywords || []).join(', ')"
            :placeholder="t('userPortrait.triggerKeywordsPlaceholder')"
            @update:value="(v: string) => updateKeywords(key, v)"
          />
        </div>
        <n-button
          size="small"
          type="error"
          secondary
          class="portrait-remove"
          :title="t('userOptions.remove')"
          @click="removePersona(key)"
        >
          ×
        </n-button>
      </div>
    </div>

    <n-button size="small" class="portrait-add" @click="addPersona">
      {{ t('userPortrait.add') }}
    </n-button>
  </n-card>
</template>

<style scoped>
.portrait-info {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-color-3);
}

.portrait-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.portrait-item {
  position: relative;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.portrait-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}

/* Narrow screens: single column (matches the sider breakpoint). */
@media (max-width: 768px) {
  .portrait-grid {
    grid-template-columns: 1fr;
  }
}

.portrait-prompt {
  grid-column: 1 / -1;
}

.portrait-remove {
  position: absolute;
  top: 10px;
  right: 10px;
}

.portrait-add {
  margin-top: 12px;
}
</style>
