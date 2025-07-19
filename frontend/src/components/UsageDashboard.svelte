<!-- frontend/src/components/UsageDashboard.svelte -->
<script>
    import { onMount, onDestroy, tick } from 'svelte';
    import { t } from '../i18n.js';
    
    let period = 'today';
    let view = 'user';
    let stats = null;
    let pricing = {};
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
        { value: 'anthropic', label: 'Anthropic' },
        { value: 'openai-compatible', label: 'OpenAI Compatible' }
    ];
    
    async function fetchStats() {
        isLoading = true;
        expandedItems.clear();
        try {
            const response = await fetch(`/api/usage/stats?period=${period}&view=${view}`);
            stats = await response.json();
        } catch (e) {
            console.error('Failed to fetch usage stats:', e);
        } finally {
            isLoading = false;
        }
    }
    
    async function fetchPricing() {
        try {
            const response = await fetch('/api/usage/pricing');
            const data = await response.json();
            pricing = data.pricing || {};
            
            editingPricing = Object.entries(pricing).map(([key, value]) => {
                if (typeof value === 'object' && value !== null) {
                    return {
                        id: key,
                        provider: value.provider || '',
                        model: value.model || '',
                        input_price_per_1m: value.input_price_per_1m || 0,
                        output_price_per_1m: value.output_price_per_1m || 0
                    };
                } else {
                    return {
                        id: key,
                        provider: 'openai',
                        model: '',
                        input_price_per_1m: 0,
                        output_price_per_1m: 0
                    };
                }
            });
        } catch (e) {
            console.error('Failed to fetch pricing:', e);
            pricing = {};
            editingPricing = [];
        }
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
            const response = await fetch('/api/usage/pricing', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pricingObj)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 强制更新 pricing 对象
            pricing = { ...pricingObj };
            showPricingModal = false;
            
            // 等待 DOM 更新
            await tick();
            
            // 重新获取统计数据以触发重新计算
            await fetchStats();
            
        } catch (e) {
            console.error('Failed to save pricing:', e);
            alert('保存价格配置失败：' + e.message);
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
    
    function removePricingRow(index) {
        editingPricing = editingPricing.filter((_, i) => i !== index);
    }
    
    function toggleExpand(key) {
        if (expandedItems.has(key)) {
            expandedItems.delete(key);
        } else {
            expandedItems.add(key);
        }
        expandedItems = expandedItems;
    }
    
    function calculateCost(modelKey, inputTokens, outputTokens) {
        const price = pricing[modelKey];
        if (!price || typeof price !== 'object') {
            return null;
        }
        
        const inputPrice = parseFloat(price.input_price_per_1m) || 0;
        const outputPrice = parseFloat(price.output_price_per_1m) || 0;
        
        if (inputPrice === 0 && outputPrice === 0) {
            return null;
        }
        
        const inputCost = (inputTokens / 1000000) * inputPrice;
        const outputCost = (outputTokens / 1000000) * outputPrice;
        return inputCost + outputCost;
    }
    
    function calculateTotalCost(models) {
        if (!models || typeof models !== 'object') {
            return 0;
        }
        
        let total = 0;
        Object.entries(models).forEach(([modelKey, data]) => {
            const cost = calculateCost(modelKey, data.input_tokens, data.output_tokens);
            if (cost !== null && !isNaN(cost)) {
                total += cost;
            }
        });
        return total;
    }
    
    function formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    }
    
    function formatCost(cost) {
        if (cost === null) return 'N/A';
        if (cost < 0.01) return `$${cost.toFixed(6)}`;
        return `$${cost.toFixed(4)}`;
    }
    
    function getDisplayName(key, type) {
        if (!stats || !stats.metadata) return key;
        
        const metadata = stats.metadata[type + 's'];
        if (!metadata || !metadata[key]) return key;
        
        const info = metadata[key];
        switch(type) {
            case 'user':
                return `${info.display_name || info.name} | ${info.name} | ${key}`;
            case 'role':
                return `${info.name} | ${key}`;
            case 'channel':
                return `${info.name} | ${key}`;
            case 'guild':
                return `${info.name} | ${key}`;
            default:
                return key;
        }
    }
    
    function getDetailedData() {
        if (!stats || !stats.stats) {
            return [];
        }
        const detailKey = `detailed_by_${view}`;
        const result = Object.entries(stats.stats[detailKey] || {});
        return result;
    }
    
    // 计算总费用的函数，确保响应式
    function calculateOverallCost() {
        return getDetailedData().reduce((total, [_, data]) => {
            return total + calculateTotalCost(data.models);
        }, 0);
    }
    
    onMount(() => {
        fetchStats();
        fetchPricing();
        refreshInterval = setInterval(() => {
            fetchStats();
        }, 30000);
    });
    
    onDestroy(() => {
        if (refreshInterval) clearInterval(refreshInterval);
    });
