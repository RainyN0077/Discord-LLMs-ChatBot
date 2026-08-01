/**
 * Theme store — style / scheme / custom CSS / animation settings with
 * localStorage persistence, CSS variable injection and naive-ui overrides.
 *
 * State is persisted under four keys:
 *   frontend-vue-style / frontend-vue-scheme / frontend-vue-custom-css / frontend-vue-animations
 * The legacy P0 key `frontend-vue-theme` ('dark'/'light') is only read as a
 * fallback by initThemeSync() and the store initializer (migration path).
 */

import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { darkTheme, lightTheme } from 'naive-ui'

import { STYLES, isValidStyleId, mergeCssVars } from '@/themes/themes'
import { deriveNaiveOverrides } from '@/themes/naiveMapping'

const STYLE_KEY = 'frontend-vue-style'
const SCHEME_KEY = 'frontend-vue-scheme'
const CSS_KEY = 'frontend-vue-custom-css'
const ANIM_KEY = 'frontend-vue-animations'
const LEGACY_THEME_KEY = 'frontend-vue-theme'

/**
 * 50KB（50000 字符）custom CSS cap, aligned with the legacy frontend's
 * frontend/src/lib/themeStore.js MAX_CUSTOM_CSS_LENGTH.
 */
export const MAX_CUSTOM_CSS_LENGTH = 50000

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // ignore persistence failures
  }
}

/** Resolve the initial style id, falling back to the legacy P0 theme key. */
function resolveInitialStyle(): string {
  const stored = readStorage(STYLE_KEY)
  if (stored && isValidStyleId(stored)) return stored
  // Legacy P0: 'frontend-vue-theme' held 'dark'/'light' (tolerate 'true' too).
  const legacy = readStorage(LEGACY_THEME_KEY)
  if (legacy === 'dark' || legacy === 'true') return 'dark'
  if (legacy === 'light') return 'light'
  return 'dark'
}

function readInitialScheme(styleId: string): string {
  const style = STYLES[styleId]
  const stored = readStorage(SCHEME_KEY)
  if (stored && style && style.schemes.some((s) => s.id === stored)) return stored
  return style?.schemes[0]?.id ?? 'default'
}

function readInitialCustomCSS(): string {
  const stored = readStorage(CSS_KEY)
  if (stored === null) return ''
  if (stored.length > MAX_CUSTOM_CSS_LENGTH) {
    console.warn('Custom CSS exceeds maximum length, truncated')
    return stored.slice(0, MAX_CUSTOM_CSS_LENGTH)
  }
  return stored
}

function readInitialAnimations(): boolean {
  return readStorage(ANIM_KEY) !== '0'
}

function ensureStyleEl(id: string): HTMLStyleElement | null {
  if (typeof document === 'undefined') return null
  let el = document.getElementById(id) as HTMLStyleElement | null
  if (!el) {
    el = document.createElement('style')
    el.id = id
    document.head.appendChild(el)
  }
  return el
}

function cssVarsToCssText(vars: Record<string, string>): string {
  const lines = Object.entries(vars)
    .map(([key, value]) => `  ${key}: ${value};`)
    .join('\n')
  return `:root {\n${lines}\n}`
}

function applyDataset(styleId: string, dark: boolean, animations: boolean): void {
  if (typeof document === 'undefined') return
  const doc = document.documentElement
  doc.dataset.style = styleId
  doc.dataset.theme = dark ? 'dark' : 'light'
  doc.dataset.animations = animations ? 'on' : 'off'
}

