import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

import { createI18n } from 'vue-i18n'
import en from './locales/en'
import zh from './locales/zh'

import './styles/global.css'

const storedLang =
  typeof window !== 'undefined' ? localStorage.getItem('lang') : null

const i18n = createI18n({
  legacy: false,
  locale: storedLang || 'zh',
  fallbackLocale: 'en',
  missingWarn: false,
  fallbackWarn: false,
  messages: { zh, en },
})

const app = createApp(App)
app.use(createPinia())
app.use(i18n)
app.use(router)
app.mount('#app')
