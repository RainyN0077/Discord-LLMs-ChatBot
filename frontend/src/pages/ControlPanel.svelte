<!-- src/pages/ControlPanel.svelte -->
<script>
    import { t, get as t_get } from '../i18n.js';
    import { config, keywordsInput, setKeywords, userPersonasArray, customFontName, showStatus, updateConfigField } from '../lib/stores.js';
    import { clearMemory, fetchAvailableModels, testModel } from '../lib/api.js';
    import { saveToIndexedDB, deleteFromIndexedDB } from '../lib/fontStorage.js';

    import Card from '../components/Card.svelte';
    import LogViewer from '../components/LogViewer.svelte';
    import ScopedPromptEditor from '../components/ScopedPromptEditor.svelte';
    import RoleConfigEditor from '../components/RoleConfigEditor.svelte';
    import PluginEditor from '../components/PluginEditor.svelte';

    export let applyFont;



    let activeTab = 'directives';
    let channelIdToClear = '';
    let fontFileInput;
    
    // 模型选择相关变量
    let availableModels = [];
    let isLoadingModels = false;
    let testResult = null;
    let isTesting = false;
    let useManualInput = false;

    function addPersona() { config.update(c => { const newKey = `new-user-${Date.now()}`; c.user_personas[newKey] = { id: '', nickname: '', prompt: '' }; return c; }); }
    function removePersona(key) { config.update(c => { delete c.user_personas[key]; return c; }); }
    function addParameter() { config.update(c => { if (!c.custom_parameters) c.custom_parameters = []; c.custom_parameters.push({ name: '', type: 'text', value: '' }); return c; }); }
    function removeParameter(index) { config.update(c => { c.custom_parameters.splice(index, 1); return c; }); }
    function handleParamTypeChange(index, newType) {
        const value = newType === 'number' ? 0 : (newType === 'boolean' ? 'true' : '');
        updateConfigField(`custom_parameters.${index}.type`, newType);
        updateConfigField(`custom_parameters.${index}.value`, value);
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
            
            // 同时在 localStorage 保存字体名称（作为标记）
            localStorage.setItem('customFontName', file.name);
            
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
    
    // 清理 localStorage
    localStorage.removeItem('customFontName');
    
    customFontName.set('');
    showStatus(t_get('uiSettings.font.resetSuccess'), 'success');
}

    
    // 模型选择相关函数
    async function loadModels() {
        if (!$config.api_key) {
            showStatus(t_get('llmProvider.noApiKey'), 'error');
            return;
        }
        
        isLoadingModels = true;
        try {
            const result = await fetchAvailableModels(
                $config.llm_provider,
                $config.api_key,
                $config.base_url
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
        if (!$config.model_name) {
            showStatus(t_get('llmProvider.selectModelFirst'), 'error');
            return;
        }
        
        isTesting = true;
        testResult = null;
        try {
            const result = await testModel(
                $config.llm_provider,
                $config.api_key,
                $config.base_url,
                $config.model_name
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
    $: if ($config.llm_provider || $config.api_key) {
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

        {#if $config}
            {#if activeTab === 'core'}
                <Card title={$t('globalConfig.title')}>
                    <label for="discord-token">{$t('globalConfig.token')}</label>
                    <input id="discord-token" type="password" placeholder={$t('globalConfig.tokenPlaceholder')} value={$config.discord_token} on:input={e => updateConfigField('discord_token', e.target.value)}>
                    <label for="api-key-display">{$t('globalConfig.apiKey')}</label>
                    <div class="api-key-container">
                        <input id="api-key-display" type="text" readonly value={$config.api_secret_key || ''} placeholder={$t('globalConfig.apiKeyUnavailable')}>
                        <button on:click={() => navigator.clipboard.writeText($config.api_secret_key)} title={$t('globalConfig.copy')}><svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>
                    </div>
                    <p class="info">{$t('globalConfig.apiKeyInfo')}</p>
                </Card>
                <Card title={$t('llmProvider.title')}>
                    <label for="llm-provider">{$t('llmProvider.select')}</label>
                    <select id="llm-provider" value={$config.llm_provider} on:change={e => updateConfigField('llm_provider', e.target.value)}>
                        <option value="openai">{$t('llmProvider.providers.openai')}</option><option value="google">{$t('llmProvider.providers.google')}</option><option value="anthropic">{$t('llmProvider.providers.anthropic')}</option>
                    </select>
                    <label for="api-key">{$t('llmProvider.apiKey')}</label>
                    <input id="api-key" type="password" placeholder={$t('llmProvider.apiKeyPlaceholder')} value={$config.api_key} on:input={e => updateConfigField('api_key', e.target.value)}>
                    {#if $config.llm_provider === 'openai'}
                        <label for="base-url">{$t('llmProvider.baseUrl')}</label>
                        <input id="base-url" type="text" placeholder={$t('llmProvider.baseUrlPlaceholder')} value={$config.base_url} on:input={e => updateConfigField('base_url', e.target.value)}>
                    {/if}
                    
                    <!-- 新增的模型选择功能 -->
                    <div class="model-selector-group">
                        <label for="model-name">{$t('defaultBehavior.modelName')}</label>
                        <div class="model-controls">
                            {#if !useManualInput && availableModels.length > 0}
                                <select id="model-name" value={$config.model_name} 
                                        on:change={e => updateConfigField('model_name', e.target.value)}>
                                    <option value="">-- {$t('llmProvider.selectModel')} --</option>
                                    {#each availableModels as model}
                                        <option value={model}>{model}</option>
                                    {/each}
                                </select>
                            {:else}
                                <input id="model-name" type="text" 
                                       placeholder={$t(`defaultBehavior.modelPlaceholders.${$config.llm_provider}`)} 
                                       value={$config.model_name} 
                                       on:input={e => updateConfigField('model_name', e.target.value)}>
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
                                        disabled={isTesting || !$config.model_name}>
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
                    <label>{$t('contextControl.contextMode')}</label>
                    <div class="radio-group">
                        <label><input type="radio" name="context-mode" value='none' checked={$config.context_mode === 'none'} on:change={e => updateConfigField('context_mode', e.target.value)}> {$t('contextControl.modes.none')}</label>
                        <label><input type="radio" name="context-mode" value='channel' checked={$config.context_mode === 'channel'} on:change={e => updateConfigField('context_mode', e.target.value)}> {$t('contextControl.modes.channel')}</label>
                        <label><input type="radio" name="context-mode" value='memory' checked={$config.context_mode === 'memory'} on:change={e => updateConfigField('context_mode', e.target.value)}> {$t('contextControl.modes.memory')}</label>
                    </div>
                    {#if $config.context_mode !== 'none'}
                        {@const settingsKey = `${$config.context_mode}_context_settings`}
                        {#if $config[settingsKey]}
                        <div class="context-settings">
                            <p class="info">{$t(`contextControl.${$config.context_mode}ModeInfo`)}</p>
                            <div class="control-grid">
                            <label for="context-messages">{$t('contextControl.historyLimit')}</label>
                            <div class="slider-container">
                                <input type="range" id="context-messages" min="0" max="50" step="5" value={$config[settingsKey].message_limit} on:input={e => updateConfigField(`${settingsKey}.message_limit`, Number(e.target.value))}>
                                <span>{$config[settingsKey].message_limit} {$t('contextControl.messages')}</span>
                            </div>
                            <label for="context-chars">{$t('contextControl.charLimit')}</label>
                            <input type="number" id="context-chars" placeholder={$t('contextControl.charLimitPlaceholder')} value={$config[settingsKey].char_limit} on:input={e => updateConfigField(`${settingsKey}.char_limit`, Number(e.target.value))}>
                            </div>
                        </div>
                        {/if}
                    {:else}<div class="context-settings"><p class="info">{$t('contextControl.noneModeInfo')}</p></div>{/if}
                </Card>
            {:else if activeTab === 'directives'}
                <Card title={$t('scopedPrompts.channels.title')}><ScopedPromptEditor type="channels" /></Card>
                <Card title={$t('scopedPrompts.guilds.title')}><ScopedPromptEditor type="guilds" /></Card>
                <RoleConfigEditor />
                <Card title={$t('userPortrait.title')}>
                    <p class="info">{$t('userPortrait.info')}</p>
                    <div class="list-container">
                        {#each $userPersonasArray as persona (persona._key)}
                            <div class="list-item">
                                <div class="list-item-main">
                                    <input class="id-input" type="text" placeholder={$t('userPortrait.userId')} value={persona.id} on:input={e => updateConfigField(`user_personas.${persona._key}.id`, e.target.value)}>
                                    <input class="nickname-input" type="text" placeholder={$t('userPortrait.customNicknamePlaceholder')} value={persona.nickname} on:input={e => updateConfigField(`user_personas.${persona._key}.nickname`, e.target.value)}>
                                    <textarea class="prompt-input" rows="2" placeholder={$t('userPortrait.personaPrompt')} value={persona.prompt} on:input={e => updateConfigField(`user_personas.${persona._key}.prompt`, e.target.value)}></textarea>
                                </div>
                                <button class="remove-btn" on:click={() => removePersona(persona._key)} title={$t('roleConfig.remove')}>×</button>
                            </div>
                        {/each}
                    </div>
                    <button class="add-btn" on:click={addPersona}>{$t('userPortrait.add')}</button>
                </Card>
                <Card title={$t('defaultBehavior.title')}>
                    <label for="system-prompt">{$t('defaultBehavior.systemPrompt')}</label>
                    <textarea id="system-prompt" rows="4" placeholder={$t('defaultBehavior.systemPromptPlaceholder')} value={$config.system_prompt} on:input={e => updateConfigField('system_prompt', e.target.value)}></textarea>
                    <label for="blocked-response">{$t('defaultBehavior.blockedResponse')}</label>
                    <input id="blocked-response" type="text" value={$config.blocked_prompt_response} on:input={e => updateConfigField('blocked_prompt_response', e.target.value)}>
                    <p class="info">{$t('defaultBehavior.blockedResponseInfo')}</p>
                    <label for="trigger-keywords">{$t('defaultBehavior.triggerKeywords')}</label>
                    <input id="trigger-keywords" type="text" placeholder={$t('defaultBehavior.triggerKeywordsPlaceholder')} value={$keywordsInput} on:input={e => setKeywords(e.target.value)}>
                    <label>{$t('defaultBehavior.responseMode')}</label>
                    <div class="radio-group">
                        <label><input type="radio" name="stream-mode" value={true} checked={$config.stream_response === true} on:change={() => updateConfigField('stream_response', true)}> {$t('defaultBehavior.modes.stream')}</label>
                        <label><input type="radio" name="stream-mode" value={false} checked={$config.stream_response === false} on:change={() => updateConfigField('stream_response', false)}> {$t('defaultBehavior.modes.nonStream')}</label>
                    </div>
                </Card>
            {:else if activeTab === 'advanced'}
                <PluginEditor />
                <Card title={$t('customParams.title')} theme="dark-theme">
                    <div class="list-container">
                        {#if $config.custom_parameters}
                        {#each $config.custom_parameters as param, i}
                            <div class="list-item param-item">
                                <input class="param-input" type="text" placeholder={$t('customParams.paramName')} value={param.name} on:input={e => updateConfigField(`custom_parameters.${i}.name`, e.target.value)}>
                                <select class="param-select" value={param.type} on:change={(e) => handleParamTypeChange(i, e.currentTarget.value)}>
                                    <option value="text">{$t('customParams.types.text')}</option><option value="number">{$t('customParams.types.number')}</option><option value="boolean">{$t('customParams.types.boolean')}</option><option value="json">{$t('customParams.types.json')}</option>
                                </select>
                                {#if param.type === 'text'}<input class="param-input" type="text" placeholder={$t('customParams.paramValue')} value={param.value} on:input={e => updateConfigField(`custom_parameters.${i}.value`, e.target.value)}>{:else if param.type === 'number'}<input class="param-input" type="number" step="0.01" placeholder={$t('customParams.paramValue')} value={param.value} on:input={e => updateConfigField(`custom_parameters.${i}.value`, e.target.value)}>{:else if param.type === 'boolean'}<select class="param-select wide" value={String(param.value)} on:change={e => updateConfigField(`custom_parameters.${i}.value`, e.target.value === 'true')}><option value="true">True</option><option value="false">False</option></select>{:else if param.type === 'json'}<textarea class="param-input param-textarea" rows="1" placeholder={$t('customParams.paramValue')} value={param.value} on:input={e => updateConfigField(`custom_parameters.${i}.value`, e.target.value)}></textarea>{/if}
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
                </Card>
            {/if}
        {/if}
    </main>
    <aside class="log-viewer">
        <LogViewer />
    </aside>
</div>

<style>
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
</style>

