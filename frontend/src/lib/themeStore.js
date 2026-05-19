import { writable, get } from 'svelte/store';
import { STYLES } from './themes.js';

const BASE_COLORS = {
  light: {
    '--bg-color': '#eef2f7',
    '--card-bg': '#fff',
    '--text-color': '#1f2a37',
    '--text-light': '#66768a',
    '--primary-color': '#1f8bd6',
    '--primary-hover': '#1c75b5',
    '--border-color': '#dde5ee',
    '--surface-tint': '#f8fbff',
    '--success-bg': '#e0f2f1',
    '--success-text': '#00796b',
    '--error-bg': '#fce4ec',
    '--error-text': '#c2185b',
    '--info-bg': '#e1f5fe',
    '--info-text': '#0277bd',
    '--save-color': '#1ea864',
    '--save-hover': '#188a51',
    '--log-shell-bg': '#1e1e1e',
    '--log-text-color': '#d4d4d4',
    '--log-time-color': '#9e9e9e',
    '--sidebar-active-indicator': '#1f8bd6',
  },
  dark: {
    '--bg-color': '#0f1620',
    '--card-bg': '#1a2431',
    '--text-color': '#e5edf6',
    '--text-light': '#b8c8da',
    '--primary-color': '#45a3e6',
    '--primary-hover': '#2b8acc',
    '--border-color': '#37506a',
    '--surface-tint': '#152434',
    '--success-bg': '#12362c',
    '--success-text': '#5dd9b8',
    '--error-bg': '#421d30',
    '--error-text': '#ff8bb4',
    '--info-bg': '#0f3348',
    '--info-text': '#88d1ff',
    '--save-color': '#2bb36f',
    '--save-hover': '#1f995d',
    '--log-shell-bg': '#101821',
    '--log-text-color': '#d2deea',
    '--log-time-color': '#8fa1b5',
    '--sidebar-active-indicator': '#45a3e6',
  },
  neon: {
    '--bg-color': '#06060d',
    '--card-bg': '#0e0e1a',
    '--text-color': '#f0f2ff',
    '--text-light': '#8b90b8',
    '--primary-color': '#00e5ff',
    '--primary-hover': '#00b8d4',
    '--border-color': 'rgba(0, 229, 255, .25)',
    '--surface-tint': '#12122a',
    '--success-bg': 'rgba(0, 255, 136, .12)',
    '--success-text': '#00ff88',
    '--error-bg': 'rgba(255, 51, 102, .14)',
    '--error-text': '#ff3366',
    '--info-bg': 'rgba(102, 170, 255, .12)',
    '--info-text': '#66aaff',
    '--save-color': '#00ff88',
    '--save-hover': '#00cc6a',
    '--log-shell-bg': '#080814',
    '--log-text-color': '#c8d6e5',
    '--log-time-color': '#6e7896',
    '--sidebar-active-indicator': '#00e5ff',
  },
  glass: {
    '--bg-color': '#1a1a2e',
    '--card-bg': 'rgba(255, 255, 255, .08)',
    '--text-color': '#e8e8f0',
    '--text-light': '#a0a0b8',
    '--primary-color': '#7c8aff',
    '--primary-hover': '#6a78e0',
    '--border-color': 'rgba(255, 255, 255, .12)',
    '--surface-tint': 'rgba(255, 255, 255, .04)',
    '--success-bg': 'rgba(0, 230, 118, .15)',
    '--success-text': '#00e676',
    '--error-bg': 'rgba(255, 82, 82, .15)',
    '--error-text': '#ff5252',
    '--info-bg': 'rgba(68, 138, 255, .15)',
    '--info-text': '#448aff',
    '--save-color': '#00e676',
    '--save-hover': '#00c853',
    '--log-shell-bg': 'rgba(0, 0, 0, .4)',
    '--log-text-color': '#d2d2e0',
    '--log-time-color': '#8888a8',
    '--sidebar-active-indicator': '#7c8aff',
  },
  minimal: {
    '--bg-color': '#fafafa',
    '--card-bg': '#fff',
    '--text-color': '#1a1a1a',
    '--text-light': '#666',
    '--primary-color': '#1a1a1a',
    '--primary-hover': '#333',
    '--border-color': '#d0d0d0',
    '--surface-tint': '#f5f5f5',
    '--success-bg': '#e8f5e9',
    '--success-text': '#2e7d32',
    '--error-bg': '#fce4ec',
    '--error-text': '#c62828',
    '--info-bg': '#e3f2fd',
    '--info-text': '#1565c0',
    '--save-color': '#1a1a1a',
    '--save-hover': '#333',
    '--log-shell-bg': '#1a1a1a',
    '--log-text-color': '#d4d4d4',
    '--log-time-color': '#888',
    '--sidebar-active-indicator': '#1a1a1a',
  },
  dawn: {
    '--bg-color': '#fdf6ee',
    '--card-bg': '#fffaf5',
    '--text-color': '#3e2723',
    '--text-light': '#8d6e63',
    '--primary-color': '#e67e22',
    '--primary-hover': '#d35400',
    '--border-color': '#e8d5c4',
    '--surface-tint': '#fff8f2',
    '--success-bg': '#e8f5e9',
    '--success-text': '#2e7d32',
    '--error-bg': '#fce4ec',
    '--error-text': '#c62828',
    '--info-bg': '#fff3e0',
    '--info-text': '#e65100',
    '--save-color': '#e67e22',
    '--save-hover': '#d35400',
    '--log-shell-bg': '#3e2723',
    '--log-text-color': '#dcc8b0',
    '--log-time-color': '#8d6e63',
    '--sidebar-active-indicator': '#e67e22',
  },
  midnight: {
    '--bg-color': '#060614',
    '--card-bg': '#0c0c22',
    '--text-color': '#d8d8f0',
    '--text-light': '#8888b8',
    '--primary-color': '#7c8aff',
    '--primary-hover': '#6a78e0',
    '--border-color': 'rgba(100, 100, 180, .25)',
    '--surface-tint': '#0a0a20',
    '--success-bg': 'rgba(0, 255, 136, .1)',
    '--success-text': '#00e676',
    '--error-bg': 'rgba(255, 82, 130, .14)',
    '--error-text': '#ff6396',
    '--info-bg': 'rgba(124, 138, 255, .12)',
    '--info-text': '#a0a0ff',
    '--save-color': '#7c8aff',
    '--save-hover': '#6a78e0',
    '--log-shell-bg': '#0a0a1a',
    '--log-text-color': '#c0c0e0',
    '--log-time-color': '#6a6a9a',
    '--sidebar-active-indicator': '#7c8aff',
  },
  nature: {
    '--bg-color': '#f4f8f0',
    '--card-bg': '#fafdf8',
    '--text-color': '#2e3b28',
    '--text-light': '#6a7a60',
    '--primary-color': '#5a8a3c',
    '--primary-hover': '#4a7030',
    '--border-color': '#d0dec4',
    '--surface-tint': '#f8fbf5',
    '--success-bg': '#e8f5e9',
    '--success-text': '#2e7d32',
    '--error-bg': '#fce4ec',
    '--error-text': '#c62828',
    '--info-bg': '#e8f5e9',
    '--info-text': '#33691e',
    '--save-color': '#5a8a3c',
    '--save-hover': '#4a7030',
    '--log-shell-bg': '#2e3b28',
    '--log-text-color': '#c8d8c0',
    '--log-time-color': '#7a8a72',
    '--sidebar-active-indicator': '#5a8a3c',
  },
};

