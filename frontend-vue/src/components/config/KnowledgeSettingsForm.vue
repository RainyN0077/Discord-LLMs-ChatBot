<script setup lang="ts">
/**
 * KnowledgeSettingsForm — dedup thresholds + auto-memory staging + recall
 * settings. Renders a standalone "Save" button that emits `save` (the parent
 * page performs the full-config round-trip).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NFormItem, NGrid, NGi, NInputNumber, NSlider, NSwitch, NText } from 'naive-ui'

import { useConfigsStore } from '@/stores/configs'
import SectionCard from '@/components/common/SectionCard.vue'

const emit = defineEmits<{ save: [] }>()

const { t } = useI18n()
const configsStore = useConfigsStore()

const config = computed(() => configsStore.config)
const markDirty = (): void => configsStore.markDirty()

/** Round a 0..1 threshold to a percentage for display. */
function percent(value: number | undefined | null): string {
  return `${Math.round((value ?? 0) * 100)}%`
}

function setDedupThreshold(field: 'memory_dedup_threshold' | 'world_book_dedup_threshold', value: number): void {
  if (config.value) config.value[field] = value
  markDirty()
}

function setQualityThreshold(value: number): void {
  if (config.value) config.value.auto_memory_quality_threshold = value
  markDirty()
}
</script>

<template>
  <div v-if="config">
    <SectionCard :title="t('knowledge.settings.title')">
      <n-text depth="3" class="section-hint">{{ t('knowledge.settings.dedupDescription') }}</n-text>

      <n-form-item :label="t('knowledge.settings.memoryDedupThreshold')" label-placement="top">
        <div class="slider-row">
          <n-slider
            :value="config.memory_dedup_threshold"
            :min="0"
            :max="1"
            :step="0.01"
            @update:value="(v: number) => setDedupThreshold('memory_dedup_threshold', v)"
          />
          <span class="slider-value">{{ percent(config.memory_dedup_threshold) }}</span>
        </div>
      </n-form-item>

      <n-form-item :label="t('knowledge.settings.worldBookDedupThreshold')" label-placement="top">
        <div class="slider-row">
          <n-slider
            :value="config.world_book_dedup_threshold"
            :min="0"
            :max="1"
            :step="0.01"
            @update:value="(v: number) => setDedupThreshold('world_book_dedup_threshold', v)"
          />
          <span class="slider-value">{{ percent(config.world_book_dedup_threshold) }}</span>
        </div>
      </n-form-item>

      <n-form-item :label="t('knowledge.settings.autoMemoryEnabled')" label-placement="top">
        <n-switch v-model:value="config.auto_memory_enabled" @update:value="markDirty" />
      </n-form-item>

      <n-grid :cols="2" :x-gap="16" :y-gap="12" responsive="screen" item-responsive>
        <n-gi :span="1">
          <n-form-item :label="t('knowledge.settings.autoMemoryMinLength')" label-placement="top">
            <n-input-number
              v-model:value="config.auto_memory_min_length"
              :min="0"
              :max="500"
              :step="1"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('knowledge.settings.autoMemoryCooldown')" label-placement="top">
            <n-input-number
              v-model:value="config.auto_memory_cooldown_seconds"
              :min="0"
              :max="3600"
              :step="1"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('knowledge.settings.autoMemoryPromoteObservations')" label-placement="top">
            <n-input-number
              v-model:value="config.auto_memory_promote_min_observations"
              :min="1"
              :max="50"
              :step="1"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('knowledge.settings.autoMemoryPromoteDistinctUsers')" label-placement="top">
            <n-input-number
              v-model:value="config.auto_memory_promote_min_distinct_users"
              :min="1"
              :max="50"
              :step="1"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('knowledge.settings.autoMemoryRecallTopK')" label-placement="top">
            <n-input-number
              v-model:value="config.auto_memory_recall_top_k"
              :min="1"
              :max="50"
              :step="1"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('knowledge.settings.autoMemoryRecallCharLimit')" label-placement="top">
            <n-input-number
              v-model:value="config.auto_memory_recall_char_limit"
              :min="300"
              :max="20000"
              :step="100"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('knowledge.settings.autoMemoryRecallMaxAgeDays')" label-placement="top">
            <n-input-number
              v-model:value="config.auto_memory_recall_max_age_days"
              :min="1"
              :max="3650"
              :step="1"
              class="full-width"
              @update:value="markDirty"
            />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('knowledge.settings.autoMemoryQualityThreshold')" label-placement="top">
            <div class="slider-row">
              <n-slider
                :value="config.auto_memory_quality_threshold"
                :min="0"
                :max="1"
                :step="0.01"
                @update:value="setQualityThreshold"
              />
              <span class="slider-value">{{ percent(config.auto_memory_quality_threshold) }}</span>
            </div>
          </n-form-item>
        </n-gi>
        <n-gi :span="2">
          <n-form-item :label="t('knowledge.settings.autoMemoryDirectPromoteAiTag')" label-placement="top">
            <n-switch v-model:value="config.auto_memory_direct_promote_ai_tag" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('knowledge.settings.memoryEmbeddingEnabled')" label-placement="top">
            <n-switch v-model:value="config.memory_embedding_enabled" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
        <n-gi :span="1">
          <n-form-item :label="t('knowledge.settings.memoryRerankEnabled')" label-placement="top">
            <n-switch v-model:value="config.memory_rerank_enabled" @update:value="markDirty" />
          </n-form-item>
        </n-gi>
      </n-grid>

      <n-button type="primary" @click="emit('save')">
        {{ t('knowledge.settings.save') }}
      </n-button>
    </SectionCard>
  </div>
</template>

<style scoped>
.section-hint {
  display: block;
  margin-bottom: 12px;
  font-size: 13px;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.slider-row .n-slider {
  flex: 1;
}

.slider-value {
  flex-shrink: 0;
  min-width: 44px;
  text-align: right;
  font-size: 13px;
  opacity: 0.85;
}

.full-width {
  width: 100%;
}
</style>
