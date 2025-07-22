<!-- frontend/src/components/SearchSettings.svelte -->
<script>
    import { derived } from 'svelte/store';
    import { t } from '../i18n.js';
    import { pluginsConfig } from '../lib/stores.js';
    import Card from './Card.svelte';

    let newDomain = { name: '', url: '' };

    const defaultSearchConfig = {
        enabled: false,
        api_key: '',
        api_url: 'https://api.tavily.com',
        command: '!search',
        trigger_mode: 'command',
        keywords: [],
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
            plugins.search = { ...currentSearch, [field]: value };
            return plugins;
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

<fieldset disabled class="disabled-plugin-container">
    <Card title={$t('Tavily API')} theme="dark-theme">
        <p class="warning-message">该组件存在严重问题，现版本不可用</p>
        <div class="plugin-grid">
            <div class="form-group">
                <label for="search-api-key">{$t('searchSettings.apiKey')}</label>
                <input id="search-api-key" type="password" placeholder="sk-..." value={$searchConfig.api_key || ''} on:change={e => updatePlugin('api_key', e.target.value)}>
            </div>

            <div class="form-group">
                <label for="search-api-url">{$t('searchSettings.apiUrl')}</label>
                <input id="search-api-url" type="text" value={$searchConfig.api_url || 'https://api.tavily.com'} on:change={e => updatePlugin('api_url', e.target.value)}>
            </div>
        </div>
    </Card>

    <Card title={$t('searchSettings.config.title')} theme="dark-theme">
        <p class="warning-message">该组件存在严重问题，现版本不可用</p>
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
                <label id="trigger-mode-label">{$t('searchSettings.triggerMode.title')}</label>
                <div class="radio-group" role="group" aria-labelledby="trigger-mode-label">
                    <label>
                        <input type="radio" value="command" bind:group={$searchConfig.trigger_mode} on:change={() => updatePlugin('trigger_mode', 'command')}>
                        {$t('searchSettings.triggerMode.command')}
                    </label>
                    <label>
                        <input type="radio" value="keyword" bind:group={$searchConfig.trigger_mode} on:change={() => updatePlugin('trigger_mode', 'keyword')}>
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
        <p class="warning-message">该组件存在严重问题，现版本不可用</p>
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
</fieldset>

<style>
    .disabled-plugin-container {
        filter: grayscale(80%);
        opacity: 0.6;
    }

    .warning-message {
        color: #e53935; /* A strong red */
        font-weight: 500;
        text-align: center;
        width: 100%;
        margin-bottom: 1rem;
        padding: 0.5rem;
        background-color: rgba(229, 57, 53, 0.15);
        border: 1px solid rgba(229, 57, 53, 0.3);
        border-radius: 4px;
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
</style>