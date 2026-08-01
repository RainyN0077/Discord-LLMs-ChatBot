<script setup lang="ts">
/**
 * KnowledgeEditor — directives tab knowledge section: 4 sub-tabs.
 *
 * The settings tab has its own Save button (emits `save` so the page runs
 * the full-config round-trip). The data tabs mount their children only while
 * active (`v-if`), so each polling component's mount/unmount lifecycle starts
 * and stops its 5s polling — polling never runs for hidden tabs.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NTabs, NTabPane } from 'naive-ui'

import KnowledgeSettingsForm from './KnowledgeSettingsForm.vue'
import MemoryTab from './MemoryTab.vue'
import CandidatesTab from './CandidatesTab.vue'
import WorldBookTab from './WorldBookTab.vue'

const emit = defineEmits<{ save: [] }>()

const { t } = useI18n()
const activeTab = ref('settings')
</script>

<template>
  <n-tabs v-model:value="activeTab" type="line" animated class="knowledge-tabs">
    <n-tab-pane name="settings" :tab="t('knowledge.tabs.settings')">
      <KnowledgeSettingsForm @save="emit('save')" />
    </n-tab-pane>
    <n-tab-pane name="worldbook" :tab="t('knowledge.tabs.worldBook')">
      <WorldBookTab v-if="activeTab === 'worldbook'" />
    </n-tab-pane>
    <n-tab-pane name="memory" :tab="t('knowledge.tabs.memory')">
      <MemoryTab v-if="activeTab === 'memory'" />
    </n-tab-pane>
    <n-tab-pane name="candidates" :tab="t('knowledge.tabs.candidates')">
      <CandidatesTab v-if="activeTab === 'candidates'" />
    </n-tab-pane>
  </n-tabs>
</template>

<style scoped>
.knowledge-tabs {
  margin-bottom: 16px;
}
</style>
