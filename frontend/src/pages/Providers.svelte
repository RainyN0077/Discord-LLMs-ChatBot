<!-- src/pages/Providers.svelte -->
<script>
    import { t } from '../i18n.js';
    import { showStatus } from '../lib/commonStores.js';
    import { fetchProviders, switchProvider } from '../lib/api.js';
    import { PROVIDER_DEFAULTS } from '../lib/providerDefaults.js';
    import Card from '../components/Card.svelte';
    import ThreeState from '../components/ThreeState.svelte';

    export let botId = null;

    let providers = [];
    let currentProvider = '';
    let currentModel = '';
    let loading = false;
    let loadError = '';

    // 行内切换表单状态
    let switchTarget = null;  // 当前展开切换表单的 provider name
    let switchModel = '';
    let switchApiKey = '';
    let switchBaseUrl = '';
    let switchingKey = null;  // 正在切换的 provider name，防重复提交

    // t() 在 key 缺失时返回 key 本身，以此回退显示 provider 原名
    function providerLabel(name) {
        const key = `llmProvider.providers.${name}`;
        const translated = $t(key);
        return translated === key ? name : translated;
    }

    function healthClass(provider) {
        if (provider.healthy === true) return 'healthy';
        if (provider.healthy === false) return 'unhealthy';
        return 'unknown';
    }

    function healthText(provider) {
        if (provider.healthy === true) return $t('providersPage.healthy');
        if (provider.healthy === false) return $t('providersPage.unhealthy');
        return $t('providersPage.unknown');
    }

    function defaultModelFor(name) {
        return PROVIDER_DEFAULTS[name]?.models?.[0]?.id || '';
    }

    async function loadProviders() {
        if (!botId) {
            providers = [];
            currentProvider = '';
            currentModel = '';
            return;
        }
        loading = true;
        loadError = '';
        try {
            const result = await fetchProviders(botId);
            providers = result.providers || [];
            currentProvider = result.current_provider || '';
            currentModel = result.current_model || '';
        } catch (e) {
            loadError = e.message || String(e);
            showStatus($t('providersPage.loadFailed', { error: loadError }), 'error');
        } finally {
            loading = false;
        }
    }

    // MEDIUM-1b: 只保留 $: 响应式加载（初始 botId 非空时 $: 会在挂载时触发，
    // botId 为空再变非空/切换 Bot 时也会触发），避免与 onMount 重复请求
    $: if (botId) loadProviders();

    function beginSwitch(provider) {
        switchTarget = provider.name;
        switchModel = defaultModelFor(provider.name) || provider.model || '';
        switchApiKey = '';
        switchBaseUrl = PROVIDER_DEFAULTS[provider.name]?.baseUrl || '';
    }

    function cancelSwitch() {
        switchTarget = null;
        switchModel = '';
        switchApiKey = '';
        switchBaseUrl = '';
    }

    async function handleSwitch(providerName) {
        if (switchingKey) return;
        if (!switchModel.trim()) {
            showStatus($t('providersPage.modelRequired'), 'error');
            return;
        }
        if (!switchApiKey.trim()) {
            showStatus($t('providersPage.apiKeyRequired'), 'error');
            return;
        }
        switchingKey = providerName;
        try {
            const payload = {
                provider: providerName,
                model: switchModel.trim(),
                api_key: switchApiKey.trim(),
            };
            // 后端 base_url 可选；空字符串会触发 422 pattern 校验失败，故为空时不传
            if (switchBaseUrl.trim()) {
                payload.base_url = switchBaseUrl.trim();
            }
            await switchProvider(botId, payload);
            showStatus($t('providersPage.switchSuccess'), 'success');
            cancelSwitch();
            await loadProviders();
        } catch (e) {
            // apiFetch 已解析后端 detail（429 速率限制 / 422 校验失败等）
            showStatus($t('providersPage.switchFailed', { error: e.message || String(e) }), 'error');
        } finally {
            switchingKey = null;
        }
    }
</script>

