<script>
    import '../styles/lists.css';
    import { onMount } from 'svelte';
    import { fade, fly } from 'svelte/transition';
    import { t, get as t_get } from '../i18n.js';
    import { fetchUsageStats } from '../lib/api.js';
    import { userPersonas, showStatus } from '../lib/stores.js';
    import Card from '../components/Card.svelte';
    import ScopedPromptEditor from '../components/ScopedPromptEditor.svelte';
    import RoleConfigEditor from '../components/RoleConfigEditor.svelte';

    let activeSection = 'users';
    let isRefreshing = false;
    let userSearch = '';
    let selectedChannelId = 'all';

    let userMetaById = {};
    let channelUsersMap = {};
    let discoveredChannels = [];
    let showHelpModal = false;

    function addPersona() {
        userPersonas.update(up => {
            const newKey = `new-user-${Date.now()}`;
            up[newKey] = { id: '', nickname: '', prompt: '', trigger_keywords: '' };
            return up;
        });
    }

    function removePersona(key) {
        userPersonas.update(up => {
            delete up[key];
            return up;
        });
    }

    function hasPersona(userId) {
        return Object.values($userPersonas || {}).some(p => p?.id === userId);
    }

    function addOrFocusPersona(userId) {
        userPersonas.update(up => {
            const existingKey = Object.keys(up).find(k => up[k]?.id === userId);
            if (existingKey) return up;

            const newKey = `user-${userId}`;
            const uniqueKey = up[newKey] ? `${newKey}-${Date.now()}` : newKey;
            const displayName = userMetaById[userId]?.display_name || userMetaById[userId]?.name || '';
            up[uniqueKey] = { id: userId, nickname: displayName, prompt: '', trigger_keywords: '' };
            return up;
        });
    }

    async function refreshDiscoveredUsers() {
        isRefreshing = true;
        try {
            const stats = await fetchUsageStats('all', 'user');
            const metadata = stats?.metadata || {};
            userMetaById = metadata.users || {};
            channelUsersMap = metadata.channel_users || {};

            const channelMeta = metadata.channels || {};
            const allChannelIds = new Set([
                ...Object.keys(channelMeta),
                ...Object.keys(channelUsersMap || {})
            ]);

            discoveredChannels = [...allChannelIds]
                .map((id) => {
                    const name = channelMeta?.[id]?.name || `${$t('personaHub.channelFallback')} ${id}`;
                    const userCount = (channelUsersMap?.[id]?.user_ids || []).length;
                    return { id, name, userCount };
                })
                .sort((a, b) => a.name.localeCompare(b.name));

            if (selectedChannelId !== 'all' && !discoveredChannels.find(ch => ch.id === selectedChannelId)) {
                selectedChannelId = 'all';
            }
        } catch (e) {
            showStatus(t_get('personaHub.loadFailed', { error: e.message }), 'error');
        } finally {
            isRefreshing = false;
        }
    }

    $: candidateUserIds = selectedChannelId === 'all'
        ? Object.keys(userMetaById || {})
        : (channelUsersMap?.[selectedChannelId]?.user_ids || []);

    $: normalizedSearch = userSearch.trim().toLowerCase();
    $: discoveredUsers = [...new Set(candidateUserIds)]
        .map((id) => ({
            id,
            name: userMetaById?.[id]?.name || '',
            display_name: userMetaById?.[id]?.display_name || userMetaById?.[id]?.name || `ID: ${id}`
        }))
        .filter((u) => {
            if (!normalizedSearch) return true;
            return (
                u.id.toLowerCase().includes(normalizedSearch) ||
                u.display_name.toLowerCase().includes(normalizedSearch) ||
                u.name.toLowerCase().includes(normalizedSearch)
            );
        })
        .sort((a, b) => a.display_name.localeCompare(b.display_name));

    onMount(() => {
        refreshDiscoveredUsers();
    });
</script>

