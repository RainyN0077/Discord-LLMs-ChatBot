<!-- src/pages/BotManager.svelte -->
<script>
    import { onMount } from 'svelte';
    import { t } from '../i18n.js';
    import {
        fetchBots, createBot, deleteBot,
        startBot, stopBot, restartBot,
    } from '../lib/api.js';

    let bots = [];
    let loading = true;
    let error = '';
    let showCreateForm = false;
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
        } catch (e) {
            error = String(e.message || e);
            console.error('Failed to fetch bots:', e);
        } finally {
            loading = false;
        }
    }

    async function handleStart(botId) {
        try {
            await startBot(botId);
            await loadBots();
        } catch (e) {
            alert(`Failed to start bot: ${e.message || e}`);
        }
    }

    async function handleStop(botId) {
        try {
            await stopBot(botId);
            await loadBots();
        } catch (e) {
            alert(`Failed to stop bot: ${e.message || e}`);
        }
    }

    async function handleRestart(botId) {
        try {
            await restartBot(botId);
            await loadBots();
        } catch (e) {
            alert(`Failed to restart bot: ${e.message || e}`);
        }
    }

    async function handleDelete(botId) {
        if (!confirm(`Delete bot "${botId}" and all its data? This cannot be undone.`)) return;
        try {
            await deleteBot(botId);
            await loadBots();
        } catch (e) {
            alert(`Failed to delete bot: ${e.message || e}`);
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
            createData = {
                bot_id: '', bot_name: '', platform: 'discord', enabled: true,
                discord_token: '', llm_provider: 'openai', api_key: '', model_name: 'gpt-4o',
            };
            await loadBots();
        } catch (e) {
            createError = String(e.message || e);
        } finally {
            creating = false;
        }
    }

    onMount(loadBots);

    function statusColor(status) {
        if (status === 'running') return 'var(--success-text, #00c853)';
        if (status === 'starting') return 'var(--info-text, #ffaa00)';
        if (status === 'error') return 'var(--error-text, #ff1744)';
        return 'var(--text-light, #888)';
    }

    function statusLabel(status) {
        if (status === 'running') return 'Running';
        if (status === 'starting') return 'Starting';
        if (status === 'error') return 'Error';
        return 'Stopped';
    }

    function formatUptime(seconds) {
        if (seconds == null) return '';
        if (seconds < 60) return `${Math.floor(seconds)}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
        return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
    }
</script>

<div class="bot-manager">
    <div class="header">
        <h2>Bot Manager</h2>
        <button class="btn-create" on:click={() => showCreateForm = !showCreateForm}>
            {showCreateForm ? 'Cancel' : '+ Create Bot'}
        </button>
    </div>

    {#if showCreateForm}
        <div class="create-form">
            <h3>Create New Bot</h3>
            {#if createError}
                <div class="error-msg">{createError}</div>
            {/if}
            <div class="form-row">
                <label>Bot ID <small>(a-z, 0-9, -, _)</small></label>
                <input type="text" bind:value={createData.bot_id} placeholder="my-discord-bot-01" />
            </div>
            <div class="form-row">
                <label>Bot Name</label>
                <input type="text" bind:value={createData.bot_name} placeholder="My Bot" />
            </div>
            <div class="form-row">
                <label>Platform</label>
                <select bind:value={createData.platform}>
                    <option value="discord">Discord</option>
                    <option value="qq">QQ</option>
                </select>
            </div>
            <div class="form-row">
                <label>Discord Token</label>
                <input type="password" bind:value={createData.discord_token} placeholder="Discord bot token" />
            </div>
            <div class="form-row">
                <label>LLM Provider</label>
                <select bind:value={createData.llm_provider}>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="google">Google (Gemini)</option>
                    <option value="xai">xAI (Grok)</option>
                </select>
            </div>
            <div class="form-row">
                <label>API Key</label>
                <input type="password" bind:value={createData.api_key} placeholder="LLM API key" />
            </div>
            <div class="form-row">
                <label>Model Name</label>
                <input type="text" bind:value={createData.model_name} placeholder="gpt-4o" />
            </div>
            <div class="form-row checkbox-row">
                <label>
                    <input type="checkbox" bind:checked={createData.enabled} />
                    Auto-start on launch
                </label>
            </div>
            <button class="btn-save" on:click={handleCreate} disabled={creating}>
                {creating ? 'Creating...' : 'Create Bot'}
            </button>
        </div>
    {/if}

    {#if loading}
        <div class="loading">Loading bots...</div>
    {:else if error}
        <div class="error-msg">{error}</div>
    {:else if bots.length === 0}
        <div class="empty">No bots configured. Click "+ Create Bot" to add one.</div>
    {:else}
        <div class="bot-list">
            {#each bots as bot (bot.bot_id)}
                <div class="bot-card">
                    <div class="bot-info">
                        <div class="bot-name-row">
                            <span class="status-dot" style="background-color: {statusColor(bot.status)}" title={statusLabel(bot.status)}></span>
                            <strong>{bot.bot_name || bot.bot_id}</strong>
                        </div>
                        <div class="bot-meta">
                            <span class="badge">{bot.platform || 'discord'}</span>
                            <span class="badge status-badge" style="color: {statusColor(bot.status)}; border-color: {statusColor(bot.status)}">
                                {statusLabel(bot.status)}
                            </span>
                            {#if bot.uptime_seconds != null}
                                <span class="uptime">Uptime: {formatUptime(bot.uptime_seconds)}</span>
                            {/if}
                        </div>
                        <div class="bot-id-label">ID: {bot.bot_id}</div>
                    </div>
                    <div class="bot-actions">
                        {#if bot.status !== 'running'}
                            <button class="btn-action btn-start" on:click={() => handleStart(bot.bot_id)}>Start</button>
                        {:else}
                            <button class="btn-action btn-stop" on:click={() => handleStop(bot.bot_id)}>Stop</button>
                            <button class="btn-action btn-restart" on:click={() => handleRestart(bot.bot_id)}>Restart</button>
                        {/if}
                        <button class="btn-action btn-delete" on:click={() => handleDelete(bot.bot_id)}>Delete</button>
                    </div>
                </div>
            {/each}
        </div>
    {/if}
</div>

<style>
    .bot-manager {
        max-width: 900px;
        margin: 0 auto;
        padding: 0 1rem;
    }
    .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;
        padding-top: 3rem;
    }
    .header h2 {
        font-size: 1.6rem;
        font-weight: 700;
        color: var(--text-color);
        margin: 0;
    }
    .btn-create {
        background: linear-gradient(135deg, var(--primary-color), #0f6fb2);
        color: #fff;
        padding: .6rem 1.2rem;
        font-weight: 600;
    }
    .create-form {
        background: var(--panel-bg, var(--floating-bg));
        border: 1px solid var(--panel-border, var(--floating-border));
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
    .create-form h3 {
        margin-top: 0;
        margin-bottom: 1rem;
    }
    .form-row {
        margin-bottom: 1rem;
    }
    .form-row label {
        display: block;
        margin-bottom: .35rem;
        color: var(--text-light);
        font-size: .9rem;
    }
    .form-row label small {
        color: var(--muted-text, #888);
    }
    .form-row input,
    .form-row select {
        width: 100%;
        padding: .55rem .75rem;
        border: 1px solid var(--border-color);
        border-radius: 8px;
        background: var(--input-bg, var(--floating-bg));
        color: var(--text-color);
        font-size: .95rem;
        box-sizing: border-box;
    }
    .checkbox-row label {
        display: flex;
        align-items: center;
        gap: .5rem;
    }
    .checkbox-row input {
        width: auto;
    }
    .btn-save {
        background: linear-gradient(135deg, var(--save-color), #1a9156);
        color: #fff;
        padding: .65rem 1.3rem;
        font-weight: 600;
        margin-top: .5rem;
    }
    .btn-save:disabled {
        opacity: .6;
        cursor: not-allowed;
    }
    .loading, .empty {
        text-align: center;
        padding: 3rem 1rem;
        color: var(--text-light);
    }
    .error-msg {
        background: var(--error-bg, #fce4ec);
        color: var(--error-text, #c62828);
        padding: .75rem 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-size: .9rem;
    }
    .bot-list {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }
    .bot-card {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--panel-bg, var(--floating-bg));
        border: 1px solid var(--panel-border, var(--floating-border));
        border-radius: 12px;
        padding: 1rem 1.25rem;
        box-shadow: var(--shadow-soft);
    }
    .bot-info {
        flex: 1;
        min-width: 0;
    }
    .bot-name-row {
        display: flex;
        align-items: center;
        gap: .6rem;
        font-size: 1.1rem;
        margin-bottom: .35rem;
    }
    .status-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
    }
    .bot-meta {
        display: flex;
        align-items: center;
        gap: .6rem;
        flex-wrap: wrap;
        margin-bottom: .25rem;
    }
    .badge {
        font-size: .78rem;
        padding: .15rem .55rem;
        border-radius: 6px;
        background: var(--panel-muted-bg);
        border: 1px solid var(--panel-muted-border);
        color: var(--text-light);
    }
    .status-badge {
        font-weight: 600;
    }
    .uptime {
        font-size: .78rem;
        color: var(--muted-text, #888);
    }
    .bot-id-label {
        font-size: .75rem;
        color: var(--muted-text, #888);
    }
    .bot-actions {
        display: flex;
        gap: .5rem;
        flex-shrink: 0;
    }
    .btn-action {
        padding: .4rem .75rem;
        font-size: .82rem;
        font-weight: 600;
        border-radius: 6px;
    }
    .btn-start {
        background: var(--success-bg, #e8f5e9);
        color: var(--success-text, #00c853);
        border: 1px solid rgba(0, 121, 107, .2);
    }
    .btn-stop {
        background: var(--error-bg, #fce4ec);
        color: var(--error-text, #ff1744);
        border: 1px solid rgba(194, 24, 91, .2);
    }
    .btn-restart {
        background: var(--info-bg, #e3f2fd);
        color: var(--info-text, #0288d1);
        border: 1px solid rgba(2, 119, 189, .2);
    }
    .btn-delete {
        background: transparent;
        color: var(--text-light);
        border: 1px solid var(--border-color);
    }
    .btn-delete:hover {
        color: var(--error-text);
        border-color: var(--error-text);
    }
    @media (max-width: 600px) {
        .bot-card {
            flex-direction: column;
            gap: .75rem;
            align-items: flex-start;
        }
        .bot-actions {
            width: 100%;
            justify-content: flex-end;
        }
    }
</style>
