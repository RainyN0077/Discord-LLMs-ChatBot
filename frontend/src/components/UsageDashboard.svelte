<!-- frontend/src/components/UsageDashboard.svelte -->
<script>
    import { onMount, onDestroy } from 'svelte';
    import { t } from '../i18n.js';
    import { fetchUsageStats, fetchPricingConfig, savePricingConfig } from '../lib/api.js';
    
    let period = 'today';
    let view = 'user';
    let stats = null;
    let pricing = {}; // 这个变量将通过 fetchPricing 保持最新
    let isLoading = false;
    let refreshInterval;
    let showPricingModal = false;
    let editingPricing = [];
    let expandedItems = new Set();
    
    const periodOptions = [
        { value: 'today', label: 'usage.periods.today' },
        { value: 'week', label: 'usage.periods.week' },
        { value: 'month', label: 'usage.periods.month' },
        { value: 'all', label: 'usage.periods.all' }
    ];
    
    const viewOptions = [
        { value: 'user', label: 'usage.views.user' },
        { value: 'role', label: 'usage.views.role' },
        { value: 'channel', label: 'usage.views.channel' },
        { value: 'guild', label: 'usage.views.guild' }
    ];
    
    const providerOptions = [
        { value: 'openai', label: 'OpenAI' },
        { value: 'google', label: 'Google' },
        { value: 'anthropic', label: 'Anthropic' }
    ];

    async function fetchData() {
        // 并行获取统计数据和价格，提高加载速度
        await Promise.all([fetchStats(), fetchPricing()]);
    }
    
    async function fetchStats() {
        isLoading = true;
        try {
            stats = await fetchUsageStats(period, view);
            // 每次获取新数据时，不清空展开项，以保持用户状态
            // expandedItems.clear(); 
        } catch (e) {
            console.error('Failed to fetch usage stats:', e);
            stats = null; // 出错时清空数据
        } finally {
            isLoading = false;
        }
    }
    
    async function fetchPricing() {
        try {
            const data = await fetchPricingConfig();
            pricing = data.pricing || {};
        } catch (e) {
            console.error('Failed to fetch pricing:', e);
            pricing = {};
        }
    }

    function openPricingModal() {
        editingPricing = Object.entries(pricing).map(([key, value]) => {
            // 确保即使后端数据不规范也能正确解析
            const [providerFromKey, modelFromKey] = key.split(/:(.*)/s);
            return {
                id: key,
                provider: value.provider || providerFromKey || 'openai',
                model: value.model || modelFromKey || '',
                input_price_per_1m: value.input_price_per_1m || 0,
                output_price_per_1m: value.output_price_per_1m || 0
            };
        });
        showPricingModal = true;
    }
    
    async function savePricing() {
        const pricingObj = {};
        editingPricing.forEach(item => {
            if (item.provider && item.model) {
                const key = `${item.provider}:${item.model}`;
                pricingObj[key] = {
                    provider: item.provider,
                    model: item.model,
                    input_price_per_1m: parseFloat(item.input_price_per_1m) || 0,
                    output_price_per_1m: parseFloat(item.output_price_per_1m) || 0
                };
            }
        });
        
        try {
            await savePricingConfig(pricingObj);
            
            showPricingModal = false;
            // 核心修复：保存成功后，先获取最新的价格，再获取最新的统计数据
            await fetchPricing(); 
            await fetchStats();
            
        } catch (e) {
            console.error('Failed to save pricing:', e);
            alert($t('status.saveFailed', {error: e.message}));
        }
    }
    
    function addPricingRow() {
        editingPricing = [...editingPricing, {
            id: `new-${Date.now()}`,
            provider: 'openai',
            model: '',
            input_price_per_1m: 0,
            output_price_per_1m: 0
        }];
    }
    
    function removePricingRow(id) {
        editingPricing = editingPricing.filter(item => item.id !== id);
    }
    
    function toggleExpand(key) {
        expandedItems.has(key) ? expandedItems.delete(key) : expandedItems.add(key);
        expandedItems = new Set(expandedItems); // 触发响应式更新
    }
    
    function calculateCost(modelKey, inputTokens, outputTokens) {
        const price = pricing[modelKey];
        if (!price || typeof price !== 'object') return null;
        
        const inputPrice = parseFloat(price.input_price_per_1m) || 0;
        const outputPrice = parseFloat(price.output_price_per_1m) || 0;
        
        if (inputPrice === 0 && outputPrice === 0) return null;
        
        const inputCost = (inputTokens / 1000000) * inputPrice;
        const outputCost = (outputTokens / 1000000) * outputPrice;
        return inputCost + outputCost;
    }

    function calculateItemTotalCost(models) {
        if (!models || typeof models !== 'object') return 0;
        return Object.entries(models).reduce((sum, [modelKey, modelData]) => {
            const cost = calculateCost(modelKey, modelData.input_tokens, modelData.output_tokens);
            return sum + (cost || 0);
        }, 0);
    }
    
    // 派生计算，确保它们是响应式的
    $: detailedData = stats?.stats?.[`detailed_by_${view}`] || {};
    $: overallCost = Object.values(detailedData).reduce((total, data) => total + calculateItemTotalCost(data.models), 0);
    
    function formatNumber(num) {
        if (typeof num !== 'number') return '0';
        return num.toLocaleString();
    }
    
    function formatCost(cost) {
        if (cost === null || cost === undefined) return 'N/A';
        if (cost === 0) return '$0.0000';
        if (cost < 0.0001) return `<$0.0001`;
        return `$${cost.toFixed(4)}`;
    }
    
    function getDisplayName(key, type) {
        const meta = stats?.metadata?.[`${type}s`]?.[key];
        if (!meta) return key;
        
        return meta.display_name || meta.name || key;
    }

    function handleOverlayClick(event) {
        if (event.target === event.currentTarget) {
            showPricingModal = false;
        }
    }

    function handleKeydown(event) {
        if (showPricingModal && event.key === 'Escape') {
            showPricingModal = false;
        }
    }

    onMount(() => {
        fetchData();
        refreshInterval = setInterval(fetchData, 30000);
        window.addEventListener('keydown', handleKeydown);
    });
    
    onDestroy(() => {
        if (refreshInterval) clearInterval(refreshInterval);
        window.removeEventListener('keydown', handleKeydown);
    });
