<script>
    import { onMount } from 'svelte';
    import { t } from '../i18n.js';
    import { simulateDebug } from '../lib/api.js';
    import Card from '../components/Card.svelte';
    import { roleBasedConfigArray, showStatus } from '../lib/stores.js';
    import {
        fetchInteractionTree,
        fetchInteractionMessages,
        fetchInteractionUsage,
        deleteInteractionRecords,
        pruneInteractions,
        fetchBotGuilds,
        reconstructContext,
        fetchBots,
    } from '../lib/api.js';

    let payload = {
        user_id: '',
        channel_id: '',
        guild_id: '',
        role_id: '',
        message_content: ''
    };

    let result = null;
    let error = null;
    let isSimulating = false;

    async function handleSimulate() {
        if (!payload.user_id.trim() || !payload.channel_id.trim() || !payload.message_content.trim()) {
            showStatus($t('debugger.errorIncomplete'), 'error');
            return;
        }
        isSimulating = true;
        error = null;
        result = null;
        try {
            result = await simulateDebug(payload);
        } catch(e) {
            error = e.message;
        } finally {
            isSimulating = false;
        }
    }

    let debugTab = 'simulate';

    let selectedHistoryBot = null;
    let selectedGuild = null;
    let selectedChannel = null;
    let selectedMember = null;
    let selectedDate = null;

    let treeItems = [];
    let treeLoading = false;
    let messages = [];
    let messagesLoading = false;
    let usage = { used_bytes: 0, max_bytes: 524288000, percent: 0 };
    let guildList = [];
    let guildListLoading = false;
    let botList = [];
    let botListLoaded = false;

    let channelIds = [];
    let memberIds = [];
    let dateStrings = [];

    let rawContext = null;
    let rawContextLoading = false;
    let rawContextError = '';

    async function handleShowRawContext() {
        if (!selectedHistoryBot || !selectedGuild || !selectedChannel || !selectedMember || !selectedDate) return;
        rawContextLoading = true;
        rawContextError = '';
        rawContext = null;
        try {
            const tree = await fetchInteractionTree(selectedHistoryBot, {
                guild_id: selectedGuild,
                channel_id: selectedChannel,
                member_id: selectedMember,
            });
            const items = tree.items || [];
            const roleId = items.length > 0 ? items[0].role_id : 'default';
            rawContext = await reconstructContext(selectedHistoryBot, selectedGuild, roleId, selectedChannel, selectedMember, selectedDate);
        } catch(e) {
            rawContextError = e.message;
        } finally {
            rawContextLoading = false;
        }
    }

    $: channelIds = [...new Set(treeItems.filter(t => !selectedChannel || t.channel_id === selectedChannel).map(t => t.channel_id))];
    $: memberIds = [...new Set(treeItems.filter(t => (!selectedChannel || t.channel_id === selectedChannel) && t.member_id).map(t => t.member_id))];
    $: dateStrings = [...new Set(treeItems.filter(t => (!selectedChannel || t.channel_id === selectedChannel) && (!selectedMember || t.member_id === selectedMember)).map(t => t.date))].sort().reverse();

    async function loadInteractionUsage() {
        if (!selectedHistoryBot) return;
        try {
            usage = await fetchInteractionUsage(selectedHistoryBot);
        } catch(e) {
            // ignore
        }
    }

    async function loadGuildsForHistory() {
        if (!selectedHistoryBot) return;
        guildListLoading = true;
        try {
            const data = await fetchBotGuilds(selectedHistoryBot);
            guildList = data.guilds || [];
        } catch(e) {
            guildList = [];
        } finally {
            guildListLoading = false;
        }
    }

    async function loadBotList() {
        if (botListLoaded) return;
        try {
            const data = await fetchBots();
            botList = (data?.bots || data || []);
            botListLoaded = true;
        } catch(e) {
            botList = [];
        }
    }

    async function loadInteractionTree() {
        if (!selectedHistoryBot) return;
        treeLoading = true;
        try {
            const filters = {};
            if (selectedGuild) filters.guild_id = selectedGuild;
            if (selectedChannel) filters.channel_id = selectedChannel;
            if (selectedMember) filters.member_id = selectedMember;
            const data = await fetchInteractionTree(selectedHistoryBot, filters);
            treeItems = data.items || [];
        } catch(e) {
            treeItems = [];
        } finally {
            treeLoading = false;
        }
    }

    async function loadMessages() {
        if (!selectedHistoryBot || !selectedGuild || !selectedChannel || !selectedMember || !selectedDate) return;
        messagesLoading = true;
        try {
            const tree = await fetchInteractionTree(selectedHistoryBot, {
                guild_id: selectedGuild,
                channel_id: selectedChannel,
                member_id: selectedMember,
            });
            const items = tree.items || [];
            if (items.length > 0) {
                const item = items[0];
                const data = await fetchInteractionMessages(
                    selectedHistoryBot,
                    selectedGuild,
                    item.role_id,
                    selectedChannel,
                    selectedMember,
                    selectedDate,
                );
                messages = data.messages || [];
            } else {
                messages = [];
            }
        } catch(e) {
            messages = [];
        } finally {
            messagesLoading = false;
        }
    }

    async function handleDeleteRecords() {
        if (!selectedHistoryBot) return;
        if (!confirm($t('debugger.confirmDelete'))) return;
        try {
            const filters = {};
            if (selectedGuild) filters.guild_id = selectedGuild;
            if (selectedChannel) filters.channel_id = selectedChannel;
            if (selectedMember) filters.member_id = selectedMember;
            if (selectedDate) filters.date = selectedDate;
            await deleteInteractionRecords(selectedHistoryBot, filters);
            showStatus($t('debugger.deleted'), 'success');
            await loadInteractionTree();
            await loadInteractionUsage();
            messages = [];
        } catch(e) {
            showStatus($t('debugger.deleteFailed', { error: e.message }), 'error');
        }
    }

    async function handlePrune() {
        if (!selectedHistoryBot) return;
        try {
            await pruneInteractions(selectedHistoryBot);
            showStatus($t('debugger.pruned'), 'success');
            await loadInteractionTree();
            await loadInteractionUsage();
        } catch(e) {
            showStatus($t('debugger.pruneFailed', { error: e.message }), 'error');
        }
    }

    function resetHistoryFilters() {
        selectedGuild = null;
        selectedChannel = null;
        selectedMember = null;
        selectedDate = null;
        messages = [];
    }

    $: if (debugTab === 'history' && selectedHistoryBot && selectedGuild) {
        loadInteractionTree();
        loadInteractionUsage();
    }

    $: if (selectedChannel && selectedMember && selectedDate) {
        loadMessages();
    }
