/**
 * i18n instance — shared singleton so both app bootstrap (main.ts) and
 * non-setup modules (e.g. Pinia stores) can translate with `i18n.global.t`.
 *
 * zh/en have real catalogs; the other 6 languages reuse the English catalog
 * and only switch naive-ui's component locale (see src/locales/languages.ts).
 */

import { createI18n } from 'vue-i18n'
import { LANGUAGES } from './languages'
import en from './en'
import zh from './zh'

/** Read the persisted language; null on absence or storage failure. */
function readStoredLang(): string | null {
  if (typeof window === 'undefined') return null
  try {
    return localStorage.getItem('lang')
  } catch {
    return null
  }
}

/** A code is valid only when it exists in the language registry. */
function isValidLang(code: string | null): code is string {
  return code !== null && LANGUAGES.some((lang) => lang.code === code)
}

const storedLang = readStoredLang()

export const i18n = createI18n({
  legacy: false,
  locale: isValidLang(storedLang) ? storedLang : 'zh',
  fallbackLocale: 'en',
  missingWarn: false,
  fallbackWarn: false,
  messages: { zh, en, ja: en, ko: en, fr: en, de: en, es: en, ru: en },
})
