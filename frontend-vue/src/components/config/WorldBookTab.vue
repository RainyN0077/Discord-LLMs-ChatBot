<script setup lang="ts">
/**
 * WorldBookTab — world book entries table with add/edit modal (keywords
 * comma-separated, content textarea, enabled switch, optional linked persona)
 * and delete confirm. Polls every 5s while mounted; poll failures are silent.
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
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  type DataTableColumns,
} from 'naive-ui'

import {
  addWorldBookItem,
  deleteWorldBookItem,
  fetchWorldBookItems,
  updateWorldBookItem,
  type WorldBookItem,
} from '@/api/memory'
import { useConfigsStore } from '@/stores/configs'
import SectionCard from '@/components/common/SectionCard.vue'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()
const configsStore = useConfigsStore()

const items = ref<WorldBookItem[]>([])
const loading = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null
let polling = false

const showModal = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  keywords: '',
  content: '',
  enabled: true,
  linked_user_id: '' as string,
})

/** Persona select options from `config.user_personas` (nickname || `ID: x`). */
const personaOptions = computed(() => {
  const personas = (configsStore.config?.user_personas ?? {}) as Record<
    string,
    { id?: string | null; nickname?: string | null } | undefined
  >
  const options = Object.entries(personas).map(([key, persona]) => {
    const id = persona?.id || key
    const nickname = persona?.nickname
    return { label: nickname || `ID: ${id}`, value: id }
  })
  return [{ label: t('knowledge.worldBook.noLinkedUser'), value: '' }, ...options]
})

function personaLabel(userId: string): string {
  const persona = (configsStore.config?.user_personas ?? {})[
    userId
  ] as { id?: string | null; nickname?: string | null } | undefined
  const id = persona?.id || userId
  return persona?.nickname || `ID: ${id}`
}

async function loadWorldBook(): Promise<void> {
  if (polling) return
  polling = true
  try {
    items.value = await fetchWorldBookItems()
  } catch {
    // silent — keep the last loaded data
  } finally {
    polling = false
  }
}

onMounted(() => {
  void loadWorldBook()
  pollTimer = setInterval(() => void loadWorldBook(), 5000)
})

onBeforeUnmount(() => {
  if (pollTimer !== null) clearInterval(pollTimer)
})

function openAdd(): void {
  editingId.value = null
  form.keywords = ''
  form.content = ''
  form.enabled = true
  form.linked_user_id = ''
  showModal.value = true
}

function openEdit(item: WorldBookItem): void {
  editingId.value = item.id ?? null
  form.keywords = item.keywords || ''
  form.content = item.content || ''
  form.enabled = item.enabled !== false
  form.linked_user_id = item.linked_user_id ?? ''
  showModal.value = true
}

async function handleSubmit(): Promise<void> {
  const keywords = form.keywords.trim()
  const content = form.content.trim()
  if (!keywords || !content) {
    message.error(t('knowledge.error.emptyFields'))
    return
  }
  const isEdit = editingId.value !== null
  const payload: WorldBookItem = {
    keywords,
    content,
    enabled: form.enabled,
    linked_user_id: form.linked_user_id || null,
  }
  try {
    if (isEdit) {
      await updateWorldBookItem(editingId.value as number, payload)
    } else {
      await addWorldBookItem(payload)
    }
    showModal.value = false
    await loadWorldBook()
  } catch {
    message.error(t('knowledge.error.saveWorldBook'))
  }
}

function confirmDelete(row: WorldBookItem): void {
  dialog.warning({
    title: t('knowledge.worldBook.title'),
    content: t('knowledge.confirmDeleteWorldBook'),
    positiveText: t('knowledge.worldBook.delete'),
    negativeText: t('knowledge.memory.cancel'),
    onPositiveClick: async () => {
      try {
        await deleteWorldBookItem(row.id as number)
        await loadWorldBook()
      } catch {
        message.error(t('knowledge.error.deleteWorldBook'))
      }
    },
  })
}

