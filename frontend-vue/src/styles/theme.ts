/**
 * Naive UI theme overrides for frontend-vue.
 *
 * Colors mirror the legacy Svelte frontend (frontend/src/styles/global.css):
 * the dark scheme is the default, with `--primary-color: #45a3e6`.
 */

import type { GlobalThemeOverrides } from 'naive-ui'

/** Legacy primary color (dark theme `--primary-color` from global.css). */
export const PRIMARY_COLOR = '#45a3e6'

/** Legacy primary hover color (`--primary-hover` from global.css). */
export const PRIMARY_HOVER = '#2b8acc'

/** Theme overrides shared by both light and dark Naive UI themes. */
export const themeOverrides = {
  common: {
    primaryColor: PRIMARY_COLOR,
    primaryColorHover: PRIMARY_HOVER,
    primaryColorPressed: '#1a6cab',
    primaryColorSuppl: PRIMARY_HOVER,
    borderRadius: '10px',
    borderRadiusSmall: '6px',
    // borderRadiusLarge is not in this naive-ui version's type surface but
    // is accepted at runtime; kept per the migration spec.
    borderRadiusLarge: '16px',
    // Panel/typography palette mirroring the legacy Svelte dark scheme.
    bodyColor: '#0f1620',
    cardColor: '#1a2431',
    textColor: '#e5edf6',
    textColor2: '#b8c8da',
    borderColor: '#37506a',
    errorColor: '#ff8bb4',
    successColor: '#5dd9b8',
    fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif',
    fontFamilyMono: '"Fira Code", "Courier New", Consolas, monospace',
  },
} as GlobalThemeOverrides