function loadFromStorage(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v !== null ? v : fallback;
  } catch (e) {
    return fallback;
  }
}

function saveToStorage(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (e) { /* ignore */ }
}

export const activeStyle = writable(loadFromStorage('theme-style', 'light'));
export const activeScheme = writable(loadFromStorage('theme-scheme', 'default'));
export const customCSS = writable(loadFromStorage('custom-css', ''));
export const animationsEnabled = writable(loadFromStorage('animations-enabled', 'true') !== 'false');

activeStyle.subscribe(v => saveToStorage('theme-style', v));
activeScheme.subscribe(v => saveToStorage('theme-scheme', v));
customCSS.subscribe(v => saveToStorage('custom-css', v));
animationsEnabled.subscribe(v => saveToStorage('animations-enabled', v ? 'true' : 'false'));

animationsEnabled.subscribe(enabled => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-animations', enabled ? 'on' : 'off');
  }
});

customCSS.subscribe(css => {
  if (typeof document === 'undefined') return;
  let el = document.getElementById('custom-css');
  if (!el) {
    el = document.createElement('style');
    el.id = 'custom-css';
    document.head.appendChild(el);
  }
  el.innerHTML = css;
});

function ensureStyleElement() {
  let el = document.getElementById('theme-vars');
  if (!el) {
    el = document.createElement('style');
    el.id = 'theme-vars';
    document.head.appendChild(el);
  }
  return el;
}

function varsToCSS(vars) {
  return Object.entries(vars)
    .map(([k, v]) => `    ${k}: ${v};`)
    .join('\n');
}

function buildThemeCSS(styleId, schemeId) {
  const style = STYLES[styleId];
  if (!style) return '';
  const scheme = style.schemes[schemeId] || style.schemes.default;
  const baseColors = BASE_COLORS[styleId] || BASE_COLORS.light;

  const merged = {
    ...baseColors,
    ...style.cssVars,
    ...scheme.cssVars,
  };

  const isNativeTheme = styleId === 'light' || styleId === 'dark' || styleId === 'neon';
  const selector = isNativeTheme ? `:root[data-theme='${styleId}']` : ':root';

  return `${selector} {\n${varsToCSS(merged)}\n}`;
}

export function applyTheme(styleId, schemeId) {
  const el = ensureStyleElement();
  el.innerHTML = buildThemeCSS(styleId, schemeId);
  document.documentElement.setAttribute('data-theme', styleId);
}

export function setCustomCSSValue(css) {
  customCSS.set(css);
}

export function resetToDefaults() {
  activeStyle.set('light');
  activeScheme.set('default');
  customCSS.set('');
  applyTheme('light', 'default');
}

export function initTheme() {
  const styleId = get(activeStyle);
  const schemeId = get(activeScheme);
  applyTheme(styleId, schemeId);

  const animEnabled = get(animationsEnabled);
  document.documentElement.setAttribute('data-animations', animEnabled ? 'on' : 'off');

  const css = get(customCSS);
  if (css) {
    let el = document.getElementById('custom-css');
    if (!el) {
      el = document.createElement('style');
      el.id = 'custom-css';
      document.head.appendChild(el);
    }
    el.innerHTML = css;
  }
}

let themeStyleSubscription;
let themeSchemeSubscription;

export function startThemeSync() {
  themeStyleSubscription = activeStyle.subscribe(styleId => {
    applyTheme(styleId, get(activeScheme));
  });
  themeSchemeSubscription = activeScheme.subscribe(schemeId => {
    applyTheme(get(activeStyle), schemeId);
  });
}

export function stopThemeSync() {
  if (themeStyleSubscription) themeStyleSubscription();
  if (themeSchemeSubscription) themeSchemeSubscription();
}