const columns = computed<DataTableColumns<WorldBookItem>>(() => [
  {
    title: t('knowledge.worldBook.keywordsLabel'),
    key: 'keywords',
    width: 200,
    render: (row) => h('span', { class: 'keyword-cell' }, row.keywords || ''),
  },
  {
    title: t('knowledge.worldBook.contentLabel'),
    key: 'content',
    render: (row) => h('div', { class: 'content-cell' }, row.content || ''),
  },
  {
    title: t('knowledge.worldBook.linkedUserLabel'),
    key: 'linked_user_id',
    width: 140,
    render: (row) =>
      row.linked_user_id
        ? h('span', { class: 'linked-user-cell' }, personaLabel(row.linked_user_id))
        : h('span', { class: 'linked-user-cell muted' }, t('knowledge.worldBook.noLinkedUser')),
  },
  {
    title: t('scopedPrompts.enabled'),
    key: 'enabled',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { size: 'small', type: row.enabled !== false ? 'success' : 'default', bordered: false },
        { default: () => (row.enabled !== false ? t('scopedPrompts.enabled') : t('sidebar.disabled')) },
      ),
  },
  {
    title: '',
    key: 'actions',
    width: 140,
    render: (row) =>
      h(NSpace, { size: 4, justify: 'end' }, [
        h(
          NButton,
          { size: 'tiny', quaternary: true, onClick: () => openEdit(row) },
          { default: () => t('knowledge.worldBook.edit') },
        ),
        h(
          NButton,
          { size: 'tiny', quaternary: true, type: 'error', onClick: () => confirmDelete(row) },
          { default: () => t('knowledge.worldBook.delete') },
        ),
      ]),
  },
])
</script>

<template>
  <SectionCard :title="t('knowledge.worldBook.title')">
    <n-data-table
      :columns="columns"
      :data="items"
      :loading="loading"
      :row-key="(row: WorldBookItem) => row.id ?? 0"
      :pagination="{ pageSize: 10 }"
      :bordered="false"
      size="small"
      class="worldbook-table"
    />

    <n-button type="primary" size="small" class="add-btn" @click="openAdd">
      {{ t('knowledge.worldBook.add') }}
    </n-button>

    <n-modal
      v-model:show="showModal"
      :title="editingId !== null ? t('knowledge.worldBook.editTitle') : t('knowledge.worldBook.addTitle')"
      preset="card"
      class="worldbook-modal"
    >
      <n-form label-placement="top">
        <n-form-item :label="t('knowledge.worldBook.keywordsLabel')">
          <n-input
            v-model:value="form.keywords"
            :placeholder="t('knowledge.worldBook.keywordsPlaceholder')"
          />
          <template #feedback>{{ t('knowledge.worldBook.keywordsHint') }}</template>
        </n-form-item>
        <n-form-item :label="t('knowledge.worldBook.contentLabel')">
          <n-input
            v-model:value="form.content"
            type="textarea"
            :rows="4"
            :placeholder="t('knowledge.worldBook.contentPlaceholder')"
          />
        </n-form-item>
        <n-form-item :label="t('knowledge.worldBook.linkedUserLabel')">
          <n-select
            v-model:value="form.linked_user_id"
            :options="personaOptions"
            :placeholder="t('knowledge.worldBook.noLinkedUser')"
          />
        </n-form-item>
        <n-form-item :label="t('scopedPrompts.enabled')">
          <n-switch v-model:value="form.enabled" />
        </n-form-item>
        <n-space justify="end">
          <n-button @click="showModal = false">{{ t('knowledge.worldBook.cancelEdit') }}</n-button>
          <n-button type="primary" @click="handleSubmit">
            {{ editingId !== null ? t('knowledge.worldBook.save') : t('knowledge.worldBook.add') }}
          </n-button>
        </n-space>
      </n-form>
    </n-modal>
  </SectionCard>
</template>

<style scoped>
.add-btn {
  margin-top: 12px;
}

.keyword-cell {
  font-style: italic;
}

.linked-user-cell {
  font-size: 12px;
}

.linked-user-cell.muted {
  opacity: 0.45;
}

.content-cell {
  white-space: pre-wrap;
  word-break: break-word;
}

.worldbook-modal {
  width: min(560px, 94vw);
}
</style>
