<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { CSSProperties } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  NLayout,
  NLayoutHeader,
  NLayoutSider,
  NLayoutContent,
  NLayoutFooter,
  NMenu,
  NButton,
  NIcon,
  NScrollbar,
  NSelect,
  NSpace,
  NTag,
  NAlert,
} from 'naive-ui'
import {
  LanguageOutline,
  MoonOutline,
  SunnyOutline,
  RefreshOutline,
  MenuOutline,
  ChevronBackOutline,
  AddOutline,
} from '@vicons/ionicons5'

import { useAuthStore } from '@/stores/auth'
import { useBotsStore } from '@/stores/bots'
import { useLogsStore } from '@/stores/logs'
import { useThemeStore } from '@/stores/theme'
import { LANGUAGES } from '@/locales/languages'
import BotCard from '@/components/BotCard.vue'
import BotModal from '@/components/BotModal.vue'
import LogPanel from '@/components/LogPanel.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const botsStore = useBotsStore()
const logsStore = useLogsStore()
const themeStore = useThemeStore()

const siderCollapsed = ref(false)
const showBotModal = ref(false)

/**
 * Responsive sider collapse. naive-ui's NLayoutSider has no `breakpoint` prop
 * (verified in node_modules LayoutSider.mjs/d.ts), so the 768px breakpoint is
 * implemented with a matchMedia listener instead.
 *
 * Semantics — the viewport state is applied only when the breakpoint is
 * *crossed*: narrow → collapse, wide → expand. Manual toggles via the sider
 * button keep working in between crossings, so e.g. a manual collapse on a
 * wide screen is preserved until the viewport actually crosses 768px.
 * `isNarrowViewport` is plain bookkeeping (not reactive state) used to detect
 * crossings; the initial matches value is applied on mount so a page that
 * loads already-narrow starts collapsed.
 */
const SIDER_MOBILE_QUERY = '(max-width: 768px)'
let isNarrowViewport = false
let siderMql: MediaQueryList | null = null

function handleViewportChange(e: MediaQueryListEvent): void {
  if (e.matches === isNarrowViewport) return // same side — no crossing
  isNarrowViewport = e.matches
  siderCollapsed.value = e.matches
}

onMounted(() => {
  if (typeof window.matchMedia !== 'function') return
  siderMql = window.matchMedia(SIDER_MOBILE_QUERY)
  isNarrowViewport = siderMql.matches
  siderCollapsed.value = siderMql.matches
  siderMql.addEventListener('change', handleViewportChange)
  // Fallback bot-list fetch: business pages fetch on their own mount, but
  // routes without a bot-dependent page (appearance, not-found) would leave
  // the sider stuck in the empty state. The length/loading guards keep this
  // idempotent with the per-page fetches.
  if (!botsStore.bots.length && !botsStore.loading) {
    void botsStore.fetchBotsList()
  }
})

onBeforeUnmount(() => {
  siderMql?.removeEventListener('change', handleViewportChange)
  siderMql = null
})

// --- log footer: height (draggable 120–500, default 180) + collapsed state,
// both persisted to localStorage so LogPanel and layout stay in sync. ---
function readStoredFooterHeight(): number {
  try {
    const n = Number(localStorage.getItem('logPanel.height'))
    if (Number.isFinite(n) && n >= 120 && n <= 500) return n
  } catch {
    // storage unavailable — fall back to the default
  }
  return 180
}

function readStoredFooterCollapsed(): boolean {
  try {
    return localStorage.getItem('logPanel.collapsed') === '1'
  } catch {
    return false
  }
}

const footerCollapsed = ref(readStoredFooterCollapsed())
const footerHeight = ref(readStoredFooterHeight())

const footerStyle = computed(() => ({
  height: footerCollapsed.value ? '36px' : `${footerHeight.value}px`,
}))

function toggleFooter(): void {
  footerCollapsed.value = !footerCollapsed.value
  try {
    localStorage.setItem('logPanel.collapsed', footerCollapsed.value ? '1' : '0')
  } catch {
    // ignore persistence failures
  }
}

/** LogPanel drags itself: `resize` applies the height live, `resize-end`
 *  (fired once on pointerup) persists it — no localStorage writes per frame. */
function onFooterResize(height: number): void {
  footerHeight.value = height
}

function onFooterResizeEnd(height: number): void {
  footerHeight.value = height
  try {
    localStorage.setItem('logPanel.height', String(height))
  } catch {
    // ignore persistence failures
  }
}