</script>

<div class="usage-dashboard">
    <div class="dashboard-header">
        <h3>{$t('usage.title')}</h3>
        <div class="controls">
            <label class="period-control">
                <span>{$t('usage.periodLabel')}</span>
                <select bind:value={period} on:change={fetchStats}>
                    {#each periodOptions as option}
                        <option value={option.value}>{$t(option.label)}</option>
                    {/each}
                </select>
            </label>
            <button class="icon-btn" on:click={openPricingModal} title={$t('usage.configurePricing')}>
                💰
            </button>
            <button class="icon-btn" on:click={fetchData} disabled={isLoading} title={$t('usage.refresh')}>
                {#if isLoading}🌀{:else}🔄{/if}
            </button>
        </div>
    </div>
    
    <div class="view-tabs">
        {#each viewOptions as option}
            <button 
                class:active={view === option.value} 
                on:click={() => { view = option.value; fetchStats(); }}>
                {$t(option.label)}
            </button>
        {/each}
    </div>
    
    {#if isLoading && !stats}
        <div class="loading">{$t('usage.loading')}</div>
    {:else if stats}
        <div class="stats-overview">
            <div class="stat-card">
                <div class="stat-value">{formatNumber(stats.stats?.requests || 0)}</div>
                <div class="stat-label">{$t('usage.totalRequests')}</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{formatNumber(stats.stats?.total_tokens || 0)}</div>
                <div class="stat-label">{$t('usage.totalTokens')}</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{formatCost(overallCost)}</div>
                <div class="stat-label">{$t('usage.estimatedCost')}</div>
            </div>
        </div>
        
        <div class="breakdown-section">
            <h4>{$t('usage.breakdown')}</h4>
            <div class="breakdown-table">
                <div class="breakdown-header">
                    <div class="expand-col"></div>
                    <div>{$t(`usage.${view}Info`)}</div>
                    <div>{$t('usage.totalUsage')}</div>
                    <div>{$t('usage.totalCost')}</div>
                </div>
                
                {#if Object.keys(detailedData).length > 0}
                    {#each Object.entries(detailedData) as [key, data] (key)}
                        <div class="main-row">
                            <button class="expand-btn" on:click={() => toggleExpand(key)}>
                                {expandedItems.has(key) ? '▼' : '▶'}
                            </button>
                            <div class="item-name" title={key}>{getDisplayName(key, view)}</div>
                            <div class="usage-stats">
                                <span>{formatNumber(data.total.requests)} {$t('usage.requestsShort')}</span>
                                <span>↓{formatNumber(data.total.input_tokens)}</span>
                                <span>↑{formatNumber(data.total.output_tokens)}</span>
                            </div>
                            <div class="cost">{formatCost(calculateItemTotalCost(data.models))}</div>
                        </div>
                        
                        {#if expandedItems.has(key)}
                            <div class="detail-rows">
                                {#if Object.keys(data.models || {}).length > 0}
                                    {#each Object.entries(data.models || {}) as [modelKey, modelData] (modelKey)}
                                        <div class="detail-row">
                                            <div></div>
                                            <div class="model-name">└─ {modelKey}</div>
                                            <div class="usage-stats">
                                                <span>{formatNumber(modelData.requests)} {$t('usage.requestsShort')}</span>
                                                <span>↓{formatNumber(modelData.input_tokens)}</span>
                                                <span>↑{formatNumber(modelData.output_tokens)}</span>
                                            </div>
                                            <div class="cost">{formatCost(calculateCost(modelKey, modelData.input_tokens, modelData.output_tokens))}</div>
                                        </div>
                                    {/each}
                                {:else}
                                     <div class="detail-row no-data">No model breakdown available.</div>
                                {/if}
                            </div>
                        {/if}
                    {/each}
                {:else}
                    <div class="no-data">No detailed data found for this view.</div>
                {/if}
            </div>
        </div>
    {/if}
</div>

{#if showPricingModal}
<div class="modal-overlay" on:click={handleOverlayClick} on:keydown={(e) => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { showPricingModal = false; } }} role="button" tabindex="0">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="pricing-modal-title">
        <h3 id="pricing-modal-title">{$t('usage.pricingConfig')}</h3>
        <p class="modal-info">{$t('usage.pricingInfo')}</p>
        <div class="pricing-table">
            <div class="pricing-header">
                <div>{$t('usage.provider')}</div>
                <div>{$t('usage.modelName')}</div>
                <div>{$t('usage.inputPrice')}</div>
                <div>{$t('usage.outputPrice')}</div>
                <div></div>
            </div>
            {#each editingPricing as item (item.id)}
                <div class="pricing-row">
                    <select bind:value={item.provider}>
                        {#each providerOptions as opt}<option value={opt.value}>{opt.label}</option>{/each}
                    </select>
                    <input type="text" bind:value={item.model} placeholder={$t('usage.modelPlaceholder')}>
                    <input type="number" step="0.01" bind:value={item.input_price_per_1m} placeholder="0.00">
                    <input type="number" step="0.01" bind:value={item.output_price_per_1m} placeholder="0.00">
                    <button class="remove-row-btn" on:click={() => removePricingRow(item.id)} title="Remove">×</button>
                </div>
            {/each}
        </div>
        <button class="add-row-btn" on:click={addPricingRow}>{$t('usage.addModel')}</button>
        <div class="modal-actions">
            <button on:click={savePricing}>{$t('usage.save')}</button>
            <button class="secondary" on:click={() => showPricingModal = false}>{$t('usage.cancel')}</button>
        </div>
    </div>
</div>
{/if}

<style>
    .usage-dashboard {
        display: flex;
        flex-direction: column;
        height: 100%;
        background-color: var(--card-bg);
        border-radius: 12px;
        padding: 1rem;
        box-shadow: var(--shadow);
    }
    .dashboard-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.75rem;
    }
    .dashboard-header h3 {
        margin: 0;
        font-size: 1.1rem;
    }
    .controls {
        display: flex;
        gap: 0.5rem;
        align-items: center;
        flex-wrap: wrap;
    }
    .period-control {
        display: inline-flex;
        align-items: center;
        gap: .45rem;
        color: var(--text-light);
        font-size: .9rem;
    }
    .period-control span {
        white-space: nowrap;
    }
    .period-control select {
        min-width: 116px;
        padding: .38rem .62rem;
        font-size: .95rem;
        background: var(--panel-soft-bg-2);
        color: var(--text-color);
        border: 1px solid var(--panel-muted-border);
    }
    .view-tabs {
        display: flex;
        gap: 0.25rem;
        margin-bottom: 1rem;
        background: var(--panel-muted-bg);
        padding: 0.25rem;
        border-radius: 6px;
        border: 1px solid var(--panel-muted-border);
    }
    .view-tabs button {
        background: transparent;
        border: none;
        padding: 0.4rem 0.8rem;
        font-size: 0.85rem;
        color: var(--text-light);
        cursor: pointer;
        border-radius: 4px;
        transition: all 0.2s;
        flex: 1;
    }
    .view-tabs button.active {
        background: var(--primary-color);
        color: white;
        font-weight: 600;
    }
    .icon-btn {
        background: none;
        border: 1px solid var(--border-color);
        padding: 0.3rem 0.5rem;
        cursor: pointer;
        border-radius: 4px;
        font-size: 1rem;
        line-height: 1;
        color: var(--text-color);
    }
    .icon-btn:hover {
        background-color: var(--panel-muted-bg);
    }
    .icon-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    .icon-btn:disabled {
        animation: spin 1.5s linear infinite;
    }
    .stats-overview {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.75rem;
        margin-bottom: 1rem;
    }
    .stat-card {
        background: var(--panel-soft-bg);
        padding: 0.75rem;
        border-radius: 6px;
        text-align: center;
        border: 1px solid var(--border-color);
    }
    .stat-value {
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--primary-color);
    }
    .stat-label {
        font-size: 0.8rem;
        color: var(--text-light);
        margin-top: 0.25rem;
    }
    .breakdown-section {
        flex: 1;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }
    .breakdown-section h4 {
        margin: 0 0 0.5rem 0;
        font-size: 0.9rem;
        color: var(--text-color);
    }
    .breakdown-table {
        flex: 1;
        overflow-y: auto;
        font-size: 0.8rem;
        border-top: 1px solid var(--border-color);
    }
    .breakdown-header {
        display: grid;
        grid-template-columns: 30px 2fr 1.5fr 0.8fr;
        gap: 0.5rem;
        padding: 0.5rem;
        font-weight: 600;
        background: var(--panel-soft-bg);
        border-bottom: 1px solid var(--border-color);
        position: sticky;
        top: 0;
        z-index: 1;
    }
    .main-row {
        display: grid;
        grid-template-columns: 30px 2fr 1.5fr 0.8fr;
        gap: 0.5rem;
        padding: 0.5rem;
        border-bottom: 1px solid var(--border-color);
        align-items: center;
    }
    .main-row:hover {
        background-color: var(--panel-hover-bg);
    }
    .detail-rows {
        background: var(--panel-soft-bg-2);
    }
    .detail-row {
        display: grid;
        grid-template-columns: 30px 2fr 1.5fr 0.8fr;
        gap: 0.5rem;
        padding: 0.4rem 0.5rem;
        border-bottom: 1px solid var(--border-color);
        font-size: 0.75rem;
    }
    .expand-btn {
        background: none;
        border: none;
        cursor: pointer;
        padding: 0;
        font-size: 0.8rem;
        color: var(--text-light);
        width: 20px;
    }
    .expand-col { width: 30px; }
    .item-name {
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .model-name {
        padding-left: 1rem;
        color: var(--text-light);
    }
    .usage-stats {
        display: flex;
        gap: 1rem;
        font-size: 0.8rem;
        color: var(--text-light);
        flex-wrap: wrap;
    }
    .usage-stats span {
        white-space: nowrap;
    }
    .cost {
        font-weight: 600;
        color: var(--primary-color);
        text-align: right;
        font-family: monospace;
    }
    .loading, .no-data {
        text-align: center;
        padding: 2rem;
        color: var(--text-light);
    }
    .no-data {
        font-style: italic;
        grid-column: 1 / -1;
    }
    .modal-overlay {
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex; align-items: center; justify-content: center;
        z-index: 1000;
    }
    .modal {
        background: var(--card-bg); padding: 2rem; border-radius: 12px;
        max-width: 800px; width: 90%; max-height: 80vh;
        overflow-y: auto; box-shadow: 0 10px 25px rgba(0,0,0,0.1);
    }
    .modal-info {
        color: var(--text-light); font-size: 0.9rem; margin-bottom: 1.5rem;
    }
    .pricing-table { margin-bottom: 1rem; }
    .pricing-header {
        display: grid; grid-template-columns: 150px 1fr 120px 120px 40px;
        gap: 0.5rem; font-weight: 600; font-size: 0.9rem;
        padding-bottom: 0.5rem; border-bottom: 2px solid var(--border-color);
        margin-bottom: 0.5rem;
    }
    .pricing-row {
        display: grid; grid-template-columns: 150px 1fr 120px 120px 40px;
        gap: 0.5rem; margin-bottom: 0.5rem; align-items: center;
    }
    .pricing-row input, .pricing-row select {
        padding: 0.5rem; border: 1px solid var(--border-color); border-radius: 4px;
        width: 100%; font-size: 0.9rem;
    }
    .remove-row-btn {
        background: transparent; border: none; color: var(--text-light);
        font-size: 1.5rem; cursor: pointer; padding: 0;
        width: 30px; height: 30px; display: flex; align-items: center;
        justify-content: center; border-radius: 50%; transition: all 0.2s;
    }
    .remove-row-btn:hover {
        background-color: var(--error-bg); color: var(--error-text);
    }
    .add-row-btn {
        background-color: var(--info-bg); color: var(--info-text);
        border: none; padding: 0.5rem 1rem; margin-bottom: 1rem;
        border-radius: 6px; font-weight: 500;
    }
    .add-row-btn:hover { background-color: #d1ecfa; }
    .modal-actions {
        display: flex; gap: 1rem; justify-content: flex-end;
        margin-top: 1.5rem; border-top: 1px solid var(--border-color);
        padding-top: 1.5rem;
    }
    .modal-actions button {
        padding: 0.6rem 1.5rem;
    }
    .modal-actions button.secondary {
        background-color: transparent;
        border: 1px solid var(--border-color);
        color: var(--text-color);
    }
    .modal-actions button.secondary:hover {
        background-color: var(--panel-muted-bg);
    }
</style>