export const useThemeStore = defineStore('theme', () => {
  const styleId = ref(resolveInitialStyle())
  const schemeId = ref(readInitialScheme(styleId.value))
  const customCSS = ref(readInitialCustomCSS())
  const animationsEnabled = ref(readInitialAnimations())

  const currentStyle = computed(() => STYLES[styleId.value] ?? STYLES.dark)
  const dark = computed(() => currentStyle.value.dark)
  const naiveTheme = computed(() => (dark.value ? darkTheme : lightTheme))
  const currentScheme = computed(
    () =>
      currentStyle.value.schemes.find((s) => s.id === schemeId.value) ??
      currentStyle.value.schemes[0] ??
      null,
  )
  const mergedCssVars = computed(() => mergeCssVars(styleId.value, schemeId.value))
  const naiveOverrides = computed(() =>
    deriveNaiveOverrides(mergedCssVars.value, dark.value ? 'dark' : 'light'),
  )

  /** Switch style; the scheme always resets to the style's first scheme. */
  function setStyle(id: string): void {
    if (!isValidStyleId(id)) return
    const style = STYLES[id]
    styleId.value = id
    schemeId.value = style.schemes[0]?.id ?? 'default'
  }

  function setScheme(id: string): void {
    if (currentStyle.value.schemes.some((s) => s.id === id)) {
      schemeId.value = id
    }
  }

  function applyCustomCSS(css: string): void {
    let value = css
    if (value.length > MAX_CUSTOM_CSS_LENGTH) {
      console.warn('Custom CSS exceeds maximum length, truncated')
      value = value.slice(0, MAX_CUSTOM_CSS_LENGTH)
    }
    customCSS.value = value
  }

  function setAnimationsEnabled(value: boolean): void {
    animationsEnabled.value = value
  }

  /**
   * Toggle between the dark and light styles. Unlike setStyle, the current
   * scheme is preserved when the target style offers it (matches the legacy
   * light↔dark behavior); it only resets to the target's first scheme as a
   * defensive fallback.
   */
  function toggleDark(): void {
    const next = dark.value ? 'light' : 'dark'
    styleId.value = next
    if (!STYLES[next].schemes.some((s) => s.id === schemeId.value)) {
      schemeId.value = STYLES[next].schemes[0]?.id ?? 'default'
    }
  }

  /** Restore style/scheme/custom CSS defaults; animations are untouched. */
  function resetAll(): void {
    styleId.value = 'light'
    schemeId.value = STYLES.light.schemes[0]?.id ?? 'default'
    customCSS.value = ''
  }

  // Persistence: 4 state keys written back on change.
  watch(styleId, (v) => writeStorage(STYLE_KEY, v))
  watch(schemeId, (v) => writeStorage(SCHEME_KEY, v))
  watch(customCSS, (v) => writeStorage(CSS_KEY, v))
  watch(animationsEnabled, (v) => writeStorage(ANIM_KEY, v ? '1' : '0'))

  // DOM injection: merged vars + custom CSS (lazily created style elements).
  watch(
    mergedCssVars,
    (vars) => {
      const el = ensureStyleEl('fv-theme-vars')
      if (el) el.textContent = cssVarsToCssText(vars)
    },
    { immediate: true },
  )
  watch(
    customCSS,
    (css) => {
      const el = ensureStyleEl('fv-custom-css')
      if (el) el.textContent = css
    },
    { immediate: true },
  )
  watch(
    [styleId, dark, animationsEnabled],
    () => applyDataset(styleId.value, dark.value, animationsEnabled.value),
    { immediate: true },
  )

  return {
    styleId,
    schemeId,
    customCSS,
    animationsEnabled,
    dark,
    naiveTheme,
    currentStyle,
    currentScheme,
    mergedCssVars,
    naiveOverrides,
    setStyle,
    setScheme,
    applyCustomCSS,
    setAnimationsEnabled,
    toggleDark,
    resetAll,
  }
})

/**
 * Synchronous startup sync (called from main.ts before mount):
 * migrates the legacy P0 'frontend-vue-theme' key into 'frontend-vue-style',
 * writes #fv-theme-vars and the <html> dataset immediately to avoid FOUC.
 * global.css carries static BASE_COLORS as an extra pre-JS fallback.
 */
export function initThemeSync(): void {
  if (typeof document === 'undefined' || typeof localStorage === 'undefined') return
  const styleId = resolveInitialStyle()
  const style = STYLES[styleId]
  if (!style) return
  // Persist the (possibly migrated/normalized) style so the store picks it up.
  writeStorage(STYLE_KEY, styleId)
  const schemeId = readInitialScheme(styleId)
  const el = ensureStyleEl('fv-theme-vars')
  if (el) {
    el.textContent = cssVarsToCssText(mergeCssVars(styleId, schemeId))
  }
  applyDataset(styleId, style.dark, readInitialAnimations())
}
