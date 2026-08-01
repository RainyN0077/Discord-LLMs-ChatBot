/**
 * Theme store — dark mode default with localStorage persistence.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { darkTheme, lightTheme } from 'naive-ui'

const STORAGE_KEY = 'frontend-vue-theme'

function readInitialDark(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored !== null) return stored === 'dark'
  } catch {
    // Storage unavailable — fall through to default.
  }
  return true // dark is the default, matching the legacy theme
}

export const useThemeStore = defineStore('theme', () => {
  const dark = ref(readInitialDark())

  const naiveTheme = computed(() => (dark.value ? darkTheme : lightTheme))

  /** Mirror the theme on <html data-theme> so plain CSS can adapt (log colors etc.). */
  function syncDomTheme(value: boolean): void {
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = value ? 'dark' : 'light'
    }
  }

  function setDark(value: boolean): void {
    dark.value = value
    syncDomTheme(value)
    try {
      localStorage.setItem(STORAGE_KEY, value ? 'dark' : 'light')
    } catch {
      // ignore persistence failures
    }
  }

  function toggle(): void {
    setDark(!dark.value)
  }

  // Apply on first load so CSS variables match the persisted theme.
  syncDomTheme(dark.value)

  return { dark, naiveTheme, setDark, toggle }
})
