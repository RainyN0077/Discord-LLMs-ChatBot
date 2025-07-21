<!-- frontend/src/components/SearchSettings.svelte -->
<script>
    import { onMount } from 'svelte';
    import { t, get as t_get } from '../i18n.js';
    import { config, updateConfigField } from '../lib/stores.js';
    import Card from './Card.svelte';

    let searchConfig;
    let newDomain = { name: '', url: '' };

    $: searchConfig = $config.plugins?.search || {
        enabled: false,
        api_key: '',
        api_url: 'https://api.tavily.com',
        search_depth: 'basic',
        max_results: 5,
        include_date: true,
        exclude_domains: [],
        compression_strategy: 'none'
    };

    onMount(() => {
        // Set max_results to 30 on component mount
        if (searchConfig.max_results !== 30) {
            updateSearchConfig('max_results', 30);
        }
    });

    function updateSearchConfig(field, value) {
        updateConfigField(`plugins.search.${field}`, value);
    }
    
    function addDomain() {
        if (!newDomain.url.trim()) {
            // 在UI中显示错误或简单地忽略它
            return;
        }
        const currentDomains = searchConfig.exclude_domains || [];
        // 假设黑名单项只是一个字符串列表
        const updatedDomains = [...currentDomains, newDomain.url];
        updateSearchConfig('exclude_domains', updatedDomains);
        newDomain = { name: '', url: '' }; // 重置输入
    }

    function removeDomain(index) {
        const updatedDomains = [...searchConfig.exclude_domains];
        updatedDomains.splice(index, 1);
        updateSearchConfig('exclude_domains', updatedDomains);
    }
</script>

<Card title={$t('Tavily API')} theme="dark-theme">
    <div class="plugin-grid">
        <div class="form-group">
            <label for="search-api-key">{$t('searchSettings.apiKey')}</label>
            <input id="search-api-key" type="password" placeholder="sk-..." value={searchConfig.api_key || ''} on:input={e => updateSearchConfig('api_key', e.target.value)}>
        </div>

        <div class="form-group">
            <label for="search-api-url">{$t('searchSettings.apiUrl')}</label>
            <input id="search-api-url" type="text" value={searchConfig.api_url || 'https://api.tavily.com'} on:input={e => updateSearchConfig('api_url', e.target.value)}>
        </div>
    </div>
</Card>

<Card title={$t('searchSettings.config.title')} theme="dark-theme">
    <div class="plugin-grid">
        <div class="form-group">
            <label for="search-include-date">{$t('searchSettings.includeDate')}</label>
            <div class="toggle-switch">
                <input type="checkbox" id="search-include-date" checked={searchConfig.include_date !== false} on:change={e => updateSearchConfig('include_date', e.target.checked)}>
                <span class="slider"></span>
            </div>
        </div>

        
        <div class="form-group full-width">
            <label for="search-compression">{$t('searchSettings.compression')}</label>
            <select id="search-compression"
                    value={searchConfig.compression_strategy || 'none'}
                    on:change={e => updateSearchConfig('compression_strategy', e.target.value)}>
                <option value="none">{$t('searchSettings.compressionNone')}</option>
                <option value="truncate">{$t('searchSettings.compressionTruncate')}</option>
                <option value="rag">{$t('searchSettings.compressionRAG')}</option>
            </select>
        </div>
    </div>
</Card>

<Card title={$t('searchSettings.blacklist.title')} theme="dark-theme">
    <div class="list-container">
        {#if searchConfig.exclude_domains && searchConfig.exclude_domains.length > 0}
            <div class="list-header">
                <span>URL</span>
            </div>
            {#each searchConfig.exclude_domains as domain, i}
                <div class="list-item-single">
                    <input type="text" placeholder="example.com/*" value={domain} on:input={e => {
                        const updatedDomains = [...searchConfig.exclude_domains];
                        updatedDomains[i] = e.target.value;
                        updateSearchConfig('exclude_domains', updatedDomains);
                    }}>
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

<style>
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
    .number-input {
        padding: 0.5rem;
        border-radius: 6px;
        border: 1px solid var(--border-color);
        background-color: var(--input-bg);
        color: var(--text-color);
        width: 100px; /* Or adjust as needed */
    }
</style>