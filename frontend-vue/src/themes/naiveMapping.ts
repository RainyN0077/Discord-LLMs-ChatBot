/**
 * Naive UI mapping — bridges the 48 CSS variable theme into naive-ui
 * `theme-overrides`. The 11 mapped keys derive from the merged CSS vars;
 * every other naive key falls back to the static dark/light override sets
 * in src/styles/theme.ts.
 */

import type { GlobalThemeOverrides } from 'naive-ui'

import type { CssVarMap } from '@/themes/themes'
import { darkOverrides, lightOverrides } from '@/styles/theme'

/** CSS variable → naive-ui common token (11 mappings). */
export const NAIVE_MAP: Record<string, string> = {
  '--primary-color': 'primaryColor',
  '--primary-hover': 'primaryColorHover',
  '--bg-color': 'bodyColor',
  '--card-bg': 'cardColor',
  '--text-color': 'textColor',
  '--text-light': 'textColor2',
  '--border-color': 'borderColor',
  '--error-text': 'errorColor',
  '--success-text': 'successColor',
  '--radius-md': 'borderRadius',
  '--radius-lg': 'borderRadiusLarge',
}

/**
 * Derive naive-ui theme overrides from merged CSS vars.
 * Keys present in the merged map override the base palette; everything
 * else keeps the base (dark/light) fallback values.
 */
export function deriveNaiveOverrides(
  vars: CssVarMap,
  base: 'dark' | 'light',
): GlobalThemeOverrides {
  const baseOverrides = base === 'dark' ? darkOverrides : lightOverrides
  const common: Record<string, string> = { ...(baseOverrides.common ?? {}) }
  for (const [cssVar, naiveKey] of Object.entries(NAIVE_MAP)) {
    const value = vars[cssVar]
    if (value !== undefined && value !== '') {
      common[naiveKey] = value
    }
  }
  return { common } as GlobalThemeOverrides
}
