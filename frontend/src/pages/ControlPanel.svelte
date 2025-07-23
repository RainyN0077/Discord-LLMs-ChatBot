<!-- src/pages/ControlPanel.svelte -->
<script>
    import '../styles/lists.css';
    import { t, get as t_get } from '../i18n.js';
    import {
        coreConfig,
        behaviorConfig,
        contextConfig,
        pluginsConfig,
        userPersonas,
        roleConfigs,
        scopedPrompts,
        customParameters,
        keywordsInput,
        setKeywords,
        userPersonasArray,
        customFontName,
        showStatus,
        timezoneStore
    } from '../lib/stores.js';
    import { clearMemory, fetchAvailableModels, testModel } from '../lib/api.js';
import { saveToIndexedDB, deleteFromIndexedDB } from '../lib/fontStorage.js';

    import Card from '../components/Card.svelte';
    import LogViewer from '../components/LogViewer.svelte';
    import ScopedPromptEditor from '../components/ScopedPromptEditor.svelte';
    import RoleConfigEditor from '../components/RoleConfigEditor.svelte';
    import PluginEditor from '../components/PluginEditor.svelte';
    import SearchSettings from '../components/SearchSettings.svelte';
    import KnowledgeEditor from '../components/KnowledgeEditor.svelte';

    export let applyFont;



    let activeTab = 'advanced';
    let channelIdToClear = '';
    let fontFileInput;
    
    // 模型选择相关变量
    let availableModels = [];
    let isLoadingModels = false;
    let testResult = null;
    let isTesting = false;
    let useManualInput = false;
    
    // A curated list of common timezones for the dropdown
    const commonTimezones = [
      'UTC',
      'Asia/Shanghai',
      'America/New_York',
      'America/Los_Angeles',
      'Europe/London',
      'Europe/Berlin',
      'Asia/Tokyo'
    ];

    function addPersona() { userPersonas.update(up => { const newKey = `new-user-${Date.now()}`; up[newKey] = { id: '', nickname: '', prompt: '' }; return up; }); }
    function removePersona(key) { userPersonas.update(up => { delete up[key]; return up; }); }
    function addParameter() { customParameters.update(cp => { cp.push({ name: '', type: 'text', value: '' }); return cp; }); }
    function removeParameter(index) { customParameters.update(cp => { cp.splice(index, 1); return cp; }); }
    function handleParamTypeChange(index, newType) {
        const value = newType === 'number' ? 0 : (newType === 'boolean' ? 'true' : '');
        customParameters.update(cp => {
            cp[index].type = newType;
            cp[index].value = value;
            return cp;
        });
    }
    
    async function handleClearMemory() {
        if (!channelIdToClear.trim()) { 
            showStatus(t_get('sessionManagement.errorNoId'), 'error'); 
            return; 
        }
        showStatus(t_get('sessionManagement.clearing'), 'loading-special');
        try {
            await clearMemory(channelIdToClear);
            showStatus(t_get('sessionManagement.clearSuccess'), 'success');
            channelIdToClear = '';
        } catch (e) {
            showStatus(t_get('sessionManagement.clearFailed') + e.message, 'error');
        }
    }

    function handleFontFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // 放宽文件大小限制到 50MB
    const maxSize = 50 * 1024 * 1024; // 50MB
    if (file.size > maxSize) {
        showStatus(t_get('uiSettings.font.fileTooLarge', { 
            size: (file.size / 1024 / 1024).toFixed(2),
            maxSize: 50 
        }), 'error');
        return;
    }
    
    const reader = new FileReader();
    reader.onload = async (e) => {
        const fontDataUrl = e.target.result;
        try {
            // 使用 IndexedDB 存储
            await saveToIndexedDB('customFontDataUrl', fontDataUrl);
            await saveToIndexedDB('customFontName', file.name);
            
            
            applyFont(fontDataUrl, file.name);
            showStatus(t_get('uiSettings.font.loadSuccess'), 'success');
        } catch (error) {
            console.error('Font storage error:', error);
            showStatus(t_get('uiSettings.font.storageError') + ': ' + error.message, 'error');
        }
    };
    reader.onerror = () => { 
        showStatus(t_get('uiSettings.font.loadError'), 'error'); 
    };
    reader.readAsDataURL(file);
}


