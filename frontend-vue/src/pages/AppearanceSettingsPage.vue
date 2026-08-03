<script setup lang="ts">
import { ref } from 'vue'
import type { CSSProperties } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NInput, NSwitch, useDialog, useMessage } from 'naive-ui'

import SectionCard from '@/components/common/SectionCard.vue'
import { MAX_CUSTOM_CSS_LENGTH, MAX_FONT_FILE_SIZE, useThemeStore } from '@/stores/theme'
import {
  STYLES,
  STYLE_ORDER,
  cssVarsToStyleObject,
  localizedName,
  mergeCssVars,
} from '@/themes/themes'

const { t, locale } = useI18n()
const themeStore = useThemeStore()
const dialog = useDialog()
const message = useMessage()

/** Local CSS draft; only pushed to the store on Apply. */
const cssDraft = ref(themeStore.customCSS)
const pendingStyleId = ref<string | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

const MAX_FONT_MB = (MAX_FONT_FILE_SIZE / 1024 / 1024).toFixed(1)

/** Map a file name to its CSS font format token; null = unsupported. */
function fontFormatFromName(name: string): string | null {
  const ext = name.toLowerCase().split('.').pop() ?? ''
  switch (ext) {
    case 'woff2':
      return 'woff2'
    case 'woff':
      return 'woff'
    case 'ttf':
      return 'truetype'
    case 'otf':
      return 'opentype'
    default:
      return null
  }
}

function handleFontFileChange(e: Event): void {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  // Reset so selecting the same file again re-triggers change.
  input.value = ''
  if (!file) return
  const format = fontFormatFromName(file.name)
  if (!format) {
    message.error(t('appearance.fontInvalid'))
    return
  }
  if (file.size > MAX_FONT_FILE_SIZE) {
    message.error(t('appearance.fontTooLarge', { limit: MAX_FONT_MB }))
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    const dataUrl = typeof reader.result === 'string' ? reader.result : ''
    if (!dataUrl) {
      message.error(t('appearance.fontReadFailed'))
      return
    }
    const name = file.name.replace(/\.[^.]+$/, '')
    if (!themeStore.importFont(name, dataUrl, format)) {
      message.error(t('appearance.fontStorageFailed'))
      return
    }
    message.success(t('appearance.fontImported'))
  }
  reader.onerror = () => {
    message.error(t('appearance.fontReadFailed'))
  }
  reader.readAsDataURL(file)
}

function handleResetFont(): void {
  themeStore.resetFont()
  message.success(t('appearance.fontResetDone'))
}

/** Preview block style for a style card (scheme = the style's first scheme). */
function previewStyleVars(styleId: string): CSSProperties {
  const style = STYLES[styleId]
  const firstSchemeId = style?.schemes[0]?.id ?? 'default'
  return cssVarsToStyleObject(mergeCssVars(styleId, firstSchemeId)) as CSSProperties
}

/** Dot color for a scheme chip under the current style. */
function schemeDotColor(schemeId: string): string {
  return mergeCssVars(themeStore.styleId, schemeId)['--primary-color'] ?? '#888'
}

function handleStyleSelect(styleId: string): void {
  // Re-entrancy guard: ignore clicks while a style dialog is already open
  // (prevents double-click from stacking two cyberpunk confirm dialogs).
  if (pendingStyleId.value) return
  if (styleId === 'cyberpunk') {
    pendingStyleId.value = styleId
    dialog.warning({
      title: t('appearance.cyberpunkWipTitle'),
      content: t('appearance.cyberpunkWipBody'),
      positiveText: t('appearance.cyberpunkWipConfirm'),
      negativeText: t('appearance.cyberpunkWipCancel'),
      onPositiveClick: () => {
        themeStore.setStyle(pendingStyleId.value ?? styleId)
        pendingStyleId.value = null
      },
      onNegativeClick: () => {
        pendingStyleId.value = null
      },
      onClose: () => {
        pendingStyleId.value = null
      },
      onMaskClick: () => {
        pendingStyleId.value = null
      },
    })
    return
  }
  themeStore.setStyle(styleId)
}

