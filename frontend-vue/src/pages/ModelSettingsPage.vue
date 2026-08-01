<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { SettingsOutline } from '@vicons/ionicons5'

import PageStub from '@/components/PageStub.vue'
import { useBotsStore } from '@/stores/bots'

const { t } = useI18n()
const botsStore = useBotsStore()

onMounted(() => {
  if (!botsStore.bots.length) void botsStore.fetchBotsList()
})
</script>

<template>
  <PageStub
    :title="t('appNav.modelSettings')"
    :icon="SettingsOutline"
    phase="2"
    hint-key="modelSettings.goToModelSettings"
  />
</template>