/**
 * Layout for the right column. naive-ui NLayout renders its children inside
 * a block-level scroll container, so the flex column must be applied there
 * via content-style; otherwise tall content pushes the log footer below the
 * viewport and the page scrolls instead of the content area.
 */
const mainColumnStyle = {
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
} as CSSProperties

/** Top navigation tabs (7 pages), router mode. */
const menuOptions = computed(() => [
  { label: t('appNav.providers'), key: '/providers' },
  { label: t('appNav.modelSettings'), key: '/model-settings' },
  { label: t('appNav.controlPanel'), key: '/config-panel' },
  { label: t('appNav.promptStudio'), key: '/prompt-studio' },
  { label: t('debugger.title'), key: '/debugger' },
  { label: t('appNav.userOptions'), key: '/user-options' },
  { label: t('appNav.appearance'), key: '/appearance' },
])

const activeMenuKey = computed(() => route.path)

function handleMenuSelect(key: string): void {
  void router.push(key)
}

/** Language dropdown options (native names, e.g. 日本語). */
const languageOptions = LANGUAGES.map((lang) => ({
  label: lang.name,
  value: lang.code,
}))

function handleLanguageChange(code: string): void {
  locale.value = code
  try {
    localStorage.setItem('lang', code)
  } catch {
    // ignore persistence failures (storage may be disabled/blocked)
  }
}

function refreshBots(): void {
  void botsStore.fetchBotsList()
}

function retryAuth(): void {
  void authStore.init()
}

watch(
  () => botsStore.selectedBotId,
  (botId) => {
    if (botId) logsStore.start(botId)
    else logsStore.stop()
  },
  { immediate: true },
)
</script>

<template>
  <div class="layout-root">
    <n-alert
      v-if="authStore.status === 'fail'"
      type="error"
      class="auth-banner"
    >
      <span class="auth-banner-msg">{{ authStore.error }}</span>
      <n-button size="small" text type="error" @click="retryAuth">
        {{ t('generic.retry') }}
      </n-button>
    </n-alert>

    <n-layout has-sider class="main-layout">
      <n-layout-sider
        bordered
        collapse-mode="width"
        :collapsed-width="64"
        :width="260"
        :collapsed="siderCollapsed"
      >
      <div class="sider-inner">
        <div class="sider-title">
          <n-button
            text
            class="sider-collapse-btn"
            :aria-label="siderCollapsed ? 'Expand' : 'Collapse'"
            @click="siderCollapsed = !siderCollapsed"
          >
            <template #icon>
              <n-icon>
                <MenuOutline v-if="siderCollapsed" />
                <ChevronBackOutline v-else />
              </n-icon>
            </template>
          </n-button>
          <span v-if="!siderCollapsed" class="sider-title-text">Bots</span>
          <n-button
            v-if="!siderCollapsed"
            quaternary
            size="small"
            class="sider-create-btn"
            @click="showBotModal = true"
          >
            <template #icon>
              <n-icon><AddOutline /></n-icon>
            </template>
            {{ t('botManager.newBot') }}
          </n-button>
          <n-button
            v-if="!siderCollapsed"
            quaternary
            circle
            size="small"
            @click="refreshBots"
          >
            <template #icon>
              <n-icon><RefreshOutline /></n-icon>
            </template>
          </n-button>
        </div>
        <n-scrollbar class="sider-scroll">
          <template v-if="botsStore.bots.length === 0">
            <div v-if="botsStore.error" class="sider-hint">
              <div class="sider-error-msg">{{ botsStore.error }}</div>
              <n-button size="tiny" quaternary type="error" @click="refreshBots">
                {{ t('generic.retry') }}
              </n-button>
            </div>
            <div v-else-if="botsStore.loading" class="sider-hint">…</div>
            <div v-else class="sider-hint">{{ t('botManager.noBots') }}</div>
          </template>
          <BotCard
            v-for="bot in botsStore.bots"
            :key="bot.bot_id"
            :bot="bot"
            :active="bot.bot_id === botsStore.selectedBotId"
            :collapsed="siderCollapsed"
            @select="botsStore.selectBot"
          />
        </n-scrollbar>
      </div>
    </n-layout-sider>

    <n-layout class="main-column" :content-style="mainColumnStyle">
      <n-layout-header bordered class="top-header">
        <n-menu
          mode="horizontal"
          :value="activeMenuKey"
          :options="menuOptions"
          @update:value="handleMenuSelect"
          class="top-menu"
        />
        <n-space :size="8" align="center">
          <n-tag v-if="botsStore.selectedBot" size="small" :bordered="false" type="info">
            {{ botsStore.selectedBot.bot_id }}
          </n-tag>
          <div class="lang-select-wrap">
            <n-icon class="lang-select-icon"><LanguageOutline /></n-icon>
            <n-select
              :value="locale"
              :options="languageOptions"
              :style="{ width: '120px' }"
              size="small"
              :consistent-menu-width="false"
              @update:value="handleLanguageChange"
            />
          </div>
          <n-button quaternary circle size="small" @click="themeStore.toggleDark()">
            <template #icon>
              <n-icon>
                <SunnyOutline v-if="themeStore.dark" />
                <MoonOutline v-else />
              </n-icon>
            </template>
          </n-button>
        </n-space>
      </n-layout-header>

      <n-layout-content
        content-style="padding: 16px; overflow: auto; min-height: 0;"
      >
        <!-- Sub-page switch animation: out-in transition on the content area
             only — the sider/top menu/log footer stay put. The page classes
             (.page-enter-active etc.) live in styles/global.css and respect
             :root[data-animations='off'] (Appearance → page transitions). -->
        <router-view v-slot="{ Component, route }">
          <transition name="page" mode="out-in">
            <component :is="Component" :key="route.path" />
          </transition>
        </router-view>
      </n-layout-content>

      <n-layout-footer
        bordered
        :style="footerStyle"
        class="log-footer"
      >
        <div class="log-footer-toggle" @click="toggleFooter">
          {{ footerCollapsed ? '▲' : '▼' }}
        </div>
        <LogPanel v-show="!footerCollapsed" @resize="onFooterResize" @resize-end="onFooterResizeEnd" />
      </n-layout-footer>
    </n-layout>
    </n-layout>

    <BotModal v-model:show="showBotModal" />
  </div>