<div class="page-container">
    <main>
        <h1>{$t('personaHub.title')}</h1>

        <div class="tabs">
            <button class:active={activeSection === 'users'} on:click={() => activeSection = 'users'}>{$t('personaHub.sections.users')}</button>
            <button class:active={activeSection === 'channels'} on:click={() => activeSection = 'channels'}>{$t('personaHub.sections.channels')}</button>
            <button class:active={activeSection === 'guilds'} on:click={() => activeSection = 'guilds'}>{$t('personaHub.sections.guilds')}</button>
            <button class:active={activeSection === 'roles'} on:click={() => activeSection = 'roles'}>{$t('personaHub.sections.roles')}</button>
        </div>

        {#if activeSection === 'users'}
            <Card title={$t('personaHub.discoveredUsersTitle')}>
                <div class="discover-controls">
                    <select bind:value={selectedChannelId}>
                        <option value="all">{$t('personaHub.allChannels')}</option>
                        {#each discoveredChannels as channel (channel.id)}
                            <option value={channel.id}>{channel.name} ({channel.userCount})</option>
                        {/each}
                    </select>
                    <input type="text" placeholder={$t('personaHub.searchPlaceholder')} bind:value={userSearch}>
                    <button class="action-btn" on:click={refreshDiscoveredUsers} disabled={isRefreshing}>
                        {isRefreshing ? $t('personaHub.refreshing') : $t('personaHub.refresh')}
                    </button>
                </div>

                {#if discoveredUsers.length === 0}
                    <p class="info">{$t('personaHub.noDiscoveredUsers')}</p>
                {:else}
                    <div class="discovered-list">
                        {#each discoveredUsers as user (user.id)}
                            <div class="discovered-item">
                                <div class="meta">
                                    <strong>{user.display_name}</strong>
                                    <span>ID: {user.id}</span>
                                </div>
                                <button class="action-btn-secondary" on:click={() => addOrFocusPersona(user.id)}>
                                    {hasPersona(user.id) ? $t('personaHub.editPortrait') : $t('personaHub.addPortrait')}
                                </button>
                            </div>
                        {/each}
                    </div>
                {/if}
            </Card>

            <Card title={$t('userPortrait.title')}>
                <p class="info">{$t('userPortrait.info')}</p>
                <div class="list-container">
                    {#each Object.keys($userPersonas || {}) as key (key)}
                        <div class="list-item">
                            <div class="list-item-main">
                                <input class="id-input" type="text" placeholder={$t('userPortrait.userId')} bind:value={$userPersonas[key].id}>
                                <input class="nickname-input" type="text" placeholder={$t('userPortrait.customNicknamePlaceholder')} bind:value={$userPersonas[key].nickname}>
                                <textarea class="prompt-input" rows="2" placeholder={$t('userPortrait.personaPrompt')} bind:value={$userPersonas[key].prompt}></textarea>
                                <input class="keywords-input" type="text" placeholder={$t('userPortrait.triggerKeywordsPlaceholder')} bind:value={$userPersonas[key].trigger_keywords}>
                            </div>
                            <button class="remove-btn" on:click={() => removePersona(key)} title={$t('roleConfig.remove')}>×</button>
                        </div>
                    {/each}
                </div>
                <button class="add-btn" on:click={addPersona}>{$t('userPortrait.add')}</button>
            </Card>
        {/if}

        {#if activeSection === 'channels'}
            <Card title={$t('scopedPrompts.channels.title')}>
                <ScopedPromptEditor type="channels" />
            </Card>
        {/if}

        {#if activeSection === 'guilds'}
            <Card title={$t('scopedPrompts.guilds.title')}>
                <ScopedPromptEditor type="guilds" />
            </Card>
        {/if}

        {#if activeSection === 'roles'}
            <RoleConfigEditor />
        {/if}
    </main>
</div>

<div class="help-footer">
    <button class="help-link" on:click={() => showHelpModal = true}>{$t('personaHub.helpLink')}</button>
</div>

{#if showHelpModal}
    <div
        class="modal-overlay"
        role="button"
        tabindex="0"
        in:fade={{ duration: 180 }}
        out:fade={{ duration: 150 }}
        on:click={(e) => { if (e.target === e.currentTarget) showHelpModal = false; }}
        on:keydown={(e) => { if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') showHelpModal = false; }}
    >
        <div class="modal-card" in:fly={{ y: 16, duration: 220 }} out:fly={{ y: 10, duration: 160 }}>
            <h3>{$t('personaHub.helpTitle')}</h3>
            <p>{$t('personaHub.helpBody')}</p>

            <h4>{$t('personaHub.commonIssuesTitle')}</h4>
            <ul class="help-list">
                <li>{$t('personaHub.commonIssue1')}</li>
                <li>{$t('personaHub.commonIssue2')}</li>
                <li>{$t('personaHub.commonIssue3')}</li>
                <li>{$t('personaHub.commonIssue4')}</li>
                <li>{$t('personaHub.commonIssue5')}</li>
            </ul>

            <h4>{$t('personaHub.quickCheckTitle')}</h4>
            <ol class="help-list ordered">
                <li>{$t('personaHub.quickCheck1')}</li>
                <li>{$t('personaHub.quickCheck2')}</li>
                <li>{$t('personaHub.quickCheck3')}</li>
                <li>{$t('personaHub.quickCheck4')}</li>
                <li>{$t('personaHub.quickCheck5')}</li>
                <li>{$t('personaHub.quickCheck6')}</li>
            </ol>

            <div class="modal-actions">
                <button class="action-btn" on:click={() => showHelpModal = false}>{$t('personaHub.helpClose')}</button>
            </div>
        </div>
    </div>
{/if}

<style>
    .page-container {
        width: min(1160px, 94%);
        margin: 5.2rem auto 6.2rem;
    }

    h1 {
        margin-bottom: 1.15rem;
    }

    .tabs {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .65rem;
        margin-bottom: 1rem;
    }

    .tabs button {
        background: var(--card-bg);
        color: var(--text-light);
        border: 1px solid var(--border-color);
    }

    .tabs button.active {
        color: #fff;
        background: linear-gradient(135deg, var(--primary-color), #0f6fb2);
    }

    .discover-controls {
        display: grid;
        grid-template-columns: 1.3fr 1.3fr auto;
        gap: .6rem;
        margin-bottom: .9rem;
    }

    .discover-controls select,
    .discover-controls input {
        min-height: 52px;
        font-size: 1.02rem;
        border: 1px solid var(--border-color);
    }

    .discovered-list {
        display: grid;
        gap: .55rem;
    }

    .discovered-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: .8rem;
        padding: .7rem .85rem;
        border: 1px solid var(--border-color);
        border-radius: 10px;
        background: var(--panel-soft-bg-2);
    }

    .meta {
        min-width: 0;
        display: grid;
    }

    .meta strong {
        color: var(--text-color);
    }

    .meta span {
        color: var(--text-light);
        font-size: .9rem;
    }

    .list-item-main {
        display: grid;
        grid-template-areas:
            "id nickname"
            "prompt prompt"
            "keywords keywords";
        grid-template-columns: 1fr 2fr;
        gap: 0.5rem;
        width: 100%;
    }

    .id-input { grid-area: id; }
    .nickname-input { grid-area: nickname; }
    .prompt-input { grid-area: prompt; }
    .keywords-input { grid-area: keywords; }

    .help-footer {
        display: flex;
        justify-content: center;
        margin-top: 1rem;
        margin-bottom: .5rem;
    }

    .help-link {
        background: transparent;
        border: none;
        color: color-mix(in srgb, var(--primary-color) 90%, white 10%);
        text-decoration: underline;
        cursor: pointer;
        padding: .2rem .4rem;
        font-size: .95rem;
    }

    .modal-overlay {
        position: fixed;
        inset: 0;
        background: rgba(15, 23, 42, .42);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1200;
        padding: 1rem;
    }

    .modal-card {
        width: min(560px, 95%);
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        box-shadow: var(--shadow);
        padding: 1rem 1rem .85rem;
    }

    .modal-card h3 {
        margin: 0 0 .55rem;
    }

    .modal-card p {
        margin: 0;
        color: var(--text-light);
        line-height: 1.5;
    }

    .modal-card h4 {
        margin: .85rem 0 .35rem;
        font-size: 1rem;
    }

    .help-list {
        margin: 0;
        padding-left: 1.15rem;
        color: var(--text-light);
        display: grid;
        gap: .22rem;
    }

    .help-list.ordered {
        padding-left: 1.25rem;
    }

    .modal-actions {
        margin-top: .9rem;
        display: flex;
        justify-content: flex-end;
    }

    @media (max-width: 960px) {
        .tabs {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .discover-controls {
            grid-template-columns: 1fr;
        }

        .list-item {
            flex-direction: column;
        }

        .list-item-main {
            grid-template-areas:
                "id"
                "nickname"
                "prompt"
                "keywords";
            grid-template-columns: 1fr;
        }
    }
</style>
