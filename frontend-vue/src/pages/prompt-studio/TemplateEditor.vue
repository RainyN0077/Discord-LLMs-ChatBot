<script setup lang="ts">
/**
 * TemplateEditor — 14-key three-column editor (legacy parity):
 *   left: grouped navigation (collapsible sections)
 *   middle: textarea + placeholder hints for the selected key
 *   right: operational_instructions list (add / remove)
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NInput, NTag, NCollapse, NCollapseItem } from 'naive-ui'

import type { PromptTemplate } from '@/api/prompts'
import {
  TEMPLATE_PLACEHOLDERS,
  TEMPLATE_SECTIONS,
} from './defaultTemplates'

const props = defineProps<{
  templates: PromptTemplate
}>()

const emit = defineEmits<{
  (e: 'update:templates', templates: PromptTemplate): void
}>()

const { t } = useI18n()

const selectedKey = ref('message_format')
const openSections = ref<string[]>(TEMPLATE_SECTIONS.map((s) => s.titleKey))

const selectedValue = computed<string>(() => {
  const value = (props.templates as unknown as Record<string, unknown>)[selectedKey.value]
  return typeof value === 'string' ? value : ''
})

function updateValue(key: string, value: string): void {
  emit('update:templates', { ...props.templates, [key]: value })
}

function addInstruction(): void {
  const next = [...(props.templates.operational_instructions || []), '']
  emit('update:templates', { ...props.templates, operational_instructions: next })
}

function removeInstruction(index: number): void {
  const next = (props.templates.operational_instructions || []).filter((_, i) => i !== index)
  emit('update:templates', { ...props.templates, operational_instructions: next })
}

function updateInstruction(index: number, value: string): void {
  const next = [...(props.templates.operational_instructions || [])]
  next[index] = value
  emit('update:templates', { ...props.templates, operational_instructions: next })
}

const selectedPlaceholders = computed(() => TEMPLATE_PLACEHOLDERS[selectedKey.value] ?? [])

const selectedLabelKey = computed(
  () =>
    TEMPLATE_SECTIONS.flatMap((s) => s.items).find((i) => i.key === selectedKey.value)
      ?.labelKey ?? selectedKey.value,
)
</script>

<template>
  <div class="template-editor">
    <!-- Left: grouped navigation -->
    <aside class="template-editor-nav">
      <n-collapse v-model:expanded-names="openSections">
        <n-collapse-item
          v-for="section in TEMPLATE_SECTIONS"
          :key="section.titleKey"
          :name="section.titleKey"
          :title="t(section.titleKey)"
        >
          <div class="template-editor-nav-list">
            <button
              v-for="item in section.items"
              :key="item.key"
              type="button"
              class="template-editor-nav-item"
              :class="{ active: selectedKey === item.key }"
              @click="selectedKey = item.key"
            >
              {{ t(item.labelKey) }}
            </button>
          </div>
        </n-collapse-item>
      </n-collapse>
    </aside>

    <!-- Middle: textarea editor -->
    <main class="template-editor-main">
      <template v-if="selectedKey !== 'operational_instructions'">
        <label class="template-editor-label">
          {{ t(selectedLabelKey) }}
        </label>
        <n-input
          :value="selectedValue"
          type="textarea"
          :autosize="{ minRows: 10, maxRows: 28 }"
          class="template-editor-textarea"
          @update:value="(v: string) => updateValue(selectedKey, v)"
        />
        <div v-if="selectedPlaceholders.length" class="template-editor-placeholders">
          <strong>{{ t('promptStudio.editor.availablePlaceholders') }}:</strong>
          <n-tag v-for="p in selectedPlaceholders" :key="p" size="small" class="placeholder-tag">
            {{ p }}
          </n-tag>
        </div>
      </template>
    </main>

    <!-- Right: operational instructions list -->
    <aside class="template-editor-instructions">
      <h3 class="template-editor-instructions-title">
        {{ t('promptStudio.editor.coreInstructions') }}
      </h3>
      <p class="template-editor-instructions-desc">
        {{ t('promptStudio.editor.coreInstructionsDesc') }}
      </p>
      <div
        v-for="(instruction, i) in templates.operational_instructions || []"
        :key="i"
        class="instruction-item"
      >
        <n-input
          :value="instruction"
          :placeholder="t('promptStudio.editor.instructionPlaceholder')"
          @update:value="(v: string) => updateInstruction(i, v)"
        />
        <n-button size="small" type="error" secondary @click="removeInstruction(i)">
          {{ t('promptStudio.editor.removeInstruction') }}
        </n-button>
      </div>
      <n-button size="small" @click="addInstruction">
        {{ t('promptStudio.editor.addInstruction') }}
      </n-button>
    </aside>
  </div>
</template>

<style scoped>
.template-editor {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr) 360px;
  gap: 16px;
  align-items: start;
}

.template-editor-nav {
  background: var(--card-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 8px;
  max-height: 560px;
  overflow-y: auto;
}

.template-editor-nav-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.template-editor-nav-item {
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-color-2);
  font-size: 13px;
  transition: all 0.15s;
}

.template-editor-nav-item:hover {
  background: var(--hover-color);
}

.template-editor-nav-item.active {
  background: var(--primary-color);
  color: #fff;
  font-weight: 600;
}

.template-editor-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-editor-label {
  font-weight: 600;
  font-size: 14px;
}

.template-editor-placeholders {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text-color-3);
}

.template-editor-instructions {
  background: var(--card-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 12px;
}

.template-editor-instructions-title {
  margin: 0 0 4px;
  font-size: 14px;
}

.template-editor-instructions-desc {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--text-color-3);
}

.instruction-item {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  align-items: center;
}
</style>