<div class="providers-panel">
    <div class="providers-header">
        <h2>{botId ? $t('providersPage.title', { botId }) : $t('providersPage.noBotSelected')}</h2>
        <div class="header-actions">
            <button class="refresh-btn" on:click={loadProviders} disabled={loading || !botId}>
                {loading ? $t('providersPage.refreshing') : $t('providersPage.refresh')}
            </button>
        </div>
    </div>

    <ThreeState loading={loading} error={loadError} empty={!botId} emptyMessage={$t('providersPage.noBotSelected')}>
        <span slot="loading-text">{$t('providersPage.loading')}</span>

        {#if currentProvider}
            <div class="current-info">
                <span class="current-badge">{$t('providersPage.current')}</span>
                <strong>{providerLabel(currentProvider)}</strong>
                {#if currentModel}
                    <span class="current-model">{$t('providersPage.currentModel')}: {currentModel}</span>
                {/if}
            </div>
        {/if}

        <div class="providers-list">
            {#each providers as provider (provider.name)}
                <Card title={providerLabel(provider.name)} extraClass={provider.is_current ? 'provider-card-current' : ''}>
                    <div class="provider-row">
                        <div class="provider-meta">
                            {#if provider.is_current}
                                <span class="current-tag">{$t('providersPage.currentTag')}</span>
                            {/if}
                            {#if provider.model}
                                <span class="provider-model">{provider.model}</span>
                            {/if}
                            <span class="health-badge {healthClass(provider)}">
                                {healthText(provider)}
                                {#if provider.latency_ms != null && provider.healthy !== null}
                                    · {$t('providersPage.latency', { ms: Math.round(provider.latency_ms) })}
                                {/if}
                            </span>
                        </div>
                        <div class="provider-actions">
                            {#if !provider.is_current && switchTarget !== provider.name}
                                <button class="switch-btn" on:click={() => beginSwitch(provider)} disabled={loading || !!switchingKey}>
                                    {$t('providersPage.switchBtn')}
                                </button>
                            {/if}
                        </div>
                    </div>

                    {#if !provider.configured}
                        <p class="not-configured">{$t('providersPage.notConfigured')}</p>
                    {/if}

                    {#if switchTarget === provider.name}
                        <div class="switch-form">
                            <div class="form-field">
                                <label for={`switch-model-${provider.name}`}>{$t('providersPage.modelLabel')}</label>
                                <input id={`switch-model-${provider.name}`} type="text" placeholder={$t('providersPage.modelPlaceholder')} bind:value={switchModel}>
                            </div>
                            <div class="form-field">
                                <label for={`switch-key-${provider.name}`}>{$t('providersPage.apiKeyLabel')}</label>
                                <input id={`switch-key-${provider.name}`} type="password" placeholder={$t('providersPage.apiKeyLabel')} bind:value={switchApiKey}>
                            </div>
                            <div class="form-field">
                                <label for={`switch-url-${provider.name}`}>{$t('providersPage.baseUrlLabel')}</label>
                                <input id={`switch-url-${provider.name}`} type="text" placeholder={$t('providersPage.baseUrlLabel')} bind:value={switchBaseUrl}>
                            </div>
                            <div class="form-actions">
                                <button class="switch-submit-btn" on:click={() => handleSwitch(provider.name)} disabled={!!switchingKey}>
                                    {switchingKey ? $t('providersPage.switching') : $t('providersPage.switchBtn')}
                                </button>
                                <button class="cancel-btn" on:click={cancelSwitch} disabled={!!switchingKey}>{$t('providersPage.cancel')}</button>
                            </div>
                        </div>
                    {/if}
                </Card>
            {/each}
        </div>
    </ThreeState>
</div>

<style>
    .providers-panel {
        padding: 1rem 1.5rem;
        overflow-y: auto;
        flex: 1;
        min-height: 0;
        box-sizing: border-box;
    }

    .providers-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        flex-shrink: 0;
        overflow: hidden;
        min-width: 0;
    }

    .providers-header h2 {
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

    .header-actions {
        display: flex;
        align-items: center;
        gap: .5rem;
        flex-shrink: 0;
    }

    .refresh-btn {
        padding: .6rem 1rem;
        background: linear-gradient(135deg, var(--primary-color), #1b73b0);
        color: #fff;
        font-size: .9rem;
        font-weight: 600;
        border-radius: 10px;
        flex-shrink: 0;
    }

    .refresh-btn:disabled {
        opacity: .6;
        cursor: not-allowed;
    }

    .current-info {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: .5rem;
        padding: .7rem .9rem;
        border-radius: 12px;
        background: var(--panel-soft-bg-2);
        border: 1px solid var(--panel-muted-border);
        margin-bottom: 1rem;
        color: var(--text-color);
        font-size: .9rem;
    }

    .current-badge {
        padding: .2rem .6rem;
        border-radius: 999px;
        background: linear-gradient(135deg, var(--primary-color), #1b73b0);
        color: #fff;
        font-size: .78rem;
        font-weight: 600;
        white-space: nowrap;
    }

    .current-model {
        color: var(--text-light);
    }

    .providers-list {
        display: flex;
        flex-direction: column;
        gap: 1.1rem;
    }

    :global(.provider-card-current) {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 1px rgba(31, 139, 214, .25), var(--shadow);
    }

    .provider-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: .75rem;
        flex-wrap: wrap;
    }

    .provider-meta {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: .5rem;
        min-width: 0;
    }

    .current-tag {
        padding: .15rem .5rem;
        border-radius: 999px;
        background: var(--success-bg);
        color: var(--success-text);
        font-size: .75rem;
        font-weight: 600;
        white-space: nowrap;
    }

    .provider-model {
        font-family: monospace;
        font-size: .85rem;
        color: var(--text-color);
        background: var(--control-bg);
        border: 1px solid var(--panel-muted-border);
        border-radius: 6px;
        padding: .15rem .45rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
    }

    .health-badge {
        display: inline-flex;
        align-items: center;
        gap: .25rem;
        padding: .15rem .55rem;
        border-radius: 999px;
        font-size: .75rem;
        font-weight: 600;
        white-space: nowrap;
    }

    .health-badge.healthy {
        background: var(--success-bg);
        color: var(--success-text);
    }

    .health-badge.unhealthy {
        background: var(--error-bg);
        color: var(--error-text);
    }

    .health-badge.unknown {
        background: var(--panel-muted-bg);
        color: var(--text-light);
    }

    .provider-actions {
        flex-shrink: 0;
    }

    .switch-btn, .cancel-btn {
        padding: .45rem .9rem;
        border-radius: 8px;
        font-size: .85rem;
        font-weight: 600;
        cursor: pointer;
    }

    .switch-btn {
        background: linear-gradient(135deg, var(--primary-color), #1b73b0);
        color: #fff;
        border: 1px solid transparent;
    }

    .switch-btn:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 8px 20px rgba(31, 139, 214, .24);
    }

    .switch-btn:disabled, .cancel-btn:disabled {
        opacity: .6;
        cursor: not-allowed;
    }

    .cancel-btn {
        background: var(--control-bg);
        color: var(--text-color);
        border: 1px solid var(--panel-muted-border);
    }

    .cancel-btn:hover:not(:disabled) {
        background: var(--control-hover-bg);
    }

    .not-configured {
        margin: 0;
        font-size: .82rem;
        color: var(--text-light);
        background: var(--panel-muted-bg);
        border: 1px dashed var(--panel-muted-border);
        border-radius: 8px;
        padding: .45rem .7rem;
    }

    .switch-form {
        display: flex;
        flex-direction: column;
        gap: .75rem;
        padding: .9rem;
        border: 1px solid var(--panel-muted-border);
        border-radius: 12px;
        background: var(--panel-soft-bg-2);
    }

    .form-field {
        display: flex;
        flex-direction: column;
        gap: .35rem;
    }

    .form-field label {
        font-size: .82rem;
        font-weight: 500;
        color: var(--text-light);
    }

    .form-field input {
        width: 100%;
        box-sizing: border-box;
    }

    .form-actions {
        display: flex;
        gap: .5rem;
        align-items: center;
    }

    .switch-submit-btn {
        padding: .5rem 1.1rem;
        background: linear-gradient(135deg, var(--save-color), #1a9156);
        color: #fff;
        border: 1px solid transparent;
        border-radius: 8px;
        font-size: .88rem;
        font-weight: 600;
        cursor: pointer;
    }

    .switch-submit-btn:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 8px 20px rgba(24, 138, 81, .25);
    }

    .switch-submit-btn:disabled {
        opacity: .6;
        cursor: not-allowed;
    }

    @media (max-width: 900px) {
        .providers-panel {
            padding: .75rem 1rem;
        }

        .providers-header {
            flex-wrap: wrap;
            gap: .5rem;
        }

        .providers-header h2 {
            font-size: 1rem;
            padding: .45rem .75rem;
        }

        .refresh-btn {
            padding: .5rem .8rem;
            font-size: .8rem;
            border-radius: 8px;
        }
    }

    @media (max-width: 600px) {
        .providers-panel {
            padding: .5rem .6rem;
        }

        .providers-header h2 {
            font-size: .85rem;
            padding: .35rem .6rem;
        }

        .refresh-btn {
            padding: .4rem .7rem;
            font-size: .75rem;
            border-radius: 7px;
        }

        .provider-row {
            flex-direction: column;
            align-items: flex-start;
        }
    }
</style>
