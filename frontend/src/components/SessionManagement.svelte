<script>
  import { t } from '../i18n.js';
  import { showStatus } from '../lib/commonStores.js';
  import { clearMemory } from '../lib/api.js';
  import Card from './Card.svelte';

  let channelIdToClear = '';

  async function handleClearMemory() {
    if (!channelIdToClear.trim()) {
      showStatus(t('sessionManagement.errorNoId'), 'error');
      return;
    }
    showStatus(t('sessionManagement.clearing'), 'loading-special');
    try {
      await clearMemory(channelIdToClear);
      showStatus(t('sessionManagement.clearSuccess'), 'success');
      channelIdToClear = '';
    } catch (e) {
      showStatus(t('sessionManagement.clearFailed') + e.message, 'error');
    }
  }
</script>

<Card title={$t('sessionManagement.title')}>
  <p class="info">{$t('sessionManagement.info')}</p>
  <div class="action-container">
    <input type="text" placeholder={$t('sessionManagement.channelIdPlaceholder')} bind:value={channelIdToClear}>
    <button class="action-btn" on:click={handleClearMemory}>{$t('sessionManagement.clearButton')}</button>
  </div>
</Card>

<style>
  .action-container {
    display: flex;
    gap: .7rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .action-btn {
    background: linear-gradient(135deg, var(--primary-color), #1b73b0);
    color: #fff;
    border: 1px solid transparent;
  }

  .action-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(31, 139, 214, .24);
  }

  @media (max-width: 600px) {
    .action-container > * {
      width: 100%;
    }
  }
</style>
