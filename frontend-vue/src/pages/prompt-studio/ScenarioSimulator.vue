<script setup lang="ts">
/**
 * ScenarioSimulator — backend-driven live preview.
 *
 * Scenario defaults are the legacy parity sample (aligned with
 * preview_builder._create_mock_objects): @张三 mention, is_reply, image_count
 * 1, triggered_plugins "搜索" sample. Preview calls debounce by 500ms on
 * templates/scenario changes; a manual refresh button re-triggers it.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NButton, NCheckbox, NInput, NInputNumber, NSelect, NSpin } from 'naive-ui'

import {
  preview,
  type PromptPreviewResult,
  type PromptPreviewScenario,
  type PromptTemplate,
} from '@/api/prompts'
import { useConfigsStore } from '@/stores/configs'

const props = defineProps<{
  templates: PromptTemplate
  botId?: string
}>()

const { t } = useI18n()
const configsStore = useConfigsStore()

const roleOptions = computed(() =>
  Object.entries(configsStore.config?.role_based_config ?? {}).map(([id, cfg]) => ({
    label: cfg.title || id,
    value: id,
  })),
)

// Scenario defaults — legacy parity with _create_mock_objects / old page.
const scenario = ref<PromptPreviewScenario>({
  user_id: '123456789',
  user_roles: [],
  channel_id: '987654321',
  guild_id: '555555555',
  message_content: '你好，我想问一下关于 @张三 的信息，顺便搜索一下今天的天气。',
  is_reply: true,
  replied_message: {
    author_id: '111222333',
    content: '你有什么问题吗？',
  },
  image_count: 1,
  triggered_plugins: [
    { name: '搜索', simulated_output: '今天天气晴朗，气温25度。' },
  ],
})

const isPreviewLoading = ref(false)
const previewError = ref('')
const previewResult = ref<PromptPreviewResult>({
  final_system_prompt: '',
  final_user_request: '',
  construction_log: [],
})

/** Guard: stale responses from rapid consecutive edits must not overwrite newer ones. */
const imageCount = computed<number>({
  get: () => scenario.value.image_count ?? 0,
  set: (v: number | null) => {
    scenario.value.image_count = v ?? 0
  },
})

let debounceTimer: ReturnType<typeof setTimeout> | null = null
let mounted = true
let previewSeq = 0

function updatePreview(): void {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(async () => {
    if (!mounted) return
    const seq = ++previewSeq
    isPreviewLoading.value = true
    previewError.value = ''
    try {
      const templatesCopy = JSON.parse(JSON.stringify(props.templates)) as PromptTemplate
      const scenarioCopy = JSON.parse(JSON.stringify(scenario.value)) as PromptPreviewScenario
      const result = await preview({ templates: templatesCopy, scenario: scenarioCopy }, props.botId)
      if (!mounted || seq !== previewSeq) return
      previewResult.value = result
    } catch (err) {
      if (!mounted || seq !== previewSeq) return
      previewError.value = err instanceof Error ? err.message : String(err)
      previewResult.value = {
        final_system_prompt: t('promptStudio.simulator.previewFailed', {
          error: err instanceof Error ? err.message : String(err),
        }),
        final_user_request: '',
        construction_log: [],
      }
    } finally {
      if (mounted && seq === previewSeq) isPreviewLoading.value = false
    }
  }, 500)
}

watch(
  () => props.templates,
  () => updatePreview(),
  { deep: true },
)
watch(scenario, () => updatePreview(), { deep: true })

// Legacy parity: the preview fires once on mount (old page: $: if ($promptTemplates) updatePreview()).
updatePreview()

onBeforeUnmount(() => {
  mounted = false
  if (debounceTimer) clearTimeout(debounceTimer)
})
</script>

<template>
  <div class="simulator">
    <!-- Scenario form -->
    <div class="simulator-controls">
      <h3 class="simulator-title">{{ t('promptStudio.simulator.title') }}</h3>
      <div class="simulator-grid">
        <div class="form-group">
          <label>{{ t('promptStudio.simulator.userMessage') }}</label>
          <n-input
            v-model:value="(scenario.message_content as string)"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 6 }"
          />
        </div>
        <div class="form-group">
          <label>{{ t('promptStudio.simulator.userRoles') }}</label>
          <n-select
            v-model:value="scenario.user_roles"
            multiple
            :options="roleOptions"
            :placeholder="t('promptStudio.simulator.userRoles')"
          />
        </div>
        <div class="form-group">
          <label>{{ t('promptStudio.simulator.imageCount') }}</label>
          <n-input-number
            v-model:value="imageCount"
            :min="0"
            style="width: 100%"
          />
        </div>
        <div class="form-group checkbox-group">
          <n-checkbox v-model:checked="(scenario.is_reply as boolean)">
            {{ t('promptStudio.simulator.isReply') }}
          </n-checkbox>
        </div>
        <div v-if="scenario.is_reply" class="form-group">
          <label>{{ t('promptStudio.simulator.replyContent') }}</label>
          <n-input
            v-model:value="(scenario.replied_message!.content as string)"
            type="text"
          />
        </div>
      </div>
      <n-button :loading="isPreviewLoading" @click="updatePreview">
        {{
          isPreviewLoading
            ? t('promptStudio.simulator.generating')
            : t('promptStudio.simulator.manualRefresh')
        }}
      </n-button>
    </div>

    <!-- Preview output: three blocks -->
    <div class="simulator-preview">
      <h3 class="simulator-title">
        {{ t('promptStudio.simulator.backendPreview') }}
        <span v-if="isPreviewLoading" class="simulator-loading-hint">
          {{ t('promptStudio.simulator.loading') }}
        </span>
      </h3>

      <n-alert v-if="previewError" type="error" :title="t('promptStudio.simulator.previewFailed', { error: previewError })" />

      <n-spin :show="isPreviewLoading">
        <div class="simulator-blocks">
          <div class="simulator-block">
            <h4>{{ t('promptStudio.simulator.systemPromptPreview') }}</h4>
            <pre class="simulator-code">{{ previewResult.final_system_prompt }}</pre>
          </div>
          <div class="simulator-block">
            <h4>{{ t('promptStudio.simulator.userRequestPreview') }}</h4>
            <pre class="simulator-code">{{ previewResult.final_user_request }}</pre>
          </div>
          <div class="simulator-block">
            <h4>{{ t('promptStudio.simulator.buildLog') }}</h4>
            <ul class="simulator-log">
              <li v-for="(entry, i) in previewResult.construction_log" :key="i">
                {{ entry }}
              </li>
            </ul>
          </div>
        </div>
      </n-spin>
    </div>
  </div>
</template>

<style scoped>
.simulator {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

.simulator-controls {
  background: var(--card-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 12px;
}

.simulator-title {
  margin: 0 0 10px;
  font-size: 15px;
}

.simulator-loading-hint {
  font-weight: normal;
  font-size: 12px;
  color: var(--text-color-3);
}

.simulator-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 16px;
  margin-bottom: 12px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-weight: 500;
  font-size: 13px;
}

.checkbox-group {
  justify-content: center;
}

.simulator-preview {
  background: var(--card-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 12px;
}

.simulator-blocks {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 4px;
}

.simulator-block h4 {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--primary-color);
}

.simulator-code {
  margin: 0;
  padding: 10px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 320px;
  overflow-y: auto;
}

.simulator-log {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--text-color-3);
  line-height: 1.7;
}
</style>
