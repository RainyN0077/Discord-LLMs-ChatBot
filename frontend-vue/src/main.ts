import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

import { i18n } from './locales'
import { assertThemeDataIntegrity } from './themes/themes'
import { initThemeSync } from './stores/theme'

import './styles/global.css'

if (import.meta.env.DEV) {
  // Fail fast on theme data regressions during development.
  assertThemeDataIntegrity()
}

// Synchronous theme bootstrap (CSS vars + dataset) before the app mounts,
// so the very first paint already has the full palette (no FOUC).
initThemeSync()

const app = createApp(App)
app.use(createPinia())
app.use(i18n)
app.use(router)
app.mount('#app')
