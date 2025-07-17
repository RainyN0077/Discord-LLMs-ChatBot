<script>
  import { onMount, onDestroy } from 'svelte';
  import { t, setLang, lang } from './i18n.js';

  let config = {
    discord_token: '', llm_provider: 'openai', api_key: '', base_url: '', model_name: 'gpt-4o', system_prompt: '', 
    trigger_keywords: [], stream_response: true, user_personas: [], role_based_config: [], context_mode: 'channel',
    channel_context_settings: { message_limit: 10, char_limit: 4000 },
    memory_context_settings: { message_limit: 15, char_limit: 6000 },
    custom_parameters: [] 
  };
  let keywordsInput = '', statusMessage = '', statusType = 'info', isLoading = false;
  let channelIdToClear = '', rawLogs = '', logLevelFilter = 'ALL', logOutputElement;
  let autoScroll = true, logInterval;
  const logLevels = ['ALL', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

  async function fetchLogs() {
    try {
        const res = await fetch('/api/logs');
        rawLogs = res.ok ? await res.text() : 'Error loading logs...';
    } catch (e) {
        console.error("Failed to fetch logs:", e); rawLogs = 'Error loading logs...';
    }
  }

  onMount(async () => {
    isLoading = true; showStatus($t('status.loading'), 'info');
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const loadedConfig = await res.json();
        config = {...config, ...loadedConfig};
        config.user_personas = Object.entries(config.user_personas || {}).map(([id, p]) => ({ id, ...p }));
        config.role_based_config = Object.entries(config.role_based_config || {}).map(([id, r]) => ({ id, ...r }));
        keywordsInput = (config.trigger_keywords || []).join(', ');
      }
      statusMessage = '';
    } catch (e) { showStatus($t('status.loadFailed') + e.message, 'error');
    } finally { isLoading = false; }
    fetchLogs();
    logInterval = setInterval(fetchLogs, 5000);
  });
  
  onDestroy(() => { if (logInterval) clearInterval(logInterval); });
  
  $: parsedLogs = rawLogs.split('\n').filter(line => line.trim() !== '').map(line => ({ level: (line.match(/ - (INFO|WARNING|ERROR|CRITICAL) - /) || [])[1] || 'UNKNOWN', message: line }));
  $: filteredLogs = logLevelFilter === 'ALL' ? parsedLogs : parsedLogs.filter(log => log.level === logLevelFilter);
  $: if (filteredLogs && logOutputElement && autoScroll) {
    setTimeout(() => { if(logOutputElement) logOutputElement.scrollTop = logOutputElement.scrollHeight; }, 50);
  }

  function showStatus(message, type = 'info', duration = 5000) {
    statusMessage = message; statusType = type;
    if (type !== 'info' && type !== 'loading-special') {
        setTimeout(() => { if (statusMessage === message) statusMessage = ''; }, duration);
    }
  }
  
  async function handleSave() {
    isLoading = true;
    const personasAsObject = (config.user_personas || []).reduce((acc, p) => { if (p.id) acc[p.id] = { nickname: p.nickname, prompt: p.prompt }; return acc; }, {});
    const rolesAsObject = (config.role_based_config || []).reduce((acc, r) => {
        if (r.id) acc[r.id] = { 
            title: r.title, prompt: r.prompt, enable_message_limit: r.enable_message_limit,
            message_limit: parseInt(r.message_limit) || 0,
            message_refresh_minutes: parseInt(r.message_refresh_minutes) || 60,
            message_output_budget: 1, 
            enable_char_limit: r.enable_char_limit,
            char_limit: parseInt(r.char_limit) || 0,
            char_refresh_minutes: parseInt(r.char_refresh_minutes) || 60,
            char_output_budget: parseInt(r.char_output_budget) || 300,
            display_color: r.display_color
        };
        return acc;
    }, {});
    const finalParams = (config.custom_parameters || []).map(p => ({ ...p, value: p.type === 'number' ? parseFloat(p.value) || 0 : (p.type === 'boolean' ? (p.value === 'true' || p.value === true) : p.value) }));
    const finalConfig = { ...config, user_personas: personasAsObject, role_based_config: rolesAsObject, custom_parameters: finalParams, trigger_keywords: keywordsInput.split(',').map(k => k.trim()).filter(Boolean) };
    
    showStatus($t('status.saving'), 'info');
    try {
      const res = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(finalConfig) });
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed to save.');
      showStatus($t('status.saveSuccess'), 'success');
    } catch (e) { showStatus($t('status.saveFailed') + e.message, 'error');
    } finally { isLoading = false; }
  }

  function addPersona() { config.user_personas = [...(config.user_personas || []), { id: '', nickname: '', prompt: '' }]; }
  function removePersona(index) { config.user_personas.splice(index, 1); config.user_personas = config.user_personas; }
  function addRoleConfig() { config.role_based_config = [...(config.role_based_config || []), { id: '', title: '', prompt: '', enable_message_limit: false, message_limit: 0, message_refresh_minutes: 60, message_output_budget: 1, enable_char_limit: false, char_limit: 0, char_refresh_minutes: 60, char_output_budget: 300, display_color: '#ffffff' }]; }
  function removeRoleConfig(index) { config.role_based_config.splice(index, 1); config.role_based_config = config.role_based_config; }
  function addParameter() { config.custom_parameters = [...(config.custom_parameters || []), { name: '', type: 'text', value: '' }]; }
  function removeParameter(index) { config.custom_parameters.splice(index, 1); config.custom_parameters = config.custom_parameters; }
  function handleParamTypeChange(param) { param.value = param.type === 'number' ? 0 : (param.type === 'boolean' ? 'true' : ''); }
  async function handleClearMemory() {
    if (!channelIdToClear.trim()) { showStatus($t('sessionManagement.errorNoId'), 'error'); return; }
    showStatus($t('sessionManagement.clearing'), 'loading-special');
    try {
        const res = await fetch('/api/memory/clear', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ channel_id: channelIdToClear }) });
        if (!res.ok) throw new Error((await res.json()).detail || 'Failed to clear memory.');
        showStatus($t('sessionManagement.clearSuccess'), 'success'); channelIdToClear = '';
    } catch (e) { showStatus($t('sessionManagement.clearFailed') + e.message, 'error'); }
  }
