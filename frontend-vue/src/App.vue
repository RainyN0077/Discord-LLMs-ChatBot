<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { NConfigProvider, NDialogProvider, NMessageProvider } from 'naive-ui'

import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { resolveLanguage } from '@/locales/languages'
import FeedbackBinder from '@/components/FeedbackBinder.vue'

const { locale } = useI18n()
const themeStore = useThemeStore()
const authStore = useAuthStore()

// naive-ui component/date locales follow the i18n locale (zh → zhCN, etc.).
const naiveLocale = computed(() => resolveLanguage(locale.value).naiveLocale)
const naiveDateLocale = computed(() => resolveLanguage(locale.value).naiveDateLocale)

onMounted(() => {
  // Bootstrap the API key on startup; MainLayout renders a banner on failure.
  void authStore.init()
})
</script>

<template>
  <NConfigProvider
    :theme="themeStore.naiveTheme"
    :theme-overrides="themeStore.naiveOverrides"
    :locale="naiveLocale"
    :date-locale="naiveDateLocale"
  >
    <NDialogProvider>
      <NMessageProvider>
        <FeedbackBinder>
          <router-view v-slot="{ Component, route }">
            <transition name="page" mode="out-in">
              <component :is="Component" :key="route.path" />
            </transition>
          </router-view>
        </FeedbackBinder>
      </NMessageProvider>
    </NDialogProvider>
  </NConfigProvider>
</template>
