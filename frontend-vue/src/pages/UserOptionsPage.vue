<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { PeopleOutline } from '@vicons/ionicons5'

import PageStub from '@/components/PageStub.vue'

const { t } = useI18n()
</script>

<template>
  <PageStub
    :title="t('appNav.userOptions')"
    :icon="PeopleOutline"
    phase="5"
    hint-key="userOptions.title"
  />
</template>
