<script setup lang="ts">
/**
 * SectionCard — the single shared card wrapper for config sections.
 * Renders an NCard with a header title; content goes in the default slot.
 */
import { NCard } from 'naive-ui'

withDefaults(
  defineProps<{
    title?: string
    /** Extra actions rendered on the right side of the header. */
    extra?: string
  }>(),
  { title: '', extra: '' },
)
</script>

<template>
  <n-card class="section-card" size="small" :bordered="true">
    <template v-if="title || $slots.extra" #header>
      <div class="section-card-header">
        <span v-if="title" class="section-card-title">{{ title }}</span>
        <span v-if="$slots.extra" class="section-card-extra">
          <slot name="extra" />
        </span>
      </div>
    </template>
    <slot />
  </n-card>
</template>

<style scoped>
.section-card {
  margin-bottom: 16px;
}

.section-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.section-card-title {
  font-weight: 600;
  font-size: 15px;
}

.section-card-extra {
  flex-shrink: 0;
}
</style>
