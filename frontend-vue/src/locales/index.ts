/**
 * i18n instance — shared singleton so both app bootstrap (main.ts) and
 * non-setup modules (e.g. Pinia stores) can translate with `i18n.global.t`.
 */

import { createI18n } from 'vue-i18n'
import en from './en'
import zh from './zh'

const storedLang =
  typeof window !== 'undefined' ? localStorage.getItem('lang') : null

export const i18n = createI18n({
  legacy: false,
  locale: storedLang || 'zh',
  fallbackLocale: 'en',
  missingWarn: false,
  fallbackWarn: false,
  messages: { zh, en },
})
