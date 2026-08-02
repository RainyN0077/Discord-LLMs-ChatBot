/**
 * Theme store — style / scheme / custom CSS / animation settings with
 * localStorage persistence, CSS variable injection and naive-ui overrides.
 *
 * State is persisted under five keys:
 *   frontend-vue-style / frontend-vue-scheme / frontend-vue-custom-css /
 *   frontend-vue-animations / frontend-vue-effects
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
const EFFECTS_KEY = 'frontend-vue-effects'
const LEGACY_THEME_KEY = 'frontend-vue-theme'

/**
 * 50KB（50000 字符）custom CSS cap, aligned with the legacy frontend's
 * frontend/src/lib/themeStore.js MAX_CUSTOM_CSS_LENGTH.
 */
export const MAX_CUSTOM_CSS_LENGTH = 50000

/**
 * Decorative effect definition. Each effect maps to a `[data-effects~='<id>']`
 * dataset hook in global.css; toggling an effect only affects the animation /
 * filter / decoration layers, never layout, colors, fonts or spacing.
 */
export interface EffectDef {
  id: string
  /** i18n key, e.g. 'appearance.effectGrid'. */
  labelKey: string
  /** Style ids the effect applies to (neon / cyberpunk / glass). */
  styles: string[]
}

export const EFFECT_DEFS: EffectDef[] = [
  { id: 'grid', labelKey: 'appearance.effectGrid', styles: ['neon', 'cyberpunk', 'matrix', 'synthwave'] },
  { id: 'scanline', labelKey: 'appearance.effectScanline', styles: ['cyberpunk', 'matrix', 'synthwave', 'pixel'] },
  { id: 'glow', labelKey: 'appearance.effectGlow', styles: ['neon', 'cyberpunk', 'aurora', 'matrix', 'synthwave'] },
  { id: 'blink', labelKey: 'appearance.effectBlink', styles: ['neon', 'cyberpunk', 'matrix', 'pixel'] },
  { id: 'glassblur', labelKey: 'appearance.effectGlassblur', styles: ['glass', 'aurora'] },
  { id: 'aurora', labelKey: 'appearance.effectAurora', styles: ['aurora'] },
  { id: 'sunset', labelKey: 'appearance.effectSunset', styles: ['synthwave'] },
  { id: 'wash', labelKey: 'appearance.effectWash', styles: ['ink'] },
  { id: 'fade', labelKey: 'appearance.effectFade', styles: ['ink'] },
  { id: 'shine', labelKey: 'appearance.effectShine', styles: ['pixel'] },
]

export const EFFECT_IDS = EFFECT_DEFS.map((e) => e.id) as readonly string[]

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

/**
 * Read the persisted effect toggles. Missing keys, corrupt JSON and unknown
 * ids all fall back to enabled (`true`) — effects default to fully on.
 */
function readInitialEffects(): Record<string, boolean> {
  const stored = readStorage(EFFECTS_KEY)
  if (stored !== null) {
    try {
      const parsed: unknown = JSON.parse(stored)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        const effects: Record<string, boolean> = {}
        for (const id of EFFECT_IDS) {
          effects[id] = (parsed as Record<string, unknown>)[id] !== false
        }
        return effects
      }
    } catch {
      // corrupt JSON → fall through to fully enabled
    }
  }
  return allEffectsEnabled()
}

function allEffectsEnabled(): Record<string, boolean> {
  return Object.fromEntries(EFFECT_IDS.map((id) => [id, true]))
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

/**
 * Write the enabled effect ids as a space-separated list on <html>
 * (`data-effects='grid scanline ...'`), so CSS can select per effect with
 * `[data-effects~='<id>']`. Fully enabled writes every id (default).
 */
function applyEffectsDataset(effects: Record<string, boolean>): void {
  if (typeof document === 'undefined') return
  const enabled = EFFECT_IDS.filter((id) => effects[id])
  document.documentElement.dataset.effects = enabled.join(' ')
}

export const useThemeStore = defineStore('theme', () => {
  const styleId = ref(resolveInitialStyle())
  const schemeId = ref(readInitialScheme(styleId.value))
  const customCSS = ref(readInitialCustomCSS())
  const animationsEnabled = ref(readInitialAnimations())
  const effects = ref<Record<string, boolean>>(readInitialEffects())

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
    deriveNaiveOverrides(
      mergedCssVars.value,
      dark.value ? 'dark' : 'light',
      styleId.value,
    ),
  )
  /** Effects whose definition lists the currently active style. */
  const availableEffects = computed(() =>
    EFFECT_DEFS.filter((e) => e.styles.includes(styleId.value)),
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

  /** Flip one effect toggle (replacing the ref to keep the watch simple). */
  function toggleEffect(id: string): void {
    if (!EFFECT_IDS.includes(id)) return
    effects.value = { ...effects.value, [id]: !effects.value[id] }
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

  /**
   * Restore style/scheme/custom CSS defaults and re-enable all effects
   * (matching the "reset all" semantics of the appearance page).
   */
  function resetAll(): void {
    styleId.value = 'light'
    schemeId.value = STYLES.light.schemes[0]?.id ?? 'default'
    customCSS.value = ''
    effects.value = allEffectsEnabled()
  }

  // Persistence: 5 state keys written back on change.
  watch(styleId, (v) => writeStorage(STYLE_KEY, v))
  watch(schemeId, (v) => writeStorage(SCHEME_KEY, v))
  watch(customCSS, (v) => writeStorage(CSS_KEY, v))
  watch(animationsEnabled, (v) => writeStorage(ANIM_KEY, v ? '1' : '0'))
  watch(effects, (v) => writeStorage(EFFECTS_KEY, JSON.stringify(v)), { deep: true })

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
  watch(
    effects,
    (v) => applyEffectsDataset(v),
    { immediate: true, deep: true },
  )

  return {
    styleId,
    schemeId,
    customCSS,
    animationsEnabled,
    effects,
    dark,
    naiveTheme,
    currentStyle,
    currentScheme,
    mergedCssVars,
    naiveOverrides,
    availableEffects,
    setStyle,
    setScheme,
    applyCustomCSS,
    setAnimationsEnabled,
    toggleEffect,
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
  // Effects default to fully enabled; write data-effects synchronously so the
  // decoration hooks in global.css behave identically to the no-toggle state.
  applyEffectsDataset(readInitialEffects())
}
