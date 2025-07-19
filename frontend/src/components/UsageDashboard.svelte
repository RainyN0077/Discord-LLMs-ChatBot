<!-- frontend/src/components/UsageDashboard.svelte -->
<script>
    import { onMount, onDestroy } from 'svelte';
    import { t } from '../i18n.js';
    
    let period = 'today';
    let stats = null;
    let pricing = {};
    let isLoading = false;
    let refreshInterval;
    let showPricingModal = false;
    let editingPricing = [];
    
    const periodOptions = [
        { value: 'today', label: 'usage.periods.today' },
        { value: 'week', label: 'usage.periods.week' },
        { value: 'month', label: 'usage.periods.month' },
        { value: 'all', label: 'usage.periods.all' }
    ];
    
    const providerOptions = [
        { value: 'openai', label: 'OpenAI' },
        { value: 'google', label: 'Google' },
        { value: 'anthropic', label: 'Anthropic' },
        { value: 'openai-compatible', label: 'OpenAI Compatible' }
    ];
    
    async function fetchStats() {
        isLoading = true;
        try {
            const response = await fetch(`/api/usage/stats?period=${period}`);
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
            // 转换为数组格式便于编辑
            editingPricing = Object.entries(pricing).map(([key, value]) => ({
                ...value,
                id: key
            }));
        } catch (e) {
            console.error('Failed to fetch pricing:', e);
        }
    }
    
    async function savePricing() {
        // 转换回对象格式
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
            await fetch('/api/usage/pricing', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pricingObj)
            });
            pricing = pricingObj;
            showPricingModal = false;
            fetchPricing(); // 重新加载
        } catch (e) {
            console.error('Failed to save pricing:', e);
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
    
    function calculateCost(modelKey, inputTokens, outputTokens) {
        const price = pricing[modelKey];
        if (!price) return null;
        
        // 价格是每百万token
        const inputCost = (inputTokens / 1000000) * price.input_price_per_1m;
        const outputCost = (outputTokens / 1000000) * price.output_price_per_1m;
        return inputCost + outputCost;
    }
    
    function formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    }
    
    function formatCost(cost) {
        if (cost === null) return 'N/A';
        if (cost < 0.01) return `$${cost.toFixed(6)}`;
        return `$${cost.toFixed(4)}`;
    }
    
    onMount(() => {
        fetchStats();
        fetchPricing();
        refreshInterval = setInterval(() => {
            fetchStats();
        }, 30000); // 每30秒刷新
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
                <div class="stat-value">
                    {formatCost(
                        Object.entries(stats.stats.by_model || {}).reduce((total, [model, data]) => {
                            const cost = calculateCost(model, data.input_tokens, data.output_tokens);
                            return total + (cost || 0);
                        }, 0)
                    )}
                </div>
                <div class="stat-label">{$t('usage.estimatedCost')}</div>
            </div>
        </div>
        
        <div class="model-breakdown">
            <h4>{$t('usage.breakdown')}</h4>
            <div class="breakdown-table">
                {#each Object.entries(stats.stats.by_model || {}) as [model, data]}
                    <div class="breakdown-row">
                        <div class="model-name">{model}</div>
                        <div class="model-stats">
                            <span class="requests">{data.requests} {$t('usage.requests')}</span>
                            <span class="tokens">↓{formatNumber(data.input_tokens)} ↑{formatNumber(data.output_tokens)}</span>
                            <span class="cost">{formatCost(calculateCost(model, data.input_tokens, data.output_tokens))}</span>
                        </div>
                    </div>
                {/each}
            </div>
        </div>
    {/if}
</div>

{#if showPricingModal}
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
        margin-bottom: 1rem;
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
        margin-bottom: 1.5rem;
    }
    
    .stat-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    
    .stat-value {
        font-size: 1.5rem;
        font-weight: bold;
        color: var(--primary-color);
    }
    
    .stat-label {
        font-size: 0.85rem;
        color: var(--text-light);
        margin-top: 0.25rem;
    }
    
    .model-breakdown {
        flex: 1;
        overflow-y: auto;
    }
    
    .model-breakdown h4 {
        margin: 0 0 0.75rem 0;
        font-size: 0.95rem;
    }
    
    .breakdown-row {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem;
        border-bottom: 1px solid var(--border-color);
        font-size: 0.85rem;
    }
    
    .model-name {
        font-weight: 500;
    }
    
    .model-stats {
        display: flex;
        gap: 1rem;
        color: var(--text-light);
    }
    
    .cost {
        font-weight: 600;
        color: var(--primary-color);
    }
    
    .loading {
        text-align: center;
        padding: 2rem;
        color: var(--text-light);
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
