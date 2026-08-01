<script setup lang="ts">
/**
 * PluginEditor — raw plugin config management (does NOT call the plugins API;
 * everything is saved through the config round-trip).
 *
 * The built-in `search` plugin is hidden from the list (legacy
 * `hiddenBuiltinPlugins` behavior) because SearchSettingsCard covers its
 * configuration. NDynamicTags manages the plugin keys; selecting a plugin
 * opens its config as a JSON textarea that is validated on blur — invalid
 * JSON shows a red border and is NOT written back; valid JSON updates the
 * store and marks it dirty.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NFormItem, NInput, NSelect } from 'naive-ui'

import { useConfigsStore } from '@/stores/configs'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const configsStore = useConfigsStore()

const config = computed(() => configsStore.config)
const markDirty = (): void => configsStore.markDirty()

/** Built-in plugins that are managed by dedicated cards, not raw JSON. */
const HIDDEN_BUILTIN_PLUGINS = new Set(['search'])

const pluginNames = computed<string[]>(() =>
  Object.keys(config.value?.plugins ?? {}).filter(
    (name) => !HIDDEN_BUILTIN_PLUGINS.has(name),
  ),
)

const selectedPlugin = ref('')
const jsonText = ref('')
const jsonError = ref(false)

function selectPlugin(name: string): void {
  selectedPlugin.value = name
  jsonError.value = false
  const raw = (config.value?.plugins ?? {})[name]
  jsonText.value = raw !== undefined ? JSON.stringify(raw, null, 2) : '{}'
}

function handleAddPlugin(name: string): void {
  if (!config.value || HIDDEN_BUILTIN_PLUGINS.has(name)) return
  config.value.plugins = { ...config.value.plugins, [name]: {} }
  markDirty()
  selectPlugin(name)
}

function handleRemovePlugin(name: string): void {
  if (!config.value) return
  const next = { ...config.value.plugins }
  delete next[name]
  config.value.plugins = next
  markDirty()
  if (selectedPlugin.value === name) {
    selectedPlugin.value = ''
    jsonText.value = ''
    jsonError.value = false
  }
}

/** Validate on blur: parse the JSON; only write back when valid. */
function handleJsonBlur(): void {
  if (!selectedPlugin.value || !config.value) return
  try {
    const parsed = JSON.parse(jsonText.value)
    config.value.plugins = {
      ...config.value.plugins,
      [selectedPlugin.value]: parsed,
    }
    jsonError.value = false
    markDirty()
  } catch {
    jsonError.value = true // invalid — keep the red border, do not write
  }
}

const pluginSelectOptions = computed(() =>
  pluginNames.value.map((name) => ({ label: name, value: name })),
)
</script>

<template>
  <SectionCard v-if="config" :title="t('pluginManager.title')">
    <n-alert type="warning" :show-icon="true" class="plugin-warning">
      {{ t('pluginManager.allowInternalWarning') }}
    </n-alert>

    <n-form-item :label="t('pluginManager.name')" label-placement="top">
      <n-dynamic-tags
        :value="pluginNames"
        @update:value="(tags: string[]) => {
          const prev = new Set(pluginNames);
          const next = new Set(tags);
          for (const tag of tags) if (!prev.has(tag)) handleAddPlugin(tag);
          for (const tag of pluginNames) if (!next.has(tag)) handleRemovePlugin(tag);
        }"
      />
    </n-form-item>

    <n-form-item :label="t('configPanel.pluginSelect')" label-placement="top">
      <n-select
        :value="selectedPlugin"
        :options="pluginSelectOptions"
        :placeholder="t('configPanel.pluginSelectPlaceholder')"
        @update:value="(v: string | null) => { if (v) selectPlugin(v) }"
      />
    </n-form-item>

    <n-form-item
      v-if="selectedPlugin"
      :label="t('configPanel.pluginConfigJson')"
      label-placement="top"
    >
      <n-input
        :value="jsonText"
        type="textarea"
        :rows="10"
        :status="jsonError ? 'error' : undefined"
        :placeholder="'{ }'"
        @update:value="(v: string) => { jsonText = v }"
        @blur="handleJsonBlur"
      />
    </n-form-item>
  </SectionCard>
</template>

<style scoped>
.plugin-warning {
  margin-bottom: 16px;
}
</style>
