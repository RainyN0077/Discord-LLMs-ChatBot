<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { GridOutline } from '@vicons/ionicons5'

import PageStub from '@/components/PageStub.vue'

const { t } = useI18n()
</script>

<template>
  <PageStub
    :title="t('appNav.controlPanel')"
    :icon="GridOutline"
    phase="1"
    hint-key="configPanel.selectBot"
  />
</template>
