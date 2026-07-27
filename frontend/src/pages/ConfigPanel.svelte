<script>
  import '../styles/lists.css';
  import { t, get as t_get } from '../i18n.js';
  import {
    coreConfig, behaviorConfig, contextConfig, customParameters,
    keywordsInput, setKeywords, pluginsConfig, userPersonas, roleConfigs, scopedPrompts
  } from '../lib/stores.js';
  import { customFontName, showStatus, activePage } from '../lib/commonStores.js';
  import { exportBotConfig, importBotConfig, getApiSecretKey } from '../lib/api.js';
  import { createConfigLoader, createSaveHandler } from '../lib/botConfigActions.js';
  import ThreeState from '../components/ThreeState.svelte';
  import Card from '../components/Card.svelte';
  import PluginEditor from '../components/PluginEditor.svelte';
  import SearchSettings from '../components/SearchSettings.svelte';
  import KnowledgeEditor from '../components/KnowledgeEditor.svelte';
  import AdvancedProviderCard from '../components/AdvancedProviderCard.svelte';
  import AutomationSettings from '../components/AutomationSettings.svelte';
  import UiSettings from '../components/UiSettings.svelte';
  import SessionManagement from '../components/SessionManagement.svelte';

  export let botId = null;
  export let applyFont;

  let isImporting = false;
  let importOverwrite = false;
  let importFileInput;
  let showImportConfirm = false;
  let importPendingData = null;
  let importPendingBotId = null;

  const { isLoading, error, trigger } = createConfigLoader(() => botId);
  const { isSaving, save } = createSaveHandler(() => botId);
  $: if (botId) trigger();

  async function handleExport() {
    if (!botId) return;
    try {
      await exportBotConfig(botId);
      showStatus(t_get('importExport.exportSuccess'), 'success');
    } catch (e) {
      showStatus(t_get('importExport.exportFailed', { error: e.message }), 'error');
    }
  }

  function handleImportClick() { if (importFileInput) importFileInput.click(); }

  async function handleImportFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    if (!file.name.endsWith('.json')) {
      showStatus(t_get('importExport.invalidFileType'), 'error');
      return;
    }
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      importPendingData = data;
      importPendingBotId = data.bot_id || '';
      showImportConfirm = true;
    } catch (e) {
      showStatus(t_get('importExport.invalidJson', { error: e.message }), 'error');
    } finally { event.target.value = ''; }
  }

  async function confirmImport() {
    if (!importPendingData) return;
    isImporting = true;
    showImportConfirm = false;
    try {
      const blob = new Blob([JSON.stringify(importPendingData, null, 2)], { type: 'application/json' });
      const file = new File([blob], 'config.json', { type: 'application/json' });
      const result = await importBotConfig(file, importOverwrite);
      showStatus(result.message || t_get('importExport.importSuccess'), 'success');
      importOverwrite = false;
    } catch (e) {
      showStatus(t_get('importExport.importFailed', { error: e.message }), 'error');
    } finally {
      isImporting = false;
      importPendingData = null;
      importPendingBotId = null;
    }
  }

  function cancelImport() {
    showImportConfirm = false;
    importPendingData = null;
    importPendingBotId = null;
    importOverwrite = false;
  }

  let activeTab = 'advanced';

  function addParameter() { customParameters.update(cp => { cp.push({ name: '', type: 'text', value: '' }); return cp; }); }
  function removeParameter(index) { customParameters.update(cp => { cp.splice(index, 1); return cp; }); }
  function handleParamTypeChange(index, newType) {
    const value = newType === 'number' ? 0 : (newType === 'boolean' ? 'true' : '');
    customParameters.update(cp => { cp[index].type = newType; cp[index].value = value; return cp; });
  }
</script>

