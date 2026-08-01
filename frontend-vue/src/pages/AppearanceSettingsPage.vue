<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ColorPaletteOutline } from '@vicons/ionicons5'

import PageStub from '@/components/PageStub.vue'

const { t } = useI18n()
</script>

<template>
  <PageStub
    :title="t('appNav.appearance')"
    :icon="ColorPaletteOutline"
    phase="6"
    hint-key="appearance.title"
  />
</template>
