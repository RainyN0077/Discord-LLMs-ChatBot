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
 * Per-style naive font overrides (design §2.4 dual-channel font solution).
 * `fontFamily: 'var(--font-mono)'` references the mono stack defined in
 * global.css :root — legal in the `font-family` shorthand context, so naive
 * components follow the site-wide mono switch for the matrix terminal look.
 * Keys omitted for a style fall back to the base static stacks.
 */
export const STYLE_FONT_STACKS: Partial<
  Record<string, { fontFamily?: string; fontFamilyMono?: string }>
> = {
  matrix: { fontFamily: 'var(--font-mono)', fontFamilyMono: 'var(--font-mono)' },
}

/**
 * Derive naive-ui theme overrides from merged CSS vars.
 * Keys present in the merged map override the base palette; everything
 * else keeps the base (dark/light) fallback values.
 *
 * `styleId` (third param, required) gates per-style adjustments:
 * - STYLE_FONT_STACKS (matrix → mono stacks);
 * - pixel corner zeroing — `borderRadiusSmall` is a static 6px in
 *   styles/theme.ts and has no NAIVE_MAP entry, so it is forced to '0px'
 *   only under the DOUBLE condition `styleId === 'pixel'` AND
 *   `--radius-md === '0px'`. The styleId filter must come first:
 *   minimal / cyberpunk already carry '0px' radius tokens and must keep
 *   their 6px borderRadiusSmall (no baseline drift).
 */
export function deriveNaiveOverrides(
  vars: CssVarMap,
  base: 'dark' | 'light',
  styleId: string,
): GlobalThemeOverrides {
  const baseOverrides = base === 'dark' ? darkOverrides : lightOverrides
  const common: Record<string, string> = { ...(baseOverrides.common ?? {}) }
  for (const [cssVar, naiveKey] of Object.entries(NAIVE_MAP)) {
    const value = vars[cssVar]
    if (value !== undefined && value !== '') {
      common[naiveKey] = value
    }
  }
  const stack = STYLE_FONT_STACKS[styleId]
  if (stack) {
    if (stack.fontFamily) common.fontFamily = stack.fontFamily
    if (stack.fontFamilyMono) common.fontFamilyMono = stack.fontFamilyMono
  }
  if (styleId === 'pixel' && vars['--radius-md'] === '0px') {
    common.borderRadiusSmall = '0px'
  }
  return { common } as GlobalThemeOverrides
}