</template>

<style scoped>
.layout-root {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-layout {
  flex: 1;
  height: 0;
}

/* Keep the right column from shrinking below its content needs; the flex
   column itself lives on the NLayout scroll container via content-style. */
.main-column {
  min-width: 0;
}

/* Let the content area shrink (then scroll) instead of squeezing the footer.
   flex-basis must be 0: with basis:auto the tall content inflates the flex
   total and the shrink algorithm crushes the footer (180px → content height). */
.main-column :deep(.n-layout-content) {
  min-height: 0;
  flex: 1 1 0%;
}

.auth-banner {
  border-radius: 0;
}

.auth-banner-msg {
  margin-right: 8px;
}

.sider-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sider-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 8px;
  font-weight: 600;
}

.sider-title-text {
  flex: 1;
  padding-left: 4px;
}

.sider-collapse-btn {
  padding: 0 4px;
}

.sider-scroll {
  flex: 1;
  min-height: 0;
}

.sider-hint {
  padding: 16px;
  text-align: center;
  opacity: 0.6;
  font-size: 13px;
}

.sider-error-msg {
  margin-bottom: 8px;
  word-break: break-all;
}

.top-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 48px;
}

.top-menu {
  flex: 1;
  min-width: 0;
  /* Narrow screens: let the 7 tabs scroll horizontally instead of
     wrapping/crowding; the scrollbar is hidden (no hamburger menu). */
  overflow-x: auto;
  scrollbar-width: none; /* Firefox */
}

.top-menu::-webkit-scrollbar,
.top-menu :deep(.n-menu-bar)::-webkit-scrollbar {
  display: none; /* WebKit/Blink */
}

.top-menu :deep(.n-menu-bar) {
  scrollbar-width: none; /* Firefox — naive-ui's internal scroller */
}

.lang-select-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
}

.lang-select-icon {
  font-size: 15px;
  opacity: 0.7;
}

.log-footer {
  position: relative;
  overflow: hidden;
}

/* NEW-5: right-aligned (not centered) so the toggle never sits over the
   middle of LogPanel's 6px resize handle — the handle's center is the
   primary drag zone, and the footer spans the full viewport width so the
   toggle stays reachable even on narrow screens. */
.log-footer-toggle {
  position: absolute;
  top: 0;
  right: 12px;
  padding: 0 10px;
  cursor: pointer;
  font-size: 10px;
  opacity: 0.6;
  z-index: 2;
  user-select: none;
}

.log-footer-toggle:hover {
  opacity: 1;
}
</style>
