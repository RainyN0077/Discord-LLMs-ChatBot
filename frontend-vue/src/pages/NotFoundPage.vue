<script setup lang="ts">
import { HelpCircleOutline } from '@vicons/ionicons5'

import PageStub from '@/components/PageStub.vue'
</script>

<template>
  <PageStub
    :title="'404'"
    :icon="HelpCircleOutline"
    phase="—"
    hint="页面不存在 / Page not found"
  />
</template>
