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

const STYLE_KEY = 'frontend-vue-style'
const SCHEME_KEY = 'frontend-vue-scheme'
const CSS_KEY = 'frontend-vue-custom-css'
const ANIM_KEY = 'frontend-vue-animations'
const LEGACY_THEME_KEY = 'frontend-vue-theme'

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
  })

  it('is a no-op for unknown legacy values (keeps default dark)', () => {
    localStorage.setItem(LEGACY_THEME_KEY, 'neon-mode')

    initThemeSync()

    expect(localStorage.getItem(STYLE_KEY)).toBe('dark')
  })
})
