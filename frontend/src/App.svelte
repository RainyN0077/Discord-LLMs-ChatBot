<script>
  import { onMount } from 'svelte';
  import { t, setLang, lang } from './i18n.js';

  let config = {
    discord_token: '', llm_provider: 'openai', api_key: '', base_url: '',
    model_name: 'gpt-4o', system_prompt: '', trigger_keywords: [], 
    stream_response: true, user_personas: [],
    context_message_limit: 10, context_char_limit: 4000
  };

  let keywordsInput = '';
  let statusMessage = '';
  let statusType = 'info';
  let isLoading = false;

  onMount(async () => {
    isLoading = true;
    showStatus($t('status.loading'), 'info');
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const loadedConfig = await res.json();
        if(Object.keys(loadedConfig).length > 0) {
            config.context_message_limit = loadedConfig.context_message_limit ?? 10;
            config.context_char_limit = loadedConfig.context_char_limit ?? 4000;
            if (loadedConfig.user_personas) {
              loadedConfig.user_personas = Object.entries(loadedConfig.user_personas).map(([id, p]) => ({ id, nickname: p.nickname, prompt: p.prompt }));
            }
            Object.assign(config, loadedConfig);
            keywordsInput = config.trigger_keywords.join(', ');
        }
      }
      statusMessage = ''; // Clear loading message on success
    } catch (e) { 
      showStatus($t('status.loadFailed') + e.message, 'error');
    } finally { 
      isLoading = false;
    }
  });
  
  function showStatus(message, type = 'info', duration = 5000) {
    statusMessage = message; statusType = type;
    if (type !== 'info') {
      setTimeout(() => { statusMessage = ''; }, duration);
    }
  }
  
  async function handleSave() {
    isLoading = true;
    const personasAsObject = config.user_personas.reduce((acc, p) => { 
        if (p.id) acc[p.id] = { nickname: p.nickname, prompt: p.prompt };
        return acc; 
    }, {});
    
    const finalConfig = { ...config, user_personas: personasAsObject };
    finalConfig.trigger_keywords = keywordsInput.split(',').map(k => k.trim()).filter(Boolean);
    
    showStatus($t('status.saving'), 'info');
    try {
      const res = await fetch('/api/config', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(finalConfig),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to save.');
      showStatus($t('status.saveSuccess'), 'success');
    } catch (e) { 
      showStatus($t('status.saveFailed') + e.message, 'error');
    } finally { 
      isLoading = false; 
    }
  }

  function addPersona() { config.user_personas = [...config.user_personas, { id: '', nickname: '', prompt: '' }]; }
  function removePersona(index) { config.user_personas = config.user_personas.filter((_, i) => i !== index); }
</script>

<div class="lang-switcher">
    <button class:active={$lang === 'zh'} on:click={() => setLang('zh')}>中文</button>
    <button class:active={$lang === 'en'} on:click={() => setLang('en')}>English</button>
</div>

<main>
    <h1>{$t('title')}</h1>

    <div class="card">
        <h2>{$t('globalConfig.title')}</h2>
        <label for="discord-token">{$t('globalConfig.token')}</label>
        <input id="discord-token" type="password" placeholder={$t('globalConfig.tokenPlaceholder')} bind:value={config.discord_token}>
    </div>

    <div class="card">
        <h2>{$t('llmProvider.title')}</h2>
        <label for="llm-provider">{$t('llmProvider.select')}</label>
        <select id="llm-provider" bind:value={config.llm_provider}>
            <option value="openai">{$t('llmProvider.providers.openai')}</option>
            <option value="google">{$t('llmProvider.providers.google')}</option>
            <option value="anthropic">{$t('llmProvider.providers.anthropic')}</option>
        </select>
        <label for="api-key">{$t('llmProvider.apiKey')}</label>
        <input id="api-key" type="password" placeholder={$t('llmProvider.apiKeyPlaceholder')} bind:value={config.api_key}>
        {#if config.llm_provider === 'openai'}
            <label for="base-url">{$t('llmProvider.baseUrl')}</label>
            <input id="base-url" type="text" placeholder={$t('llmProvider.baseUrlPlaceholder')} bind:value={config.base_url}>
        {/if}
    </div>
  
    <div class="card">
        <h2>{$t('contextControl.title')}</h2>
        <p class="info">{$t('contextControl.info')}</p>
        <div class="control-grid">
            <label for="context-messages">{$t('contextControl.historyLimit')}</label>
            <div class="slider-container">
                <input type="range" id="context-messages" min="0" max="50" step="5" bind:value={config.context_message_limit}>
                <span>{config.context_message_limit} {$t('contextControl.messages')}</span>
            </div>
            <label for="context-chars">{$t('contextControl.charLimit')}</label>
            <input type="number" id="context-chars" placeholder={$t('contextControl.charLimitPlaceholder')} bind:value={config.context_char_limit}>
        </div>
    </div>

    <div class="card">
        <h2>{$t('userPortrait.title')}</h2>
        <p class="info">{$t('userPortrait.info')}</p>
        <div class="list-container">
            {#each config.user_personas as persona, i}
                <div class="list-item">
                    <div class="list-item-main">
                        <input class="id-input" type="text" placeholder={$t('userPortrait.userId')} bind:value={persona.id}>
                        <input class="nickname-input" type="text" placeholder={$t('userPortrait.customNicknamePlaceholder')} bind:value={persona.nickname}>
                        <textarea class="prompt-input" rows="2" placeholder={$t('userPortrait.personaPrompt')} bind:value={persona.prompt}></textarea>
                    </div>
                    <button class="remove-btn" on:click={() => removePersona(i)} title="Remove">×</button>
                </div>
            {/each}
        </div>
        <button class="add-btn" on:click={addPersona}>{$t('userPortrait.add')}</button>
    </div>

    <div class="card">
        <h2>{$t('defaultBehavior.title')}</h2>
        <label for="model-name">{$t('defaultBehavior.modelName')}</label>
        <input id="model-name" type="text" placeholder={$t(`defaultBehavior.modelPlaceholders.${config.llm_provider}`)} bind:value={config.model_name}>
        
        <label for="system-prompt">{$t('defaultBehavior.systemPrompt')}</label>
        <textarea id="system-prompt" rows="4" placeholder={$t('defaultBehavior.systemPromptPlaceholder')} bind:value={config.system_prompt}></textarea>
        
        <label for="trigger-keywords">{$t('defaultBehavior.triggerKeywords')}</label>
        <input id="trigger-keywords" type="text" placeholder={$t('defaultBehavior.triggerKeywordsPlaceholder')} bind:value={keywordsInput}>
        
        <label>{$t('defaultBehavior.responseMode')}</label>
        <div class="radio-group">
            <label><input type="radio" bind:group={config.stream_response} value={true}> {$t('defaultBehavior.modes.stream')}</label>
            <label><input type="radio" bind:group={config.stream_response} value={false}> {$t('defaultBehavior.modes.nonStream')}</label>
        </div>
    </div>

    <div class="save-container">
        <button class="save-button" on:click={handleSave} disabled={isLoading}>
            {isLoading ? $t('buttons.saving') : $t('buttons.save')}
        </button>
        <div class="status-container">
            <div class="status {statusType}" style:visibility={statusMessage ? 'visible' : 'hidden'}>{statusMessage || '...'}</div>
        </div>
    </div>
</main>

<style>
:root {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif;
    --bg-color: #f7f9fc;
    --card-bg: #ffffff;
    --text-color: #2c3e50;
    --text-light: #7f8c8d;
    --primary-color: #3498db;
    --primary-hover: #2980b9;
    --border-color: #e4e7eb;
    --success-bg: #e0f2f1; --success-text: #00796b;
    --error-bg: #fce4ec; --error-text: #c2185b;
    --info-bg: #e1f5fe; --info-text: #0277bd;
    --save-color: #2ecc71; --save-hover: #27ae60;
    --shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
}
body { background-color: var(--bg-color); color: var(--text-color); margin: 0; padding: 2rem; -webkit-font-smoothing: antialiased; }
main { max-width: 900px; margin: 4rem auto 0; display: flex; flex-direction: column; gap: 2rem; }
h1 { color: var(--primary-color); text-align: center; font-weight: 300; letter-spacing: 1px; margin-bottom: 2rem; }
h2 { color: var(--text-color); font-weight: 600; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-top: 0; }
.card { background: var(--card-bg); border-radius: 12px; padding: 2rem; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 1.2rem; transition: transform 0.2s ease-in-out; }
label { font-weight: 500; color: var(--text-light); }
input, textarea, select {
    width: 100%; padding: 0.8rem 1rem; border: 1px solid var(--border-color);
    border-radius: 8px; font-size: 1rem; box-sizing: border-box; background-color: #fcfdfe;
    transition: all 0.2s ease;
}
input:focus, textarea:focus, select:focus {
    outline: none; border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.2);
}
textarea { resize: vertical; font-family: inherit; }
button { border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: all 0.2s ease; padding: 0.8rem 1.5rem; }
button:disabled { cursor: not-allowed; opacity: 0.6; }
.save-container { text-align: center; }
.save-button { background-color: var(--save-color); color: white; font-size: 1.2rem; box-shadow: 0 2px 4px rgba(46, 204, 113, 0.3); }
.save-button:hover:not(:disabled) { background-color: var(--save-hover); transform: translateY(-2px); }
.radio-group { display: flex; gap: 1.5rem; }
.radio-group label { display: flex; align-items: center; gap: 0.5rem; font-weight: normal; color: var(--text-color); cursor: pointer; }
.info { font-size: 0.9rem; color: var(--text-light); margin-top: -0.5rem; }
.status-container { min-height: 60px; display: flex; justify-content: center; align-items: center; }
.status { padding: 1rem; border-radius: 8px; text-align: center; margin-top: 1rem; width: 100%; }
.status.success { background-color: var(--success-bg); color: var(--success-text); }
.status.error { background-color: var(--error-bg); color: var(--error-text); }
.status.info { background-color: var(--info-bg); color: var(--info-text); }
.list-container { display: flex; flex-direction: column; gap: 1rem; }
.list-item { display: flex; gap: 0.5rem; align-items: flex-start; }
.list-item-main { display: grid; grid-template-columns: 2fr 1.5fr; grid-template-rows: auto auto; gap: 0.5rem; flex-grow: 1; }
.id-input { grid-column: 1 / 2; }
.nickname-input { grid-column: 2 / 3; }
.prompt-input { grid-column: 1 / 3; }
.remove-btn { background-color: transparent; color: var(--text-light); padding: 0; width: 44px; height: 44px; line-height: 44px; text-align: center; font-size: 1.5rem; flex-shrink: 0; border-radius: 50%; }
.remove-btn:hover { background-color: var(--error-bg); color: var(--error-text); }
.add-btn { background-color: var(--info-bg); color: var(--info-text); align-self: flex-start; padding: 0.6rem 1.2rem; font-weight: 500;}
.add-btn:hover { background-color: #d1ecfa; }
.control-grid { display: grid; grid-template-columns: auto 1fr; gap: 1rem; align-items: center; }
.slider-container { display: flex; align-items: center; gap: 1rem; }
.slider-container input[type="range"] { flex-grow: 1; accent-color: var(--primary-color); }
.slider-container span { min-width: 110px; font-weight: 500; text-align: right; }
.lang-switcher { position: fixed; top: 1rem; right: 1rem; display: flex; gap: 0.5rem; background-color: var(--card-bg); padding: 0.5rem; border-radius: 8px; box-shadow: var(--shadow); z-index: 1000; }
.lang-switcher button { background-color: transparent; color: var(--text-light); padding: 0.5rem 1rem; }
.lang-switcher button.active { color: var(--primary-color); font-weight: 700; }
</style>
