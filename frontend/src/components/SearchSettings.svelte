<!-- frontend/src/components/SearchSettings.svelte -->
<script>
    import { derived } from 'svelte/store';
    import { fade, fly } from 'svelte/transition';
    import { t } from '../i18n.js';
    import { pluginsConfig } from '../lib/stores.js';
    import Card from './Card.svelte';

    let newDomain = { name: '', url: '' };
    let showUsageGuide = false;

    const defaultSearchConfig = {
        enabled: false,
        api_key: '',
        api_url: 'https://api.tavily.com',
        command: '!search',
        trigger_mode: 'command',
        keywords: [],
        require_main_trigger: true,
        rewrite_query_with_llm: true,
        search_depth: 'basic',
        max_results: 5,
        include_date: true,
        exclude_domains: [],
        compression_strategy: 'none'
    };

    // Derived store for search settings, ensuring it's always valid
    const searchConfig = derived(pluginsConfig, $plugins => {
        return { ...defaultSearchConfig, ...($plugins.search || {}) };
    });

    // Centralized update function
    function updatePlugin(field, value) {
        pluginsConfig.update(plugins => {
            const currentSearch = plugins.search || {};
            return {
                ...plugins,
                search: { ...currentSearch, [field]: value }
            };
        });
    }

    function addDomain() {
        if (!newDomain.url.trim()) return;
        const currentDomains = $searchConfig.exclude_domains || [];
        const updatedDomains = [...currentDomains, newDomain.url];
        updatePlugin('exclude_domains', updatedDomains);
        newDomain = { name: '', url: '' };
    }

    function removeDomain(index) {
        const updatedDomains = [...$searchConfig.exclude_domains];
        updatedDomains.splice(index, 1);
        updatePlugin('exclude_domains', updatedDomains);
    }

    function handleDomainChange(index, value) {
        const updatedDomains = [...$searchConfig.exclude_domains];
        updatedDomains[index] = value;
        updatePlugin('exclude_domains', updatedDomains);
    }
</script>