<div class="config-panel">
  <div class="config-header">
    <h2>{botId ? $t('configPanel.configFor', { botId }) : $t('configPanel.selectBot')}</h2>
    <div class="header-actions">
      <button class="export-btn" on:click={handleExport} disabled={!botId} title={$t('importExport.exportTitle')}>&#8615; {$t('importExport.export')}</button>
      <button class="import-btn" on:click={handleImportClick} disabled={isImporting} title={$t('importExport.importTitle')}>&#8614; {$t('importExport.import')}</button>
      <input type="file" accept=".json" bind:this={importFileInput} on:change={handleImportFile} class="hidden-input">
      <button class="save-btn" on:click={save} disabled={$isSaving || !botId}>{$isSaving ? $t('configPanel.saving') : $t('configPanel.saveAndRestart')}</button>
    </div>
  </div>

  {#if showImportConfirm}
    <div class="import-confirm-overlay" role="dialog" aria-modal="true" tabindex="-1" on:click={cancelImport} on:keydown={(e) => e.key === 'Escape' && cancelImport()}>
      <div class="import-confirm-dialog" role="presentation" on:click|stopPropagation>
        <h3>{$t('importExport.importTitle_Dialog')}</h3>
        <p>{$t('importExport.importPrompt')} <strong>{importPendingBotId || 'unknown'}</strong>?</p>
        <label class="checkbox-inline fancy-checkbox" style="margin-bottom: 1rem;">
          <input type="checkbox" bind:checked={importOverwrite}>
          <span class="checkbox-box" aria-hidden="true"></span>
          <span class="checkbox-text">{$t('importExport.overwriteExisting')}</span>
        </label>
        <div class="import-confirm-actions">
          <button class="import-confirm-btn" on:click={confirmImport} disabled={isImporting}>{isImporting ? $t('importExport.importing') : $t('importExport.confirmImport')}</button>
          <button class="import-cancel-btn" on:click={cancelImport}>{$t('importExport.cancel')}</button>
        </div>
      </div>
    </div>
  {/if}

  <ThreeState loading={$isLoading} error={$error} empty={!botId} emptyMessage={$t('configPanel.selectBot')}>
    <span slot="loading-text">{botId ? $t('configPanel.loadingConfig', { botId }) : $t('status.loading')}</span>
    <div class="tabs">
      <button class:active={activeTab === 'core'} on:click={() => activeTab = 'core'}>{$t('tabs.core')}</button>
      <button class:active={activeTab === 'directives'} on:click={() => activeTab = 'directives'}>{$t('tabs.directives')}</button>
      <button class:active={activeTab === 'automation'} on:click={() => activeTab = 'automation'}>{$t('tabs.automation')}</button>
      <button class:active={activeTab === 'advanced'} on:click={() => activeTab = 'advanced'}>{$t('tabs.advanced')}</button>
    </div>

    {#if $coreConfig}
      {#if activeTab === 'core'}
      <div class="tab-content">
        <Card title={$t('globalConfig.title')}>
          <label for="discord-token">{$t('globalConfig.token')}</label>
          <input id="discord-token" type="password" placeholder={$t('globalConfig.tokenPlaceholder')} bind:value={$coreConfig.discord_token}>
          <label for="api-key-display">{$t('globalConfig.apiKey')}</label>
          <div class="api-key-container">
            <input id="api-key-display" type="password" readonly value={'\u2022'.repeat(16)} placeholder={$t('globalConfig.apiKeyUnavailable')}>
            <button on:click={async () => {
              try {
                await navigator.clipboard.writeText(getApiSecretKey() || '');
                showStatus(t_get('globalConfig.copied'), 'success', 2000);
              } catch (e) {
                showStatus(t_get('globalConfig.copyFailed'), 'error', 2000);
              }
            }} title={$t('globalConfig.copy')}>
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            </button>
          </div>
          <p class="info">{$t('globalConfig.apiKeyInfo')}</p>
        </Card>

        {#if botId && $coreConfig.discord_token}
          {@const intents = $coreConfig.discord_intents || {}}
          <Card title={$t('globalConfig.intents.title')}>
            <p class="info">{$t('globalConfig.intents.info')}</p>
            <div class="intent-grid">
              <label class="toggle-switch"><input type="checkbox" checked={intents.guilds !== false} on:change={(e) => coreConfig.update(c => ({...c, discord_intents: {...(c.discord_intents||{}), guilds: e.target.checked}}))}><span class="slider"></span>{$t('globalConfig.intents.guilds')}</label>
              <label class="toggle-switch"><input type="checkbox" checked={intents.guild_messages !== false} on:change={(e) => coreConfig.update(c => ({...c, discord_intents: {...(c.discord_intents||{}), guild_messages: e.target.checked}}))}><span class="slider"></span>{$t('globalConfig.intents.guildMessages')}</label>
              <label class="toggle-switch"><input type="checkbox" checked={intents.direct_messages !== false} on:change={(e) => coreConfig.update(c => ({...c, discord_intents: {...(c.discord_intents||{}), direct_messages: e.target.checked}}))}><span class="slider"></span>{$t('globalConfig.intents.directMessages')}</label>
              <label class="toggle-switch"><input type="checkbox" checked={intents.message_content !== false} on:change={(e) => coreConfig.update(c => ({...c, discord_intents: {...(c.discord_intents||{}), message_content: e.target.checked}}))}><span class="slider"></span>{$t('globalConfig.intents.messageContent')}</label>
              <label class="toggle-switch"><input type="checkbox" checked={intents.members !== false} on:change={(e) => coreConfig.update(c => ({...c, discord_intents: {...(c.discord_intents||{}), members: e.target.checked}}))}><span class="slider"></span>{$t('globalConfig.intents.members')}</label>
            </div>
          </Card>
        {/if}

        <Card title={$t('llmProvider.title')}>
          <p class="info">{$t('modelSettings.goToModelSettings')}</p>
          <button class="action-btn" on:click={() => activePage.set('models')}>{$t('modelSettings.openSettings')}</button>
        </Card>

        {#if !$coreConfig.llm_is_multimodal}
          <AdvancedProviderCard task="ocr" />
        {/if}
        <AdvancedProviderCard task="embedding" />
        <AdvancedProviderCard task="rerank" />

        <Card title={$t('contextControl.title')}>
          <div class="group-label">{$t('contextControl.contextMode')}</div>
          <div class="radio-group">
            <label><input type="radio" name="context-mode" value='none' bind:group={$contextConfig.context_mode}> {$t('contextControl.modes.none')}</label>
            <label><input type="radio" name="context-mode" value='channel' bind:group={$contextConfig.context_mode}> {$t('contextControl.modes.channel')}</label>
            <label><input type="radio" name="context-mode" value='memory' bind:group={$contextConfig.context_mode}> {$t('contextControl.modes.memory')}</label>
          </div>
          {#if $contextConfig.context_mode !== 'none'}
            {@const settingsKey = `${$contextConfig.context_mode}_context_settings`}
            {#if $contextConfig[settingsKey]}
            <div class="context-settings">
              <p class="info">{$t(`contextControl.${$contextConfig.context_mode}ModeInfo`)}</p>
              <div class="control-grid">
              <label for="context-messages">{$t('contextControl.historyLimit')}</label>
              <div class="inline-input">
                <input type="number" id="context-messages" min="0" step="1" bind:value={$contextConfig[settingsKey].message_limit} disabled={$contextConfig[settingsKey].unlimited_message_count}>
                <label class="checkbox-inline fancy-checkbox">
                  <input type="checkbox" bind:checked={$contextConfig[settingsKey].unlimited_message_count}>
                  <span class="checkbox-box" aria-hidden="true"></span>
                  <span class="checkbox-text">{$t('contextControl.unlimitedHistoryMessages')}</span>
                </label>
              </div>
              <label for="context-chars">{$t('contextControl.charLimit')}</label>
              <div class="inline-input">
                <input type="number" id="context-chars" placeholder={$t('contextControl.charLimitPlaceholder')} bind:value={$contextConfig[settingsKey].char_limit} disabled={$contextConfig[settingsKey].unlimited_context_length}>
                <label class="checkbox-inline fancy-checkbox">
                  <input type="checkbox" bind:checked={$contextConfig[settingsKey].unlimited_context_length}>
                  <span class="checkbox-box" aria-hidden="true"></span>
                  <span class="checkbox-text">{$t('contextControl.unlimitedContextLength')}</span>
                </label>
              </div>
              </div>
            </div>
            {/if}
          {:else}<div class="context-settings"><p class="info">{$t('contextControl.noneModeInfo')}</p></div>{/if}
        </Card>
      </div>
      {/if}

      {#if activeTab === 'directives'}
      <div class="tab-content">
        <KnowledgeEditor {botId} />
        <Card title={$t('defaultBehavior.title')}>
          <label for="bot-nickname">{$t('defaultBehavior.botNickname')}</label>
          <input id="bot-nickname" type="text" placeholder={$t('defaultBehavior.botNicknamePlaceholder')} bind:value={$behaviorConfig.bot_nickname}>
          <label for="system-prompt">{$t('defaultBehavior.systemPrompt')}</label>
          <textarea id="system-prompt" rows="4" placeholder={$t('defaultBehavior.systemPromptPlaceholder')} bind:value={$behaviorConfig.system_prompt}></textarea>
          <label for="blocked-response">{$t('defaultBehavior.blockedResponse')}</label>
          <input id="blocked-response" type="text" bind:value={$behaviorConfig.blocked_prompt_response}>
          <p class="info">{$t('defaultBehavior.blockedResponseInfo')}</p>
          <label for="trigger-keywords">{$t('defaultBehavior.triggerKeywords')}</label>
          <input id="trigger-keywords" type="text" placeholder={$t('defaultBehavior.triggerKeywordsPlaceholder')} value={$keywordsInput} on:input={e => setKeywords(e.target.value)}>
          <label for="trigger-match-mode">{$t('defaultBehavior.triggerMatchMode')}</label>
          <select id="trigger-match-mode" bind:value={$behaviorConfig.trigger_match_mode}>
            <option value="contains">{$t('defaultBehavior.triggerMatchModes.contains')}</option>
            <option value="starts_with">{$t('defaultBehavior.triggerMatchModes.startsWith')}</option>
            <option value="exact">{$t('defaultBehavior.triggerMatchModes.exact')}</option>
            <option value="regex">{$t('defaultBehavior.triggerMatchModes.regex')}</option>
          </select>
          <label><input type="checkbox" bind:checked={$behaviorConfig.trigger_case_sensitive}>{$t('defaultBehavior.triggerCaseSensitive')}</label>
          <div class="group-label">{$t('defaultBehavior.responseMode')}</div>
          <div class="radio-group">
            <label><input type="radio" name="stream-mode" value={true} bind:group={$behaviorConfig.stream_response}> {$t('defaultBehavior.modes.stream')}</label>
            <label><input type="radio" name="stream-mode" value={false} bind:group={$behaviorConfig.stream_response}> {$t('defaultBehavior.modes.nonStream')}</label>
          </div>
        </Card>
      </div>
      {/if}

      {#if activeTab === 'advanced'}
      <div class="tab-content">
        <PluginEditor />
        <SearchSettings />
        <Card title={$t('customParams.title')} theme="dark-theme">
          <div class="list-container">
            {#if $customParameters}
            {#each $customParameters as param, i}
              <div class="list-item param-item">
                <input class="param-input" type="text" placeholder={$t('customParams.paramName')} bind:value={param.name}>
                <select class="param-select" bind:value={param.type} on:change={(e) => handleParamTypeChange(i, e.currentTarget.value)}>
                  <option value="text">{$t('customParams.types.text')}</option><option value="number">{$t('customParams.types.number')}</option><option value="boolean">{$t('customParams.types.boolean')}</option><option value="json">{$t('customParams.types.json')}</option>
                </select>
                {#if param.type === 'text'}<input class="param-input" type="text" placeholder={$t('customParams.paramValue')} bind:value={param.value}>{:else if param.type === 'number'}<input class="param-input" type="number" step="0.01" placeholder={$t('customParams.paramValue')} bind:value={param.value}>{:else if param.type === 'boolean'}<select class="param-select wide" bind:value={param.value}><option value="true">True</option><option value="false">False</option></select>{:else if param.type === 'json'}<textarea class="param-input param-textarea" rows="1" placeholder={$t('customParams.paramValue')} bind:value={param.value}></textarea>{/if}
                <button class="remove-btn" on:click={() => removeParameter(i)} title={$t('customParams.remove')}>×</button>
              </div>
            {/each}
            {/if}
          </div>
          <button class="add-btn" on:click={addParameter}>{$t('customParams.add')}</button>
        </Card>
        <SessionManagement />
        <UiSettings {applyFont} />
      </div>
      {/if}

      {#if activeTab === 'automation'}
      <div class="tab-content">
        <AutomationSettings />
      </div>
      {/if}
    {/if}
  </ThreeState>
</div>

<style>
  .config-panel { padding: 1rem 1.5rem; overflow-y: auto; flex: 1; min-height: 0; box-sizing: border-box; }
  .config-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-shrink: 0; overflow: hidden; min-width: 0; }
  .config-header h2 { margin: 0; font-size: 1.2rem; color: var(--text-color); padding: .6rem 1rem; border-radius: 10px; background: linear-gradient(135deg, rgba(31, 139, 214, .1), rgba(24, 138, 81, .08)); border: 1px solid rgba(15, 23, 42, .08); box-shadow: var(--shadow-soft); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .save-btn { padding: .6rem 1.4rem; background: linear-gradient(135deg, var(--save-color), #1a9156); color: #fff; font-size: .95rem; font-weight: 600; border-radius: 10px; flex-shrink: 0; }
  .save-btn:disabled, .export-btn:disabled, .import-btn:disabled, .import-confirm-btn:disabled { opacity: .6; cursor: not-allowed; }
  .header-actions { display: flex; align-items: center; gap: .5rem; flex-shrink: 0; }
  .export-btn { padding: .6rem 1rem; background: linear-gradient(135deg, var(--primary-color), #1b73b0); color: #fff; font-size: .9rem; font-weight: 600; border-radius: 10px; flex-shrink: 0; }
  .import-btn { padding: .6rem 1rem; background: var(--panel-muted-bg); color: var(--text-color); font-size: .9rem; font-weight: 600; border: 1px solid var(--border-color); border-radius: 10px; flex-shrink: 0; }
  .hidden-input { display: none; }
  .import-confirm-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, .45); display: flex; align-items: center; justify-content: center; z-index: 200; }
  .import-confirm-dialog { background: var(--card-bg); border-radius: 14px; padding: 1.5rem; max-width: 420px; width: 90%; box-shadow: var(--shadow); border: 1px solid var(--border-color); }
  .import-confirm-dialog h3 { margin: 0 0 .75rem 0; font-size: 1.1rem; color: var(--text-color); }
  .import-confirm-dialog p { margin: 0 0 .5rem 0; color: var(--text-light); font-size: .95rem; }
  .import-confirm-actions { display: flex; gap: .75rem; justify-content: flex-end; margin-top: .5rem; }
  .import-confirm-btn { padding: .55rem 1.2rem; background: linear-gradient(135deg, var(--save-color), #1a9156); color: #fff; font-size: .9rem; font-weight: 600; border-radius: 8px; box-shadow: none; }
  .import-cancel-btn { padding: .55rem 1.2rem; background: var(--panel-muted-bg); color: var(--text-color); font-size: .9rem; font-weight: 600; border: 1px solid var(--border-color); border-radius: 8px; box-shadow: none; }
  .group-label { font-weight: 500; margin-bottom: .5rem; color: var(--text-light); }
  .tabs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); background: var(--floating-bg); border-radius: 14px; padding: .4rem; box-shadow: var(--shadow); margin-top: .85rem; margin-bottom: .2rem; position: sticky; top: .75rem; z-index: 20; border: 1px solid var(--floating-border); -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px); }
  .tabs button { flex: 1; padding: .65rem .5rem; border: none; background: transparent; font-size: .97rem; font-weight: 600; border-radius: 10px; cursor: pointer; color: var(--text-light); transition: all .2s ease-in-out; position: relative; }
  .tabs button::after { content: ''; position: absolute; bottom: -6px; left: 50%; transform: translateX(-50%) scaleX(0); width: 60%; height: 3px; background: var(--primary-color); border-radius: 2px; transition: transform .25s ease; }
  .tabs button.active::after { transform: translateX(-50%) scaleX(1); }
  .tabs button:hover { color: var(--text-color); background: var(--panel-muted-bg); }
  .tabs button.active { background: linear-gradient(135deg, var(--primary-color), #1d81bf); color: #fff; box-shadow: 0 4px 14px rgba(52, 152, 219, .28); }
  .action-btn { background: linear-gradient(135deg, var(--primary-color), #1b73b0); color: #fff; border: 1px solid transparent; }
  .action-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(31, 139, 214, .24); }
  .tab-content { display: flex; flex-direction: column; gap: 1.35rem; }
  .radio-group { display: flex; flex-wrap: wrap; gap: 1.5rem; }
  .radio-group label { display: flex; align-items: center; gap: .5rem; font-weight: 400; color: var(--text-color); cursor: pointer; white-space: nowrap; }
  .control-grid { display: grid; grid-template-columns: auto 1fr; gap: 1rem; align-items: center; }
  .context-settings { border-top: 1px solid var(--border-color); margin-top: 1rem; padding-top: 1.5rem; }
  .param-item { display: grid; grid-template-columns: 1.5fr 1fr 2fr auto; gap: .7rem; align-items: center; }
  .param-select.wide, .param-textarea { grid-column: 3/4; resize: vertical; min-height: 44px; font-family: monospace; }
  .param-item > .remove-btn { justify-self: center; }
  .api-key-container { display: grid; grid-template-columns: 1fr auto; gap: .5rem; align-items: center; }
  .api-key-container button { padding: .65rem .8rem; background: var(--control-bg); color: var(--text-color); border: 1px solid var(--panel-muted-border); }
  .inline-input { display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; }
  .inline-input input[type="number"] { max-width: 180px; }
  .checkbox-inline { display: inline-flex; align-items: center; gap: .45rem; color: var(--text-light); font-weight: 500; }
  .fancy-checkbox { position: relative; cursor: pointer; user-select: none; padding: .36rem .62rem .36rem .45rem; border-radius: 999px; border: 1px solid var(--panel-muted-border); background: var(--panel-muted-bg); transition: border-color .2s ease, background-color .2s ease, transform .15s ease; }
  .fancy-checkbox:hover { border-color: var(--primary-color); background: var(--control-bg); }
  .fancy-checkbox input[type="checkbox"] { position: absolute; opacity: 0; width: 0; height: 0; }
  .checkbox-box { width: 20px; height: 20px; border-radius: 6px; border: 1px solid var(--border-color); background: var(--surface-tint); display: inline-flex; align-items: center; justify-content: center; box-shadow: var(--shadow-soft); transition: all .2s ease; flex-shrink: 0; }
  .checkbox-box::after { content: ""; width: 10px; height: 6px; border-left: 2px solid #fff; border-bottom: 2px solid #fff; transform: rotate(-45deg) scale(0); transform-origin: center; margin-top: -1px; transition: transform .15s ease; }
  .checkbox-text { color: var(--text-color); line-height: 1.2; }
  .fancy-checkbox input[type="checkbox"]:checked + .checkbox-box { background: linear-gradient(135deg, var(--primary-color), #1b73b0); border-color: var(--primary-color); }
  .fancy-checkbox input[type="checkbox"]:checked + .checkbox-box::after { transform: rotate(-45deg) scale(1); }
  .fancy-checkbox input[type="checkbox"]:focus-visible + .checkbox-box { box-shadow: 0 0 0 3px rgba(69, 163, 230, .35); }
  .intent-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: .5rem 1rem; }
  .intent-grid .toggle-switch { font-size: .8rem; }
  @media (max-width: 900px) {
    .config-panel { padding: .75rem 1rem; }
    .config-header { flex-wrap: wrap; gap: .5rem; }
    .config-header h2 { font-size: 1rem; padding: .45rem .75rem; }
    .save-btn { padding: .5rem 1rem; font-size: .85rem; }
    .export-btn, .import-btn { padding: .5rem .8rem; font-size: .8rem; border-radius: 8px; }
    .tabs { top: .5rem; }
    .tabs button { font-size: .85rem; padding: .5rem .35rem; }
    .radio-group { gap: 1rem; }
    .control-grid { grid-template-columns: 1fr; gap: .6rem; }
    .param-item { grid-template-columns: 1fr; }
    .param-item > .remove-btn { justify-self: start; }
  }
  @media (max-width: 600px) {
    .config-panel { padding: .5rem .6rem; }
    .config-header h2 { font-size: .85rem; padding: .35rem .6rem; }
    .save-btn { padding: .4rem .8rem; font-size: .78rem; border-radius: 8px; }
    .export-btn, .import-btn { padding: .35rem .55rem; font-size: .72rem; border-radius: 7px; }
    .header-actions { gap: .35rem; }
    .tabs { border-radius: 10px; padding: .25rem; top: .35rem; }
    .tabs button { font-size: .75rem; padding: .4rem .25rem; border-radius: 7px; }
    .tab-content { gap: .8rem; }
    .inline-input { flex-direction: column; align-items: flex-start; }
    .inline-input input[type="number"] { max-width: 100%; }
  }
</style>
