<script setup lang="ts">
/**
 * CandidatesTab — memory candidates table (content sample, observation stats,
 * status tag) with promote/delete actions behind confirm dialogs. A "show
 * promoted" switch and manual refresh button sit above the table (mirrors the
 * legacy KnowledgeEditor); polls every 5s while mounted; poll failures are
 * silent and keep the last loaded data.
 */
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDialog, useMessage } from 'naive-ui'
import {
  NButton,
  NCheckbox,
  NDataTable,
  NSpace,
  NTag,
  type DataTableColumns,
} from 'naive-ui'

import {
  deleteMemoryCandidate,
  fetchMemoryCandidates,
  promoteMemoryCandidate,
  type MemoryCandidateItem,
} from '@/api/memory'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()

const items = ref<MemoryCandidateItem[]>([])
const loading = ref(false)
const includePromoted = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null
let polling = false

async function loadCandidates(): Promise<void> {
  if (polling) return
  polling = true
  try {
    items.value = await fetchMemoryCandidates(includePromoted.value, 200)
  } catch {
    // silent — keep the last loaded data
  } finally {
    polling = false
  }
}

function setIncludePromoted(value: boolean): void {
  includePromoted.value = value
  void loadCandidates()
}

onMounted(() => {
  void loadCandidates()
  pollTimer = setInterval(() => void loadCandidates(), 5000)
})

onBeforeUnmount(() => {
  if (pollTimer !== null) clearInterval(pollTimer)
})

function confirmPromote(row: MemoryCandidateItem): void {
  dialog.warning({
    title: t('knowledge.candidates.title'),
    content: row.content_sample,
    positiveText: t('knowledge.candidates.promote'),
    negativeText: t('knowledge.memory.cancel'),
    onPositiveClick: async () => {
      try {
        await promoteMemoryCandidate(row.id)
        await loadCandidates()
      } catch {
        message.error(t('knowledge.error.promoteMemoryCandidate'))
      }
    },
  })
}

function confirmDelete(row: MemoryCandidateItem): void {
  dialog.warning({
    title: t('knowledge.candidates.title'),
    content: t('knowledge.confirmDeleteMemoryCandidate'),
    positiveText: t('knowledge.candidates.delete'),
    negativeText: t('knowledge.memory.cancel'),
    onPositiveClick: async () => {
      try {
        await deleteMemoryCandidate(row.id)
        await loadCandidates()
      } catch {
        message.error(t('knowledge.error.deleteMemoryCandidate'))
      }
    },
  })
}

const columns = computed<DataTableColumns<MemoryCandidateItem>>(() => [
  { title: t('knowledge.memory.contentLabel'), key: 'content_sample' },
  { title: t('knowledge.candidates.seenCount'), key: 'seen_count', width: 90 },
  { title: t('knowledge.candidates.distinctUsers'), key: 'distinct_user_count', width: 90 },
  {
    title: t('knowledge.candidates.lastSeen'),
    key: 'last_seen',
    width: 170,
    render: (row) => (row.last_seen ? new Date(row.last_seen).toLocaleString() : ''),
  },
  {
    title: t('knowledge.candidates.status'),
    key: 'promoted',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { size: 'small', type: row.promoted ? 'success' : 'default', bordered: false },
        { default: () => (row.promoted ? t('knowledge.candidates.promoted') : t('knowledge.candidates.staged')) },
      ),
  },
  {
    title: '',
    key: 'actions',
    width: 140,
    render: (row) =>
      h(NSpace, { size: 4, justify: 'end' }, [
        ...(row.promoted
          ? []
          : [
              h(
                NButton,
                { size: 'tiny', type: 'primary', quaternary: true, onClick: () => confirmPromote(row) },
                { default: () => t('knowledge.candidates.promote') },
              ),
            ]),
        h(
          NButton,
          { size: 'tiny', quaternary: true, type: 'error', onClick: () => confirmDelete(row) },
          { default: () => t('knowledge.candidates.delete') },
        ),
      ]),
  },
])
</script>

<template>
  <SectionCard :title="t('knowledge.candidates.title')">
    <div class="candidates-toolbar">
      <n-checkbox
        :checked="includePromoted"
        @update:checked="setIncludePromoted"
      >
        {{ t('knowledge.candidates.showPromoted') }}
      </n-checkbox>
      <n-button size="small" secondary @click="() => void loadCandidates()">
        {{ t('knowledge.candidates.refresh') }}
      </n-button>
    </div>
    <n-data-table
      :columns="columns"
      :data="items"
      :loading="loading"
      :row-key="(row: MemoryCandidateItem) => row.id"
      :bordered="false"
      size="small"
    />
  </SectionCard>
</template>

<style scoped>
.candidates-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}
</style>
