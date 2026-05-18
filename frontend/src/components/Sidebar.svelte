<!-- src/components/Sidebar.svelte -->
<script>
    import { onMount, createEventDispatcher } from 'svelte';
    import { t, get as t_get } from '../i18n.js';
    import {
        fetchBots, createBot, deleteBot, renameBot,
        startBot, stopBot, restartBot,
    } from '../lib/api.js';

    export let selectedBotId = null;

    const dispatch = createEventDispatcher();

    let bots = [];
    let loading = true;
    let error = '';
    let showCreateForm = false;
    let collapsed = false;
    let operatingBotIds = [];
    let createData = {
        bot_id: '',
        bot_name: '',
        platform: 'discord',
        enabled: true,
        discord_token: '',
        llm_provider: 'openai',
        api_key: '',
        model_name: 'gpt-4o',
    };
    let createError = '';
    let creating = false;
    let editingBotId = null;
    let editValue = '';
    let renameError = '';

    async function handleRename(botId, e) {
        e.stopPropagation();
        const newId = editValue.trim();
        if (!newId || newId === botId) {
            editingBotId = null;
            return;
        }
        if (!newId.match(/^[a-z0-9_-]+$/)) {
            renameError = 'Only lowercase letters, digits, hyphens, underscores.';
            return;
        }
        renameError = '';
        operatingBotIds = [...operatingBotIds, botId];
        try {
            const result = await renameBot(botId, newId);
            editingBotId = null;
            const idx = bots.findIndex(b => b.bot_id === botId);
            if (idx >= 0) {
                bots[idx] = { ...bots[idx], bot_id: result.bot_id };
                bots = [...bots];
                const nextId = result.bot_id;
                if (selectedBotId === botId) {
                    selectedBotId = nextId;
                    dispatch('select', selectedBotId);
                }
            }
        } catch (err) {
            renameError = String(err.message || err);
        } finally {
            operatingBotIds = operatingBotIds.filter(id => id !== botId);
        }
    }

    function startEdit(botId, e) {
        e.stopPropagation();
        editingBotId = botId;
        editValue = botId;
        renameError = '';
        setTimeout(() => {
            const input = document.querySelector(`.card-title-input[data-bot="${botId}"]`);
            if (input) { input.focus(); input.select(); }
        }, 50);
    }

    function cancelEdit(e) {
        e.stopPropagation();
        editingBotId = null;
        renameError = '';
    }

    async function loadBots() {
        loading = true;
        error = '';
        try {
            bots = await fetchBots() || [];
            if (bots.length > 0 && !selectedBotId) {
                selectedBotId = bots[0].bot_id;
                dispatch('select', selectedBotId);
            }
        } catch (e) {
            error = String(e.message || e);
        } finally {
            loading = false;
        }
    }

    function selectBot(botId) {
        selectedBotId = botId;
        dispatch('select', botId);
    }

    async function handleStart(botId, e) {
        e.stopPropagation();
        operatingBotIds = [...operatingBotIds, botId];
        try {
            const result = await startBot(botId);
            const idx = bots.findIndex(b => b.bot_id === botId);
            if (idx >= 0) {
                bots[idx] = { ...bots[idx], status: result.status || 'starting' };
                bots = [...bots];
            }
        } catch (err) {
            error = String(err.message || err);
            console.error('Operation failed:', err);
        } finally {
            operatingBotIds = operatingBotIds.filter(id => id !== botId);
        }
    }

    async function handleStop(botId, e) {
        e.stopPropagation();
        operatingBotIds = [...operatingBotIds, botId];
        try {
            const result = await stopBot(botId);
            const idx = bots.findIndex(b => b.bot_id === botId);
            if (idx >= 0) {
                bots[idx] = { ...bots[idx], status: result.status || 'stopped' };
                bots = [...bots];
            }
        } catch (err) {
            error = String(err.message || err);
            console.error('Operation failed:', err);
        } finally {
            operatingBotIds = operatingBotIds.filter(id => id !== botId);
        }
    }

    async function handleRestart(botId, e) {
        e.stopPropagation();
        operatingBotIds = [...operatingBotIds, botId];
        try {
            const result = await restartBot(botId);
            const idx = bots.findIndex(b => b.bot_id === botId);
            if (idx >= 0) {
                bots[idx] = { ...bots[idx], status: result.status || 'running' };
                bots = [...bots];
            }
        } catch (err) {
            error = String(err.message || err);
            console.error('Operation failed:', err);
        } finally {
            operatingBotIds = operatingBotIds.filter(id => id !== botId);
        }
    }

    async function handleDelete(botId, e) {
        e.stopPropagation();
        if (!confirm(t_get('botManager.deleteConfirm', { botId }))) return;
        operatingBotIds = [...operatingBotIds, botId];
        try {
            await deleteBot(botId);
            bots = bots.filter(b => b.bot_id !== botId);
            if (selectedBotId === botId) {
                selectedBotId = bots.length > 0 ? bots[0]?.bot_id || null : null;
                dispatch('select', selectedBotId);
            }
        } catch (err) {
            error = String(err.message || err);
            console.error('Operation failed:', err);
        } finally {
            operatingBotIds = operatingBotIds.filter(id => id !== botId);
        }
    }

    async function handleCreate() {
        createError = '';
        creating = true;
        try {
            const payload = { ...createData };
            if (!payload.bot_id || !payload.bot_id.match(/^[a-z0-9_-]+$/)) {
                createError = 'Bot ID must contain only lowercase letters, numbers, hyphens, and underscores.';
                creating = false;
                return;
            }
            if (!payload.bot_name) payload.bot_name = payload.bot_id;
            await createBot(payload);
            showCreateForm = false;
            createData = { bot_id: '', bot_name: '', platform: 'discord', enabled: true, discord_token: '', llm_provider: 'openai', api_key: '', model_name: 'gpt-4o' };
            await loadBots();
        } catch (e) {
            createError = String(e.message || e);
        } finally {
            creating = false;
        }
    }

    function statusColor(status) {
        if (status === 'running') return 'var(--success-text, #5dd9b8)';
        if (status === 'starting') return 'var(--info-text, #88d1ff)';
        if (status === 'error') return 'var(--error-text, #ff8bb4)';
        return 'var(--text-light, #888)';
    }

    function statusLabel(status) {
        if (status === 'running') return '●';
        if (status === 'starting') return '◐';
        if (status === 'error') return '✕';
        return '○';
    }

    onMount(loadBots);