<fieldset class="search-plugin-container">
  <div class="search-layout">
    <Card title={$t('Tavily API')} theme="dark-theme">
        <div class="plugin-grid">
            <div class="form-group">
                <label for="search-api-key">{$t('searchSettings.apiKey')}</label>
                <input id="search-api-key" type="password" placeholder="sk-..." value={$searchConfig.api_key || ''} on:change={e => updatePlugin('api_key', e.target.value)}>
                <a
                    class="api-help-link"
                    href="https://app.tavily.com/home"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    {$t('searchSettings.getApiKey')}
                </a>
                <button class="guide-link" type="button" on:click={() => showUsageGuide = true}>
                    {$t('searchSettings.usageGuide.link')}
                </button>
            </div>

            <div class="form-group">
                <label for="search-api-url">{$t('searchSettings.apiUrl')}</label>
                <input id="search-api-url" type="text" value={$searchConfig.api_url || 'https://api.tavily.com'} on:change={e => updatePlugin('api_url', e.target.value)}>
            </div>
        </div>
    </Card>

    <Card title={$t('searchSettings.config.title')} theme="dark-theme">
        <div class="plugin-grid">
            <!-- 启用开关 -->
            <div class="form-group">
                <label for="search-enabled">{$t('searchSettings.enable')}</label>
                <div class="toggle-switch">
                    <input type="checkbox" id="search-enabled" checked={$searchConfig.enabled} on:change={e => updatePlugin('enabled', e.target.checked)}>
                    <span class="slider"></span>
                </div>
            </div>

            <!-- 触发模式 -->
            <div class="form-group full-width">
                <span id="trigger-mode-label" class="group-label">{$t('searchSettings.triggerMode.title')}</span>
                <div class="radio-group" role="group" aria-labelledby="trigger-mode-label">
                    <label>
                        <input type="radio" value="command" checked={$searchConfig.trigger_mode === 'command'} on:change={() => updatePlugin('trigger_mode', 'command')}>
                        {$t('searchSettings.triggerMode.command')}
                    </label>
                    <label>
                        <input type="radio" value="keyword" checked={$searchConfig.trigger_mode === 'keyword'} on:change={() => updatePlugin('trigger_mode', 'keyword')}>
                        {$t('searchSettings.triggerMode.keyword')}
                    </label>
                </div>
            </div>

            <!-- 触发内容输入框 -->
            <div class="form-group full-width">
                {#if $searchConfig.trigger_mode === 'command'}
                    <label for="search-command">{$t('searchSettings.commandLabel')}</label>
                    <input id="search-command" type="text" value={$searchConfig.command || ''} on:change={e => updatePlugin('command', e.target.value)}>
                    <p class="info">{$t('searchSettings.commandInfo')}</p>
                {:else}
                    <label for="search-keywords">{$t('searchSettings.keywordsLabel')}</label>
                    <input id="search-keywords" type="text" value={($searchConfig.keywords || []).join(', ')} on:change={e => updatePlugin('keywords', e.target.value.split(',').map(k => k.trim()).filter(k => k))}>
                    <p class="info">{$t('searchSettings.keywordsInfo')}</p>
                {/if}
            </div>

            <div class="form-group">
                <label for="search-include-date">{$t('searchSettings.includeDate')}</label>
                <div class="toggle-switch">
                    <input type="checkbox" id="search-include-date" checked={$searchConfig.include_date !== false} on:change={e => updatePlugin('include_date', e.target.checked)}>
                    <span class="slider"></span>
                </div>
            </div>
            <div class="form-group">
                <label for="search-require-main-trigger">{$t('searchSettings.requireMainTrigger')}</label>
                <div class="toggle-switch">
                    <input type="checkbox" id="search-require-main-trigger" checked={$searchConfig.require_main_trigger !== false} on:change={e => updatePlugin('require_main_trigger', e.target.checked)}>
                    <span class="slider"></span>
                </div>
            </div>
            <div class="form-group">
                <label for="search-rewrite-query">{$t('searchSettings.rewriteQueryWithLlm')}</label>
                <div class="toggle-switch">
                    <input type="checkbox" id="search-rewrite-query" checked={$searchConfig.rewrite_query_with_llm !== false} on:change={e => updatePlugin('rewrite_query_with_llm', e.target.checked)}>
                    <span class="slider"></span>
                </div>
            </div>
            <div class="form-group">
                <label for="search-max-results">{$t('searchSettings.maxResults')}</label>
                <input
                    id="search-max-results"
                    type="number"
                    min="1"
                    step="1"
                    value={$searchConfig.max_results ?? 5}
                    on:change={e => updatePlugin('max_results', Math.max(1, parseInt(e.target.value || '1', 10) || 1))}
                >
            </div>

            
            <div class="form-group full-width">
                <label for="search-compression">{$t('searchSettings.compression')}</label>
                <select id="search-compression"
                        value={$searchConfig.compression_strategy || 'none'}
                        on:change={e => updatePlugin('compression_strategy', e.target.value)}>
                    <option value="none">{$t('searchSettings.compressionNone')}</option>
                    <option value="truncate">{$t('searchSettings.compressionTruncate')}</option>
                    <option value="rag">{$t('searchSettings.compressionRAG')}</option>
                </select>
            </div>
        </div>
    </Card>

    <Card title={$t('searchSettings.blacklist.title')} theme="dark-theme">
        <div class="list-container">
            {#if $searchConfig.exclude_domains && $searchConfig.exclude_domains.length > 0}
                <div class="list-header">
                    <span>URL</span>
                </div>
                {#each $searchConfig.exclude_domains as domain, i}
                    <div class="list-item-single">
                        <input type="text" placeholder="example.com/*" value={domain} on:change={e => handleDomainChange(i, e.target.value)}>
                        <button class="remove-btn" on:click={() => removeDomain(i)}>×</button>
                    </div>
                {/each}
            {:else}
                <div class="empty-state">
                    <div class="empty-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><path d="M12 18h.01"/><path d="M16 12h-4"/></svg>
                    </div>
                    <p>{$t('searchSettings.blacklist.empty')}</p>
                </div>
            {/if}
        </div>
        <div class="add-item-form">
            <input type="text" placeholder={$t('searchSettings.blacklist.addPlaceholder')} bind:value={newDomain.url}>
            <button class="add-btn" on:click={addDomain}>{$t('searchSettings.blacklist.add')}</button>
        </div>
    </Card>
  </div>
</fieldset>

{#if showUsageGuide}
<div
    class="modal-overlay"
    role="button"
    tabindex="0"
    in:fade={{ duration: 160 }}
    out:fade={{ duration: 120 }}
    on:click={(e) => { if (e.target === e.currentTarget) showUsageGuide = false; }}
    on:keydown={(e) => { if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') showUsageGuide = false; }}
>
    <div class="modal-card" role="dialog" aria-modal="true" in:fly={{ y: 12, duration: 180 }} out:fly={{ y: 8, duration: 120 }}>
        <h3>{$t('searchSettings.usageGuide.title')}</h3>
        <p>{$t('searchSettings.usageGuide.intro')}</p>

        <h4>{$t('searchSettings.usageGuide.commandTitle')}</h4>
        <ul>
            <li>{$t('searchSettings.usageGuide.command1')}</li>
            <li>{$t('searchSettings.usageGuide.command2')}</li>
            <li>{$t('searchSettings.usageGuide.command3')}</li>
        </ul>

        <h4>{$t('searchSettings.usageGuide.keywordTitle')}</h4>
        <ul>
            <li>{$t('searchSettings.usageGuide.keyword1')}</li>
            <li>{$t('searchSettings.usageGuide.keyword2')}</li>
            <li>{$t('searchSettings.usageGuide.keyword3')}</li>
        </ul>

        <h4>{$t('searchSettings.usageGuide.troubleshootTitle')}</h4>
        <ol>
            <li>{$t('searchSettings.usageGuide.troubleshoot1')}</li>
            <li>{$t('searchSettings.usageGuide.troubleshoot2')}</li>
            <li>{$t('searchSettings.usageGuide.troubleshoot3')}</li>
            <li>{$t('searchSettings.usageGuide.troubleshoot4')}</li>
        </ol>

        <div class="modal-actions">
            <button class="add-btn" type="button" on:click={() => showUsageGuide = false}>
                {$t('searchSettings.usageGuide.close')}
            </button>
        </div>
    </div>
</div>
{/if}

<style>
    .search-plugin-container {
        border: 0;
        margin: 0;
        padding: 0;
        min-width: 0;
    }

    .search-layout {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
    }

    .search-layout :global(.card:last-child) {
        grid-column: 1 / -1;
    }

    .plugin-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem 1.5rem;
    }
    .form-group {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }
    .form-group.full-width {
        grid-column: 1 / -1;
    }
    .list-header {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 1rem;
        padding: 0 1rem 0 0;
        color: var(--text-light);
        font-weight: 500;
        margin-bottom: 0.5rem;
    }
    .group-label {
        font-weight: 500;
    }
    .radio-group {
        display: flex;
        gap: 1.5rem;
        align-items: center;
    }
    .radio-group label {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        cursor: pointer;
    }
    .info {
        font-size: 0.85rem;
        color: var(--text-light);
        margin-top: -0.25rem;
    }
    .api-help-link {
        color: var(--primary-color);
        font-size: 0.85rem;
        text-decoration: underline;
        width: fit-content;
    }
    .api-help-link:hover {
        color: var(--primary-hover);
    }
    .guide-link {
        background: transparent;
        color: var(--text-light);
        border: none;
        box-shadow: none;
        padding: 0;
        text-decoration: underline;
        width: fit-content;
        font-size: 0.85rem;
    }
    .guide-link:hover {
        color: var(--primary-color);
    }
    .modal-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, .5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1200;
        padding: 1rem;
    }
    .modal-card {
        width: min(640px, 96%);
        max-height: 88vh;
        overflow: auto;
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        box-shadow: var(--shadow);
        padding: 1rem 1rem .9rem;
        color: var(--text-color);
    }
    .modal-card h3 {
        margin: 0 0 .5rem;
    }
    .modal-card h4 {
        margin: .85rem 0 .35rem;
    }
    .modal-card p {
        margin: 0;
        color: var(--text-light);
    }
    .modal-card ul,
    .modal-card ol {
        margin: .35rem 0 0;
        padding-left: 1.1rem;
        color: var(--text-light);
        display: grid;
        gap: .25rem;
    }
    .modal-actions {
        margin-top: .9rem;
        display: flex;
        justify-content: flex-end;
    }
    .list-item-single {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 1rem;
        align-items: center;
    }
    .empty-state {
        text-align: center;
        padding: 2rem 1rem;
        color: var(--text-light);
    }
    .empty-icon {
        background: #2a2b2f;
        border-radius: 50%;
        width: 60px;
        height: 60px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 1rem;
    }
    .empty-icon svg {
        color: #5d616d;
        width: 30px;
        height: 30px;
    }
    .add-item-form {
        display: flex;
        gap: 1rem;
        margin-top: 1.5rem;
        border-top: 1px solid #444654;
        padding-top: 1.5rem;
    }

    @media (max-width: 1000px) {
        .search-layout {
            grid-template-columns: 1fr;
        }
    }
</style>
