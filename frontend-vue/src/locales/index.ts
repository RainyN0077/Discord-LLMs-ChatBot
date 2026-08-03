/**
 * i18n instance — shared singleton so both app bootstrap (main.ts) and
 * non-setup modules (e.g. Pinia stores) can translate with `i18n.global.t`.
 *
 * All 8 languages ship real message catalogs; naive-ui's component locale is
 * switched alongside via src/locales/languages.ts.
 */

import { createI18n } from 'vue-i18n'
import { LANGUAGES } from './languages'
import de from './de'
import en from './en'
import es from './es'
import fr from './fr'
import ja from './ja'
import ko from './ko'
import ru from './ru'
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
  messages: { zh, en, ja, ko, fr, de, es, ru },
})
