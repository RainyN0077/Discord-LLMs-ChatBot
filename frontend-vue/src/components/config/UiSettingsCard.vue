<script setup lang="ts">
/**
 * UiSettingsCard — custom UI font management (IndexedDB via fontStore) and
 * timezone selection (persisted to localStorage under the legacy `timezone`
 * key so it stays compatible with the old frontend's timezoneStore).
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage } from 'naive-ui'
import { NButton, NFormItem, NSelect, NText } from 'naive-ui'

import { loadFont, removeFont, saveFont } from '@/utils/fontStore'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const message = useMessage()

const currentFontName = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)

/** Same presets as the legacy UiSettings.svelte (7 common IANA timezones). */
const TIMEZONE_PRESETS = [
  'UTC',
  'Asia/Shanghai',
  'America/New_York',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Asia/Tokyo',
]
const TIMEZONE_STORAGE_KEY = 'timezone'

function readStoredTimezone(): string {
  try {
    const saved = localStorage.getItem(TIMEZONE_STORAGE_KEY)
    if (saved) return saved
  } catch {
    // storage unavailable — fall through to the detected zone
  }
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

const timezone = ref<string>(readStoredTimezone())

function setTimezone(value: string): void {
  timezone.value = value
  try {
    localStorage.setItem(TIMEZONE_STORAGE_KEY, value)
  } catch {
    // persistence failure must not block the UI selection
  }
}

const ALLOWED_EXTENSIONS = ['ttf', 'otf', 'woff', 'woff2']
const MAX_SIZE = 50 * 1024 * 1024
const STYLE_ID = 'custom-font-style'
const FONT_FAMILY = 'BotCustomFont'

function fontFormat(ext: string): string {
  if (ext === 'woff2') return 'woff2'
  if (ext === 'woff') return 'woff'
  if (ext === 'otf') return 'opentype'
  return 'truetype'
}

/** Apply the font data URL as the body font-family via an injected <style>. */
function applyFont(dataUrl: string): void {
  const existing = document.getElementById(STYLE_ID)
  if (existing) existing.remove()
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
@font-face {
  font-family: "${FONT_FAMILY}";
  src: url("${dataUrl}") format("${fontFormat(currentFontName.value.split('.').pop()?.toLowerCase() || 'truetype')}");
  font-display: swap;
}
body {
  font-family: "${FONT_FAMILY}", -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", Roboto, sans-serif !important;
}`
  document.head.appendChild(style)
}

/** Remove the injected style (restore the default font). */
function restoreFont(): void {
  const style = document.getElementById(STYLE_ID)
  if (style) style.remove()
}

onMounted(async () => {
  try {
    const stored = await loadFont()
    if (stored) {
      currentFontName.value = stored.name
      applyFont(stored.data)
    }
  } catch {
    // storage unavailable — keep the default font silently
  }
})

function openFilePicker(): void {
  fileInputRef.value?.click()
}

async function handleFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  const ext = file.name.split('.').pop()?.toLowerCase() || ''
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    message.error(t('uiSettings.font.invalidType'))
    return
  }
  if (file.size > MAX_SIZE) {
    message.error(
      t('uiSettings.font.fileTooLarge', {
        size: (file.size / 1024 / 1024).toFixed(2),
        maxSize: 50,
      }),
    )
    return
  }

  const reader = new FileReader()
  reader.onload = async () => {
    const dataUrl = typeof reader.result === 'string' ? reader.result : ''
    if (!dataUrl) {
      message.error(t('uiSettings.font.loadError'))
      return
    }
    try {
      await saveFont(file.name, dataUrl)
      currentFontName.value = file.name
      applyFont(dataUrl)
      message.success(t('uiSettings.font.loadSuccess'))
    } catch {
      message.error(t('uiSettings.font.storageError'))
    }
  }
  reader.onerror = () => {
    message.error(t('uiSettings.font.loadError'))
  }
  reader.readAsDataURL(file)
}

async function handleResetFont(): Promise<void> {
  restoreFont()
  try {
    await removeFont()
  } catch {
    // removal failure should not block the UI reset
  }
  currentFontName.value = ''
  message.success(t('uiSettings.font.resetSuccess'))
}
</script>

<template>
  <SectionCard :title="t('uiSettings.title')">
    <div class="font-actions">
      <n-button size="small" @click="openFilePicker">
        {{ t('uiSettings.font.loadButton') }}
      </n-button>
      <n-button size="small" secondary @click="handleResetFont">
        {{ t('uiSettings.font.resetButton') }}
      </n-button>
    </div>

    <n-text depth="3" class="font-status">
      {{ currentFontName
        ? t('uiSettings.font.currentFont', { fontName: currentFontName })
        : t('uiSettings.font.defaultFont') }}
    </n-text>

    <n-form-item :label="t('uiSettings.timezone.title')" label-placement="top" class="timezone-field">
      <n-select
        :value="timezone"
        :options="TIMEZONE_PRESETS.map((tz) => ({ label: tz, value: tz }))"
        class="timezone-select"
        @update:value="(v: string) => setTimezone(v)"
      />
    </n-form-item>

    <input
      ref="fileInputRef"
      type="file"
      accept=".ttf,.otf,.woff,.woff2"
      class="hidden-file-input"
      @change="handleFileChange"
    />
  </SectionCard>
</template>

<style scoped>
.font-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.font-status {
  font-size: 13px;
}

.timezone-field {
  margin-top: 16px;
}

.timezone-select {
  max-width: 320px;
}

.hidden-file-input {
  display: none;
}
</style>
