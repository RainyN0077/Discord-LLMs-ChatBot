<!-- src/components/Sidebar.svelte -->
<script>
    import { onMount, createEventDispatcher } from 'svelte';
    import { t, get as t_get } from '../i18n.js';
    import {
        fetchBots, createBot, deleteBot,
        startBot, stopBot, restartBot,
    } from '../lib/api.js';

    export let selectedBotId = null;

    const dispatch = createEventDispatcher();

    let bots = [];
    let loading = true;
    let error = '';
    let showCreateForm = false;
    let collapsed = false;
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
        try { await startBot(botId); await loadBots(); } catch (err) {
            error = String(err.message || err);
            console.error('Operation failed:', err);
        }
    }

    async function handleStop(botId, e) {
        e.stopPropagation();
        try { await stopBot(botId); await loadBots(); } catch (err) {
            error = String(err.message || err);
            console.error('Operation failed:', err);
        }
    }

    async function handleRestart(botId, e) {
        e.stopPropagation();
        try { await restartBot(botId); await loadBots(); } catch (err) {
            error = String(err.message || err);
            console.error('Operation failed:', err);
        }
    }

    async function handleDelete(botId, e) {
        e.stopPropagation();
        if (!confirm(t_get('botManager.deleteConfirm', { botId }))) return;
        try {
            await deleteBot(botId);
            if (selectedBotId === botId) {
                selectedBotId = bots.length > 1 ? bots.find(b => b.bot_id !== botId)?.bot_id || null : null;
                dispatch('select', selectedBotId);
            }
            await loadBots();
        } catch (err) {
            error = String(err.message || err);
            console.error('Operation failed:', err);
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
                        <button
                            class="bot-item"
                            class:active={selectedBotId === bot.bot_id}
                            on:click={() => selectBot(bot.bot_id)}
                        >
                            <span class="status-dot" class:running={bot.status === 'running'} style="color: {statusColor(bot.status)}">{statusLabel(bot.status)}</span>
                            <span class="bot-name">{bot.bot_name || bot.bot_id}</span>
                            <span class="bot-platform" class:discord={bot.platform === 'discord' || !bot.platform} class:qq={bot.platform === 'qq'}>{bot.platform || 'discord'}</span>
                            <div class="bot-item-actions" role="presentation" on:click|stopPropagation>
                                {#if bot.status !== 'running'}
                                    <button class="mini-btn start" on:click={(e) => handleStart(bot.bot_id, e)} title={$t('botManager.start')}>▶</button>
                                {:else}
                                    <button class="mini-btn stop" on:click={(e) => handleStop(bot.bot_id, e)} title={$t('botManager.stop')}>■</button>
                                    <button class="mini-btn restart" on:click={(e) => handleRestart(bot.bot_id, e)} title={$t('botManager.restart')}>↻</button>
                                {/if}
                                <button class="mini-btn delete" on:click={(e) => handleDelete(bot.bot_id, e)} title={$t('botManager.delete')}>×</button>
                            </div>
                        </button>
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

    .bot-item {
        display: grid;
        grid-template-columns: 20px 1fr auto auto;
        align-items: center;
        gap: .4rem;
        width: 100%;
        padding: .55rem .6rem;
        margin-bottom: .2rem;
        border: none;
        border-radius: 8px;
        background: transparent;
        color: var(--text-light);
        cursor: pointer;
        font-size: .88rem;
        text-align: left;
        box-shadow: none;
        position: relative;
    }

    .bot-item:hover {
        background: var(--panel-muted-bg);
        color: var(--text-color);
    }

    .bot-item.active {
        background: linear-gradient(135deg, rgba(31, 139, 214, .18), rgba(31, 139, 214, .08));
        color: var(--primary-color);
    }

    .bot-item.active::before {
        content: '';
        position: absolute;
        left: 0;
        top: 6px;
        bottom: 6px;
        width: 3px;
        background: var(--sidebar-active-indicator, #1f8bd6);
        border-radius: 0 3px 3px 0;
    }

    :root[data-theme='neon'] .bot-item.active::before {
        width: 4px;
        box-shadow: 0 0 10px rgba(0, 229, 255, .4);
    }

    :root[data-theme='neon'] .bot-item.active {
        background: linear-gradient(135deg, rgba(0, 229, 255, .12), rgba(0, 145, 255, .06));
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

    .bot-name {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-weight: 500;
    }

    .bot-platform {
        font-size: .65rem;
        opacity: .6;
        padding: .1rem .35rem;
        border-radius: 4px;
        background: var(--panel-muted-bg);
        transition: opacity .18s ease, background .18s ease;
    }

    .bot-item:hover .bot-platform {
        opacity: .85;
    }

    .bot-platform.discord {
        background: rgba(88, 101, 242, .15);
        color: #8ea1e1;
    }

    .bot-platform.qq {
        background: rgba(18, 183, 106, .15);
        color: #5cd9a6;
    }

    .bot-item-actions {
        display: none;
        gap: .15rem;
    }

    .bot-item:hover .bot-item-actions {
        display: flex;
    }

    .mini-btn {
        width: 22px;
        height: 22px;
        padding: 0;
        font-size: .6rem;
        border-radius: 4px;
        border: 1px solid var(--border-color);
        background: var(--control-bg);
        color: var(--text-light);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        box-shadow: none;
    }

    .mini-btn.start:hover { color: var(--success-text); border-color: var(--success-text); }
    .mini-btn.stop:hover { color: var(--error-text); border-color: var(--error-text); }
    .mini-btn.restart:hover { color: var(--info-text); border-color: var(--info-text); }
    .mini-btn.delete:hover { color: var(--error-text); border-color: var(--error-text); }

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

        .bot-item {
            font-size: .8rem;
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

        .bot-item {
            font-size: .82rem;
        }
    }
</style>
