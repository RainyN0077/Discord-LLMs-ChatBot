<script setup lang="ts">
import { NTag } from 'naive-ui'
import type { BotSummary } from '@/api/bots'

defineProps<{ bot: BotSummary; active: boolean }>()
const emit = defineEmits<{ select: [botId: string] }>()
</script>

<template>
  <div
    class="bot-card"
    :class="{ active }"
    role="button"
    tabindex="0"
    @click="emit('select', bot.bot_id)"
    @keydown.enter="emit('select', bot.bot_id)"
  >
    <div class="bot-card-header">
      <span class="bot-card-name">{{ bot.bot_name || bot.bot_id }}</span>
      <span class="bot-card-id">{{ bot.bot_id }}</span>
    </div>
    <div class="bot-card-meta">
      <n-tag size="small" :bordered="false" type="info">{{ bot.platform }}</n-tag>
      <n-tag
        size="small"
        :bordered="false"
        :type="bot.enabled ? (bot.status === 'running' ? 'success' : 'warning') : 'default'"
      >
        {{ bot.status }}
      </n-tag>
    </div>
  </div>
</template>

<style scoped>
.bot-card {
  padding: 10px 12px;
  margin: 4px 8px;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;
}

.bot-card:hover {
  background: rgba(148, 163, 184, 0.12);
}

.bot-card.active {
  background: rgba(69, 163, 230, 0.16);
  border-color: var(--n-primary-color, #45a3e6);
}

.bot-card-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.bot-card-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bot-card-id {
  font-size: 12px;
  opacity: 0.65;
  font-family: var(--font-mono);
}

.bot-card-meta {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
</style>
