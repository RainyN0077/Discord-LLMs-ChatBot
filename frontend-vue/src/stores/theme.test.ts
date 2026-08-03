/**
 * Unit tests for the theme store (src/stores/theme.ts).
 *
 * Focus: `dark` derivation from the active style, localStorage
 * persistence (4 keys + legacy migration key), initialization reads,
 * and the startup sync helper initThemeSync().
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { darkTheme, lightTheme } from 'naive-ui'

import { initThemeSync, MAX_CUSTOM_CSS_LENGTH, useThemeStore } from '@/stores/theme'
import {
  assertThemeDataIntegrity,
  CSS_VAR_KEYS,
  STYLE_ORDER,
  STYLES,
  mergeCssVars,
} from '@/themes/themes'
import type { CssVarMap } from '@/themes/themes'
import { deriveNaiveOverrides, STYLE_FONT_STACKS } from '@/themes/naiveMapping'
import zh from '@/locales/zh'
import en from '@/locales/en'

const STYLE_KEY = 'frontend-vue-style'
const SCHEME_KEY = 'frontend-vue-scheme'
const CSS_KEY = 'frontend-vue-custom-css'
const ANIM_KEY = 'frontend-vue-animations'
const EFFECTS_KEY = 'frontend-vue-effects'
const LEGACY_THEME_KEY = 'frontend-vue-theme'

const EFFECT_ID_LIST = [
  'grid',
  'scanline',
  'glow',
  'blink',
  'glassblur',
  'aurora',
  'sunset',
  'wash',
  'fade',
  'shine',
  'glitch',
] as const

function makeStore() {
  setActivePinia(createPinia())
  return useThemeStore()
}

beforeEach(() => {
  localStorage.clear()
})

describe('theme store — initialization from storage', () => {
  it('defaults to the dark style when nothing is stored', () => {
    const store = makeStore()
    expect(store.styleId).toBe('dark')
    expect(store.dark).toBe(true)
    expect(store.naiveTheme).toBe(darkTheme)
    expect(store.currentScheme?.id).toBe('default')
  })

  it('reads the persisted style key', () => {
    localStorage.setItem(STYLE_KEY, 'light')
    const store = makeStore()
    expect(store.styleId).toBe('light')
    expect(store.dark).toBe(false)
    expect(store.naiveTheme).toBe(lightTheme)
  })

  it('reads the persisted dark variant style (neon)', () => {
    localStorage.setItem(STYLE_KEY, 'neon')
    const store = makeStore()
    expect(store.styleId).toBe('neon')
    expect(store.dark).toBe(true)
  })

  it('migrates the legacy P0 theme key when no style key exists', () => {
    localStorage.setItem(LEGACY_THEME_KEY, 'dark')
    expect(makeStore().styleId).toBe('dark')

    localStorage.setItem(LEGACY_THEME_KEY, 'light')
    expect(makeStore().styleId).toBe('light')

    localStorage.setItem(LEGACY_THEME_KEY, 'true')
    expect(makeStore().styleId).toBe('dark')
  })

  it('ignores an unknown stored style id and falls back to dark', () => {
    localStorage.setItem(STYLE_KEY, 'no-such-style')
    expect(makeStore().styleId).toBe('dark')
  })

  it('reads the persisted scheme when it is valid for the style', () => {
    localStorage.setItem(STYLE_KEY, 'light')
    localStorage.setItem(SCHEME_KEY, 'miku')
    expect(makeStore().schemeId).toBe('miku')
  })

  it('falls back to the first scheme when the stored scheme is invalid', () => {
    localStorage.setItem(STYLE_KEY, 'dark')
    localStorage.setItem(SCHEME_KEY, 'no-such-scheme')
    expect(makeStore().schemeId).toBe('default')
  })

  it('reads persisted custom CSS and animations flags', () => {
    localStorage.setItem(CSS_KEY, 'body { color: red }')
    localStorage.setItem(ANIM_KEY, '0')
    const store = makeStore()
    expect(store.customCSS).toBe('body { color: red }')
    expect(store.animationsEnabled).toBe(false)
  })

  it('reads animations as enabled by default', () => {
    expect(makeStore().animationsEnabled).toBe(true)
  })

  it('truncates oversized persisted custom CSS', () => {
    localStorage.setItem(CSS_KEY, 'x'.repeat(MAX_CUSTOM_CSS_LENGTH + 10))
    expect(makeStore().customCSS).toHaveLength(MAX_CUSTOM_CSS_LENGTH)
  })
})

describe('theme store — dark derivation & switching', () => {
  it('setStyle switches dark/light styles and resets the scheme', () => {
    const store = makeStore() // dark
    expect(store.dark).toBe(true)

    store.setScheme('miku')
    expect(store.schemeId).toBe('miku')

    store.setStyle('minimal')
    expect(store.styleId).toBe('minimal')
    expect(store.dark).toBe(false)
    expect(store.schemeId).toBe('default') // reset to first scheme

    store.setStyle('cyberpunk')
    expect(store.dark).toBe(true)
    expect(store.schemeId).toBe('samurai') // cyberpunk's first scheme
  })

  it('ignores invalid style ids', () => {
    const store = makeStore()
    store.setStyle('bogus')
    expect(store.styleId).toBe('dark')
  })

  it('toggleDark flips between dark and light while preserving the scheme', () => {
    const store = makeStore()
    expect(store.dark).toBe(true)
    store.setScheme('miku')

    store.toggleDark()
    expect(store.styleId).toBe('light')
    expect(store.dark).toBe(false)
    expect(store.schemeId).toBe('miku') // preserved across dark↔light

    store.toggleDark()
    expect(store.styleId).toBe('dark')
    expect(store.dark).toBe(true)
  })

  it('setScheme ignores schemes not offered by the current style', () => {
    const store = makeStore() // dark → DEFAULT_SCHEMES
    store.setScheme('combat') // cyberpunk-only scheme
    expect(store.schemeId).toBe('default')
  })

  it('naiveTheme follows the dark derivation', () => {
    const store = makeStore()
    expect(store.naiveTheme).toBe(darkTheme)
    store.setStyle('light')
    expect(store.naiveTheme).toBe(lightTheme)
  })

  it('resetAll restores light style with empty custom CSS', () => {
    const store = makeStore()
    store.applyCustomCSS('body {}')
    store.setStyle('neon')

    store.resetAll()

    expect(store.styleId).toBe('light')
    expect(store.dark).toBe(false)
    expect(store.customCSS).toBe('')
    expect(store.schemeId).toBe('default')
  })
})

describe('theme store — localStorage persistence', () => {
  it('persists style changes (async watch flush)', async () => {
    const store = makeStore()
    // Initialization alone does not write back — only changes persist.
    expect(localStorage.getItem(STYLE_KEY)).toBeNull()

    store.setStyle('light')
    await nextTick()
    expect(localStorage.getItem(STYLE_KEY)).toBe('light')

    store.setStyle('minimal')
    await nextTick()
    expect(localStorage.getItem(STYLE_KEY)).toBe('minimal')
  })

  it('persists scheme changes', async () => {
    const store = makeStore()
    store.setScheme('tianyi')
    await nextTick()
    expect(localStorage.getItem(SCHEME_KEY)).toBe('tianyi')
  })

  it('persists custom CSS changes', async () => {
    const store = makeStore()
    store.applyCustomCSS('body { color: blue }')
    await nextTick()
    expect(localStorage.getItem(CSS_KEY)).toBe('body { color: blue }')
  })

  it('persists animations on/off', async () => {
    const store = makeStore()
    store.setAnimationsEnabled(false)
    await nextTick()
    expect(localStorage.getItem(ANIM_KEY)).toBe('0')
    store.setAnimationsEnabled(true)
    await nextTick()
    expect(localStorage.getItem(ANIM_KEY)).toBe('1')
  })

  it('truncates oversized custom CSS and warns', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    try {
      const store = makeStore()
      store.applyCustomCSS('y'.repeat(MAX_CUSTOM_CSS_LENGTH + 5))
      expect(store.customCSS).toHaveLength(MAX_CUSTOM_CSS_LENGTH)
      expect(warnSpy).toHaveBeenCalled()
      await nextTick()
      expect(localStorage.getItem(CSS_KEY)).toHaveLength(MAX_CUSTOM_CSS_LENGTH)
    } finally {
      warnSpy.mockRestore()
    }
  })
})

describe('theme store — DOM side effects', () => {
  it('injects the merged vars style element on creation (immediate watch)', () => {
    makeStore()
    const el = document.getElementById('fv-theme-vars')
    expect(el).not.toBeNull()
    expect(el!.textContent).toContain(':root')
    expect(el!.textContent).toContain('--primary-color')
  })

  it('injects custom CSS into its own style element', async () => {
    const store = makeStore()
    store.applyCustomCSS('body { color: red }')
    await nextTick()
    const el = document.getElementById('fv-custom-css')
    expect(el).not.toBeNull()
    expect(el!.textContent).toBe('body { color: red }')
  })

  it('updates the <html> dataset for style/theme/animations', async () => {
    const store = makeStore()
    const doc = document.documentElement
    expect(doc.dataset.style).toBe('dark')
    expect(doc.dataset.theme).toBe('dark')
    expect(doc.dataset.animations).toBe('on')

    store.setStyle('light')
    await nextTick()
    expect(doc.dataset.style).toBe('light')
    expect(doc.dataset.theme).toBe('light')

    store.setAnimationsEnabled(false)
    await nextTick()
    expect(doc.dataset.animations).toBe('off')
  })
})

describe('theme store — effects', () => {
  it('enables every effect by default and lists all ids in the dataset', () => {
    const store = makeStore()
    for (const id of EFFECT_ID_LIST) {
      expect(store.effects[id]).toBe(true)
    }
    const enabled = (document.documentElement.dataset.effects ?? '').split(' ')
    for (const id of EFFECT_ID_LIST) {
      expect(enabled).toContain(id)
    }
  })

  it('persists a toggled-off effect to localStorage as JSON false', async () => {
    const store = makeStore()
    store.toggleEffect('grid')
    await nextTick()
    const parsed = JSON.parse(localStorage.getItem(EFFECTS_KEY) ?? '{}')
    expect(parsed.grid).toBe(false)
    expect(parsed.scanline).toBe(true) // untouched effects stay enabled
  })

  it('drops the toggled-off effect id from the dataset', async () => {
    const store = makeStore()
    store.toggleEffect('scanline')
    await nextTick()
    const enabled = (document.documentElement.dataset.effects ?? '').split(' ')
    expect(enabled).not.toContain('scanline')
    expect(enabled).toContain('grid') // other effects unaffected
  })

  it('resetAll re-enables every effect', async () => {
    const store = makeStore()
    store.toggleEffect('grid')
    store.toggleEffect('glow')
    await nextTick()

    store.resetAll()
    await nextTick()

    expect(store.effects.grid).toBe(true)
    expect(store.effects.glow).toBe(true)
    const enabled = (document.documentElement.dataset.effects ?? '').split(' ')
    for (const id of EFFECT_ID_LIST) {
      expect(enabled).toContain(id)
    }
  })

  it('falls back to fully enabled when the stored JSON is corrupt', () => {
    localStorage.setItem(EFFECTS_KEY, '{oops not json')
    const store = makeStore()
    for (const id of EFFECT_ID_LIST) {
      expect(store.effects[id]).toBe(true)
    }
  })

  it('reads partially disabled persisted effects', () => {
    localStorage.setItem(EFFECTS_KEY, JSON.stringify({ grid: false }))
    const store = makeStore()
    expect(store.effects.grid).toBe(false)
    expect(store.effects.scanline).toBe(true)
    expect(store.effects.glassblur).toBe(true)
  })

  it('availableEffects follows the active style', () => {
    const store = makeStore() // 'dark' — no effect applies
    expect(store.availableEffects).toEqual([])

    store.setStyle('neon')
    expect(store.availableEffects.map((e) => e.id).sort()).toEqual(
      ['grid', 'glow', 'blink'].sort(),
    )

    store.setStyle('cyberpunk')
    expect(store.availableEffects.map((e) => e.id).sort()).toEqual(
      ['grid', 'scanline', 'glow', 'blink', 'glitch'].sort(),
    )

    store.setStyle('glass')
    expect(store.availableEffects.map((e) => e.id)).toEqual(['glassblur'])

    // Wave 1 — aurora (EFFECT_DEFS derived, stable since Wave 1 registers
    // all 10 ids; the remaining styles follow in Wave 2-4).
    store.setStyle('aurora')
    expect(store.availableEffects.map((e) => e.id).sort()).toEqual(
      ['aurora', 'glassblur', 'glow'].sort(),
    )

    // Wave 2 — matrix / synthwave.
    store.setStyle('matrix')
    expect(store.availableEffects.map((e) => e.id).sort()).toEqual(
      ['grid', 'scanline', 'blink', 'glow'].sort(),
    )

    store.setStyle('synthwave')
    expect(store.availableEffects.map((e) => e.id).sort()).toEqual(
      ['sunset', 'grid', 'scanline', 'glow'].sort(),
    )

    // Wave 3 — zen (no effects → shared noEffects empty state) / ink.
    store.setStyle('zen')
    expect(store.availableEffects).toEqual([])

    store.setStyle('ink')
    expect(store.availableEffects.map((e) => e.id).sort()).toEqual(
      ['wash', 'fade'].sort(),
    )

    // Wave 4 — pixel.
    store.setStyle('pixel')
    expect(store.availableEffects.map((e) => e.id).sort()).toEqual(
      ['blink', 'scanline', 'shine'].sort(),
    )
  })

  it('legacy 5-key effects JSON keeps new ids enabled by default', () => {
    // A pre-refactor localStorage payload only knows the original 5 ids;
    // readInitialEffects defaults missing ids to true (backward compat).
    localStorage.setItem(
      EFFECTS_KEY,
      JSON.stringify({ grid: false, scanline: true, glow: true, blink: true, glassblur: true }),
    )
    const store = makeStore()
    expect(store.effects.grid).toBe(false)
    for (const id of ['scanline', 'glow', 'blink', 'glassblur', 'aurora', 'sunset', 'wash', 'fade', 'shine']) {
      expect(store.effects[id]).toBe(true)
    }
  })

  it('ignores unknown ids in toggleEffect', async () => {
    const store = makeStore()
    store.toggleEffect('no-such-effect')
    await nextTick()
    // No state change → nothing is written back (initialization never writes).
    expect(localStorage.getItem(EFFECTS_KEY)).toBeNull()
  })
})

describe('initThemeSync — startup migration', () => {
  it('migrates the legacy key, writes the style key and applies the dataset', () => {
    localStorage.setItem(LEGACY_THEME_KEY, 'dark')

    initThemeSync()

    expect(localStorage.getItem(STYLE_KEY)).toBe('dark')
    const el = document.getElementById('fv-theme-vars')
    expect(el).not.toBeNull()
    expect(el!.textContent).toContain('--primary-color')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(document.documentElement.dataset.style).toBe('dark')
    // Effects default to fully enabled, so data-effects lists every id.
    expect(document.documentElement.dataset.effects).toContain('grid')
  })

  it('is a no-op for unknown legacy values (keeps default dark)', () => {
    localStorage.setItem(LEGACY_THEME_KEY, 'neon-mode')

    initThemeSync()

    expect(localStorage.getItem(STYLE_KEY)).toBe('dark')
  })
})

describe('new style data integrity — Wave 1 (aurora)', () => {
  it('passes assertThemeDataIntegrity (DEV hard constraint)', () => {
    expect(() => assertThemeDataIntegrity()).not.toThrow()
  })

  it("registers aurora with dark classification, ≥1 scheme and STYLE_ORDER sync", () => {
    const style = STYLES.aurora
    expect(style).toBeDefined()
    expect(style.dark).toBe(true)
    expect(style.schemes.length).toBeGreaterThanOrEqual(1)
    expect(STYLE_ORDER).toContain('aurora')
  })

  it('merges all 48 CSS_VAR_KEYS non-empty for aurora × every scheme', () => {
    const style = STYLES.aurora
    for (const scheme of style.schemes) {
      const merged = mergeCssVars('aurora', scheme.id)
      for (const key of CSS_VAR_KEYS) {
        const value = merged[key]
        expect(value, `aurora/${scheme.id} missing or empty '${key}'`).toBeTruthy()
      }
    }
  })
})

describe('new style data integrity — Wave 2 (synthwave + matrix)', () => {
  it("registers synthwave/matrix with dark classification, ≥1 scheme and STYLE_ORDER sync", () => {
    for (const id of ['synthwave', 'matrix']) {
      const style = STYLES[id]
      expect(style, `${id} registered`).toBeDefined()
      expect(style.dark, `${id} is dark`).toBe(true)
      expect(style.schemes.length, `${id} has schemes`).toBeGreaterThanOrEqual(1)
      expect(STYLE_ORDER, `${id} in STYLE_ORDER`).toContain(id)
    }
  })

  it('merges all 48 CSS_VAR_KEYS non-empty for synthwave/matrix × every scheme', () => {
    for (const styleId of ['synthwave', 'matrix']) {
      const style = STYLES[styleId]
      for (const scheme of style.schemes) {
        const merged = mergeCssVars(styleId, scheme.id)
        for (const key of CSS_VAR_KEYS) {
          const value = merged[key]
          expect(value, `${styleId}/${scheme.id} missing or empty '${key}'`).toBeTruthy()
        }
      }
    }
  })
})

describe('new style data integrity — Wave 3 (zen + ink)', () => {
  it("registers zen/ink as light styles with ≥1 scheme and STYLE_ORDER sync", () => {
    for (const id of ['zen', 'ink']) {
      const style = STYLES[id]
      expect(style, `${id} registered`).toBeDefined()
      expect(style.dark, `${id} is light (dark:false)`).toBe(false)
      expect(style.schemes.length, `${id} has schemes`).toBeGreaterThanOrEqual(1)
      expect(STYLE_ORDER, `${id} in STYLE_ORDER`).toContain(id)
    }
  })

  it('merges all 48 CSS_VAR_KEYS non-empty for zen/ink × every scheme', () => {
    for (const styleId of ['zen', 'ink']) {
      const style = STYLES[styleId]
      for (const scheme of style.schemes) {
        const merged = mergeCssVars(styleId, scheme.id)
        for (const key of CSS_VAR_KEYS) {
          const value = merged[key]
          expect(value, `${styleId}/${scheme.id} missing or empty '${key}'`).toBeTruthy()
        }
      }
    }
  })

  // M1 (design §2.2): zen's private schemes are NOT in SCHEME_ORDER, so the
  // integrity light/dark key-set check (which only walks SCHEME_ORDER) does
  // not cover them. These assertions explicitly take over that guarantee:
  // both schemes carry 38 keys in each set (20 palette + 14 panel + 4
  // scheme-only sidebar) and the key sets are identical.
  it('M1: zen exposes exactly two schemes with zen-paper first', () => {
    expect(STYLES.zen.schemes.map((s) => s.id)).toEqual(['zen-paper', 'zen-night'])
  })

  it('M1: both private zen schemes have 38 keys in light and dark with identical key sets', () => {
    for (const scheme of STYLES.zen.schemes) {
      const lightKeys = Object.keys(scheme.cssVars.light).sort()
      const darkKeys = Object.keys(scheme.cssVars.dark).sort()
      expect(lightKeys, `${scheme.id} light key count`).toHaveLength(38)
      expect(darkKeys, `${scheme.id} dark key count`).toHaveLength(38)
      expect(darkKeys, `${scheme.id} light/dark key sets`).toEqual(lightKeys)
    }
  })

  it('M1: zen-paper carries the paper palette and zen-night the ink-night palette', () => {
    const paper = STYLES.zen.schemes.find((s) => s.id === 'zen-paper')!
    const night = STYLES.zen.schemes.find((s) => s.id === 'zen-night')!
    // dark:false → mergeCssVars always picks the .light set; the variant
    // values live there (zen.html :root vs html.dark, verbatim).
    expect(mergeCssVars('zen', paper.id)['--bg-color']).toBe('#faf8f5')
    expect(mergeCssVars('zen', paper.id)['--primary-color']).toBe('#3b5bdb')
    expect(mergeCssVars('zen', night.id)['--bg-color']).toBe('#16181d')
    expect(mergeCssVars('zen', night.id)['--primary-color']).toBe('#7b93f5')
  })
})

describe('new style data integrity — Wave 4 (pixel)', () => {
  it('registers pixel as a dark style with ≥1 scheme and STYLE_ORDER sync', () => {
    expect(STYLES.pixel.dark).toBe(true)
    expect(STYLES.pixel.schemes.length).toBeGreaterThanOrEqual(1)
    expect(STYLE_ORDER).toContain('pixel')
    expect(STYLE_ORDER.indexOf('pixel')).toBe(STYLE_ORDER.length - 1)
  })

  it('merges all 48 CSS_VAR_KEYS non-empty for pixel × every scheme', () => {
    for (const scheme of STYLES.pixel.schemes) {
      const merged = mergeCssVars('pixel', scheme.id)
      for (const key of CSS_VAR_KEYS) {
        const value = merged[key]
        expect(value, `pixel/${scheme.id} missing or empty '${key}'`).toBeTruthy()
      }
    }
  })

  it('ships zero radius via cssVars (naiveMapping double condition activates)', () => {
    expect(STYLES.pixel.cssVars['--radius-md']).toBe('0px')
    expect(STYLES.pixel.cssVars['--radius-lg']).toBe('0px')
  })
})

describe('deriveNaiveOverrides — pixel corner special-case (H1)', () => {
  it('keeps borderRadiusSmall 6px for minimal/cyberpunk (value-only check would drift the baseline)', () => {
    // Both styles ship '--radius-md: 0px' in their real merged vars; the
    // styleId filter must run first so neither drifts to 0px.
    const minimalVars = mergeCssVars('minimal', STYLES.minimal.schemes[0].id)
    expect(minimalVars['--radius-md']).toBe('0px')
    expect(deriveNaiveOverrides(minimalVars, 'light', 'minimal').common?.borderRadiusSmall).toBe('6px')

    const cyberpunkVars = mergeCssVars('cyberpunk', STYLES.cyberpunk.schemes[0].id)
    expect(cyberpunkVars['--radius-md']).toBe('0px')
    expect(deriveNaiveOverrides(cyberpunkVars, 'dark', 'cyberpunk').common?.borderRadiusSmall).toBe('6px')
  })

  it('forces borderRadiusSmall 0px only under the double condition (styleId pixel + radius 0px)', () => {
    // Identical vars across three styleIds: only 'pixel' must zero the
    // small radius (pixel itself registers in Wave 4; the mapping is
    // data-ready from Wave 1 and must not fire for other styles).
    const vars: CssVarMap = { ...mergeCssVars('dark', 'default'), '--radius-md': '0px' }
    expect(deriveNaiveOverrides(vars, 'dark', 'minimal').common?.borderRadiusSmall).toBe('6px')
    expect(deriveNaiveOverrides(vars, 'dark', 'cyberpunk').common?.borderRadiusSmall).toBe('6px')
    expect(deriveNaiveOverrides(vars, 'dark', 'pixel').common?.borderRadiusSmall).toBe('0px')
  })

  it('applies the mono font stack only to matrix (STYLE_FONT_STACKS)', () => {
    // Matrix must receive the mono stack via the mapping; every other
    // style must keep the base fontFamily untouched (no leakage).
    expect(STYLE_FONT_STACKS.matrix?.fontFamily).toBe('var(--font-mono)')

    const matrixVars = mergeCssVars('matrix', STYLES.matrix.schemes[0].id)
    expect(deriveNaiveOverrides(matrixVars, 'dark', 'matrix').common?.fontFamily).toBe('var(--font-mono)')

    const darkVars = mergeCssVars('dark', 'default')
    expect(deriveNaiveOverrides(darkVars, 'dark', 'dark').common?.fontFamily).not.toContain('var(--font-mono)')

    const pixelVars = mergeCssVars('pixel', STYLES.pixel.schemes[0].id)
    expect(deriveNaiveOverrides(pixelVars, 'dark', 'pixel').common?.fontFamily).not.toContain('var(--font-mono)')
  })
})

describe('i18n — new effect label keys (Wave 1)', () => {
  it('exposes the five new effect label keys in both zh.ts and en.ts', () => {
    const keys = ['effectAurora', 'effectSunset', 'effectWash', 'effectFade', 'effectShine'] as const
    for (const key of keys) {
      expect(zh.appearance[key], `zh.appearance.${key}`).toBeTruthy()
      expect(en.appearance[key], `en.appearance.${key}`).toBeTruthy()
    }
  })
})
