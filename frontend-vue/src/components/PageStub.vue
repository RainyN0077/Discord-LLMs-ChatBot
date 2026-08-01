<script setup lang="ts">
import type { Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { NIcon, NText } from 'naive-ui'

const props = withDefaults(
  defineProps<{
    /** Page title shown under the icon. */
    title: string
    /** Ionicon component to render. */
    icon: Component
    /** Phase marker, e.g. "0". */
    phase?: string
    /** i18n key for the hint; falls back to a hardcoded Chinese placeholder. */
    hintKey?: string
    /** Direct hint text; overrides hintKey when provided. */
    hint?: string
  }>(),
  { phase: '0', hintKey: '', hint: '' },
)

const { t, te } = useI18n()

const hint = (): string => {
  if (props.hint) return props.hint
  if (props.hintKey && te(props.hintKey)) return t(props.hintKey)
  return '此页面将在后续 Phase 实现，敬请期待。'
}
</script>

<template>
  <div class="page-stub">
    <n-icon :size="56" :depth="3">
      <component :is="icon" />
    </n-icon>
    <h2 class="page-stub-title">{{ title }}</h2>
    <n-text depth="3" class="page-stub-hint">
      Phase {{ phase }}: {{ hint() }}
    </n-text>
  </div>
</template>

<style scoped>
.page-stub {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 60vh;
  padding: 32px;
  text-align: center;
}

.page-stub-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.page-stub-hint {
  font-size: 14px;
}
</style>
