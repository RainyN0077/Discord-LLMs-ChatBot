<script setup lang="ts">
/**
 * EmptyState — icon + description + optional action slot.
 * Thin wrapper over NEmpty for consistent empty states across pages.
 */
import type { Component } from 'vue'
import { NEmpty } from 'naive-ui'

withDefaults(
  defineProps<{
    description?: string
    /** Ionicon component to render in place of NEmpty's default icon. */
    icon?: Component
  }>(),
  { description: '', icon: undefined },
)
</script>

<template>
  <n-empty :description="description" class="empty-state">
    <template v-if="icon" #icon>
      <n-icon :size="48" :depth="3">
        <component :is="icon" />
      </n-icon>
    </template>
    <template v-if="$slots.action" #extra>
      <slot name="action" />
    </template>
  </n-empty>
</template>

<style scoped>
.empty-state {
  padding: 24px 0;
}
</style>