async function resetFont() {
    const styleElement = document.getElementById('custom-font-style');
    if (styleElement) styleElement.remove();
    
    // 清理 IndexedDB
    try {
        await deleteFromIndexedDB('customFontDataUrl');
        await deleteFromIndexedDB('customFontName');
    } catch (e) {
        console.error('Failed to clear IndexedDB:', e);
    }
    
    
    customFontName.set('');
    showStatus(t_get('uiSettings.font.resetSuccess'), 'success');
}

    
    // 模型选择相关函数
    async function loadModels() {
        if (!$coreConfig.api_key) {
            showStatus(t_get('llmProvider.noApiKey'), 'error');
            return;
        }
        
        isLoadingModels = true;
        try {
            const result = await fetchAvailableModels(
                $coreConfig.llm_provider,
                $coreConfig.api_key,
                $coreConfig.base_url
            );
            availableModels = result.models;
            useManualInput = false;
            showStatus(t_get('llmProvider.modelsLoaded'), 'success');
        } catch (e) {
            showStatus(t_get('llmProvider.modelsLoadFailed') + e.message, 'error');
            availableModels = [];
            useManualInput = true;
        } finally {
            isLoadingModels = false;
        }
    }
    
    async function handleTestModel() {
        if (!$coreConfig.model_name) {
            showStatus(t_get('llmProvider.selectModelFirst'), 'error');
            return;
        }
        
        isTesting = true;
        testResult = null;
        try {
            const result = await testModel(
                $coreConfig.llm_provider,
                $coreConfig.api_key,
                $coreConfig.base_url,
                $coreConfig.model_name
            );
            testResult = result;
            if (result.success) {
                showStatus(t_get('llmProvider.testSuccess'), 'success');
            } else {
                showStatus(t_get('llmProvider.testFailed') + result.error, 'error');
            }
        } catch (e) {
            showStatus(t_get('llmProvider.testError') + e.message, 'error');
        } finally {
            isTesting = false;
        }
    }
    
    // 当provider或API key改变时，重置状态
    $: if ($coreConfig.llm_provider || $coreConfig.api_key) {
        availableModels = [];
        testResult = null;
        useManualInput = false;
    }
</script>

