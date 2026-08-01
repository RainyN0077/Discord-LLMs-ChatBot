<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  zhCN,
  enUS,
  dateZhCN,
  dateEnUS,
} from 'naive-ui'

import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { darkOverrides, lightOverrides } from '@/styles/theme'
import FeedbackBinder from '@/components/FeedbackBinder.vue'

const { locale } = useI18n()
const themeStore = useThemeStore()
const authStore = useAuthStore()

const naiveLocale = computed(() => (locale.value === 'zh' ? zhCN : enUS))
const naiveDateLocale = computed(() => (locale.value === 'zh' ? dateZhCN : dateEnUS))

const themeOverrides = computed(() => (themeStore.dark ? darkOverrides : lightOverrides))

onMounted(() => {
  // Bootstrap the API key on startup; MainLayout renders a banner on failure.
  void authStore.init()
})
</script>

<template>
  <NConfigProvider
    :theme="themeStore.naiveTheme"
    :theme-overrides="themeOverrides"
    :locale="naiveLocale"
    :date-locale="naiveDateLocale"
  >
    <NDialogProvider>
      <NMessageProvider>
        <FeedbackBinder>
          <router-view />
        </FeedbackBinder>
      </NMessageProvider>
    </NDialogProvider>
  </NConfigProvider>
</template>
