<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { BugOutline } from '@vicons/ionicons5'

import PageStub from '@/components/PageStub.vue'

const { t } = useI18n()
</script>

<template>
  <PageStub
    :title="t('debugger.title')"
    :icon="BugOutline"
    phase="4"
    hint-key="debugger.info"
  />
</template>