</script>

<div class="debugger-container">
    <div class="tabs">
        <button class:active={debugTab === 'simulate'} on:click={() => debugTab = 'simulate'}>{$t('debugger.simulateTab')}</button>
        <button class:active={debugTab === 'history'} on:click={() => debugTab = 'history'}>{$t('debugger.historyTab')}</button>
    </div>

    {#if debugTab === 'simulate'}
        <Card title={$t('debugger.title')}>
            <p class="info">{$t('debugger.info')}</p>
            <div class="debugger-grid">
                <label for="dbg-user-id">{$t('debugger.userId')}</label>
                <input id="dbg-user-id" type="text" placeholder={$t('debugger.userIdPlaceholder')} bind:value={payload.user_id}>

                <label for="dbg-role-id">{$t('debugger.roleId')}</label>
                <select id="dbg-role-id" bind:value={payload.role_id}>
                    <option value="">-- No Role --</option>
                    {#if $roleBasedConfigArray}
                        {#each $roleBasedConfigArray as role}
                            <option value={role.id}>{role.title || role.id}</option>
                        {/each}
                    {/if}
                </select>

                <label for="dbg-channel-id">{$t('debugger.channelId')}</label>
                <input id="dbg-channel-id" type="text" placeholder={$t('debugger.channelIdPlaceholder')} bind:value={payload.channel_id}>

                 <label for="dbg-guild-id">{$t('debugger.guildId')}</label>
                <input id="dbg-guild-id" type="text" placeholder={$t('debugger.guildIdPlaceholder')} bind:value={payload.guild_id}>

                <div class="message-input">
                    <label for="dbg-message">{$t('debugger.message')}</label>
                    <textarea id="dbg-message" rows="4" placeholder={$t('debugger.messagePlaceholder')} bind:value={payload.message_content}></textarea>
                </div>
            </div>
            <button class="action-btn" on:click={handleSimulate} disabled={isSimulating}>
                {isSimulating ? $t('debugger.simulating') : $t('debugger.button')}
            </button>

            {#if error}
                <div class="status error" style="visibility: visible; margin-top: 1rem;">{$t('debugger.error')}{error}</div>
            {/if}
        </Card>

        {#if result}
            <Card title={$t('debugger.generatedPrompt')}>
                <pre class="result-box"><code>{result.generated_system_prompt}</code></pre>
            </Card>
            <Card title={$t('debugger.llmResponse')}>
                <div class="result-box response">{result.llm_response}</div>
            </Card>
        {/if}

    {:else if debugTab === 'history'}
        <Card title={$t('debugger.historyTitle')}>
            <div class="ih-filters">
                <select bind:value={selectedHistoryBot} on:change={() => { resetHistoryFilters(); loadGuildsForHistory(); }} on:focus={loadBotList}>
                    <option value={null}>{$t('debugger.selectBot')}</option>
                    {#each botList as b}
                        <option value={b.bot_id || b.id}>{b.bot_name || b.name || b.bot_id || b.id}</option>
                    {/each}
                </select>
                <select bind:value={selectedGuild} on:change={() => { selectedChannel = null; selectedMember = null; selectedDate = null; messages = []; }} disabled={!selectedHistoryBot}>
                    <option value={null}>{$t('debugger.selectServer')}</option>
                    {#each guildList as g}
                        <option value={g.id}>{g.name}</option>
                    {/each}
                </select>
                <select bind:value={selectedChannel} on:change={() => { selectedMember = null; selectedDate = null; messages = []; }} disabled={!selectedGuild}>
                    <option value={null}>{$t('debugger.selectChannel')}</option>
                    {#each channelIds as cid}
                        <option value={cid}>#{cid}</option>
                    {/each}
                </select>
                <select bind:value={selectedMember} on:change={() => { selectedDate = null; messages = []; }} disabled={!selectedChannel}>
                    <option value={null}>{$t('debugger.selectMember')}</option>
                    {#each memberIds as mid}
                        <option value={mid}>{mid}</option>
                    {/each}
                </select>
                <select bind:value={selectedDate} disabled={!selectedMember}>
                    <option value={null}>{$t('debugger.selectDate')}</option>
                    {#each dateStrings as d}
                        <option value={d}>{d}</option>
                    {/each}
                </select>
            </div>

            {#if selectedHistoryBot}
                <div class="ih-usage-bar">
                    <span>{$t('debugger.storageUsage')}: {Math.round(usage.used_bytes / 1024 / 1024 * 100) / 100}MB / {Math.round(usage.max_bytes / 1024 / 1024)}MB ({usage.percent}%)</span>
                    <div class="ih-bar-track">
                        <div class="ih-bar-fill" style="width: {Math.min(usage.percent, 100)}%"></div>
                    </div>
                    <button class="ih-action-btn" on:click={handlePrune}>{$t('debugger.prune')}</button>
                    <button class="ih-action-btn ih-delete-btn" on:click={handleDeleteRecords}>{$t('debugger.deleteSelected')}</button>
                </div>
            {/if}
        </Card>

        {#if messagesLoading}
            <div class="loading-state">{$t('debugger.loadingMessages')}</div>
        {:else if messages.length > 0}
            <Card title="{$t('debugger.messagesFor')} {selectedDate}">
                <div class="ih-msg-actions">
                    <button class="action-btn" on:click={handleShowRawContext} disabled={rawContextLoading}>
                        {rawContextLoading ? '...' : $t('debugger.showRawContext')}
                    </button>
                </div>
                <div class="ih-messages">
                    {#each messages as msg, i (msg.message_id || i)}
                        <div class="ih-msg" class:ih-bot-msg={msg.is_bot_reply}>
                            <div class="ih-msg-meta">
                                <span class="ih-msg-time">{msg.timestamp ? msg.timestamp.substring(11, 19) : ''}</span>
                                <span class="ih-msg-author">{msg.author_name}</span>
                                {#if msg.trigger_source && msg.trigger_source !== 'none'}
                                    <span class="ih-msg-trigger">[{msg.trigger_source}]</span>
                                {/if}
                            </div>
                            <div class="ih-msg-content">{msg.content}</div>
                        </div>
                    {/each}
                </div>
            </Card>

            {#if rawContext}
                <Card title={$t('debugger.rawContext')}>
                    <div class="ih-context-section">
                        <h4>{$t('debugger.systemPrompt')}</h4>
                        <pre class="result-box">{rawContext.system_prompt}</pre>
                    </div>
                    {#if rawContext.messages && rawContext.messages.length}
                        <div class="ih-context-section">
                            <h4>{$t('debugger.formattedMessages')}</h4>
                            {#each rawContext.messages as fm}
                                <div class="ih-context-msg">
                                    <span class="ih-msg-author">{fm.author_name}</span>
                                    <pre class="result-box" style="max-height: 200px;">{fm.formatted_content}</pre>
                                </div>
                            {/each}
                        </div>
                    {/if}
                </Card>
            {:else if rawContextError}
                <div class="error-state">{$t('debugger.contextError')}: {rawContextError}</div>
            {/if}
        {:else if selectedDate}
            <div class="empty-state">{$t('debugger.noMessages')}</div>
        {/if}
    {/if}
</div>

<style>
    .debugger-container { max-width: 900px; margin: 2rem auto; display: flex; flex-direction: column; gap: 2rem;}
    .tabs { display: flex; gap: .25rem; margin-bottom: -.5rem; }
    .tabs button {
        padding: .45rem 1rem; font-size: .82rem; border: 1px solid var(--floating-border);
        background: var(--panel-muted-bg); color: var(--text-light); border-radius: 5px 5px 0 0;
        cursor: pointer; transition: all .15s; box-shadow: none;
    }
    .tabs button:hover { background: var(--panel-hover-bg); }
    .tabs button.active { background: var(--card-bg); color: var(--primary-color); border-bottom-color: var(--card-bg); font-weight: 600; }
    .debugger-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem 1.5rem; align-items: center; }
    .message-input { grid-column: 1 / -1; }
    .action-btn { margin-top: 1rem; }
    .result-box { background-color: var(--panel-muted-bg); border: 1px solid var(--floating-border); border-radius: 8px; padding: 1rem; font-family: monospace; white-space: pre-wrap; word-break: break-all; max-height: 400px; overflow-y: auto; color: var(--text-color); }
    .result-box.response { font-family: inherit; white-space: normal;}

    .ih-filters { display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: .75rem; }
    .ih-filters select {
        padding: .35rem .5rem; font-size: .78rem; border: 1px solid var(--floating-border);
        border-radius: 5px; background: var(--panel-muted-bg); color: var(--text-color);
        min-width: 120px; cursor: pointer;
    }
    .ih-filters select:disabled { opacity: .5; cursor: not-allowed; }
    .ih-filters select:focus { outline: none; border-color: var(--primary-color); }

    .ih-usage-bar {
        display: flex; align-items: center; gap: .6rem; font-size: .78rem;
        color: var(--text-light); padding: .5rem 0; flex-wrap: wrap;
    }
    .ih-bar-track {
        flex: 1; min-width: 120px; height: 8px; background: var(--panel-muted-bg);
        border-radius: 4px; overflow: hidden; border: 1px solid var(--floating-border);
    }
    .ih-bar-fill { height: 100%; background: var(--primary-color); border-radius: 4px; transition: width .3s; }
    .ih-action-btn {
        padding: .25rem .6rem; font-size: .72rem; border: 1px solid var(--floating-border);
        border-radius: 4px; background: var(--panel-muted-bg); color: var(--text-color);
        cursor: pointer; box-shadow: none; transition: all .15s;
    }
    .ih-action-btn:hover { background: var(--panel-hover-bg); }
    .ih-delete-btn { color: var(--danger-color); border-color: var(--danger-color); }
    .ih-delete-btn:hover { background: rgba(var(--danger-color), .1); }

    .ih-messages { display: flex; flex-direction: column; gap: .5rem; }
    .ih-msg {
        padding: .55rem .7rem; border-radius: 6px; background: var(--panel-muted-bg);
        border-left: 3px solid var(--floating-border);
    }
    .ih-bot-msg { border-left-color: var(--primary-color); }
    .ih-msg-meta {
        display: flex; align-items: center; gap: .5rem; font-size: .72rem;
        color: var(--text-light); margin-bottom: .2rem;
    }
    .ih-msg-author { font-weight: 600; color: var(--text-color); }
    .ih-msg-trigger { color: var(--primary-color); font-size: .68rem; }
    .ih-msg-content { font-size: .82rem; color: var(--text-color); white-space: pre-wrap; word-break: break-word; }
    .ih-msg-actions { display: flex; gap: .5rem; margin-bottom: .5rem; }
    .ih-msg-actions .action-btn { margin-top: 0; }
    .ih-context-section { margin-bottom: 1rem; }
    .ih-context-section h4 { font-size: .85rem; color: var(--text-color); margin-bottom: .3rem; }
    .ih-context-msg { margin-bottom: .5rem; }
</style>
