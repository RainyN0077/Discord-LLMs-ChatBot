<script setup lang="ts">
/**
 * MemoryTab — memory item table with add/edit modals, delete confirm and a
 * 200ms-debounced username search. Polls every 5s while mounted (the parent
 * only mounts this tab when it is active); poll failures are silent and keep
 * the last loaded data.
 */
import { computed, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDialog, useMessage } from 'naive-ui'
import {
  NButton,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSpace,
  type DataTableColumns,
} from 'naive-ui'

import {
  addMemoryItem,
  deleteMemoryItem,
  fetchMemoryItems,
  updateMemoryItem,
  type MemoryItem,
} from '@/api/memory'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()

const items = ref<MemoryItem[]>([])
const loading = ref(false)
const searchQuery = ref('')
const debouncedQuery = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let polling = false

const showModal = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ content: '', user_name: 'WebUI', user_id: '', timestamp: '' })

const filteredItems = computed(() => {
  const q = debouncedQuery.value.toLowerCase()
  if (!q) return items.value
  return items.value.filter((item) => (item.user_name || '').toLowerCase().includes(q))
})

async function loadItems(): Promise<void> {
  if (polling) return
  polling = true
  loading.value = true
  try {
    items.value = await fetchMemoryItems()
  } catch {
    // silent — keep the last loaded data
  } finally {
    loading.value = false
    polling = false
  }
}

onMounted(() => {
  void loadItems()
  pollTimer = setInterval(() => void loadItems(), 5000)
})

onBeforeUnmount(() => {
  if (pollTimer !== null) clearInterval(pollTimer)
  if (searchTimer !== null) clearTimeout(searchTimer)
})

function handleSearchInput(value: string): void {
  searchQuery.value = value
  if (searchTimer !== null) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    debouncedQuery.value = value
  }, 200)
}

/** Strip the `[memory ...]` tag the bot prepends to extracted memories. */
function formatContent(raw: string | null | undefined): string {
  return (raw || '').replace(/\[memory\s+.*?\]\s*/, '')
}

function openAdd(): void {
  editingId.value = null
  form.content = ''
  form.user_name = 'WebUI'
  form.user_id = ''
  form.timestamp = ''
  showModal.value = true
}

function openEdit(item: MemoryItem): void {
  editingId.value = item.id ?? null
  form.content = formatContent(item.content)
  form.user_name = item.user_name || 'WebUI'
  form.user_id = item.user_id || ''
  form.timestamp = toLocalInputValue(item.timestamp)
  showModal.value = true
}

/** ISO timestamp → `<input type="datetime-local">` value (local time). */
function toLocalInputValue(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function handleSubmit(): Promise<void> {
  const content = form.content.trim()
  if (!content) return
  const isEdit = editingId.value !== null
  try {
    if (isEdit) {
      await updateMemoryItem(editingId.value as number, content)
    } else {
      const timezone = form.timestamp ? Intl.DateTimeFormat().resolvedOptions().timeZone : null
      await addMemoryItem({
        content,
        user_name: form.user_name.trim() || 'WebUI',
        user_id: form.user_id.trim() || null,
        timestamp: form.timestamp || null,
        timezone,
        source: t('knowledge.memory.sourceManual'),
      })
    }
    showModal.value = false
    await loadItems()
  } catch {
    message.error(isEdit ? t('knowledge.error.updateMemory') : t('knowledge.error.addMemory'))
  }
}

function confirmDelete(row: MemoryItem): void {
  dialog.warning({
    title: t('knowledge.memory.title'),
    content: t('knowledge.confirmDeleteMemory'),
    positiveText: t('knowledge.memory.delete'),
    negativeText: t('knowledge.memory.cancel'),
    onPositiveClick: async () => {
      try {
        await deleteMemoryItem(row.id as number)
        await loadItems()
      } catch {
        message.error(t('knowledge.error.deleteMemory'))
      }
    },
  })
}

const columns = computed<DataTableColumns<MemoryItem>>(() => [
  {
    title: t('knowledge.memory.contentLabel'),
    key: 'content',
    render: (row) => h('div', { class: 'content-cell' }, formatContent(row.content)),
  },
  {
    title: t('knowledge.memory.at'),
    key: 'timestamp',
    render: (row) => (row.timestamp ? new Date(row.timestamp).toLocaleString() : ''),
  },
  { title: t('knowledge.memory.by'), key: 'user_name' },
  { title: t('knowledge.memory.source'), key: 'source' },
  {
    title: '',
    key: 'actions',
    width: 140,
    render: (row) =>
      h(NSpace, { size: 4, justify: 'end' }, [
        h(
          NButton,
          { size: 'tiny', quaternary: true, onClick: () => openEdit(row) },
          { default: () => t('knowledge.memory.edit') },
        ),
        h(
          NButton,
          { size: 'tiny', quaternary: true, type: 'error', onClick: () => confirmDelete(row) },
          { default: () => t('knowledge.memory.delete') },
        ),
      ]),
  },
])
</script>

<template>
  <SectionCard :title="t('knowledge.memory.title')">
    <n-input
      :value="searchQuery"
      :placeholder="t('knowledge.memory.searchPlaceholder')"
      class="search-bar"
      @update:value="handleSearchInput"
    />

    <n-data-table
      :columns="columns"
      :data="filteredItems"
      :loading="loading"
      :row-key="(row: MemoryItem) => row.id ?? 0"
      :pagination="{ pageSize: 10 }"
      :bordered="false"
      size="small"
      class="memory-table"
    />

    <n-button type="primary" size="small" class="add-btn" @click="openAdd">
      {{ t('knowledge.memory.add') }}
    </n-button>

    <n-modal
      v-model:show="showModal"
      :title="editingId !== null ? t('knowledge.memory.edit') : t('knowledge.memory.add')"
      preset="card"
      class="memory-modal"
    >
      <n-form label-placement="top">
        <n-form-item :label="t('knowledge.memory.contentLabel')">
          <n-input
            v-model:value="form.content"
            type="textarea"
            :rows="3"
            :placeholder="t('knowledge.memory.addPlaceholder')"
          />
        </n-form-item>
        <n-grid :cols="3" :x-gap="12" responsive="screen" item-responsive>
          <n-gi :span="1">
            <n-form-item :label="t('knowledge.memory.by')">
              <n-input v-model:value="form.user_name" :placeholder="t('knowledge.memory.byPlaceholder')" />
            </n-form-item>
          </n-gi>
          <n-gi :span="1">
            <n-form-item :label="t('knowledge.memory.userIdLabel')">
              <n-input v-model:value="form.user_id" :placeholder="t('knowledge.memory.userIdPlaceholder')" />
            </n-form-item>
          </n-gi>
          <n-gi :span="1">
            <n-form-item :label="t('knowledge.memory.timestampLabel')">
              <input v-model="form.timestamp" type="datetime-local" class="datetime-input" />
            </n-form-item>
          </n-gi>
        </n-grid>
        <n-space justify="end">
          <n-button @click="showModal = false">{{ t('knowledge.memory.cancel') }}</n-button>
          <n-button type="primary" @click="handleSubmit">{{ t('knowledge.memory.save') }}</n-button>
        </n-space>
      </n-form>
    </n-modal>
  </SectionCard>
</template>

<style scoped>
.search-bar {
  margin-bottom: 12px;
}

.add-btn {
  margin-top: 12px;
}

.content-cell {
  white-space: pre-wrap;
  word-break: break-word;
}

.memory-modal {
  width: min(640px, 94vw);
}
</style>
