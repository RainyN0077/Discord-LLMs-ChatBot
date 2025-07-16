<script>
  import { onMount } from 'svelte';
  import { t, setLang, lang } from './i18n.js';

  let config = {
    discord_token: '', 
    llm_provider: 'openai', 
    api_key: '', 
    base_url: '',
    model_name: 'gpt-4o', 
    system_prompt: '', 
    trigger_keywords: [], 
    stream_response: true, 
    user_personas: [],
    context_mode: 'channel',
    channel_context_settings: { message_limit: 10, char_limit: 4000 },
    memory_context_settings: { message_limit: 15, char_limit: 6000 },
    custom_parameters: [] 
  };

  let keywordsInput = '';
  let statusMessage = '';
  let statusType = 'info';
  let isLoading = false;
  let channelIdToClear = '';

  onMount(async () => {
    isLoading = true;
    showStatus($t('status.loading'), 'info');
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const loadedConfig = await res.json();
        if (Object.keys(loadedConfig).length > 0) {
            config = {...config, ...loadedConfig};
            if (config.user_personas) {
              config.user_personas = Object.entries(config.user_personas).map(([id, p]) => ({ id, nickname: p.nickname, prompt: p.prompt }));
            } else {
              config.user_personas = [];
            }
            keywordsInput = config.trigger_keywords.join(', ');
        }
      }
      statusMessage = '';
    } catch (e) { 
      showStatus($t('status.loadFailed') + e.message, 'error');
    } finally { 
      isLoading = false;
    }
  });
  
  function showStatus(message, type = 'info', duration = 5000) {
    statusMessage = message; statusType = type;
    if (type !== 'info' && type !== 'loading-special') {
        setTimeout(() => { if (statusMessage === message) statusMessage = ''; }, duration);
    }
  }
  
  async function handleSave() {
    isLoading = true;
    const personasAsObject = config.user_personas.reduce((acc, p) => { 
        if (p.id) acc[p.id] = { nickname: p.nickname, prompt: p.prompt };
        return acc; 
    }, {});
    const finalParams = config.custom_parameters.map(p => {
        let finalValue = p.value;
        if (p.type === 'number') { finalValue = parseFloat(p.value) || 0; }
        else if (p.type === 'boolean') { finalValue = p.value === 'true' || p.value === true; }
        return { ...p, value: finalValue };
    });
    const finalConfig = { 
        ...config, 
        user_personas: personasAsObject,
        custom_parameters: finalParams
    };
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
  function removePersona(index) { config.user_personas.splice(index, 1); config.user_personas = config.user_personas; }
  function addParameter() { config.custom_parameters = [...config.custom_parameters, { name: '', type: 'text', value: '' }]; }
  function removeParameter(index) { config.custom_parameters.splice(index, 1); config.custom_parameters = config.custom_parameters; }
  function handleParamTypeChange(param) {
    switch(param.type) {
        case 'number': param.value = 0; break;
        case 'boolean': param.value = 'true'; break;
        default: param.value = ''; break;
    }
  }
  
  async function handleClearMemory() {
    if (!channelIdToClear.trim()) {
        showStatus($t('sessionManagement.errorNoId'), 'error');
        return;
    }
    showStatus($t('sessionManagement.clearing'), 'loading-special');
    try {
        const res = await fetch('/api/memory/clear', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ channel_id: channelIdToClear })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to clear memory.');
        showStatus($t('sessionManagement.clearSuccess'), 'success');
        channelIdToClear = '';
    } catch (e) {
        showStatus($t('sessionManagement.clearFailed') + e.message, 'error');
    }
  }
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
        <label>{$t('contextControl.contextMode')}</label>
        <div class="radio-group">
            <label><input type="radio" bind:group={config.context_mode} value={'none'}> {$t('contextControl.modes.none')}</label>
            <label><input type="radio" bind:group={config.context_mode} value={'channel'}> {$t('contextControl.modes.channel')}</label>
            <label><input type="radio" bind:group={config.context_mode} value={'memory'}> {$t('contextControl.modes.memory')}</label>
        </div>
        {#if config.context_mode === 'channel'}
            <div class="context-settings">
                <p class="info">{$t('contextControl.channelModeInfo')}</p>
                 <div class="control-grid">
                    <label for="channel-context-messages">{$t('contextControl.historyLimit')}</label>
                    <div class="slider-container">
                        <input type="range" id="channel-context-messages" min="0" max="50" step="5" bind:value={config.channel_context_settings.message_limit}>
                        <span>{config.channel_context_settings.message_limit} {$t('contextControl.messages')}</span>
                    </div>
                    <label for="channel-context-chars">{$t('contextControl.charLimit')}</label>
                    <input type="number" id="channel-context-chars" placeholder={$t('contextControl.charLimitPlaceholder')} bind:value={config.channel_context_settings.char_limit}>
                </div>
            </div>
        {:else if config.context_mode === 'memory'}
             <div class="context-settings">
                <p class="info">{$t('contextControl.memoryModeInfo')}</p>
                 <div class="control-grid">
                    <label for="memory-context-messages">{$t('contextControl.historyLimit')}</label>
                    <div class="slider-container">
                        <input type="range" id="memory-context-messages" min="0" max="50" step="5" bind:value={config.memory_context_settings.message_limit}>
                        <span>{config.memory_context_settings.message_limit} {$t('contextControl.messages')}</span>
                    </div>
                    <label for="memory-context-chars">{$t('contextControl.charLimit')}</label>
                    <input type="number" id="memory-context-chars" placeholder={$t('contextControl.charLimitPlaceholder')} bind:value={config.memory_context_settings.char_limit}>
                </div>
            </div>
        {:else}
             <div class="context-settings">
                 <p class="info">{$t('contextControl.noneModeInfo')}</p>
             </div>
        {/if}
    </div>

    <div class="card">
        <h2>{$t('userPortrait.title')}</h2>
        <p class="info">{$t('userPortrait.info')}</p>
        <div class="list-container">
            {#if config.user_personas}
                {#each config.user_personas as persona, i (persona.id || i)}
                    <div class="list-item">
                        <div class="list-item-main">
                            <input class="id-input" type="text" placeholder={$t('userPortrait.userId')} bind:value={persona.id}>
                            <input class="nickname-input" type="text" placeholder={$t('userPortrait.customNicknamePlaceholder')} bind:value={persona.nickname}>
                            <textarea class="prompt-input" rows="2" placeholder={$t('userPortrait.personaPrompt')} bind:value={persona.prompt}></textarea>
                        </div>
                        <button class="remove-btn" on:click={() => removePersona(i)} title="Remove">×</button>
                    </div>
                {/each}
            {/if}
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
    
    <div class="card dark-theme">
        <h2>{$t('customParams.title')}</h2>
        <div class="list-container">
            {#if config.custom_parameters}
                {#each config.custom_parameters as param, i (i)}
                    <div class="list-item param-item">
                        <input class="param-input" type="text" placeholder={$t('customParams.paramName')} bind:value={param.name}>
                        <select class="param-select" bind:value={param.type} on:change={() => handleParamTypeChange(param)}>
                            <option value="text">{$t('customParams.types.text')}</option>
                            <option value="number">{$t('customParams.types.number')}</option>
                            <option value="boolean">{$t('customParams.types.boolean')}</option>
                            <option value="json">{$t('customParams.types.json')}</option>
                        </select>
                        {#if param.type === 'text'}
                            <input class="param-input" type="text" placeholder={$t('customParams.paramValue')} bind:value={param.value}>
                        {:else if param.type === 'number'}
                            <input class="param-input" type="number" step="0.01" placeholder={$t('customParams.paramValue')} bind:value={param.value}>
                        {:else if param.type === 'boolean'}
                            <select class="param-select wide" bind:value={param.value}>
                                <option value="true">True</option>
                                <option value="false">False</option>
                            </select>
                        {:else if param.type === 'json'}
                            <textarea class="param-input param-textarea" rows="1" placeholder={$t('customParams.paramValue')} bind:value={param.value}></textarea>
                        {/if}
                        <button class="remove-btn" on:click={() => removeParameter(i)} title="Remove">×</button>
                    </div>
                {/each}
            {/if}
        </div>
        <button class="add-btn" on:click={addParameter}>{$t('customParams.add')}</button>
    </div>

    <div class="card">
        <h2>{$t('sessionManagement.title')}</h2>
        <p class="info">{$t('sessionManagement.info')}</p>
        <div class="action-container">
            <input type="text" placeholder={$t('sessionManagement.channelIdPlaceholder')} bind:value={channelIdToClear}>
            <button class="action-btn" on:click={handleClearMemory}>{$t('sessionManagement.clearButton')}</button>
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
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif;
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
.save-container { text-align: center; margin-top: 1rem; }
.save-button { background-color: var(--save-color); color: white; font-size: 1.2rem; box-shadow: 0 2px 4px rgba(46, 204, 113, 0.3); }
.save-button:hover:not(:disabled) { background-color: var(--save-hover); transform: translateY(-2px); }
.radio-group { display: flex; flex-wrap: wrap; gap: 1.5rem; margin-bottom: 1rem; }
.radio-group label { display: flex; align-items: center; gap: 0.5rem; font-weight: normal; color: var(--text-color); cursor: pointer; white-space: nowrap; }
.info { font-size: 0.9rem; color: var(--text-light); margin: 0; padding-bottom: 0.5rem; }
.status-container { min-height: 60px; display: flex; justify-content: center; align-items: center; }
.status { padding: 1rem; border-radius: 8px; text-align: center; margin-top: 1rem; width: 100%; transition: opacity 0.3s ease; }
.status.success { background-color: var(--success-bg); color: var(--success-text); }
.status.error { background-color: var(--error-bg); color: var(--error-text); }
.status.info, .status.loading-special { background-color: var(--info-bg); color: var(--info-text); }
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
.context-settings { border-top: 1px solid var(--border-color); margin-top: 1rem; padding-top: 1.5rem; }
.lang-switcher { position: fixed; top: 1rem; right: 1rem; display: flex; gap: 0.5rem; background-color: var(--card-bg); padding: 0.5rem; border-radius: 8px; box-shadow: var(--shadow); z-index: 1000; }
.lang-switcher button { background-color: transparent; color: var(--text-light); padding: 0.5rem 1rem; }
.lang-switcher button.active { color: var(--primary-color); font-weight: 700; }
.dark-theme { background-color: #202123; border: 1px solid #444654; color: #ececf1; }
.dark-theme h2, .dark-theme label { color: #ececf1; border-color: #444654; }
.dark-theme input, .dark-theme select, .dark-theme textarea { background-color: #40414f; border: 1px solid #565869; color: #ececf1; border-radius: 6px; }
.dark-theme input::placeholder, .dark-theme textarea::placeholder { color: #8e8ea0; }
.dark-theme .remove-btn { color: #acacbe; }
.dark-theme .remove-btn:hover { background-color: rgba(239, 68, 68, 0.2); color: #ef4444; }
.dark-theme .add-btn { color: #ececf1; background-color: #40414f; border: 1px solid #565869; }
.dark-theme .add-btn:hover { background-color: #4d4e5a; }
.param-item { display: grid; grid-template-columns: 1.5fr 1fr 2fr auto; gap: 1rem; align-items: center; }
.param-select.wide { grid-column: 3 / 4; }
.param-textarea { resize: vertical; min-height: 44px; font-family: monospace; grid-column: 3 / 4; }
.param-item > .remove-btn { justify-self: center; }
.action-container { display: flex; gap: 1rem; align-items: center; }
.action-container input { flex-grow: 1; }
.action-btn { background-color: var(--error-bg); color: var(--error-text); border: 1px solid var(--error-text); white-space: nowrap; }
.action-btn:hover { background-color: var(--error-text); color: white; }
</style>
