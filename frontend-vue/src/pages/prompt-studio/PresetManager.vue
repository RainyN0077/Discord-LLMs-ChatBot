<script setup lang="ts">
/**
 * PresetManager — load / save-as / import / delete presets.
 *
 * - List loads via listPresets (default readonly item is synthesized first).
 * - Load: default preset → local DEFAULT_TEMPLATES (no API call); custom →
 *   getPreset.
 * - Save As: guarded against the default preset name, NModal + NInput.
 * - Import: JSON.parse failure / missing required keys → toast listing them;
 *   a valid import overwrites currentTemplates WITHOUT persisting.
 * - Delete: confirm dialog; the default preset cannot be deleted; after
 *   deletion the selection falls back to the default preset.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDialog, useMessage } from 'naive-ui'
import { NButton, NInput, NModal, NSelect } from 'naive-ui'

import {
  deletePreset,
  getPreset,
  listPresets,
  savePreset,
  type PresetItem,
  type PromptTemplate,
} from '@/api/prompts'
import {
  DEFAULT_PRESET_NAME,
  DEFAULT_TEMPLATES,
  REQUIRED_TEMPLATE_KEYS,
  normalizeTemplates,
} from './defaultTemplates'

const props = withDefaults(
  defineProps<{
    templates: PromptTemplate
    botId?: string
  }>(),
  { botId: undefined },
)

const emit = defineEmits<{
  (e: 'apply', templates: PromptTemplate): void
}>()

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()

const presets = ref<PresetItem[]>([])
const selectedName = ref<string | null>(null)
const loading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const saveAsVisible = ref(false)
const saveAsName = ref('')
const savingAs = ref(false)

const selectOptions = computed(() =>
  presets.value.map((p) => ({ label: p.name, value: p.name, disabled: false })),
)

const selectedPreset = computed(
  () => presets.value.find((p) => p.name === selectedName.value) ?? null,
)

async function loadPresets(): Promise<void> {
  try {
    presets.value = await listPresets(props.botId)
    if (!selectedName.value && presets.value.length > 0) {
      selectedName.value = presets.value[0].name
    }
  } catch (err) {
    message.error(
      t('promptStudio.preset.presetsLoadFailed', {
        error: err instanceof Error ? err.message : String(err),
      }),
    )
  }
}

onMounted(loadPresets)

async function handleLoad(): Promise<void> {
  const name = selectedName.value
  if (!name) return
  loading.value = true
  try {
    // Default preset is synthesized locally (readonly item — no API call).
    const data =
      name === DEFAULT_PRESET_NAME ? { ...DEFAULT_TEMPLATES } : await getPreset(name, props.botId)
    emit('apply', normalizeTemplates(data))
    message.success(t('promptStudio.preset.loadSuccess', { name }))
  } catch (err) {
    message.error(
      t('promptStudio.preset.loadFailed', {
        error: err instanceof Error ? err.message : String(err),
      }),
    )
  } finally {
    loading.value = false
  }
}

function openSaveAs(): void {
  // Legacy parity: prefill the save-as dialog with the currently selected preset.
  saveAsName.value = selectedName.value ?? ''
  saveAsVisible.value = true
}

async function handleSaveAs(): Promise<void> {
  const name = saveAsName.value.trim()
  if (!name) return
  if (name.length > 64) {
    // Client-side guard mirroring the backend's 64-char limit.
    message.error(t('promptStudio.preset.nameTooLong'))
    return
  }
  if (name === DEFAULT_PRESET_NAME) {
    message.error(t('promptStudio.preset.defaultPresetLocked'))
    return
  }
  savingAs.value = true
  try {
    await savePreset(name, props.templates, props.botId)
    message.success(t('promptStudio.preset.saveSuccess', { name }))
    saveAsVisible.value = false
    await loadPresets()
    selectedName.value = name
  } catch (err) {
    message.error(
      t('promptStudio.preset.saveFailed', {
        error: err instanceof Error ? err.message : String(err),
      }),
    )
  } finally {
    savingAs.value = false
  }
}

function handleImportClick(): void {
  fileInput.value?.click()
}

function handleFileSelected(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const imported = JSON.parse(String(e.target?.result ?? '')) as Record<string, unknown>
      const missing = REQUIRED_TEMPLATE_KEYS.filter((key) => imported[key] === undefined)
      if (missing.length > 0) {
        throw new Error(
          t('promptStudio.preset.invalidFormat', { keys: missing.join(', ') }),
        )
      }
      // Overwrite currentTemplates locally — NOT persisted until "save".
      emit('apply', normalizeTemplates(imported))
      message.success(t('promptStudio.preset.importSuccess', { name: file.name }))
    } catch (err) {
      message.error(
        t('promptStudio.preset.importFailed', {
          error: err instanceof Error ? err.message : String(err),
        }),
      )
    }
  }
  reader.onerror = () => {
    message.error(String(reader.error ?? 'FileReader error'))
  }
  reader.readAsText(file)
}

async function handleDelete(): Promise<void> {
  const name = selectedName.value
  if (!name || name === DEFAULT_PRESET_NAME) return
  dialog.warning({
    title: t('promptStudio.preset.deleteConfirm', { name }),
    content: '',
    positiveText: t('promptStudio.preset.delete'),
    negativeText: t('importExport.cancel'),
    onPositiveClick: async () => {
      try {
        await deletePreset(name, props.botId)
        message.success(t('promptStudio.preset.deleteSuccess', { name }))
        selectedName.value = null
        await loadPresets()
        if (!selectedName.value && presets.value.length > 0) {
          selectedName.value = presets.value[0].name
        }
      } catch (err) {
        message.error(
          t('promptStudio.preset.deleteFailed', {
            error: err instanceof Error ? err.message : String(err),
          }),
        )
      }
    },
  })
}
</script>

<template>
  <div class="preset-manager">
    <n-select
      v-model:value="selectedName"
      :options="selectOptions"
      :placeholder="t('promptStudio.preset.selectPlaceholder')"
      class="preset-manager-select"
    />
    <n-button :loading="loading" :disabled="!selectedName" @click="handleLoad">
      {{ t('promptStudio.preset.load') }}
    </n-button>
    <n-button :loading="loading" @click="openSaveAs">
      {{ t('promptStudio.preset.saveAs') }}
    </n-button>
    <n-button :loading="loading" @click="handleImportClick">
      {{ t('promptStudio.preset.import') }}
    </n-button>
    <n-button
      type="error"
      secondary
      :disabled="!selectedName || selectedPreset?.readonly"
      @click="handleDelete"
    >
      {{ t('promptStudio.preset.delete') }}
    </n-button>
    <input
      ref="fileInput"
      type="file"
      accept=".json"
      class="preset-manager-file"
      @change="handleFileSelected"
    />
  </div>

  <n-modal
    v-model:show="saveAsVisible"
    preset="dialog"
    :title="t('promptStudio.preset.savePrompt')"
    :positive-text="t('promptStudio.preset.saveAs')"
    :negative-text="t('importExport.cancel')"
    :positive-disabled="!saveAsName.trim()"
    :on-positive-click="handleSaveAs"
  >
    <n-input
      v-model:value="saveAsName"
      :placeholder="t('promptStudio.preset.selectPlaceholder')"
      :disabled="savingAs"
      @keyup.enter="handleSaveAs"
    />
  </n-modal>
</template>

<style scoped>
.preset-manager {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px;
  margin-bottom: 16px;
  background: var(--card-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  flex-wrap: wrap;
}

.preset-manager-select {
  flex: 1;
  min-width: 180px;
}

.preset-manager-file {
  display: none;
}
</style>
