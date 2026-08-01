<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
} from '@vicons/ionicons5'

import { useAuthStore } from '@/stores/auth'
import { useBotsStore } from '@/stores/bots'
import { useLogsStore } from '@/stores/logs'
import { useThemeStore } from '@/stores/theme'
import BotCard from '@/components/BotCard.vue'
import LogPanel from '@/components/LogPanel.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const botsStore = useBotsStore()
const logsStore = useLogsStore()
const themeStore = useThemeStore()

const siderCollapsed = ref(false)
const footerCollapsed = ref(false)
const footerHeight = computed(() => (footerCollapsed.value ? 36 : 180))

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

function switchLanguage(): void {
  locale.value = locale.value === 'zh' ? 'en' : 'zh'
  localStorage.setItem('lang', locale.value)
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
      @collapse="siderCollapsed = true"
      @expand="siderCollapsed = false"
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
            <div v-else class="sider-hint">{{ t('status.loading') }}</div>
          </template>
          <BotCard
            v-for="bot in botsStore.bots"
            :key="bot.bot_id"
            :bot="bot"
            :active="bot.bot_id === botsStore.selectedBotId"
            @select="botsStore.selectBot"
          />
        </n-scrollbar>
      </div>
    </n-layout-sider>

    <n-layout>
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
          <n-button quaternary circle size="small" @click="switchLanguage">
            <template #icon>
              <n-icon><LanguageOutline /></n-icon>
            </template>
            <span class="lang-label">{{ locale === 'zh' ? 'EN' : '中' }}</span>
          </n-button>
          <n-button quaternary circle size="small" @click="themeStore.toggle()">
            <template #icon>
              <n-icon>
                <MoonOutline v-if="themeStore.dark" />
                <SunnyOutline v-else />
              </n-icon>
            </template>
          </n-button>
        </n-space>
      </n-layout-header>

      <n-layout-content content-style="padding: 16px; min-height: 0;">
        <router-view />
      </n-layout-content>

      <n-layout-footer
        bordered
        :style="{ height: footerHeight + 'px' }"
        class="log-footer"
      >
        <div class="log-footer-toggle" @click="footerCollapsed = !footerCollapsed">
          {{ footerCollapsed ? '▲' : '▼' }}
        </div>
        <LogPanel v-show="!footerCollapsed" />
      </n-layout-footer>
    </n-layout>
    </n-layout>
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
}

.lang-label {
  font-size: 12px;
  padding-left: 2px;
}

.log-footer {
  position: relative;
  overflow: hidden;
}

.log-footer-toggle {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
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
