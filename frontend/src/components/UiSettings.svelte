<script>
  import { t } from '../i18n.js';
  import { customFontName, timezoneStore, showStatus } from '../lib/commonStores.js';
  import { saveToIndexedDB, deleteFromIndexedDB } from '../lib/fontStorage.js';
  import { handleError } from '../lib/errorHandler.js';
  import Card from './Card.svelte';

  /**
   * @prop {function} applyFont - callback to apply font data to the document
   */
  export let applyFont;

  let fontFileInput;

  const commonTimezones = [
    'UTC',
    'Asia/Shanghai',
    'America/New_York',
    'America/Los_Angeles',
    'Europe/London',
    'Europe/Berlin',
    'Asia/Tokyo'
  ];

  function handleFontFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const ALLOWED_FONT_TYPES = [
      'font/ttf',
      'font/otf',
      'font/woff',
      'font/woff2',
      'application/font-woff',
      'application/x-font-ttf',
      'application/x-font-otf',
      'application/octet-stream'
    ];

    if (!ALLOWED_FONT_TYPES.includes(file.type)) {
      const ext = file.name.split('.').pop()?.toLowerCase();
      const allowedExts = ['ttf', 'otf', 'woff', 'woff2'];
      if (!ext || !allowedExts.includes(ext)) {
        showStatus(t('uiSettings.font.invalidType'), 'error');
        event.target.value = '';
        return;
      }
    }

    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      showStatus(t('uiSettings.font.fileTooLarge', {
        size: (file.size / 1024 / 1024).toFixed(2),
        maxSize: 50
      }), 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
      const fontDataUrl = e.target.result;
      try {
        await saveToIndexedDB('customFontDataUrl', fontDataUrl);
        await saveToIndexedDB('customFontName', file.name);
        applyFont(fontDataUrl, file.name);
        showStatus(t('uiSettings.font.loadSuccess'), 'success');
      } catch (error) {
        handleError('FontStorage', error);
        showStatus(t('uiSettings.font.storageError') + ': ' + error.message, 'error');
      }
    };
    reader.onerror = () => {
      showStatus(t('uiSettings.font.loadError'), 'error');
    };
    reader.readAsDataURL(file);
  }

  async function resetFont() {
    const styleElement = document.getElementById('custom-font-style');
    if (styleElement) styleElement.remove();

    try {
      await deleteFromIndexedDB('customFontDataUrl');
      await deleteFromIndexedDB('customFontName');
    } catch (e) {
      handleError('FontClear', e);
    }

    customFontName.set('');
    showStatus(t('uiSettings.font.resetSuccess'), 'success');
  }
</script>

<Card title={$t('uiSettings.title')}>
  <div class="action-container">
    <button class="action-btn" on:click={() => fontFileInput.click()}>{$t('uiSettings.font.loadButton')}</button>
    <input type="file" bind:this={fontFileInput} on:change={handleFontFileSelect} accept=".ttf,.otf,.woff,.woff2" style="display:none;">
    <button class="action-btn-secondary" on:click={resetFont}>{$t('uiSettings.font.resetButton')}</button>
  </div>
  {#if $customFontName}
    <p class="info">{$t('uiSettings.font.currentFont', { fontName: $customFontName })}</p>
  {:else}
    <p class="info">{$t('uiSettings.font.defaultFont')}</p>
  {/if}
  <div class="setting-item">
    <label for="timezone-select">{$t('uiSettings.timezone.title')}</label>
    <select id="timezone-select" bind:value={$timezoneStore}>
      {#each commonTimezones as tz}
        <option value={tz}>{tz}</option>
      {/each}
    </select>
  </div>
</Card>

<style>
  .action-container {
    display: flex;
    gap: .7rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .setting-item {
    margin-top: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .setting-item label {
    flex-shrink: 0;
  }

  .setting-item select {
    width: 100%;
    padding: 0.5rem;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background-color: var(--input-bg);
    color: var(--text-color);
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

  .action-btn-secondary {
    background: var(--control-bg);
    color: var(--text-color);
    border: 1px solid var(--panel-muted-border);
  }

  .action-btn-secondary:hover:not(:disabled) {
    background: var(--control-hover-bg);
    transform: translateY(-1px);
  }

  @media (max-width: 600px) {
    .action-container > * {
      width: 100%;
    }

    .setting-item {
      flex-direction: column;
      align-items: flex-start;
      gap: .35rem;
    }

    .setting-item select {
      width: 100%;
    }
  }
</style>