</script>

<div class="usage-dashboard">
    <div class="dashboard-header">
        <h3>{$t('usage.title')}</h3>
        <div class="controls">
            <select bind:value={period} on:change={fetchStats}>
                {#each periodOptions as option}
                    <option value={option.value}>{$t(option.label)}</option>
                {/each}
            </select>
            <button class="icon-btn" on:click={() => showPricingModal = true} title={$t('usage.configurePricing')}>
                💰
            </button>
            <button class="icon-btn" on:click={fetchStats} disabled={isLoading} title={$t('usage.refresh')}>
                🔄
            </button>
        </div>
    </div>
    
    <!-- 视图切换按钮 -->
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
                <div class="stat-value">{formatNumber(stats.stats.requests)}</div>
                <div class="stat-label">{$t('usage.totalRequests')}</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{formatNumber(stats.stats.total_tokens)}</div>
                <div class="stat-label">{$t('usage.totalTokens')}</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{formatCost(calculateOverallCost())}</div>
                <div class="stat-label">{$t('usage.estimatedCost')}</div>
            </div>
        </div>
        
        <div class="breakdown-section">
            <h4>{$t('usage.breakdown')}</h4>
            
            <div class="breakdown-table">
                <div class="breakdown-header">
                    <div class="expand-col"></div>
                    <div>{$t('usage.' + view + 'Info')}</div>
                    <div>{$t('usage.totalUsage')}</div>
                    <div>{$t('usage.totalCost')}</div>
                </div>
                
                {#if stats && stats.stats}
                    {@const detailKey = `detailed_by_${view}`}
                    {@const detailData = stats.stats[detailKey] || {}}
                    {#if Object.keys(detailData).length > 0}
                        {#each Object.entries(detailData) as [key, data] (key)}
                            <div class="main-row">
                                <button class="expand-btn" on:click={() => toggleExpand(key)}>
                                    {expandedItems.has(key) ? '▼' : '▶'}
                                </button>
                                <div class="item-name">{getDisplayName(key, view)}</div>
                                <div class="usage-stats">
                                    <span>{formatNumber(data.total.requests)} {$t('usage.requestsShort')}</span>
                                    <span>↓{formatNumber(data.total.input_tokens)}</span>
                                    <span>↑{formatNumber(data.total.output_tokens)}</span>
                                </div>
                                <div class="cost">{formatCost(calculateTotalCost(data.models))}</div>
                            </div>
                            
                            {#if expandedItems.has(key)}
                                <div class="detail-rows">
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
                                </div>
                            {/if}
                        {/each}
                    {:else}
                        <div class="no-data">没有找到详细数据</div>
                    {/if}
                {:else}
                    <div class="no-data">正在加载数据...</div>
                {/if}
            </div>
        </div>
    {/if}
</div>

{#if showPricingModal}
<!-- 价格配置模态框 -->
<div class="modal-overlay" on:click={() => showPricingModal = false}>
    <div class="modal" on:click|stopPropagation>
        <h3>{$t('usage.pricingConfig')}</h3>
        <p class="modal-info">{$t('usage.pricingInfo')}</p>
        
        <div class="pricing-table">
            <div class="pricing-header">
                <div>{$t('usage.provider')}</div>
                <div>{$t('usage.modelName')}</div>
                <div>{$t('usage.inputPrice')}</div>
                <div>{$t('usage.outputPrice')}</div>
                <div></div>
            </div>
            
            {#each editingPricing as item, i}
                <div class="pricing-row">
                    <select bind:value={item.provider}>
                        {#each providerOptions as opt}
                            <option value={opt.value}>{opt.label}</option>
                        {/each}
                    </select>
                    <input type="text" 
                        bind:value={item.model}
                        placeholder={$t('usage.modelPlaceholder')}>
                    <input type="number" step="0.01" 
                        bind:value={item.input_price_per_1m}
                        placeholder="0.00">
                    <input type="number" step="0.01"
                        bind:value={item.output_price_per_1m}
                        placeholder="0.00">
                    <button class="remove-row-btn" on:click={() => removePricingRow(i)}>×</button>
                </div>
            {/each}
        </div>
        
        <button class="add-row-btn" on:click={addPricingRow}>{$t('usage.addModel')}</button>
        
        <div class="modal-actions">
            <button on:click={savePricing}>{$t('usage.save')}</button>
            <button on:click={() => showPricingModal = false}>{$t('usage.cancel')}</button>
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
    }
    
    .view-tabs {
        display: flex;
        gap: 0.25rem;
        margin-bottom: 1rem;
        background: #f0f2f5;
        padding: 0.25rem;
        border-radius: 6px;
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
    }
    
    .view-tabs button.active {
        background: var(--primary-color);
        color: white;
    }
    
    .icon-btn {
        background: none;
        border: 1px solid var(--border-color);
        padding: 0.3rem 0.5rem;
        cursor: pointer;
        border-radius: 4px;
        font-size: 1rem;
    }
    
    .icon-btn:hover {
        background-color: var(--border-color);
    }
    
    .stats-overview {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.75rem;
        margin-bottom: 1rem;
    }
    
    .stat-card {
        background: #f8f9fa;
        padding: 0.75rem;
        border-radius: 6px;
        text-align: center;
    }
    
    .stat-value {
        font-size: 1.25rem;
        font-weight: bold;
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
    }
    
    .breakdown-table {
        flex: 1;
        overflow-y: auto;
        font-size: 0.8rem;
    }
    
    .breakdown-header {
        display: grid;
        grid-template-columns: 30px 2fr 1.5fr 0.8fr;
        gap: 0.5rem;
        padding: 0.5rem;
        font-weight: 600;
        background: #f8f9fa;
        border-radius: 4px;
        margin-bottom: 0.25rem;
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
    
    .detail-rows {
        background: #f8f9fa;
    }
    
    .detail-row {
        display: grid;
        grid-template-columns: 30px 2fr 1.5fr 0.8fr;
        gap: 0.5rem;
        padding: 0.3rem 0.5rem;
        border-bottom: 1px solid #e9ecef;
        font-size: 0.75rem;
        color: var(--text-light);
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
    
    .expand-col {
        width: 30px;
    }
    
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
    }
    
    .usage-stats span {
        white-space: nowrap;
    }
    
    .cost {
        font-weight: 600;
        color: var(--primary-color);
        text-align: right;
    }
    
    .loading {
        text-align: center;
        padding: 2rem;
        color: var(--text-light);
    }
    
    .no-data {
        padding: 2rem;
        text-align: center;
        color: var(--text-light);
        font-style: italic;
        grid-column: 1 / -1;
    }
    
    /* Modal styles */
    .modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }
    
    .modal {
        background: var(--card-bg);
        padding: 2rem;
        border-radius: 12px;
        max-width: 800px;
        width: 90%;
        max-height: 80vh;
        overflow-y: auto;
    }
    
    .modal-info {
        color: var(--text-light);
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
    }
    
    .pricing-table {
        margin-bottom: 1rem;
    }
    
    .pricing-header {
        display: grid;
        grid-template-columns: 150px 1fr 120px 120px 40px;
        gap: 0.5rem;
        font-weight: 600;
        font-size: 0.9rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--border-color);
        margin-bottom: 0.5rem;
    }
    
    .pricing-row {
        display: grid;
        grid-template-columns: 150px 1fr 120px 120px 40px;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
        align-items: center;
    }
    
    .pricing-row input,
    .pricing-row select {
        padding: 0.5rem;
        border: 1px solid var(--border-color);
        border-radius: 4px;
        width: 100%;
    }
    
    .remove-row-btn {
        background: transparent;
        border: none;
        color: var(--text-light);
        font-size: 1.5rem;
        cursor: pointer;
        padding: 0;
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 4px;
    }
    
    .remove-row-btn:hover {
        background-color: var(--error-bg);
        color: var(--error-text);
    }
    
    .add-row-btn {
        background-color: var(--info-bg);
        color: var(--info-text);
        border: none;
        padding: 0.5rem 1rem;
        margin-bottom: 1rem;
    }
    
    .add-row-btn:hover {
        background-color: #d1ecfa;
    }
    
    .modal-actions {
        display: flex;
        gap: 1rem;
        justify-content: flex-end;
        margin-top: 1.5rem;
    }
</style>
