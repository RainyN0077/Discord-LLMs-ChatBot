<script setup lang="ts">
/**
 * Renderless bridge that captures the naive-ui message/dialog APIs mounted
 * by App.vue and publishes them for non-setup usage (Pinia stores).
 */
import { onBeforeUnmount } from 'vue'
import { useDialog, useMessage } from 'naive-ui'

import { bindFeedbackApis } from '@/utils/feedback'

bindFeedbackApis(useMessage(), useDialog())

// Defensive: drop the captured APIs if this bridge is ever unmounted so a
// stale instance can never serve feedback after teardown.
onBeforeUnmount(() => bindFeedbackApis(null, null))
</script>

<template>
  <slot />
</template>