function handleSchemeSelect(schemeId: string): void {
  themeStore.setScheme(schemeId)
}

function applyCustomCSS(): void {
  themeStore.applyCustomCSS(cssDraft.value)
}

function resetCustomCSS(): void {
  cssDraft.value = ''
  themeStore.applyCustomCSS('')
}

function handleResetAll(): void {
  themeStore.resetAll()
  cssDraft.value = ''
}

/** 50KB cap hint — no dedicated i18n key (per migration spec). */
const cssLimitHint = () => {
  const kb = (MAX_CUSTOM_CSS_LENGTH / 1000).toFixed(0)
  return locale.value.startsWith('zh')
    ? `最大 ${kb}KB（${MAX_CUSTOM_CSS_LENGTH} 字符）`
    : `Max ${kb}KB (${MAX_CUSTOM_CSS_LENGTH} characters)`
}
</script>

<template>
  <div class="appearance-page">
    <SectionCard :title="t('appearance.uiStyle')">
      <div class="style-grid">
        <button
          v-for="styleId in STYLE_ORDER"
          :key="styleId"
          class="style-card"
          :class="{ active: themeStore.styleId === styleId }"
          type="button"
          @click="handleStyleSelect(styleId)"
        >
          <div class="style-preview" :style="previewStyleVars(styleId)">
            <div class="preview-dots">
              <span class="preview-dot" style="background: var(--primary-color)" />
              <span class="preview-dot" style="background: var(--success-text)" />
              <span class="preview-dot" style="background: var(--error-text)" />
            </div>
            <div class="preview-bar" />
          </div>
          <span class="style-name">{{ localizedName(STYLES[styleId].name, locale) }}</span>
        </button>
      </div>
    </SectionCard>

    <SectionCard :title="t('appearance.colorScheme')">
      <div class="scheme-chips">
        <button
          v-for="scheme in themeStore.currentStyle.schemes"
          :key="scheme.id"
          class="scheme-chip"
          :class="{ active: themeStore.schemeId === scheme.id }"
          type="button"
          @click="handleSchemeSelect(scheme.id)"
        >
          <span class="scheme-dot" :style="{ background: schemeDotColor(scheme.id) }" />
          <span class="scheme-label">{{ localizedName(scheme.name, locale) }}</span>
        </button>
      </div>
    </SectionCard>

    <SectionCard :title="t('appearance.animationSettings')">
      <div class="toggle-row">
        <n-switch
          :value="themeStore.animationsEnabled"
          @update:value="themeStore.setAnimationsEnabled"
        />
        <span class="toggle-label">{{ t('appearance.enablePageTransitions') }}</span>
      </div>
    </SectionCard>

    <SectionCard :title="t('appearance.effectSettings')">
      <div v-if="themeStore.availableEffects.length === 0" class="effect-row">
        <span class="toggle-label">{{ t('appearance.noEffects') }}</span>
      </div>
      <div v-else class="effect-rows">
        <div
          v-for="fx in themeStore.availableEffects"
          :key="fx.id"
          class="effect-row"
        >
          <span class="toggle-label">{{ t(fx.labelKey) }}</span>
          <n-switch
            :value="!!themeStore.effects[fx.id]"
            @update:value="() => themeStore.toggleEffect(fx.id)"
          />
        </div>
      </div>
    </SectionCard>

    <SectionCard :title="t('appearance.customCSS')">
      <n-input
        v-model:value="cssDraft"
        type="textarea"
        :rows="10"
        :placeholder="t('appearance.cssPlaceholder')"
        show-count
        :maxlength="MAX_CUSTOM_CSS_LENGTH"
        class="css-input"
      />
      <div class="css-hint">{{ cssLimitHint() }} · {{ t('appearance.cssFvHint') }}</div>
      <div class="css-actions">
        <n-button type="primary" size="small" @click="applyCustomCSS">
          {{ t('appearance.applyCSS') }}
        </n-button>
        <n-button size="small" @click="resetCustomCSS">
          {{ t('appearance.resetCSS') }}
        </n-button>
      </div>
    </SectionCard>

    <SectionCard :title="t('appearance.fontSettings')">
      <div class="font-status">
        <span
          v-if="themeStore.customFont"
          class="font-status-name"
        >{{ t('appearance.fontStatusCustom', { name: themeStore.customFont.name }) }}</span>
        <span v-else class="toggle-label">{{ t('appearance.fontStatusDefault') }}</span>
      </div>
      <div class="font-actions">
        <input
          ref="fileInputRef"
          type="file"
          accept=".ttf,.otf,.woff,.woff2"
          class="font-file-input"
          @change="handleFontFileChange"
        />
        <n-button size="small" @click="fileInputRef?.click()">
          {{ t('appearance.fontImport') }}
        </n-button>
        <n-button
          size="small"
          :disabled="!themeStore.customFont"
          @click="handleResetFont"
        >
          {{ t('appearance.fontReset') }}
        </n-button>
      </div>
      <div class="css-hint">{{ t('appearance.fontImportHint', { limit: MAX_FONT_MB }) }}</div>
    </SectionCard>

    <div class="reset-section">
      <n-button quaternary type="error" size="small" @click="handleResetAll">
        {{ t('appearance.resetAll') }}
      </n-button>
    </div>
  </div>
