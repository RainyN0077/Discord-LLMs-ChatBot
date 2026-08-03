/**
 * Language registry — 8 languages with their naive-ui locale pairs.
 * Every language ships a full message catalog (see src/locales/index.ts).
 */

import type { NDateLocale, NLocale } from 'naive-ui'
import {
  dateDeDE,
  dateEnUS,
  dateEsAR,
  dateFrFR,
  dateJaJP,
  dateKoKR,
  dateRuRU,
  dateZhCN,
  deDE,
  enUS,
  esAR,
  frFR,
  jaJP,
  koKR,
  ruRU,
  zhCN,
} from 'naive-ui'

export interface LanguageDef {
  code: string
  name: string
  naiveLocale: NLocale
  naiveDateLocale: NDateLocale
}

export const LANGUAGES: LanguageDef[] = [
  { code: 'zh', name: '中文', naiveLocale: zhCN, naiveDateLocale: dateZhCN },
  { code: 'en', name: 'English', naiveLocale: enUS, naiveDateLocale: dateEnUS },
  { code: 'ja', name: '日本語', naiveLocale: jaJP, naiveDateLocale: dateJaJP },
  { code: 'ko', name: '한국어', naiveLocale: koKR, naiveDateLocale: dateKoKR },
  { code: 'fr', name: 'Français', naiveLocale: frFR, naiveDateLocale: dateFrFR },
  { code: 'de', name: 'Deutsch', naiveLocale: deDE, naiveDateLocale: dateDeDE },
  { code: 'es', name: 'Español', naiveLocale: esAR, naiveDateLocale: dateEsAR },
  { code: 'ru', name: 'Русский', naiveLocale: ruRU, naiveDateLocale: dateRuRU },
]

/** Resolve a language code; unknown codes fall back to English. */
export function resolveLanguage(code: string): LanguageDef {
  return LANGUAGES.find((lang) => lang.code === code) ?? LANGUAGES[1]
}
