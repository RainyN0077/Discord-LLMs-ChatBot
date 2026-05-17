<!-- src/pages/ModelSettings.svelte -->
<script>
    import { t } from '../i18n.js';
    import {
        coreConfig,
        behaviorConfig,
        activePage,
        customParameters,
        showStatus,
        saveConfig,
        loadBotConfigToStores
    } from '../lib/stores.js';
    import { fetchAvailableModels, testModel } from '../lib/api.js';
    import { PROVIDER_DEFAULTS, KNOWN_PROVIDERS, getProviderBaseUrl, providerForPlaceholder } from '../lib/providerDefaults.js';
    import Card from '../components/Card.svelte';

    export let botId = null;

    let loadingConfig = false;
    let configError = '';
    let isSaving = false;

    let availableModels = [];
    let isLoadingModels = false;
    let testResult = null;
    let isTesting = false;
    let useManualInput = false;

    let prevLlmProvider = null;
    let prevApiKey = null;

    let configLoadSeq = 0;

    async function loadInstanceConfig(seq) {
        if (seq !== configLoadSeq) return;
        if (!botId) return;
        loadingConfig = true;
        configError = '';
        try {
            await loadBotConfigToStores(botId);
        } catch (e) {
            configError = String(e.message || e);
        } finally {
            loadingConfig = false;
        }
    }

    $: if (botId) { const seq = ++configLoadSeq; loadInstanceConfig(seq); }

    async function handleSave() {
        isSaving = true;
        showStatus('Saving...', 'info');
        try {
            await saveConfig(botId);
            showStatus('Configuration saved and bot restarted!', 'success');
        } catch (e) {
            showStatus('Save failed: ' + e.message, 'error');
        } finally {
            isSaving = false;
        }
    }

    $: knownModels = PROVIDER_DEFAULTS[$coreConfig.llm_provider]?.models || [];

    $: if (KNOWN_PROVIDERS.has($coreConfig.llm_provider)) {
        const defaults = PROVIDER_DEFAULTS[$coreConfig.llm_provider];
        if ($coreConfig.openai_base_url !== defaults.baseUrl) {
            coreConfig.update(c => ({ ...c, openai_base_url: defaults.baseUrl }));
        }
    }

    async function loadModels() {
        if (!$coreConfig.api_key) {
            showStatus('Please enter API key first', 'error');
            return;
        }
        isLoadingModels = true;
        try {
            const result = await fetchAvailableModels(
                $coreConfig.llm_provider,
                $coreConfig.api_key,
                getProviderBaseUrl($coreConfig)
            );
            availableModels = result.models;
            useManualInput = false;
            showStatus('Model list loaded successfully', 'success');
        } catch (e) {
            showStatus('Failed to load model list: ' + e.message, 'error');
            availableModels = [];
            useManualInput = true;
        } finally {
            isLoadingModels = false;
        }
    }

    async function handleTestModel() {
        if (!$coreConfig.model_name) {
            showStatus('Please select a model first', 'error');
            return;
        }
        isTesting = true;
        testResult = null;
        try {
            const result = await testModel(
                $coreConfig.llm_provider,
                $coreConfig.api_key,
                getProviderBaseUrl($coreConfig),
                $coreConfig.model_name
            );
            testResult = result;
            if (result.success) {
                showStatus('Connection test successful!', 'success');
            } else {
                showStatus('Connection test failed: ' + result.error, 'error');
            }
        } catch (e) {
            showStatus('Test error: ' + e.message, 'error');
        } finally {
            isTesting = false;
        }
    }

    $: if ($coreConfig.llm_provider !== prevLlmProvider || $coreConfig.api_key !== prevApiKey) {
        prevLlmProvider = $coreConfig.llm_provider;
        prevApiKey = $coreConfig.api_key;
        availableModels = [];
        testResult = null;
        useManualInput = false;
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

    function addHeader() {
        coreConfig.update(c => {
            const headers = [...(c.custom_headers || [])];
            headers.push({ name: '', value: '' });
            return { ...c, custom_headers: headers };
        });
    }
    function removeHeader(index) {
        coreConfig.update(c => {
            const headers = [...(c.custom_headers || [])];
            headers.splice(index, 1);
            return { ...c, custom_headers: headers };
        });
    }
</script>

<div class="config-panel">
    <div class="config-header">
        <h2>{botId ? 'Model Settings — ' + botId : 'Select a bot first'}</h2>
        <div class="header-actions">
            <button class="export-btn" on:click={() => activePage.set('config')}>
                &larr; {$t('modelSettings.backToConfig')}
            </button>
            <button class="save-btn" on:click={handleSave} disabled={isSaving || !botId}>
                {isSaving ? 'Saving...' : $t('modelSettings.saveAndRestart')}
            </button>
        </div>
    </div>

    {#if loadingConfig}
        <div class="loading-state">{botId ? 'Loading configuration for ' + botId + '...' : 'Loading...'}</div>
    {:else if configError}
        <div class="error-state">{configError}</div>
    {:else if !botId}
        <div class="empty-state">{$t('configPanel.selectBot')}</div>
    {:else if $coreConfig}
        <div class="tab-content">

            <Card title={$t('llmProvider.title')}>
                <div class="provider-top-grid">
                    <div>
                        <label for="llm-provider">{$t('llmProvider.select')}</label>
                        <select id="llm-provider" bind:value={$coreConfig.llm_provider}>
                            <option value="openai">{$t('llmProvider.providers.openai')}</option>
                            <option value="grok">{$t('llmProvider.providers.grok')}</option>
                            <option value="google">{$t('llmProvider.providers.google')}</option>
                            <option value="anthropic">{$t('llmProvider.providers.anthropic')}</option>
                            <option value="deepseek">{$t('llmProvider.providers.deepseek')}</option>
                            <option value="siliconflow">{$t('llmProvider.providers.siliconflow')}</option>
                            <option value="volcengine">{$t('llmProvider.providers.volcengine')}</option>
                            <option value="dashscope">{$t('llmProvider.providers.dashscope')}</option>
                            <option value="moonshot">{$t('llmProvider.providers.moonshot')}</option>
                            <option value="zhipu">{$t('llmProvider.providers.zhipu')}</option>
                            <option value="stepfun">{$t('llmProvider.providers.stepfun')}</option>
                        </select>
                    </div>
                    <div>
                        <label for="api-key">{$t('llmProvider.apiKey')}</label>
                        <input id="api-key" type="password" placeholder={$t('llmProvider.apiKeyPlaceholder')} bind:value={$coreConfig.api_key}>
                    </div>
                </div>

                {#if !KNOWN_PROVIDERS.has($coreConfig.llm_provider)}
                    {#if $coreConfig.llm_provider === 'grok'}
                    <div class="provider-extra-row">
                        <label for="grok-base-url">{$t('llmProvider.baseUrl')} (Grok)</label>
                        <input id="grok-base-url" type="text" placeholder={$t('llmProvider.baseUrlPlaceholder')} bind:value={$coreConfig.grok_base_url}>
                    </div>
                {:else if $coreConfig.llm_provider === 'anthropic'}
                    <div class="provider-extra-row">
                        <label for="anthropic-base-url">{$t('llmProvider.baseUrl')} (Anthropic)</label>
                        <input id="anthropic-base-url" type="text" placeholder={$t('llmProvider.baseUrlPlaceholder')} bind:value={$coreConfig.anthropic_base_url}>
                    </div>
                {:else}
                    <div class="provider-extra-row">
                        <label for="openai-base-url">{$t('llmProvider.baseUrl')} (API Base)</label>
                        <input id="openai-base-url" type="text" placeholder={$t('llmProvider.baseUrlPlaceholder')} bind:value={$coreConfig.openai_base_url}>
                    </div>
                {/if}
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
                        {:else if !useManualInput && knownModels.length > 0}
                            <select id="model-name" bind:value={$coreConfig.model_name}>
                                <option value="">-- {$t('llmProvider.selectModel')} --</option>
                                {#each knownModels as model}
                                    <option value={model.id}>{model.label}</option>
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
                                    &#x1F504;
                                {:else}
                                    {$t('llmProvider.fetchModels')}
                                {/if}
                            </button>

                            {#if availableModels.length > 0 || knownModels.length > 0}
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

                <div class="provider-extra-row">
                    <label class="checkbox-inline fancy-checkbox">
                        <input type="checkbox" bind:checked={$coreConfig.llm_is_multimodal}>
                        <span class="checkbox-box" aria-hidden="true"></span>
                        <span class="checkbox-text">{$t('llmProvider.multimodalLabel')}</span>
                    </label>
                    <p class="info">{$t('llmProvider.multimodalInfo')}</p>
                    {#if $coreConfig.llm_is_multimodal}
                        <p class="info">{$t('llmProvider.ocrHiddenHint')}</p>
                    {/if}
                </div>

                <div class="group-label">{$t('defaultBehavior.responseMode')}</div>
                <div class="radio-group">
                    <label><input type="radio" name="stream-mode" value={true} bind:group={$behaviorConfig.stream_response}> {$t('defaultBehavior.modes.stream')}</label>
                    <label><input type="radio" name="stream-mode" value={false} bind:group={$behaviorConfig.stream_response}> {$t('defaultBehavior.modes.nonStream')}</label>
                </div>
            </Card>

            <Card title={$t('inferenceParams.title')}>
                <p class="info">{$t('inferenceParams.hint')}</p>
                <div class="param-grid">
                    <div class="param-field">
                        <label for="temperature">{$t('inferenceParams.temperature')}</label>
                        <div class="param-input-row">
                            <input id="temperature" type="number" min="0" max="2" step="0.1"
                                   bind:value={$coreConfig.temperature}
                                   placeholder={$t(`inferenceParams.placeholders.${$coreConfig.llm_provider}`) || $t('inferenceParams.placeholders.default')}>
                            <button class="clear-btn" on:click={() => coreConfig.update(c => ({ ...c, temperature: null }))} title="Clear">&times;</button>
                        </div>
                    </div>
                    <div class="param-field">
                        <label for="top-p">{$t('inferenceParams.topP')}</label>
                        <div class="param-input-row">
                            <input id="top-p" type="number" min="0" max="1" step="0.05"
                                   bind:value={$coreConfig.top_p}
                                   placeholder={$t('inferenceParams.placeholders.topP')}>
                            <button class="clear-btn" on:click={() => coreConfig.update(c => ({ ...c, top_p: null }))} title="Clear">&times;</button>
                        </div>
                    </div>
                    <div class="param-field">
                        <label for="max-tokens">{$t('inferenceParams.maxTokens')}</label>
                        <div class="param-input-row">
                            <input id="max-tokens" type="number" min="1" step="1"
                                   bind:value={$coreConfig.max_tokens}
                                   placeholder={$t('inferenceParams.maxTokensHint')}>
                            <button class="clear-btn" on:click={() => coreConfig.update(c => ({ ...c, max_tokens: null }))} title="Clear">&times;</button>
                        </div>
                    </div>
                    <div class="param-field">
                        <label for="top-k">{$t('inferenceParams.topK')}</label>
                        <div class="param-input-row">
                            <input id="top-k" type="number" min="1" step="1"
                                   bind:value={$coreConfig.top_k}
                                   placeholder={$t('inferenceParams.placeholders.topK')}>
                            <button class="clear-btn" on:click={() => coreConfig.update(c => ({ ...c, top_k: null }))} title="Clear">&times;</button>
                        </div>
                    </div>
                    <div class="param-field">
                        <label for="frequency-penalty">{$t('inferenceParams.frequencyPenalty')}</label>
                        <div class="param-input-row">
                            <input id="frequency-penalty" type="number" min="-2" max="2" step="0.1"
                                   bind:value={$coreConfig.frequency_penalty}
                                   placeholder={$t('inferenceParams.placeholders.frequencyPenalty')}>
                            <button class="clear-btn" on:click={() => coreConfig.update(c => ({ ...c, frequency_penalty: null }))} title="Clear">&times;</button>
                        </div>
                    </div>
                    <div class="param-field">
                        <label for="presence-penalty">{$t('inferenceParams.presencePenalty')}</label>
                        <div class="param-input-row">
                            <input id="presence-penalty" type="number" min="-2" max="2" step="0.1"
                                   bind:value={$coreConfig.presence_penalty}
                                   placeholder={$t('inferenceParams.placeholders.presencePenalty')}>
                            <button class="clear-btn" on:click={() => coreConfig.update(c => ({ ...c, presence_penalty: null }))} title="Clear">&times;</button>
                        </div>
                    </div>
                </div>
            </Card>

            <Card title={$t('customHeaders.title')}>
                <div class="list-container">
                    {#each $coreConfig.custom_headers || [] as header, i}
                        <div class="list-item header-item">
                            <input class="param-input" type="text" placeholder={$t('customHeaders.namePlaceholder')} bind:value={header.name}>
                            <input class="param-input" type="text" placeholder={$t('customHeaders.valuePlaceholder')} bind:value={header.value}>
                            <button class="remove-btn" on:click={() => removeHeader(i)} title={$t('customHeaders.remove')}>&times;</button>
                        </div>
                    {/each}
                </div>
                <button class="add-btn" on:click={addHeader}>{$t('customHeaders.add')}</button>
            </Card>

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
                            <button class="remove-btn" on:click={() => removeParameter(i)} title={$t('customParams.remove')}>&times;</button>
                        </div>
                    {/each}
                    {/if}
                </div>
                <button class="add-btn" on:click={addParameter}>{$t('customParams.add')}</button>
            </Card>
        </div>
    {/if}
</div>

<style>
    .config-panel {
        padding: 1rem 1.5rem;
        overflow-y: auto;
        flex: 1;
        min-height: 0;
        box-sizing: border-box;
    }

    .config-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        flex-shrink: 0;
        overflow: hidden;
        min-width: 0;
    }

    .config-header h2 {
        margin: 0;
        font-size: 1.2rem;
        color: var(--text-color);
        padding: .6rem 1rem;
        border-radius: 10px;
        background: linear-gradient(135deg, rgba(31, 139, 214, .1), rgba(24, 138, 81, .08));
        border: 1px solid rgba(15, 23, 42, .08);
        box-shadow: var(--shadow-soft);
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .save-btn {
        padding: .6rem 1.4rem;
        background: linear-gradient(135deg, var(--save-color), #1a9156);
        color: #fff;
        font-size: .95rem;
        font-weight: 600;
        border-radius: 10px;
        flex-shrink: 0;
    }

    .save-btn:disabled {
        opacity: .6;
        cursor: not-allowed;
    }

    .header-actions {
        display: flex;
        align-items: center;
        gap: .5rem;
        flex-shrink: 0;
    }

    .export-btn {
        padding: .6rem 1rem;
        background: linear-gradient(135deg, var(--primary-color), #1b73b0);
        color: #fff;
        font-size: .9rem;
        font-weight: 600;
        border-radius: 10px;
        flex-shrink: 0;
    }

    .export-btn:disabled {
        opacity: .6;
        cursor: not-allowed;
    }

    .loading-state, .error-state, .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        color: var(--text-light);
        font-size: 1rem;
    }

    .error-state {
        color: var(--error-text);
    }

    .tab-content {
        display: flex;
        flex-direction: column;
        gap: 1.35rem;
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

    .model-selector-group {
        margin-top: .9rem;
    }

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

    .group-label {
        font-weight: 500;
        margin-top: .9rem;
        margin-bottom: 0.5rem;
        color: var(--text-light);
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

    .param-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
    }

    .param-field {
        display: flex;
        flex-direction: column;
        gap: .35rem;
    }

    .param-input-row {
        display: flex;
        gap: .35rem;
        align-items: center;
    }

    .param-input-row input {
        flex: 1;
    }

    .clear-btn {
        padding: .35rem .55rem;
        background: var(--control-bg);
        color: var(--text-light);
        border: 1px solid var(--panel-muted-border);
        border-radius: 6px;
        cursor: pointer;
        font-size: .9rem;
        line-height: 1;
    }

    .clear-btn:hover {
        color: var(--text-color);
        background: var(--control-hover-bg);
    }

    .checkbox-inline {
        display: inline-flex;
        align-items: center;
        gap: .45rem;
        color: var(--text-light);
        font-weight: 500;
    }

    .fancy-checkbox {
        position: relative;
        cursor: pointer;
        user-select: none;
        padding: .36rem .62rem .36rem .45rem;
        border-radius: 999px;
        border: 1px solid var(--panel-muted-border);
        background: var(--panel-muted-bg);
        transition: border-color .2s ease, background-color .2s ease, transform .15s ease;
    }

    .fancy-checkbox:hover {
        border-color: var(--primary-color);
        background: var(--control-bg);
    }

    .fancy-checkbox input[type="checkbox"] {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
    }

    .checkbox-box {
        width: 20px;
        height: 20px;
        border-radius: 6px;
        border: 1px solid var(--border-color);
        background: var(--surface-tint);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        box-shadow: var(--shadow-soft);
        transition: all .2s ease;
        flex-shrink: 0;
    }

    .checkbox-box::after {
        content: "";
        width: 10px;
        height: 6px;
        border-left: 2px solid #fff;
        border-bottom: 2px solid #fff;
        transform: rotate(-45deg) scale(0);
        transform-origin: center;
        margin-top: -1px;
        transition: transform .15s ease;
    }

    .checkbox-text {
        color: var(--text-color);
        line-height: 1.2;
    }

    .fancy-checkbox input[type="checkbox"]:checked + .checkbox-box {
        background: linear-gradient(135deg, var(--primary-color), #1b73b0);
        border-color: var(--primary-color);
    }

    .fancy-checkbox input[type="checkbox"]:checked + .checkbox-box::after {
        transform: rotate(-45deg) scale(1);
    }

    .fancy-checkbox input[type="checkbox"]:focus-visible + .checkbox-box {
        box-shadow: 0 0 0 3px rgba(69, 163, 230, .35);
    }

    .list-container {
        margin-bottom: .75rem;
    }

    .list-item {
        margin-bottom: .5rem;
    }

    .header-item {
        display: grid;
        grid-template-columns: 1.5fr 2fr auto;
        gap: .7rem;
        align-items: center;
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

    .remove-btn {
        padding: .3rem .55rem;
        background: transparent;
        color: var(--text-light);
        border: 1px solid var(--panel-muted-border);
        border-radius: 6px;
        cursor: pointer;
        font-size: 1.1rem;
        line-height: 1;
    }

    .remove-btn:hover {
        color: var(--error-text);
        border-color: var(--error-text);
        background: var(--error-bg);
    }

    .add-btn {
        padding: .45rem .9rem;
        background: var(--control-bg);
        color: var(--text-color);
        border: 1px solid var(--panel-muted-border);
        border-radius: 8px;
        cursor: pointer;
        font-size: .85rem;
    }

    .add-btn:hover {
        background: var(--control-hover-bg);
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

    @media (max-width: 900px) {
        .config-panel {
            padding: .75rem 1rem;
        }

        .config-header {
            flex-wrap: wrap;
            gap: .5rem;
        }

        .config-header h2 {
            font-size: 1rem;
            padding: .45rem .75rem;
        }

        .save-btn {
            padding: .5rem 1rem;
            font-size: .85rem;
        }

        .export-btn {
            padding: .5rem .8rem;
            font-size: .8rem;
            border-radius: 8px;
        }

        .provider-top-grid {
            grid-template-columns: 1fr;
        }

        .param-grid {
            grid-template-columns: 1fr;
        }

        .radio-group {
            gap: 1rem;
        }

        .param-item, .header-item {
            grid-template-columns: 1fr;
        }

        .param-select.wide, .param-textarea {
            grid-column: auto;
        }

        .param-item > .remove-btn {
            justify-self: start;
        }

        .model-controls {
            flex-direction: column;
        }

        .model-controls select,
        .model-controls input {
            width: 100%;
        }
    }

    @media (max-width: 600px) {
        .config-panel {
            padding: .5rem .6rem;
        }

        .config-header h2 {
            font-size: .85rem;
            padding: .35rem .6rem;
        }

        .save-btn {
            padding: .4rem .8rem;
            font-size: .78rem;
            border-radius: 8px;
        }

        .export-btn {
            padding: .35rem .55rem;
            font-size: .72rem;
            border-radius: 7px;
        }

        .header-actions {
            gap: .35rem;
        }
    }
</style>
