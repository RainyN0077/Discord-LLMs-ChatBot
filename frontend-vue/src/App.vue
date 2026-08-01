<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  NAlert,
  NButton,
  NConfigProvider,
  NDialogProvider,
  NMessageProvider,
  NSpin,
} from 'naive-ui'

import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { resolveLanguage } from '@/locales/languages'
import FeedbackBinder from '@/components/FeedbackBinder.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const authStore = useAuthStore()

// naive-ui component/date locales follow the i18n locale (zh → zhCN, etc.).
const naiveLocale = computed(() => resolveLanguage(locale.value).naiveLocale)
const naiveDateLocale = computed(() => resolveLanguage(locale.value).naiveDateLocale)

onMounted(() => {
  // Bootstrap the API key on startup; MainLayout renders a banner on failure.
  void authStore.init()
})

// ---------------------------------------------------------------------------
// Auth first-frame guard: while the key bootstrap is in flight (idle/pending)
// render only a full-screen loader, so no page mounts before the API key is
// available (avoids first-frame requests and flashing error states).
// ---------------------------------------------------------------------------
const authBooted = computed(
  () => authStore.status === 'ok' || authStore.status === 'fail',
)

// ---------------------------------------------------------------------------
// Router error fallback: a failed lazy chunk load must show a unified error
// UI instead of a blank page (auth-banner pattern: alert + retry).
// ---------------------------------------------------------------------------
const routeLoadError = ref<string | null>(null)

router.onError((err: unknown) => {
  routeLoadError.value = err instanceof Error ? err.message : String(err)
})

// M3: a successful navigation clears the stale failure banner — without
// this, the error from a failed lazy-chunk load stays visible forever
// even after the user navigates/retries successfully.
router.afterEach(() => {
  routeLoadError.value = null
})

/** Retry the failed navigation; `force` re-triggers it even when the target
 *  equals the current location (vue-router 5 RouteLocationOptions.force). */
function retryRoute(): void {
  routeLoadError.value = null
  void router
    .replace({ path: route.path, force: true })
    .catch(() => {
      // Navigation failed again — router.onError re-sets the banner.
    })
}
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
          <div v-if="!authBooted" class="boot-loading">
            <n-spin size="large" />
          </div>
          <template v-else>
            <n-alert v-if="routeLoadError" type="error" class="route-error-banner">
              <div class="route-error-body">
                <span class="route-error-text">
                  {{ t('errors.routeLoadFailed', { error: routeLoadError }) }}
                </span>
                <n-button size="small" text type="error" @click="retryRoute">
                  {{ t('generic.retry') }}
                </n-button>
              </div>
            </n-alert>
            <router-view v-slot="{ Component, route }">
              <transition name="page" mode="out-in">
                <component :is="Component" :key="route.path" />
              </transition>
            </router-view>
          </template>
        </FeedbackBinder>
      </NMessageProvider>
    </NDialogProvider>
  </NConfigProvider>
</template>

<style scoped>
/* Full-viewport loader while the auth bootstrap is in flight. */
.boot-loading {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Unified route-load failure banner (auth-banner pattern). */
.route-error-banner {
  border-radius: 0;
}

.route-error-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.route-error-text {
  flex: 1;
  min-width: 0;
  word-break: break-all;
}
</style>