<div class="page-container">
    <main>
        <h1>{$t('title')}</h1>
        
        <div class="tabs">
            <button class:active={activeTab === 'core'} on:click={() => activeTab = 'core'}>{$t('tabs.core')}</button>
            <button class:active={activeTab === 'directives'} on:click={() => activeTab = 'directives'}>{$t('tabs.directives')}</button>
            <button class:active={activeTab === 'advanced'} on:click={() => activeTab = 'advanced'}>{$t('tabs.advanced')}</button>
        </div>

        {#if $coreConfig}
            <div class="tab-content" class:hidden={activeTab !== 'core'}>
                <Card title={$t('globalConfig.title')}>
                    <label for="discord-token">{$t('globalConfig.token')}</label>
                    <input id="discord-token" type="password" placeholder={$t('globalConfig.tokenPlaceholder')} bind:value={$coreConfig.discord_token}>
                    <label for="api-key-display">{$t('globalConfig.apiKey')}</label>
                    <div class="api-key-container">
                        <input id="api-key-display" type="text" readonly bind:value={$coreConfig.api_secret_key} placeholder={$t('globalConfig.apiKeyUnavailable')}>
                        <button on:click={() => navigator.clipboard.writeText($coreConfig.api_secret_key)} title={$t('globalConfig.copy')}><svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>
                    </div>
                    <p class="info">{$t('globalConfig.apiKeyInfo')}</p>
                </Card>
                <Card title={$t('llmProvider.title')}>
                    <label for="llm-provider">{$t('llmProvider.select')}</label>
                    <select id="llm-provider" bind:value={$coreConfig.llm_provider}>
                        <option value="openai">{$t('llmProvider.providers.openai')}</option><option value="google">{$t('llmProvider.providers.google')}</option><option value="anthropic">{$t('llmProvider.providers.anthropic')}</option>
                    </select>
                    <label for="api-key">{$t('llmProvider.apiKey')}</label>
                    <input id="api-key" type="password" placeholder={$t('llmProvider.apiKeyPlaceholder')} bind:value={$coreConfig.api_key}>
                    {#if $coreConfig.llm_provider === 'openai'}
                        <label for="base-url">{$t('llmProvider.baseUrl')}</label>
                        <input id="base-url" type="text" placeholder={$t('llmProvider.baseUrlPlaceholder')} bind:value={$coreConfig.base_url}>
                    {/if}
                    
                    <div class="model-selector-group">
                        <label for="model-name">{$t('defaultBehavior.modelName')}</label>
                        <div class="model-controls">
                            {#if !useManualInput && availableModels.length > 0}
                                <select id="model-name" bind:value={$coreConfig.model_name}>
                                    <option value="">-- {$t('llmProvider.selectModel')} --</option>
                                    {#each availableModels as model}
                                        <option value={model}>{model}</option>
                                    {/each}
                                </select>
                            {:else}
                                <input id="model-name" type="text"
                                       placeholder={$t(`defaultBehavior.modelPlaceholders.${$coreConfig.llm_provider}`)}
                                       bind:value={$coreConfig.model_name}>
                            {/if}
                            
                            <div class="model-buttons">
                                <button class="action-btn-secondary"
                                        on:click={loadModels}
                                        disabled={isLoadingModels}
                                        title={$t('llmProvider.fetchModelsTooltip')}>
                                    {#if isLoadingModels}
                                        {$t('llmProvider.loading')}
                                    {:else if availableModels.length > 0}
                                        🔄
                                    {:else}
                                        {$t('llmProvider.fetchModels')}
                                    {/if}
                                </button>
                                
                                {#if availableModels.length > 0}
                                    <button class="action-btn-secondary"
                                            on:click={() => useManualInput = !useManualInput}
                                            title={$t('llmProvider.toggleInputMode')}>
                                        {useManualInput ? '📋' : '✏️'}
                                    </button>
                                {/if}
                                
                                <button class="action-btn"
                                        on:click={handleTestModel}
                                        disabled={isTesting || !$coreConfig.model_name}>
                                    {isTesting ? $t('llmProvider.testing') : $t('llmProvider.testConnection')}
                                </button>
                            </div>
                        </div>
                        
                        {#if availableModels.length > 0 && !useManualInput}
                            <p class="info">{$t('llmProvider.modelListInfo', { count: availableModels.length })}</p>
                        {/if}
                    </div>
                    
                    {#if testResult}
                        <div class="test-result {testResult.success ? 'success' : 'error'}">
                            <strong>{$t('llmProvider.testResult')}:</strong>
                            {#if testResult.success}
                                <p>{$t('llmProvider.modelResponded')}: "{testResult.response}"</p>
                                {#if testResult.model_info?.usage}
                                    <p class="usage-info">
                                        Tokens: {testResult.model_info.usage.total_tokens}
                                        (Prompt: {testResult.model_info.usage.prompt_tokens},
                                        Completion: {testResult.model_info.usage.completion_tokens})
                                    </p>
                                {/if}
                            {:else}
                                <p>{testResult.error}</p>
                            {/if}
                        </div>
                    {/if}
                </Card>
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
                            <div class="slider-container">
                                <input type="range" id="context-messages" min="0" max="50" step="5" bind:value={$contextConfig[settingsKey].message_limit}>
                                <span>{$contextConfig[settingsKey].message_limit} {$t('contextControl.messages')}</span>
                            </div>
                            <label for="context-chars">{$t('contextControl.charLimit')}</label>
                            <input type="number" id="context-chars" placeholder={$t('contextControl.charLimitPlaceholder')} bind:value={$contextConfig[settingsKey].char_limit}>
                            </div>
                        </div>
                        {/if}
                    {:else}<div class="context-settings"><p class="info">{$t('contextControl.noneModeInfo')}</p></div>{/if}
                </Card>
            </div>

            <div class="tab-content" class:hidden={activeTab !== 'directives'}>
                <KnowledgeEditor />
                <Card title={$t('scopedPrompts.channels.title')}><ScopedPromptEditor type="channels" /></Card>
                <Card title={$t('scopedPrompts.guilds.title')}><ScopedPromptEditor type="guilds" /></Card>
                <RoleConfigEditor />
                <Card title={$t('userPortrait.title')}>
                    <p class="info">{$t('userPortrait.info')}</p>
                    <div class="list-container">
                        {#each Object.keys($userPersonas) as key (key)}
                            <div class="list-item">
                                <div class="list-item-main">
                                    <input class="id-input" type="text" placeholder={$t('userPortrait.userId')} bind:value={$userPersonas[key].id}>
                                    <input class="nickname-input" type="text" placeholder={$t('userPortrait.customNicknamePlaceholder')} bind:value={$userPersonas[key].nickname}>
                                    <textarea class="prompt-input" rows="2" placeholder={$t('userPortrait.personaPrompt')} bind:value={$userPersonas[key].prompt}></textarea>
                                </div>
                                <button class="remove-btn" on:click={() => removePersona(key)} title={$t('roleConfig.remove')}>×</button>
                            </div>
                        {/each}
                    </div>
                    <button class="add-btn" on:click={addPersona}>{$t('userPortrait.add')}</button>
                </Card>
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
                    <div class="group-label">{$t('defaultBehavior.responseMode')}</div>
                    <div class="radio-group">
                        <label><input type="radio" name="stream-mode" value={true} bind:group={$behaviorConfig.stream_response}> {$t('defaultBehavior.modes.stream')}</label>
                        <label><input type="radio" name="stream-mode" value={false} bind:group={$behaviorConfig.stream_response}> {$t('defaultBehavior.modes.nonStream')}</label>
                    </div>
                </Card>
            </div>

            <div class="tab-content" class:hidden={activeTab !== 'advanced'}>
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
                <Card title={$t('sessionManagement.title')}>
                     <p class="info">{$t('sessionManagement.info')}</p>
                    <div class="action-container"><input type="text" placeholder={$t('sessionManagement.channelIdPlaceholder')} bind:value={channelIdToClear}><button class="action-btn" on:click={handleClearMemory}>{$t('sessionManagement.clearButton')}</button></div>
                </Card>
                 <Card title={$t('uiSettings.title')}>
                    <div class="action-container">
                        <button class="action-btn" on:click={() => fontFileInput.click()}>{$t('uiSettings.font.loadButton')}</button>
                        <input type="file" bind:this={fontFileInput} on:change={handleFontFileSelect} accept=".ttf,.otf,.woff,.woff2" style="display:none;">
                        <button class="action-btn-secondary" on:click={resetFont}>{$t('uiSettings.font.resetButton')}</button>
                    </div>
                    {#if $customFontName}<p class="info">{$t('uiSettings.font.currentFont', { fontName: $customFontName })}</p>{:else}<p class="info">{$t('uiSettings.font.defaultFont')}</p>{/if}
                    <div class="setting-item">
                        <label for="timezone-select">{$t('uiSettings.timezone.title')}</label>
                        <select id="timezone-select" bind:value={$timezoneStore}>
                            {#each commonTimezones as tz}
                                <option value={tz}>{tz}</option>
                            {/each}
                        </select>
                    </div>
                </Card>
            </div>
        {/if}
    </main>
    <aside class="log-viewer">
        <LogViewer />
    </aside>
</div>

<style>
.tab-content {
        display: flex;
        flex-direction: column;
        gap: 2rem;
    }
    .tab-content.hidden {
        display: none;
    }
    .group-label {
        font-weight: 500;
        margin-bottom: 0.5rem;
        color: var(--text-light);
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
    .tabs { display: flex; background: var(--card-bg); border-radius: 12px; padding: .5rem; box-shadow: var(--shadow); margin-top: 2rem; }
    .tabs button { flex: 1; padding: .75rem; border: none; background: transparent; font-size: 1rem; font-weight: 500; border-radius: 8px; cursor: pointer; color: var(--text-light); transition: all 0.2s ease-in-out; }
    .tabs button.active { background: var(--primary-color); color: #fff; box-shadow: 0 2px 5px rgba(52,152,219,.2); }
    
    /* 新增的模型选择器样式 */
    .model-controls {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }
    
    .model-controls > * {
        width: 100%;
    }
    
    .model-buttons {
        display: flex;
        gap: 0.5rem;
    }
    
    .model-buttons button:first-child {
        flex: 1;
    }
    
    .test-result {
        margin-top: 1rem;
        padding: 1rem;
        border-radius: 8px;
        font-size: 0.9rem;
    }
    
    .test-result.success {
        background-color: var(--success-bg);
        color: var(--success-text);
    }
    
    .test-result.error {
        background-color: var(--error-bg);
        color: var(--error-text);
    }
    
    .usage-info {
        font-size: 0.85rem;
        opacity: 0.8;
        margin-top: 0.5rem;
    }
    
    @media (min-width: 768px) {
        .model-controls {
            flex-direction: row;
            align-items: center;
        }
        
        .model-controls select,
        .model-controls input {
            flex: 1;
            width: auto;
        }
        
        .model-buttons {
            flex-shrink: 0;
            width: auto;
        }
    }
    
    .page-container {
        display: flex;
        align-items: flex-start;
        gap: 2rem;
        max-width: 1600px;
        margin: 0 auto;
    }

    main {
        flex: 1;
        min-width: 600px;
        display: flex;
        flex-direction: column;
        gap: 3.5rem;
    }
    
    .radio-group {
        display: flex;
        flex-wrap: wrap;
        gap: 1.5rem;
    }
    
    .radio-group label {
        display: flex;
        align-items: center;
        gap: .5rem;
        font-weight: 400;
        color: var(--text-color);
        cursor: pointer;
    }

    .control-grid {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 1rem;
        align-items: center;
    }

    .slider-container {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .slider-container input[type=range] {
        flex-grow: 1;
        accent-color: var(--primary-color);
    }
    
    .slider-container span {
        min-width: 110px;
        font-weight: 500;
        text-align: right;
    }
    
    .context-settings {
        border-top: 1px solid var(--border-color);
        margin-top: 1rem;
        padding-top: 1.5rem;
    }
    
    .param-item {
        display: grid;
        grid-template-columns: 1.5fr 1fr 2fr auto;
        gap: 1rem;
        align-items: center;
    }
    
    .param-select.wide, .param-textarea {
        grid-column: 3/4;
        resize: vertical;
        min-height: 44px;
        font-family: monospace;
    }
    
    .param-item > .remove-btn {
        justify-self: center;
    }

    .action-container {
        display: flex;
        gap: 1rem;
        align-items: center;
    }

    .log-viewer {
        width: 600px;
        flex-shrink: 0;
        position: sticky;
        top: 2rem;
    }

    @media (max-width:1400px){
      .page-container {
          flex-direction: column;
          align-items: stretch;
      }
      main {
          min-width: unset;
      }
      .log-viewer {
          width: auto;
          position: relative;
          top: 0;
          height: 70vh;
          margin-top: 2rem;
      }
    }
</style>
