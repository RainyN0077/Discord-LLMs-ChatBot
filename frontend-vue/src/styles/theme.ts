/**
 * Naive UI theme overrides for frontend-vue.
 *
 * Colors mirror the legacy Svelte frontend (frontend/src/styles/global.css):
 * the dark scheme is the default, with `--primary-color: #45a3e6`.
 * Light and dark each get their own override set so theme switching
 * actually re-colors the page (a shared palette would pin the dark
 * colors onto the light theme).
 */

import type { GlobalThemeOverrides } from 'naive-ui'

/** Legacy primary color (dark theme `--primary-color` from global.css). */
export const PRIMARY_COLOR = '#45a3e6'

/** Legacy primary hover color (`--primary-hover` from global.css). */
export const PRIMARY_HOVER = '#2b8acc'

const FONT_FAMILY =
  '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif'
const FONT_FAMILY_MONO = '"Fira Code", "Courier New", Consolas, monospace'

/**
 * Common shape shared by both palettes: border radii + font stacks.
 * Palette-specific colors live in each override set below.
 */
function baseCommon(): Record<string, string> {
  return {
    borderRadius: '10px',
    borderRadiusSmall: '6px',
    // borderRadiusLarge is not in this naive-ui version's type surface but
    // is accepted at runtime; kept per the migration spec.
    borderRadiusLarge: '16px',
    fontFamily: FONT_FAMILY,
    fontFamilyMono: FONT_FAMILY_MONO,
  }
}

/** Dark palette (legacy `:root[data-theme='dark']` from global.css). */
export const darkOverrides = {
  common: {
    ...baseCommon(),
    primaryColor: PRIMARY_COLOR,
    primaryColorHover: PRIMARY_HOVER,
    primaryColorPressed: '#1a6cab',
    primaryColorSuppl: PRIMARY_HOVER,
    bodyColor: '#0f1620',
    cardColor: '#1a2431',
    textColor: '#e5edf6',
    textColor2: '#b8c8da',
    borderColor: '#37506a',
    errorColor: '#ff8bb4',
    successColor: '#5dd9b8',
  },
} as GlobalThemeOverrides

/** Light palette (legacy `:root` from global.css). */
export const lightOverrides = {
  common: {
    ...baseCommon(),
    primaryColor: '#1f8bd6',
    primaryColorHover: '#1a75b8',
    primaryColorPressed: '#15649e',
    primaryColorSuppl: '#1a75b8',
    bodyColor: '#eef2f7',
    cardColor: '#ffffff',
    textColor: '#1f2a37',
    textColor2: '#66768a',
    borderColor: '#dde5ee',
    errorColor: '#c2185b',
    successColor: '#00796b',
  },
} as GlobalThemeOverrides
