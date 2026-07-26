<script>
  import { onDestroy } from 'svelte';
  import { t } from '../i18n.js';
  import { coreConfig } from '../lib/stores.js';
  import { showStatus } from '../lib/commonStores.js';
  import Card from './Card.svelte';

  let showAstrbotModal = false;
  let astrbotCountdown = 0;
  let astrbotCountdownTimer = null;
  let astrbotPendingMode = 'nonebot';

  function handleAstrbotToggle(event) {
    const wantsAstrbot = event.target.checked;
    const currentMode = $coreConfig.provider_mode || 'nonebot';

    if (wantsAstrbot && currentMode !== 'astrbot') {
      astrbotPendingMode = 'astrbot';
      showAstrbotModal = true;
      astrbotCountdown = 3;
      startAstrbotCountdown();
    } else if (!wantsAstrbot && currentMode === 'astrbot') {
      coreConfig.update(c => ({ ...c, provider_mode: 'nonebot' }));
      showStatus(t('astrBotMigration.switchBackSuccess'), 'success', 3000);
    }
  }

  function startAstrbotCountdown() {
    if (astrbotCountdownTimer) clearInterval(astrbotCountdownTimer);
    astrbotCountdownTimer = setInterval(() => {
      astrbotCountdown -= 1;
      if (astrbotCountdown <= 0) {
        clearInterval(astrbotCountdownTimer);
        astrbotCountdownTimer = null;
        astrbotCountdown = 0;
      }
    }, 1000);
  }

  function confirmAstrbotSwitch() {
    if (astrbotCountdown > 0) return;
    coreConfig.update(c => ({ ...c, provider_mode: astrbotPendingMode }));
    showAstrbotModal = false;
    if (astrbotCountdownTimer) {
      clearInterval(astrbotCountdownTimer);
      astrbotCountdownTimer = null;
    }
    showStatus(t('astrBotMigration.switchSuccess'), 'warning', 6000);
  }

  function cancelAstrbotSwitch() {
    showAstrbotModal = false;
    astrbotPendingMode = 'nonebot';
    if (astrbotCountdownTimer) {
      clearInterval(astrbotCountdownTimer);
      astrbotCountdownTimer = null;
    }
    coreConfig.update(c => ({ ...c, provider_mode: 'nonebot' }));
  }

  onDestroy(() => {
    if (astrbotCountdownTimer) {
      clearInterval(astrbotCountdownTimer);
      astrbotCountdownTimer = null;
    }
  });
</script>

<!-- AstrBot Migration Toggle -->
<Card title={$t('astrBotMigration.title')}>
  <p class="info">{$t('astrBotMigration.info')}</p>
  <label class="toggle-switch switch-spring">
    <input
      type="checkbox"
      checked={($coreConfig.provider_mode || 'nonebot') === 'astrbot'}
      on:change={(e) => handleAstrbotToggle(e)}
    >
    <span class="slider"></span>
    <span class="toggle-label">
      {($coreConfig.provider_mode || 'nonebot') === 'astrbot' ? $t('astrBotMigration.switchToAstrbot') : $t('astrBotMigration.switchToNonebot')}
    </span>
  </label>
</Card>

<!-- AstrBot Migration Confirmation Modal -->
{#if showAstrbotModal}
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-overlay" role="dialog" aria-modal="true" tabindex="-1" on:click={cancelAstrbotSwitch} on:keydown={(e) => { if (e.key === 'Escape') cancelAstrbotSwitch(); }}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="modal-content astrbot-modal" role="presentation" on:click|stopPropagation>
      <h3>{$t('astrBotMigration.modalTitle')}</h3>
      <div class="astrbot-warning">
        <p><strong>{$t('astrBotMigration.warningBeta')}</strong></p>
        <p>{$t('astrBotMigration.warningInfo1')}</p>
        <p>{$t('astrBotMigration.warningInfo2')}</p>
      </div>
      <div class="astrbot-countdown">
        {#if astrbotCountdown > 0}
          <p>{$t('astrBotMigration.countdownText', { countdown: astrbotCountdown })}</p>
        {:else}
          <p>{$t('astrBotMigration.countdownReady')}</p>
        {/if}
      </div>
      <div class="astrbot-modal-actions">
        <button
          class="astrbot-confirm-btn"
          disabled={astrbotCountdown > 0}
          on:click={confirmAstrbotSwitch}
        >
          {astrbotCountdown > 0 ? $t('astrBotMigration.confirmButtonWait', { countdown: astrbotCountdown }) : $t('astrBotMigration.confirmButton')}
        </button>
        <button class="astrbot-cancel-btn" on:click={cancelAstrbotSwitch}>
          {$t('astrBotMigration.cancelButton')}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .toggle-label {
    font-weight: 500;
  }

  /* --- AstrBot Migration Modal --- */
  .modal-overlay {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.6); display: flex; align-items: center;
    justify-content: center; z-index: 1000;
  }

  .astrbot-modal {
    background: var(--card-bg); border: 1px solid var(--border-color);
    border-radius: 12px; padding: 2rem; max-width: 480px; width: 90%;
    box-shadow: 0 8px 32px rgba(0,0,0,.4);
  }

  .astrbot-modal h3 {
    margin: 0 0 1rem; font-size: 1.2rem; color: var(--primary-color);
  }

  .astrbot-warning {
    background: rgba(255, 152, 0, 0.12); border-left: 4px solid #ff9800;
    border-radius: 6px; padding: .75rem 1rem; margin-bottom: 1rem;
    font-size: .85rem; line-height: 1.5;
  }

  .astrbot-warning p { margin: .25rem 0; }

  .astrbot-countdown {
    text-align: center; padding: .75rem; margin-bottom: 1rem;
    font-size: .9rem; color: var(--text-light);
  }

  .astrbot-modal-actions {
    display: flex; gap: .75rem; justify-content: flex-end;
  }

  .astrbot-confirm-btn {
    padding: .55rem 1.25rem; border: none; border-radius: 6px;
    cursor: pointer; font-size: .85rem; font-weight: 600;
    background: var(--primary-color); color: #fff; transition: opacity .2s;
  }

  .astrbot-confirm-btn:disabled {
    opacity: .45; cursor: not-allowed;
  }

  .astrbot-cancel-btn {
    padding: .55rem 1.25rem; border: 1px solid var(--border-color);
    border-radius: 6px; cursor: pointer; font-size: .85rem;
    background: transparent; color: var(--text-light);
  }

  .astrbot-cancel-btn:hover { background: var(--border-color); }
</style>