</script>

<aside class="sidebar" class:collapsed>
    <div class="sidebar-header">
        {#if !collapsed}
            <span class="sidebar-title">{$t('botManager.title')}</span>
        {/if}
        <button class="collapse-btn" on:click={() => collapsed = !collapsed} title={collapsed ? $t('botManager.expand') : $t('botManager.collapse')}>
            {collapsed ? '▶' : '◀'}
        </button>
    </div>

    {#if !collapsed}
        <div class="sidebar-content">
            {#if loading}
                <div class="sidebar-status">{$t('botManager.loading')}</div>
            {:else if error}
                <div class="sidebar-status error">{error}</div>
            {:else if bots.length === 0}
                <div class="sidebar-status">{$t('botManager.noBots')}</div>
            {:else}
                <div class="bot-list">
                    {#each bots as bot (bot.bot_id)}
                        <!-- svelte-ignore a11y-no-static-element-interactions -->
                        <div
                            class="bot-card"
                            class:active={selectedBotId === bot.bot_id}
                            class:operating={operatingBotIds.includes(bot.bot_id)}
                            on:click={() => selectBot(bot.bot_id)}
                            on:keypress={(e) => e.key === 'Enter' && selectBot(bot.bot_id)}
                            role="button"
                            tabindex="0"
                        >
                            {#if operatingBotIds.includes(bot.bot_id)}
                                <div class="card-progress-bar"></div>
                            {/if}
                            <div class="card-top">
                                <span class="status-dot" class:running={bot.status === 'running'} style="color: {statusColor(bot.status)}">{statusLabel(bot.status)}</span>
                                {#if editingBotId === bot.bot_id}
                                    <div class="card-title-edit" role="presentation" on:click|stopPropagation on:keypress|stopPropagation>
                                        <input
                                            class="card-title-input"
                                            data-bot={bot.bot_id}
                                            type="text"
                                            bind:value={editValue}
                                            on:keypress={(e) => e.key === 'Enter' && handleRename(bot.bot_id, e)}
                                            on:blur={() => editingBotId = null}
                                            pattern="^[a-z0-9_-]+$"
                                        />
                                        <button class="mini-btn confirm" on:click={(e) => handleRename(bot.bot_id, e)} title="Save">✓</button>
                                        <button class="mini-btn cancel-edit" on:click={cancelEdit} title="Cancel">×</button>
                                        {#if renameError}
                                            <span class="rename-error">{renameError}</span>
                                        {/if}
                                    </div>
                                {:else}
                                    <span class="card-title" on:dblclick={(e) => startEdit(bot.bot_id, e)} title="Double-click to rename">{bot.bot_id}</span>
                                {/if}
                            </div>
                            <div class="card-info-primary">
                                <span class="bot-name-text">{bot.bot_name || bot.bot_id}</span>
                                <span class="platform-badge" class:discord={bot.platform === 'discord' || !bot.platform} class:qq={bot.platform === 'qq'}>{bot.platform || 'discord'}</span>
                                {#if bot.enabled === false}
                                    <span class="disabled-badge">DISABLED</span>
                                {/if}
                            </div>
                            <div class="card-info-secondary">
                                {#if bot.bot_nickname}<span>{bot.bot_nickname}</span>{/if}
                                {#if bot.model_name}<span class="dot-sep">·</span><span>{bot.model_name}</span>{/if}
                                {#if bot.llm_provider}<span class="dot-sep">·</span><span>{bot.llm_provider}</span>{/if}
                            </div>
                            {#if bot.trigger_keywords?.length}
                                <div class="card-tags">
                                    {#each bot.trigger_keywords.slice(0, 4) as kw}
                                        <span class="keyword-tag">{kw}</span>
                                    {/each}
                                    {#if bot.trigger_keywords.length > 4}
                                        <span class="keyword-tag more">+{bot.trigger_keywords.length - 4}</span>
                                    {/if}
                                </div>
                            {/if}
                            <div class="card-actions" role="presentation" on:click|stopPropagation on:keypress|stopPropagation>
                                {#if bot.status !== 'running'}
                                    <button class="mini-btn start" on:click={(e) => handleStart(bot.bot_id, e)} title={$t('botManager.start')}>
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                                        <span>{$t('actionBtn.start')}</span>
                                    </button>
                                {:else}
                                    <button class="mini-btn stop" on:click={(e) => handleStop(bot.bot_id, e)} title={$t('botManager.stop')}>
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
                                        <span>{$t('actionBtn.stop')}</span>
                                    </button>
                                    <button class="mini-btn restart" on:click={(e) => handleRestart(bot.bot_id, e)} title={$t('botManager.restart')}>
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
                                        <span>{$t('actionBtn.restart')}</span>
                                    </button>
                                {/if}
                                <button class="mini-btn delete" on:click={(e) => handleDelete(bot.bot_id, e)} title={$t('botManager.delete')}>
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                                    <span>{$t('actionBtn.delete')}</span>
                                </button>
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}

            <div class="sidebar-footer">
                {#if !showCreateForm}
                    <button class="create-btn" on:click={() => showCreateForm = true}>{$t('botManager.newBot')}</button>
                {:else}
                    <div class="create-form">
                        <h4>{$t('botManager.createBot')}</h4>
                        {#if createError}
                            <div class="create-error">{createError}</div>
                        {/if}
                        <input type="text" bind:value={createData.bot_id} placeholder="bot-id (a-z, 0-9, -, _)" />
                        <input type="text" bind:value={createData.bot_name} placeholder="Bot name" />
                        <select bind:value={createData.platform}>
                            <option value="discord">Discord</option>
                            <option value="qq">QQ</option>
                        </select>
                        <input type="password" bind:value={createData.discord_token} placeholder="Discord token" />
                        <select bind:value={createData.llm_provider}>
                            <option value="openai">OpenAI</option>
                            <option value="anthropic">Anthropic</option>
                            <option value="google">Google (Gemini)</option>
                            <option value="xai">xAI (Grok)</option>
                            <option value="deepseek">DeepSeek</option>
                            <option value="siliconflow">SiliconFlow</option>
                            <option value="volcengine">Volcano Ark</option>
                            <option value="dashscope">DashScope</option>
                            <option value="moonshot">Moonshot</option>
                            <option value="zhipu">Zhipu GLM</option>
                            <option value="stepfun">StepFun</option>
                        </select>
                        <input type="password" bind:value={createData.api_key} placeholder="LLM API key" />
                        <input type="text" bind:value={createData.model_name} placeholder="Model name (gpt-4o)" />
                        <div class="create-actions">
                            <button class="create-submit" on:click={handleCreate} disabled={creating}>
                                {creating ? $t('botManager.creating') : $t('botManager.createBot')}
                            </button>
                            <button class="create-cancel" on:click={() => { showCreateForm = false; createError = ''; }}>
                                {$t('botManager.cancel')}
                            </button>
                        </div>
                    </div>
                {/if}
            </div>
        </div>
    {/if}
</aside>

<style>
    .sidebar {
        display: flex;
        flex-direction: column;
        background: var(--sidebar-bg);
        border-right: 1px solid var(--sidebar-border);
        width: 250px;
        min-width: 250px;
        height: 100%;
        transition: width .2s ease, min-width .2s ease;
        -webkit-backdrop-filter: blur(6px);
        backdrop-filter: blur(6px);
    }

    .sidebar.collapsed {
        width: 48px;
        min-width: 48px;
    }

    .sidebar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: .85rem .75rem;
        border-bottom: 1px solid var(--sidebar-border);
        flex-shrink: 0;
    }

    .sidebar-title {
        font-weight: 700;
        font-size: 1rem;
        color: var(--text-color);
    }

    .collapse-btn {
        background: transparent;
        border: none;
        color: var(--text-light);
        cursor: pointer;
        padding: .25rem;
        font-size: .85rem;
        box-shadow: none;
    }

    .collapse-btn:hover {
        color: var(--text-color);
    }

    .sidebar-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .bot-list {
        flex: 1;
        overflow-y: auto;
        padding: .5rem;
    }

    .bot-card {
        background: var(--card-bg);
        border-radius: var(--radius-md, 10px);
        box-shadow: var(--shadow-soft);
        margin-bottom: .5rem;
        padding: .55rem .65rem;
        cursor: pointer;
        transition: all .18s ease;
        position: relative;
        border: 2px solid transparent;
        outline: none;
        overflow: hidden;
    }

    .bot-card.operating {
        pointer-events: none;
        opacity: .85;
    }

    .card-progress-bar {
        position: absolute;
        top: 0;
        left: 0;
        height: 2px;
        width: 100%;
        background: linear-gradient(90deg, transparent 0%, var(--primary-color) 50%, transparent 100%);
        background-size: 200% 100%;
        animation: cardProgress 1.2s ease-in-out infinite;
        z-index: 1;
    }

    @keyframes cardProgress {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }

    .bot-card:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow);
        border-color: var(--border-color);
    }

    .bot-card.active {
        border-color: var(--primary-color);
        box-shadow: 0 0 14px rgba(31, 139, 214, .12);
    }

    .bot-card.active::before {
        content: '';
        position: absolute;
        left: -2px;
        top: 8px;
        bottom: 8px;
        width: 3px;
        background: var(--sidebar-active-indicator);
        border-radius: 0 3px 3px 0;
    }

    .card-top {
        display: flex;
        align-items: center;
        gap: .35rem;
        margin-bottom: .25rem;
    }

    .card-title {
        font-family: var(--font-mono, monospace);
        font-size: .78rem;
        font-weight: 700;
        color: var(--text-color);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        cursor: text;
    }

    .card-title:hover {
        color: var(--primary-color);
    }

    .card-title-edit {
        display: flex;
        align-items: center;
        gap: .15rem;
        flex: 1;
        min-width: 0;
    }

    .card-title-input {
        flex: 1;
        min-width: 0;
        font-family: var(--font-mono, monospace);
        font-size: .72rem;
        font-weight: 600;
        padding: .18rem .3rem;
        border: 1px solid var(--primary-color);
        border-radius: 4px;
        background: var(--surface-tint);
        color: var(--text-color);
        box-shadow: 0 0 6px rgba(31, 139, 214, .1);
    }

    .card-title-input:focus {
        outline: none;
    }

    .mini-btn.confirm {
        width: 22px;
        height: 22px;
    }

    .mini-btn.confirm:hover {
        color: var(--success-text);
        border-color: var(--success-text);
        background: var(--success-bg);
    }

    .mini-btn.cancel-edit {
        width: 22px;
        height: 22px;
    }

    .mini-btn.cancel-edit:hover {
        color: var(--error-text);
        border-color: var(--error-text);
        background: var(--error-bg);
    }

    .rename-error {
        font-size: .55rem;
        color: var(--error-text);
        position: absolute;
        bottom: -14px;
        left: 0;
        white-space: nowrap;
    }

    .card-info-primary {
        display: flex;
        align-items: center;
        gap: .35rem;
        font-size: .72rem;
        color: var(--text-light);
        margin-bottom: .18rem;
    }

    .bot-name-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-weight: 500;
    }

    .platform-badge {
        font-size: .6rem;
        text-transform: uppercase;
        padding: .04rem .28rem;
        border-radius: 3px;
        font-weight: 600;
        flex-shrink: 0;
    }

    .platform-badge.discord {
        background: rgba(88, 101, 242, .15);
        color: #8ea1e1;
    }

    .platform-badge.qq {
        background: rgba(18, 183, 106, .15);
        color: #5cd9a6;
    }

    .disabled-badge {
        font-size: .55rem;
        padding: .02rem .22rem;
        border-radius: 3px;
        background: rgba(255, 51, 102, .12);
        color: var(--error-text);
        font-weight: 600;
        flex-shrink: 0;
    }

    .card-info-secondary {
        font-size: .65rem;
        color: var(--text-muted, var(--text-light));
        display: flex;
        flex-wrap: wrap;
        gap: .15rem;
        margin-bottom: .25rem;
    }

    .dot-sep {
        opacity: .4;
    }

    .card-tags {
        display: flex;
        flex-wrap: wrap;
        gap: .2rem;
        margin-bottom: .35rem;
    }

    .keyword-tag {
        font-size: .58rem;
        background: var(--panel-muted-bg);
        color: var(--text-light);
        border-radius: 3px;
        padding: .03rem .3rem;
        line-height: 1.4;
    }

    .keyword-tag.more {
        opacity: .6;
    }

    .card-actions {
        display: none;
        gap: .12rem;
        justify-content: flex-end;
        padding-top: .3rem;
        border-top: 1px solid var(--border-color);
    }

    .bot-card:hover .card-actions {
        display: flex;
    }

    .bot-card.active .card-actions {
        display: flex;
    }

    :root[data-theme='neon'] .bot-card {
        border-width: 2px;
        border-style: solid;
        border-color: rgba(0, 229, 255, .12);
        box-shadow: 0 0 16px rgba(0, 229, 255, .04);
    }

    :root[data-theme='neon'] .bot-card:hover {
        border-color: rgba(0, 229, 255, .25);
        box-shadow: 0 0 20px rgba(0, 229, 255, .08);
    }

    :root[data-theme='neon'] .bot-card.active {
        border-color: #00e5ff;
        box-shadow: 0 0 18px rgba(0, 229, 255, .16);
        background: linear-gradient(135deg, rgba(0, 229, 255, .06), rgba(0, 145, 255, .03));
    }

    :root[data-theme='neon'] .bot-card.active::before {
        width: 4px;
        box-shadow: 0 0 10px rgba(0, 229, 255, .4);
    }

    :root[data-theme='neon'] .card-title {
        color: #c8d6ff;
    }

    :root[data-theme='neon'] .bot-card.active .card-title {
        color: #00e5ff;
    }

    :root[data-theme='neon'] .status-dot.running {
        animation: neonPulse 1.5s ease-in-out infinite;
    }

    @keyframes neonPulse {
        0%, 100% { opacity: 1; filter: drop-shadow(0 0 4px currentColor); }
        50% { opacity: .6; filter: drop-shadow(0 0 8px currentColor); }
    }

    .status-dot {
        font-size: .75rem;
        width: 16px;
        text-align: center;
    }

    .status-dot.running {
        animation: statusPulse 2s ease-in-out infinite;
    }

    @keyframes statusPulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    .mini-btn {
        height: 26px;
        padding: 0 .4rem;
        border-radius: 6px;
        border: 1px solid var(--border-color);
        background: var(--control-bg);
        color: var(--text-light);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: .3rem;
        box-shadow: none;
        transition: all .15s ease;
        font-size: .65rem;
        font-weight: 600;
        white-space: nowrap;
    }

    .mini-btn span {
        line-height: 1;
    }

    .mini-btn:hover {
        background: var(--control-hover-bg);
        transform: scale(1.05);
    }

    .mini-btn:active {
        transform: scale(.95);
    }

    .mini-btn.start:hover { color: var(--success-text); border-color: var(--success-text); background: var(--success-bg); }
    .mini-btn.stop:hover { color: var(--error-text); border-color: var(--error-text); background: var(--error-bg); }
    .mini-btn.restart:hover { color: var(--info-text); border-color: var(--info-text); background: var(--info-bg); }
    .mini-btn.delete:hover { color: var(--error-text); border-color: var(--error-text); background: var(--error-bg); }

    .sidebar-status {
        padding: 2rem 1rem;
        text-align: center;
        color: var(--text-light);
        font-size: .85rem;
    }

    .sidebar-status.error {
        color: var(--error-text);
    }

    .sidebar-footer {
        padding: .5rem;
        border-top: 1px solid var(--sidebar-border);
        flex-shrink: 0;
    }

    .create-btn {
        width: 100%;
        padding: .55rem;
        background: linear-gradient(135deg, var(--primary-color), #1b73b0);
        color: #fff;
        border: none;
        font-weight: 600;
        font-size: .88rem;
        border-radius: 8px;
    }

    .create-form {
        display: flex;
        flex-direction: column;
        gap: .4rem;
    }

    .create-form h4 {
        margin: 0 0 .2rem 0;
        font-size: .85rem;
        color: var(--text-color);
    }

    .create-form input,
    .create-form select {
        width: 100%;
        padding: .4rem .55rem;
        border: 1px solid var(--border-color);
        border-radius: 6px;
        background: var(--input-bg, var(--floating-bg));
        color: var(--text-color);
        font-size: .8rem;
        box-sizing: border-box;
    }

    .create-error {
        background: var(--error-bg);
        color: var(--error-text);
        padding: .35rem .5rem;
        border-radius: 4px;
        font-size: .75rem;
    }

    .create-actions {
        display: flex;
        gap: .35rem;
    }

    .create-submit {
        flex: 1;
        padding: .4rem;
        background: linear-gradient(135deg, var(--save-color), #1a9156);
        color: #fff;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        font-size: .8rem;
    }

    .create-submit:disabled {
        opacity: .6;
    }

    .create-cancel {
        padding: .4rem .6rem;
        background: var(--control-bg);
        color: var(--text-light);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        font-size: .8rem;
    }

    @media (max-width: 900px) {
        .sidebar {
            width: 200px;
            min-width: 200px;
        }

        .sidebar.collapsed {
            width: 42px;
            min-width: 42px;
        }

        .bot-card {
            padding: .45rem .5rem;
        }

        .sidebar-title {
            font-size: .9rem;
        }
    }

    @media (max-width: 600px) {
        .sidebar {
            position: fixed;
            left: 0;
            top: 40px;
            width: 260px;
            min-width: 260px;
            z-index: 90;
            box-shadow: var(--shadow);
        }

        .sidebar.collapsed {
            width: 0;
            min-width: 0;
            border-right: none;
        }

        .bot-card {
            padding: .4rem .5rem;
        }
    }
</style>
