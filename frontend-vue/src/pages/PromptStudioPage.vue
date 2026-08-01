<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ColorWandOutline } from '@vicons/ionicons5'

import PageStub from '@/components/PageStub.vue'

const { t } = useI18n()
</script>

<template>
  <PageStub
    :title="t('appNav.promptStudio')"
    :icon="ColorWandOutline"
    phase="3"
    hint-key="promptStudio.title"
  />
</template>
