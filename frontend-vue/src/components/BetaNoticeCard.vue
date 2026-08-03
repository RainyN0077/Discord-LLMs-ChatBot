<script setup lang="ts">
/**
 * BetaNoticeCard — once-a-day test-phase notice, shown on the first WebUI
 * open of each day (persisted via `frontend-vue-beta-notice-date`). A
 * dismissible floating card in the bottom-right corner with a link to the
 * GitHub repo (issues/PRs welcome). Styling uses theme CSS variables so the
 * card follows all 15 styles.
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const NOTICE_KEY = 'frontend-vue-beta-notice-date'
const GITHUB_URL = 'https://github.com/RainyN0077/ELA-Bot'

const { t } = useI18n()
const visible = ref(false)

function today(): string {
  const d = new Date()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

onMounted(() => {
  try {
    // Show only on the first open of each day.
    visible.value = localStorage.getItem(NOTICE_KEY) !== today()
  } catch {
    visible.value = true
  }
})

function dismiss(): void {
  visible.value = false
  try {
    localStorage.setItem(NOTICE_KEY, today())
  } catch {
    // ignore persistence failures
  }
}
</script>

<template>
  <Transition name="beta-fade">
    <aside v-if="visible" class="beta-notice" role="note" aria-label="Beta notice">
      <button
        type="button"
        class="beta-notice-close"
        :title="t('betaNotice.dismiss')"
        @click="dismiss"
      >×</button>
      <div class="beta-notice-head">
        <span class="beta-notice-badge">Beta</span>
        <span class="beta-notice-title">{{ t('betaNotice.title') }}</span>
      </div>
      <p class="beta-notice-body">{{ t('betaNotice.body') }}</p>
      <div class="beta-notice-actions">
        <a
          class="beta-notice-link"
          :href="GITHUB_URL + '/issues/new/choose'"
          target="_blank"
          rel="noopener noreferrer"
        >{{ t('betaNotice.githubIssue') }}</a>
        <a
          class="beta-notice-link"
          :href="GITHUB_URL + '/pulls'"
          target="_blank"
          rel="noopener noreferrer"
        >{{ t('betaNotice.githubPr') }}</a>
        <button type="button" class="beta-notice-ok" @click="dismiss">
          {{ t('betaNotice.dismiss') }}
        </button>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.beta-notice {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 2000;
  width: min(340px, calc(100vw - 32px));
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.25));
  background: var(--card-bg, rgba(30, 34, 48, 0.95));
  color: var(--text-color, #e2e8f0);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
  font-size: 13px;
  line-height: 1.55;
}

.beta-notice-close {
  position: absolute;
  top: 6px;
  right: 8px;
  border: none;
  background: transparent;
  color: var(--text-muted, #94a3b8);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.beta-notice-close:hover {
  background: rgba(148, 163, 184, 0.15);
  color: var(--text-color, #e2e8f0);
}

.beta-notice-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.beta-notice-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 999px;
  color: var(--primary-color, #45a3e6);
  border: 1px solid var(--primary-color, #45a3e6);
}

.beta-notice-title {
  font-weight: 600;
  font-size: 14px;
}

.beta-notice-body {
  margin: 0 0 10px;
  opacity: 0.85;
}

.beta-notice-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.beta-notice-link {
  font-size: 12px;
  color: var(--primary-color, #45a3e6);
  text-decoration: none;
}

.beta-notice-link:hover {
  text-decoration: underline;
}

.beta-notice-ok {
  margin-left: auto;
  border: none;
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  background: var(--primary-color, #45a3e6);
  cursor: pointer;
}

.beta-notice-ok:hover {
  filter: brightness(1.1);
}

.beta-fade-enter-active,
.beta-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.beta-fade-enter-from,
.beta-fade-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
