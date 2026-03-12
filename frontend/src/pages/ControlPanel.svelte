<!-- src/pages/ControlPanel.svelte -->
<script>
    import '../styles/lists.css';
    import { t, get as t_get } from '../i18n.js';
    import {
        coreConfig,
        behaviorConfig,
        contextConfig,
        customParameters,
        keywordsInput,
        setKeywords,
        customFontName,
        showStatus,
        timezoneStore
    } from '../lib/stores.js';
    import { clearMemory, fetchAvailableModels, testModel } from '../lib/api.js';
import { saveToIndexedDB, deleteFromIndexedDB } from '../lib/fontStorage.js';

    import Card from '../components/Card.svelte';
    import LogViewer from '../components/LogViewer.svelte';
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

    function getProviderBaseUrl() {
        if ($coreConfig.llm_provider === 'openai') return $coreConfig.openai_base_url || '';
        if ($coreConfig.llm_provider === 'anthropic') return $coreConfig.anthropic_base_url || '';
        return '';
    }

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
                getProviderBaseUrl()
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
                getProviderBaseUrl(),
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
                        <input id="api-key-display" type="text" readonly bind:value={$coreConfig.api_secret_key} placeholder={$t('globalConfig.apiKeyUnavailable')}>
                        <button on:click={() => navigator.clipboard.writeText($coreConfig.api_secret_key)} title={$t('globalConfig.copy')}><svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>
                    </div>
                    <p class="info">{$t('globalConfig.apiKeyInfo')}</p>
                </Card>
                <Card title={$t('llmProvider.title')}>
                    <div class="provider-top-grid">
                        <div>
                            <label for="llm-provider">{$t('llmProvider.select')}</label>
                            <select id="llm-provider" bind:value={$coreConfig.llm_provider}>
                                <option value="openai">{$t('llmProvider.providers.openai')}</option><option value="google">{$t('llmProvider.providers.google')}</option><option value="anthropic">{$t('llmProvider.providers.anthropic')}</option>
                            </select>
                        </div>
                        <div>
                            <label for="api-key">{$t('llmProvider.apiKey')}</label>
                            <input id="api-key" type="password" placeholder={$t('llmProvider.apiKeyPlaceholder')} bind:value={$coreConfig.api_key}>
                        </div>
                    </div>

                    {#if $coreConfig.llm_provider === 'openai'}
                        <div class="provider-extra-row">
                            <label for="openai-base-url">{$t('llmProvider.baseUrl')} (OpenAI)</label>
                            <input id="openai-base-url" type="text" placeholder={$t('llmProvider.baseUrlPlaceholder')} bind:value={$coreConfig.openai_base_url}>
                        </div>
                    {:else if $coreConfig.llm_provider === 'anthropic'}
                        <div class="provider-extra-row">
                            <label for="anthropic-base-url">{$t('llmProvider.baseUrl')} (Anthropic)</label>
                            <input id="anthropic-base-url" type="text" placeholder={$t('llmProvider.baseUrlPlaceholder')} bind:value={$coreConfig.anthropic_base_url}>
                        </div>
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
            {/if}

            {#if activeTab === 'directives'}
            <div class="tab-content">
                <KnowledgeEditor />
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
                    <label>
                        <input type="checkbox" bind:checked={$behaviorConfig.trigger_case_sensitive}>
                        {$t('defaultBehavior.triggerCaseSensitive')}
                    </label>
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

            {#if activeTab === 'automation'}
            <div class="tab-content">
                <Card title={$t('automation.title')}>
                    <p class="info">{$t('automation.description')}</p>

                    <div class="automation-section">
                        <h3>{$t('automation.autoInterjectTitle')}</h3>
                        <p class="info">{$t('automation.autoInterjectInfo')}</p>
                        <label>
                            <input type="checkbox" bind:checked={$behaviorConfig.auto_interject_enabled}>
                            {$t('automation.autoInterjectEnabled')}
                        </label>
                        <label for="auto-interject-interval">{$t('automation.autoInterjectInterval')}</label>
                        <input id="auto-interject-interval" type="number" min="1" step="1" bind:value={$behaviorConfig.auto_interject_interval}>
                        <label for="auto-interject-min-length">{$t('automation.autoInterjectMinLength')}</label>
                        <div class="inline-input">
                            <input id="auto-interject-min-length" type="number" min="0" step="1" bind:value={$behaviorConfig.auto_interject_min_length}>
                            <span>{$t('automation.autoInterjectMinLengthHint')}</span>
                        </div>
                    </div>

                    <div class="automation-section">
                        <h3>{$t('automation.repeatParrotTitle')}</h3>
                        <p class="info">{$t('automation.repeatParrotInfo')}</p>
                        <label>
                            <input type="checkbox" bind:checked={$behaviorConfig.repeat_parrot_enabled}>
                            {$t('automation.repeatParrotEnabled')}
                        </label>
                        <label for="repeat-parrot-threshold">{$t('automation.repeatParrotThreshold')}</label>
                        <input id="repeat-parrot-threshold" type="number" min="2" step="1" bind:value={$behaviorConfig.repeat_parrot_threshold}>
                        <label for="repeat-parrot-min-length">{$t('automation.repeatParrotMinLength')}</label>
                        <input id="repeat-parrot-min-length" type="number" min="0" step="1" bind:value={$behaviorConfig.repeat_parrot_min_length}>
                        <label>
                            <input type="checkbox" bind:checked={$behaviorConfig.repeat_parrot_case_sensitive}>
                            {$t('automation.repeatParrotCaseSensitive')}
                        </label>
                        <label>
                            <input type="checkbox" bind:checked={$behaviorConfig.repeat_parrot_trim_whitespace}>
                            {$t('automation.repeatParrotTrimWhitespace')}
                        </label>
                        <label>
                            <input type="checkbox" bind:checked={$behaviorConfig.repeat_parrot_require_multiple_users}>
                            {$t('automation.repeatParrotRequireMultipleUsers')}
                        </label>
                    </div>
                </Card>
            </div>
            {/if}
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
        gap: 1.35rem;
    }
    main h1 {
        margin-top: .2rem;
        padding: .85rem 1rem;
        border-radius: 14px;
        background: linear-gradient(135deg, rgba(31, 139, 214, .1), rgba(24, 138, 81, .08));
        border: 1px solid rgba(15, 23, 42, .08);
        box-shadow: var(--shadow-soft);
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
    .tabs {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        background: var(--floating-bg);
        border-radius: 14px;
        padding: .4rem;
        box-shadow: var(--shadow);
        margin-top: .85rem;
        margin-bottom: .2rem;
        position: sticky;
        top: .75rem;
        z-index: 20;
        border: 1px solid var(--floating-border);
        -webkit-backdrop-filter: blur(10px);
        backdrop-filter: blur(10px);
    }
    .tabs button {
        flex: 1;
        padding: .65rem .5rem;
        border: none;
        background: transparent;
        font-size: .97rem;
        font-weight: 600;
        border-radius: 10px;
        cursor: pointer;
        color: var(--text-light);
        transition: all 0.2s ease-in-out;
    }
    .tabs button:hover {
        color: var(--text-color);
        background: var(--panel-muted-bg);
    }
    .tabs button.active {
        background: linear-gradient(135deg, var(--primary-color), #1d81bf);
        color: #fff;
        box-shadow: 0 4px 14px rgba(52, 152, 219, .28);
    }
    .automation-section {
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid var(--border-color);
        display: flex;
        flex-direction: column;
        gap: .75rem;
    }
    .automation-section:first-of-type {
        margin-top: .5rem;
    }
    .automation-section h3 {
        margin: 0;
    }
    .inline-input {
        display: flex;
        align-items: center;
        gap: .75rem;
    }
    .inline-input input {
        max-width: 180px;
    }
    
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
        align-items: center;
    }
    
    .model-buttons button:first-child {
        flex: 1;
    }
    
    .test-result {
        margin-top: 1rem;
        padding: 1rem;
        border-radius: 8px;
        font-size: 0.9rem;
        border: 1px solid rgba(15, 23, 42, .08);
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

    .provider-top-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: .9rem;
    }

    .provider-extra-row {
        display: flex;
        flex-direction: column;
        gap: .45rem;
        padding: .7rem .8rem;
        border: 1px solid var(--panel-muted-border);
        border-radius: 12px;
        background: var(--panel-soft-bg-2);
    }

    .api-key-container {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: .5rem;
        align-items: center;
    }

    .api-key-container button {
        padding: .65rem .8rem;
        background: var(--control-bg);
        color: var(--text-color);
        border: 1px solid var(--panel-muted-border);
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
        display: grid;
        grid-template-columns: minmax(0, 1.85fr) minmax(360px, 1fr);
        align-items: start;
        gap: clamp(1rem, 2vw, 1.65rem);
        max-width: 1700px;
        margin: 0 auto;
    }

    main {
        display: flex;
        flex-direction: column;
        min-width: 0;
        gap: 1.35rem;
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
        white-space: nowrap;
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
        gap: .7rem;
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
        gap: .7rem;
        align-items: center;
        flex-wrap: wrap;
    }

    .log-viewer {
        position: sticky;
        top: .75rem;
        min-width: 0;
    }

    @media (max-width: 1280px) {
      .page-container {
          grid-template-columns: 1fr;
      }

      .log-viewer {
          position: relative;
          top: 0;
          margin-top: .2rem;
      }
    }

    @media (max-width: 900px) {
      .provider-top-grid {
          grid-template-columns: 1fr;
      }

      .tabs {
          top: .5rem;
      }

      .tabs button {
          font-size: .9rem;
          padding: .55rem .4rem;
      }

      .radio-group {
          gap: 1rem;
      }

      .control-grid {
          grid-template-columns: 1fr;
          gap: .6rem;
      }

      .slider-container {
          flex-direction: column;
          align-items: stretch;
          gap: .4rem;
      }

      .slider-container span {
          min-width: 0;
          text-align: left;
      }

      .param-item {
          grid-template-columns: 1fr;
      }

      .param-item > .remove-btn {
          justify-self: start;
      }

       .action-container > * {
           width: 100%;
       }
    }
</style>