</script>

<div class="lang-switcher"><button class:active={$lang === 'zh'} on:click={() => setLang('zh')}>中文</button><button class:active={$lang === 'en'} on:click={() => setLang('en')}>English</button></div>
<div class="page-container">
    <main>
        <h1>{$t('title')}</h1>
        <div class="card"><h2>{$t('globalConfig.title')}</h2><label for="discord-token">{$t('globalConfig.token')}</label><input id="discord-token" type="password" placeholder={$t('globalConfig.tokenPlaceholder')} bind:value={config.discord_token}></div>
        <div class="card"><h2>{$t('llmProvider.title')}</h2><label for="llm-provider">{$t('llmProvider.select')}</label><select id="llm-provider" bind:value={config.llm_provider}><option value="openai">{$t('llmProvider.providers.openai')}</option><option value="google">{$t('llmProvider.providers.google')}</option><option value="anthropic">{$t('llmProvider.providers.anthropic')}</option></select><label for="api-key">{$t('llmProvider.apiKey')}</label><input id="api-key" type="password" placeholder={$t('llmProvider.apiKeyPlaceholder')} bind:value={config.api_key}>{#if config.llm_provider === 'openai'}<label for="base-url">{$t('llmProvider.baseUrl')}</label><input id="base-url" type="text" placeholder={$t('llmProvider.baseUrlPlaceholder')} bind:value={config.base_url}>{/if}</div>
        <div class="card"><h2>{$t('contextControl.title')}</h2><label>{$t('contextControl.contextMode')}</label><div class="radio-group"><label><input type="radio" bind:group={config.context_mode} value={'none'}> {$t('contextControl.modes.none')}</label><label><input type="radio" bind:group={config.context_mode} value={'channel'}> {$t('contextControl.modes.channel')}</label><label><input type="radio" bind:group={config.context_mode} value={'memory'}> {$t('contextControl.modes.memory')}</label></div>{#if config.context_mode !== 'none'}<div class="context-settings"><p class="info">{config.context_mode === 'channel' ? $t('contextControl.channelModeInfo') : $t('contextControl.memoryModeInfo')}</p><div class="control-grid"><label for="context-messages">{$t('contextControl.historyLimit')}</label><div class="slider-container"><input type="range" id="context-messages" min="0" max="50" step="5" bind:value={config[config.context_mode + '_context_settings'].message_limit}><span>{config[config.context_mode + '_context_settings'].message_limit} {$t('contextControl.messages')}</span></div><label for="context-chars">{$t('contextControl.charLimit')}</label><input type="number" id="context-chars" placeholder={$t('contextControl.charLimitPlaceholder')} bind:value={config[config.context_mode + '_context_settings'].char_limit}></div></div>{:else}<div class="context-settings"><p class="info">{$t('contextControl.noneModeInfo')}</p></div>{/if}</div>
        <div class="card"><h2>{$t('userPortrait.title')}</h2><p class="info">{$t('userPortrait.info')}</p><div class="list-container">{#each (config.user_personas || []) as persona, i (persona.id || i)}<div class="list-item"><div class="list-item-main"><input class="id-input" type="text" placeholder={$t('userPortrait.userId')} bind:value={persona.id}><input class="nickname-input" type="text" placeholder={$t('userPortrait.customNicknamePlaceholder')} bind:value={persona.nickname}><textarea class="prompt-input" rows="2" placeholder={$t('userPortrait.personaPrompt')} bind:value={persona.prompt}></textarea></div><button class="remove-btn" on:click={() => removePersona(i)} title="Remove">×</button></div>{/each}</div><button class="add-btn" on:click={addPersona}>{$t('userPortrait.add')}</button></div>
        <div class="card"><h2>{$t('roleConfig.title')}</h2><p class="info">{$t('roleConfig.info')}</p><div class="list-container">{#each (config.role_based_config || []) as role, i (role.id || i)}<div class="list-item complex-item">
            <div class="list-item-main very-wide-grid">
                <input class="id-input" type="text" placeholder={$t('roleConfig.roleId')} bind:value={role.id}><input class="nickname-input" type="text" placeholder={$t('roleConfig.roleTitle')} bind:value={role.title}>
                <textarea class="prompt-input" rows="3" placeholder={$t('roleConfig.rolePrompt')} bind:value={role.prompt}></textarea>
                <div class="limit-control-group"><label class="toggle-switch"><input type="checkbox" bind:checked={role.enable_message_limit}><span class="slider"></span>{$t('roleConfig.enableMsgLimit')}</label><div class="limit-group" class:disabled={!role.enable_message_limit}><label>{$t('roleConfig.totalQuota')}:</label><input type="number" min="0" placeholder="0" bind:value={role.message_limit} disabled={!role.enable_message_limit}><span>/</span><input type="number" min="1" placeholder="60" bind:value={role.message_refresh_minutes} disabled={!role.enable_message_limit}><span class="unit">{$t('roleConfig.minutes')}</span></div></div>
                <div class="limit-control-group"><label class="toggle-switch"><input type="checkbox" bind:checked={role.enable_char_limit}><span class="slider"></span>{$t('roleConfig.enableTokenLimit')}</label><div class="limit-group" class:disabled={!role.enable_char_limit}><label>{$t('roleConfig.totalQuota')}:</label><input type="number" min="0" placeholder="0" bind:value={role.char_limit} disabled={!role.enable_char_limit}><span>/</span><input type="number" min="1" placeholder="60" bind:value={role.char_refresh_minutes} disabled={!role.enable_char_limit}><span class="unit">{$t('roleConfig.minutes')}</span></div><div class="limit-group budget-group" class:disabled={!role.enable_char_limit}><label>{$t('roleConfig.outputBudget')}:</label><input type="number" min="0" placeholder="300" bind:value={role.char_output_budget} disabled={!role.enable_char_limit}></div></div>
                <div class="preview-section"><label>{$t('roleConfig.previewTitle')}</label><div class="quota-preview"><div class="preview-header" style="color: {role.display_color};">{$t('roleConfig.previewHeader')}</div><div class="preview-field"><span class="field-name">{$t('roleConfig.msgLimit')}</span><span class="field-value" style="color: {role.display_color};">{#if role.enable_message_limit}{role.message_limit - Math.floor(role.message_limit / 3)}/{role.message_limit > 0 ? role.message_limit : '∞'}{:else}{$t('roleConfig.disabled')}{/if}</span></div><div class="preview-field"><span class="field-name">{$t('roleConfig.tokenLimit')}</span><span class="field-value" style="color: {role.display_color};">{#if role.enable_char_limit}{role.char_limit - Math.floor(role.char_limit / 4)}/{role.char_limit > 0 ? role.char_limit : '∞'}{:else}{$t('roleConfig.disabled')}{/if}</span></div></div></div>
                <div class="color-picker-section"><label for={`color-picker-${i}`}>{$t('roleConfig.displayColor')}</label><input id={`color-picker-${i}`} type="color" bind:value={role.display_color}></div>
            </div><button class="remove-btn" on:click={() => removeRoleConfig(i)} title="Remove">×</button>
        </div>{/each}</div><button class="add-btn" on:click={addRoleConfig}>{$t('roleConfig.add')}</button></div>
        <div class="card"><h2>{$t('defaultBehavior.title')}</h2><label for="model-name">{$t('defaultBehavior.modelName')}</label><input id="model-name" type="text" placeholder={$t(`defaultBehavior.modelPlaceholders.${config.llm_provider}`)} bind:value={config.model_name}><label for="system-prompt">{$t('defaultBehavior.systemPrompt')}</label><textarea id="system-prompt" rows="4" placeholder={$t('defaultBehavior.systemPromptPlaceholder')} bind:value={config.system_prompt}></textarea><label for="trigger-keywords">{$t('defaultBehavior.triggerKeywords')}</label><input id="trigger-keywords" type="text" placeholder={$t('defaultBehavior.triggerKeywordsPlaceholder')} bind:value={keywordsInput}><label>{$t('defaultBehavior.responseMode')}</label><div class="radio-group"><label><input type="radio" bind:group={config.stream_response} value={true}> {$t('defaultBehavior.modes.stream')}</label><label><input type="radio" bind:group={config.stream_response} value={false}> {$t('defaultBehavior.modes.nonStream')}</label></div></div>
        <div class="card dark-theme"><h2>{$t('customParams.title')}</h2><div class="list-container">{#each (config.custom_parameters || []) as param, i (i)}<div class="list-item param-item"><input class="param-input" type="text" placeholder={$t('customParams.paramName')} bind:value={param.name}><select class="param-select" bind:value={param.type} on:change={() => handleParamTypeChange(param)}><option value="text">{$t('customParams.types.text')}</option><option value="number">{$t('customParams.types.number')}</option><option value="boolean">{$t('customParams.types.boolean')}</option><option value="json">{$t('customParams.types.json')}</option></select>{#if param.type === 'text'}<input class="param-input" type="text" placeholder={$t('customParams.paramValue')} bind:value={param.value}>{:else if param.type === 'number'}<input class="param-input" type="number" step="0.01" placeholder={$t('customParams.paramValue')} bind:value={param.value}>{:else if param.type === 'boolean'}<select class="param-select wide" bind:value={param.value}><option value="true">True</option><option value="false">False</option></select>{:else if param.type === 'json'}<textarea class="param-input param-textarea" rows="1" placeholder={$t('customParams.paramValue')} bind:value={param.value}></textarea>{/if}<button class="remove-btn" on:click={() => removeParameter(i)} title="Remove">×</button></div>{/each}</div><button class="add-btn" on:click={addParameter}>{$t('customParams.add')}</button></div>
        <div class="card"><h2>{$t('sessionManagement.title')}</h2><p class="info">{$t('sessionManagement.info')}</p><div class="action-container"><input type="text" placeholder={$t('sessionManagement.channelIdPlaceholder')} bind:value={channelIdToClear}><button class="action-btn" on:click={handleClearMemory}>{$t('sessionManagement.clearButton')}</button></div></div>
        <div class="save-container"><button class="save-button" on:click={handleSave} disabled={isLoading}>{isLoading ? $t('buttons.saving') : $t('buttons.save')}</button><div class="status-container"><div class="status {statusType}" style:visibility={statusMessage ? 'visible' : 'hidden'}>{statusMessage || '...'}</div></div></div>
    </main>
    <aside class="log-viewer"><h2>{$t('logViewer.title')}</h2><div class="log-controls"><div class="log-filter-group"><span>{$t('logViewer.filterLevel')}:</span>{#each logLevels as level}<button class:active={logLevelFilter === level} on:click={() => {logLevelFilter = level; autoScroll = true;}}>{level}</button>{/each}</div><label class="autoscroll-toggle"><input type="checkbox" bind:checked={autoScroll}><span>{$t('logViewer.autoscroll')}</span></label></div><div class="log-output-wrapper"><pre bind:this={logOutputElement}><code>{#each filteredLogs as log, i (log.message + i)}<span class="log-line {log.level}">{log.message}</span>{'\n'}{/each}</code></pre></div></aside>
</div>

<style>
:root{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei UI","Microsoft YaHei",Segoe UI,Roboto,Oxygen,Ubuntu,Cantarell,"Fira Sans","Droid Sans",Helvetica Neue,sans-serif;--bg-color:#f7f9fc;--card-bg:#fff;--text-color:#2c3e50;--text-light:#7f8c8d;--primary-color:#3498db;--primary-hover:#2980b9;--border-color:#e4e7eb;--success-bg:#e0f2f1;--success-text:#00796b;--error-bg:#fce4ec;--error-text:#c2185b;--info-bg:#e1f5fe;--info-text:#0277bd;--save-color:#2ecc71;--save-hover:#27ae60;--shadow:0 4px 6px rgba(0,0,0,.05)}body{background-color:var(--bg-color);color:var(--text-color);margin:0;padding:2rem;-webkit-font-smoothing:antialiased}.page-container{display:flex;align-items:flex-start;gap:2rem;max-width:1600px;margin:0 auto}main{flex:1;min-width:600px;display:flex;flex-direction:column;gap:2rem}h1{color:var(--primary-color);text-align:center;font-weight:300;letter-spacing:1px;margin-bottom:0}h2{color:var(--text-color);font-weight:600;border-bottom:1px solid var(--border-color);padding-bottom:.5rem;margin-top:0}.card{background:var(--card-bg);border-radius:12px;padding:1.5rem 2rem;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:1.2rem}label{font-weight:500;color:var(--text-light)}input,select,textarea{width:100%;padding:.8rem 1rem;border:1px solid var(--border-color);border-radius:8px;font-size:1rem;box-sizing:border-box;background-color:#fcfdfe;transition:all .2s ease}input:focus,select:focus,textarea:focus{outline:0;border-color:var(--primary-color);box-shadow:0 0 0 3px rgba(52,152,219,.2)}textarea{resize:vertical;font-family:inherit}button{border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;transition:all .2s ease;padding:.8rem 1.5rem}button:disabled{cursor:not-allowed;opacity:.6}.save-container{text-align:center;margin-top:1rem}.save-button{background-color:var(--save-color);color:#fff;font-size:1.2rem;box-shadow:0 2px 4px rgba(46,204,113,.3)}.save-button:hover:not(:disabled){background-color:var(--save-hover);transform:translateY(-2px)}.radio-group{display:flex;flex-wrap:wrap;gap:1.5rem}.radio-group label{display:flex;align-items:center;gap:.5rem;font-weight:400;color:var(--text-color);cursor:pointer}.info{font-size:.9rem;color:var(--text-light);margin:0;padding-bottom:.5rem}.status-container{min-height:60px;display:flex;justify-content:center;align-items:center}.status{padding:1rem;border-radius:8px;text-align:center;margin-top:1rem;width:100%;transition:opacity .3s ease}.status.success{background-color:var(--success-bg);color:var(--success-text)}.status.error{background-color:var(--error-bg);color:var(--error-text)}.status.info,.status.loading-special{background-color:var(--info-bg);color:var(--info-text)}.list-container{display:flex;flex-direction:column;gap:1.5rem}.list-item{display:flex;gap:.5rem;align-items:flex-start}.list-item-main{display:grid;grid-template-columns:2fr 1.5fr;grid-template-rows:auto auto;gap:.5rem;flex-grow:1}.id-input{grid-column:1/2}.nickname-input{grid-column:2/3}.prompt-input{grid-column:1/3}.remove-btn{background-color:transparent;color:var(--text-light);padding:0;width:44px;height:44px;line-height:44px;text-align:center;font-size:1.5rem;flex-shrink:0;border-radius:50%}.remove-btn:hover{background-color:var(--error-bg);color:var(--error-text)}.add-btn{background-color:var(--info-bg);color:var(--info-text);align-self:flex-start;padding:.6rem 1.2rem;font-weight:500}.add-btn:hover{background-color:#d1ecfa}.control-grid{display:grid;grid-template-columns:auto 1fr;gap:1rem;align-items:center}.slider-container{display:flex;align-items:center;gap:1rem}.slider-container input[type=range]{flex-grow:1;accent-color:var(--primary-color)}.slider-container span{min-width:110px;font-weight:500;text-align:right}.context-settings{border-top:1px solid var(--border-color);margin-top:1rem;padding-top:1.5rem}.lang-switcher{position:fixed;top:1rem;right:1rem;display:flex;gap:.5rem;background-color:var(--card-bg);padding:.5rem;border-radius:8px;box-shadow:var(--shadow);z-index:1000}.lang-switcher button{background-color:transparent;color:var(--text-light);padding:.5rem 1rem}.lang-switcher button.active{color:var(--primary-color);font-weight:700}.dark-theme{background-color:#202123;border:1px solid #444654;color:#ececf1}.dark-theme h2,.dark-theme label{color:#ececf1;border-color:#444654}.dark-theme input,.dark-theme select,.dark-theme textarea{background-color:#40414f;border:1px solid #565869;color:#ececf1}.dark-theme input::placeholder,.dark-theme textarea::placeholder{color:#8e8ea0}.dark-theme .remove-btn{color:#acacbe}.dark-theme .remove-btn:hover{background-color:rgba(239,68,68,.2);color:#ef4444}.dark-theme .add-btn{color:#ececf1;background-color:#40414f;border:1px solid #565869}.dark-theme .add-btn:hover{background-color:#4d4e5a}.param-item{display:grid;grid-template-columns:1.5fr 1fr 2fr auto;gap:1rem;align-items:center}.param-select.wide,.param-textarea{grid-column:3/4;resize:vertical;min-height:44px;font-family:monospace}.param-item>.remove-btn{justify-self:center}.action-container{display:flex;gap:1rem;align-items:center}.action-btn{background-color:var(--error-bg);color:var(--error-text);border:1px solid var(--error-text);white-space:nowrap}.action-btn:hover{background-color:var(--error-text);color:#fff}.log-viewer{width:600px;flex-shrink:0;background-color:var(--card-bg);border-radius:12px;padding:1rem 1.5rem;box-shadow:var(--shadow);position:sticky;top:2rem;height:calc(100vh - 4rem);display:flex;flex-direction:column}.log-viewer h2{font-size:1.25rem}.log-controls{display:flex;justify-content:space-between;align-items:center;gap:1rem;margin-bottom:1rem;flex-shrink:0;flex-wrap:wrap}.log-filter-group{display:flex;gap:.5rem;align-items:center}.log-filter-group span{color:var(--text-light);font-size:.9rem}.log-filter-group button{background:#f0f2f5;color:#555;padding:.3rem .8rem;font-size:.85rem;border:1px solid var(--border-color)}.log-filter-group button.active{background-color:var(--primary-color);color:#fff;border-color:var(--primary-color)}.autoscroll-toggle{display:flex;align-items:center;gap:.5rem;color:var(--text-light);font-size:.9rem;cursor:pointer;user-select:none}.autoscroll-toggle input{width:auto}.log-output-wrapper{flex-grow:1;overflow:hidden;background-color:#1e1e1e;border-radius:8px;position:relative}.log-output-wrapper pre{height:100%;margin:0;overflow-y:auto;padding:1rem;box-sizing:border-box;font-family:'Fira Code','Courier New',monospace;font-size:.8rem;line-height:1.6;color:#d4d4d4;white-space:pre-wrap;word-break:break-all}.log-output-wrapper code{display:block}.log-line.INFO{color:#81c784}.log-line.WARNING{color:#ffd54f}.log-line.ERROR{color:#e57373}.log-line.CRITICAL{color:#ff8a65;font-weight:700}.log-line.UNKNOWN{color:#90a4ae}.very-wide-grid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto auto auto auto;gap:1rem 1.5rem;width:100%}.very-wide-grid .id-input{grid-column:1/2;grid-row:1}.very-wide-grid .nickname-input{grid-column:2/3;grid-row:1}.very-wide-grid .prompt-input{grid-column:1/3;grid-row:2}.very-wide-grid .limit-control-group{grid-row:3;display:flex;flex-direction:column;gap:.5rem}.very-wide-grid .preview-section{grid-row:4;grid-column:1/2}.very-wide-grid .color-picker-section{grid-row:4;grid-column:2/3}.limit-group{display:flex;align-items:center;gap:.5rem;transition:opacity .3s}.limit-group.disabled{opacity:.5;pointer-events:none}.limit-group input{padding:.5rem;text-align:center}.limit-group span.unit{font-size:.8em;color:var(--text-light)}.limit-group label{white-space:nowrap}.budget-group{margin-top:.5rem}.toggle-switch{position:relative;display:inline-flex;align-items:center;cursor:pointer;font-weight:500;font-size:.9rem}.toggle-switch input{opacity:0;width:0;height:0}.toggle-switch .slider{width:44px;height:24px;background-color:#ccc;border-radius:12px;transition:.4s;position:relative;margin-right:10px}.toggle-switch .slider:before{position:absolute;content:"";height:18px;width:18px;left:3px;bottom:3px;background-color:#fff;transition:.4s;border-radius:50%}.toggle-switch input:checked+.slider{background-color:var(--primary-color)}.toggle-switch input:checked+.slider:before{transform:translateX(20px)}.quota-preview{background-color:#fff;border:1px solid #000;border-radius:8px;padding:1rem;font-family:monospace;color:#333}.preview-header{font-weight:700;margin-bottom:.5rem}.preview-field{display:flex;justify-content:space-between;border-top:1px dashed #ccc;padding-top:.5rem;margin-top:.5rem}.color-picker-section input[type=color]{width:100%;height:40px;padding:.2rem;border-radius:8px;cursor:pointer}@media (max-width:1400px){.page-container{flex-direction:column;align-items:stretch}main{min-width:unset}.log-viewer{width:auto;position:relative;top:0;height:70vh;margin-top:2rem}}
</style>