</template>

<style scoped>
.appearance-page {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 800px;
  width: 100%;
}

.style-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
}

.style-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 0.5rem;
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--panel-soft-bg-2);
  cursor: pointer;
  transition: all 0.2s ease;
  font-weight: 500;
  font-size: 0.85rem;
  color: var(--text-color);
  font-family: inherit;
}

.style-card:hover {
  transform: translateY(-2px);
  border-color: var(--primary-color);
}

.style-card.active {
  border-color: var(--primary-color);
  box-shadow: 0 4px 14px rgba(31, 139, 214, 0.18);
}

.style-preview {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}

.preview-dots {
  display: flex;
  gap: 4px;
}

.preview-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.preview-bar {
  height: 12px;
  border-radius: 3px;
  background: var(--sidebar-bg);
  border-left: 3px solid var(--sidebar-active-bg);
}

.style-name {
  font-size: 0.8rem;
  line-height: 1.2;
}

.scheme-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.scheme-chip {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.7rem;
  border: 1.5px solid var(--border-color);
  border-radius: 20px;
  background: var(--panel-soft-bg-2);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 0.82rem;
  color: var(--text-color);
  font-family: inherit;
}

.scheme-chip:hover {
  border-color: var(--primary-color);
}

.scheme-chip.active {
  border-color: var(--primary-color);
  background: var(--panel-muted-bg);
}

.scheme-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.scheme-chip.active .scheme-dot {
  transform: scale(1.15);
}

.scheme-label {
  font-size: 0.8rem;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.toggle-label {
  font-size: 0.85rem;
}

/* FX: per-effect toggle rows (same rhythm as .toggle-row). */
.effect-rows {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.effect-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.css-input {
  font-family: var(--font-mono);
}

.css-hint {
  margin-top: 0.4rem;
  font-size: 0.78rem;
  opacity: 0.6;
}

.css-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.font-file-input {
  display: none;
}

.font-status {
  margin-bottom: 0.5rem;
}

.font-status-name {
  font-weight: 600;
  word-break: break-all;
}

.font-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.reset-section {
  display: flex;
  justify-content: flex-end;
  padding-top: 0.5rem;
}

@media (max-width: 768px) {
  .style-grid {
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 0.5rem;
  }
}
</style>
