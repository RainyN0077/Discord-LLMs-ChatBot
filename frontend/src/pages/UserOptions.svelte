<!-- src/pages/UserOptions.svelte -->
<script>
    import '../styles/lists.css';
    import { onMount } from 'svelte';
    import { t, get as t_get } from '../i18n.js';
    import {
        userPersonas,
        userPersonasArray,
        scopedPrompts,
        scopedPromptsObject,
        roleConfigs,
        roleBasedConfigArray,
        userOptionsConfig,
        showStatus,
        saveConfig,
        loadBotConfigToStores
    } from '../lib/stores.js';
    import { fetchBotGuilds, fetchGuildChannels, fetchGuildRoles, searchGuildMembers, fetchBotDiagnostics } from '../lib/api.js';
    import Card from '../components/Card.svelte';

    export let botId = null;

    let activeTab = 'portrait';
    let loadingConfig = false;
    let configError = '';
    let isSaving = false;

    let configLoadSeq = 0;

    async function loadInstanceConfig(seq) {
        if (seq !== configLoadSeq) return;
        if (!botId) return;
        loadingConfig = true;
        configError = '';
        try {
            await loadBotConfigToStores(botId);
        } catch (e) {
            configError = String(e.message || e);
        } finally {
            loadingConfig = false;
        }
    }

    $: if (botId) { const seq = ++configLoadSeq; loadInstanceConfig(seq); }

    async function handleSave() {
        isSaving = true;
        showStatus('Saving...', 'info');
        try {
            await saveConfig(botId);
            showStatus('Configuration saved and bot restarted!', 'success');
        } catch (e) {
            showStatus('Save failed: ' + e.message, 'error');
        } finally {
            isSaving = false;
        }
    }

    function _makeKey(scopeType, scopeId) {
        if (scopeType === 'global' || !scopeId) return '*';
        return `${scopeType}:${scopeId}`;
    }

    let ruleDisplayNames = {};

    async function resolveScopeName(scopeType, scopeId) {
        if (scopeType === 'global') return $t('userOptions.scopeGlobal');
        if (scopeType === 'dm') return $t('userOptions.scopeDm', { id: scopeId });
        const cacheKey = `${scopeType}:${scopeId}`;
        if (ruleDisplayNames[cacheKey]) return ruleDisplayNames[cacheKey];
        if (!botId) return scopeId;
        try {
            if (scopeType === 'guild') {
                const data = await fetchBotGuilds(botId);
                const g = (data.guilds || []).find(g => g.id === scopeId);
                ruleDisplayNames[cacheKey] = g ? g.name : scopeId;
            } else if (scopeType === 'channel') {
                const guildsData = await fetchBotGuilds(botId);
                for (const g of (guildsData.guilds || [])) {
                    try {
                        const chData = await fetchGuildChannels(botId, g.id);
                        const ch = (chData.channels || []).find(c => c.id === scopeId);
                        if (ch) { ruleDisplayNames[cacheKey] = `#${ch.name} (${g.name})`; break; }
                    } catch (_) { continue; }
                }
                ruleDisplayNames[cacheKey] = ruleDisplayNames[cacheKey] || scopeId;
            }
        } catch (_) {
            ruleDisplayNames[cacheKey] = scopeId;
        }
        return ruleDisplayNames[cacheKey] || scopeId;
    }

    function addRule() {
        const key = `rule-${Date.now()}`;
        userOptionsConfig.update(uoc => {
            const rules = { ...(uoc.rules || {}) };
            rules[key] = {
                scope_type: 'global', scope_id: '', mode: 'blacklist',
                whitelist_behavior: 'triggers_only', users: {}
            };
            return { ...uoc, rules };
        });
    }

    function removeRule(key) {
        userOptionsConfig.update(uoc => {
            const rules = { ...(uoc.rules || {}) };
            delete rules[key];
            return { ...uoc, rules };
        });
    }

    function updateRuleField(key, field, value) {
        userOptionsConfig.update(uoc => {
            const rules = { ...(uoc.rules || {}) };
            if (rules[key]) {
                rules[key] = { ...rules[key], [field]: value };
            }
            return { ...uoc, rules };
        });
    }

    function addUserToRule(ruleKey) {
        userOptionsConfig.update(uoc => {
            const rules = { ...(uoc.rules || {}) };
            if (rules[ruleKey]) {
                const uid = `u-${Date.now()}`;
                const users = { ...(rules[ruleKey].users || {}) };
                users[uid] = {
                    user_id: '', user_display_name: '',
                    blacklist_mode: 'deny_response', negative_portrait: ''
                };
                rules[ruleKey] = { ...rules[ruleKey], users };
            }
            return { ...uoc, rules };
        });
    }

    function removeUserFromRule(ruleKey, userKey) {
        userOptionsConfig.update(uoc => {
            const rules = { ...(uoc.rules || {}) };
            if (rules[ruleKey]) {
                const users = { ...(rules[ruleKey].users || {}) };
                delete users[userKey];
                rules[ruleKey] = { ...rules[ruleKey], users };
            }
            return { ...uoc, rules };
        });
    }

    function updateRuleUserField(ruleKey, userKey, field, value) {
        userOptionsConfig.update(uoc => {
            const rules = { ...(uoc.rules || {}) };
            if (rules[ruleKey]?.users?.[userKey]) {
                const users = { ...rules[ruleKey].users };
                users[userKey] = { ...users[userKey], [field]: value };
                rules[ruleKey] = { ...rules[ruleKey], users };
            }
            return { ...uoc, rules };
        });
    }

    function setRuleMode(ruleKey, mode) {
        userOptionsConfig.update(uoc => {
            const rules = { ...(uoc.rules || {}) };
            if (rules[ruleKey]) {
                rules[ruleKey] = { ...rules[ruleKey], mode };
            }
            return { ...uoc, rules };
        });
    }

    function setWhitelistBehavior(ruleKey, behavior) {
        userOptionsConfig.update(uoc => {
            const rules = { ...(uoc.rules || {}) };
            if (rules[ruleKey]) {
                rules[ruleKey] = { ...rules[ruleKey], whitelist_behavior: behavior };
            }
            return { ...uoc, rules };
        });
    }

    let searchResults = {};
    let isSearching = {};
    let searchError = {};
    let memberSearchInput = {};
    let isResolving = {};

    async function handleMemberSearch(ruleKey, guildId) {
        if (!botId || !guildId || !memberSearchInput[ruleKey]) return;
        const query = memberSearchInput[ruleKey].trim();
        if (!query) return;
        isSearching[ruleKey] = true;
        searchError[ruleKey] = '';
        searchResults[ruleKey] = [];
        try {
            const data = await searchGuildMembers(botId, guildId, query, $userOptionsConfig.memberSearchTimeoutMs || 5000);
            if (data.error) {
                searchError[ruleKey] = data.message;
            } else {
                searchResults[ruleKey] = data.members || [];
                if (!searchResults[ruleKey].length) {
                    searchError[ruleKey] = $t('userOptions.noMembersFound');
                }
            }
        } catch (e) {
            searchError[ruleKey] = e.message;
        } finally {
            isSearching[ruleKey] = false;
        }
    }

    function selectSearchedMember(ruleKey, member) {
        userOptionsConfig.update(uoc => {
            const rules = { ...(uoc.rules || {}) };
            if (rules[ruleKey]) {
                const uid = `u-${Date.now()}`;
                const users = { ...(rules[ruleKey].users || {}) };
                users[uid] = {
                    user_id: member.id, user_display_name: member.display_name || member.username,
                    blacklist_mode: 'deny_response', negative_portrait: ''
                };
                rules[ruleKey] = { ...rules[ruleKey], users };
            }
            return { ...uoc, rules };
        });
        memberSearchInput[ruleKey] = '';
        searchResults[ruleKey] = [];
    }

    $: ruleKeys = $userOptionsConfig.rules ? Object.keys($userOptionsConfig.rules) : [];

    let guildList = [];
    let guildListLoaded = false;
    async function loadGuildList() {
        if (!botId || guildListLoaded) return;
        try { const data = await fetchBotGuilds(botId); guildList = data.guilds || []; guildListLoaded = true; } catch (_) {}
    }
    $: if (botId && activeTab === 'blocklist') loadGuildList();

    let channelListCache = {};
    async function loadChannelsForGuild(guildId) {
        if (!guildId || !botId) return;
        if (channelListCache[guildId]) return;
        try {
            const data = await fetchGuildChannels(botId, guildId);
            channelListCache[guildId] = data.channels || [];
        } catch (e) {
            channelListCache[guildId] = [];
        }
    }

    let showDiagnostics = false;
    let diagnosticsData = null;
    let diagnosticsLoading = false;
    let manualGuildId = '';
    let manualGuildIdInput = {};
    let isRefreshingGuilds = false;

    async function refreshGuilds() {
        guildList = [];
        guildListLoaded = false;
        isRefreshingGuilds = true;
        await loadGuildList();
        isRefreshingGuilds = false;
        showStatus($t('userOptions.guildListRefreshed'), 'success');
    }

    async function loadDiagnostics() {
        if (!botId) return;
        diagnosticsLoading = true;
        try {
            diagnosticsData = await fetchBotDiagnostics(botId);
            showDiagnostics = true;
        } catch (e) {
            showStatus($t('userOptions.diagnosticsFailed', { error: e.message }), 'error');
        } finally {
            diagnosticsLoading = false;
        }
    }

    async function resolveManualGuild(ruleKey) {
        const gid = manualGuildIdInput[ruleKey];
        if (!gid || !botId) return;
        isResolving[ruleKey] = true;
        try {
            const data = await fetchBotGuilds(botId);
            guildList = data.guilds || [];
            guildListLoaded = true;
            const match = guildList.find(g => g.id === gid || g.name === gid);
            if (match) {
                userOptionsConfig.update(config => {
                    const rules = { ...config.rules };
                    const rule = { ...rules[ruleKey] };
                    rule.scope_id = match.id;
                    rules[ruleKey] = rule;
                    return { ...config, rules };
                });
                await loadChannelsForGuild(match.id);
                showStatus($t('userOptions.guildResolved', { name: match.name }), 'success');
            } else {
                showStatus($t('userOptions.guildNotFound', { id: gid }), 'error');
            }
        } catch (e) {
            showStatus($t('userOptions.guildResolveFailed', { error: e.message }), 'error');
        } finally {
            isResolving[ruleKey] = false;
        }
    }

    function updateStore() { userOptionsConfig.set({ ...$userOptionsConfig }); }

    function updatePersonaField(key, field, value) {
        userPersonas.update(up => { if (up[key]) up[key][field] = value; return up; });
    }
    function updatePersonaId(oldKey, newId) {
        if (!newId || oldKey === newId) return;
        userPersonas.update(up => {
            if (up[newId]) { alert(t_get('errors.duplicateId', { id: newId })); return up; }
            up[newId] = { ...up[oldKey], id: newId }; delete up[oldKey]; return up;
        });
    }
    function addPersona() {
        userPersonas.update(up => {
            up[`new-${Date.now()}`] = { id: '', nickname: '', prompt: '', trigger_keywords: [] };
            return up;
        });
    }
    function removePersona(key) { userPersonas.update(up => { delete up[key]; return up; }); }
    function updatePersonaKeywords(key, value) {
        userPersonas.update(up => {
            if (up[key]) up[key].trigger_keywords = value.split(',').map(k => k.trim()).filter(Boolean);
            return up;
        });
    }

    function updateScopedField(type, key, field, value) {
        scopedPrompts.update(sp => { if (sp[type]?.[key]) sp[type][key][field] = value; return sp; });
    }
    function updateScopedId(type, oldKey, newId) {
        if (!newId || oldKey === newId) return;
        scopedPrompts.update(sp => {
            if (sp[type]?.[newId]) { alert(t_get('errors.duplicateId', { id: newId })); return sp; }
            sp[type][newId] = { ...sp[type][oldKey], id: newId }; delete sp[type][oldKey]; return sp;
        });
    }
    function addScopedItem(type) {
        scopedPrompts.update(sp => {
            if (!sp[type]) sp[type] = {};
            sp[type][`new-${type}-${Date.now()}`] = { id: '', enabled: true, mode: 'append', prompt: '' };
            return sp;
        });
    }
    function removeScopedItem(type, key) {
        scopedPrompts.update(sp => { if (sp[type]) delete sp[type][key]; return sp; });
    }

    function updateRoleField(key, field, value) {
        roleConfigs.update(rc => {
            if (rc[key]) {
                const numFields = ['message_limit','message_refresh_minutes','char_limit','char_refresh_minutes','char_output_budget'];
                rc[key][field] = numFields.includes(field) ? (value === '' ? 0 : Number(value)) : value;
            }
            return rc;
        });
    }
    function updateRoleId(oldKey, newId) {
        if (!newId || oldKey === newId) return;
        roleConfigs.update(rc => {
            if (rc[newId]) { alert(t_get('errors.duplicateId', { id: newId })); return rc; }
            rc[newId] = { ...rc[oldKey], id: newId }; delete rc[oldKey]; return rc;
        });
    }
    function addRoleConfig() {
        roleConfigs.update(rc => {
            rc[`new-role-${Date.now()}`] = {
                id:'',title:'',prompt:'',enable_message_limit:false,message_limit:0,
                message_refresh_minutes:60,message_output_budget:1,enable_char_limit:false,
                char_limit:0,char_refresh_minutes:60,char_output_budget:300,display_color:'#ffffff'
            };
            return rc;
        });
    }
    function removeRoleConfig(key) { roleConfigs.update(rc => { delete rc[key]; return rc; }); }
</script>

<div class="user-options-panel">
    <div class="config-header">
        <h2>{botId ? $t('userOptions.titleFor', { botId }) : $t('userOptions.title')}</h2>
        <div class="header-actions">
            <button class="save-btn" on:click={handleSave} disabled={isSaving || !botId}>
                {isSaving ? $t('configPanel.saving') : $t('configPanel.saveAndRestart')}
            </button>
        </div>
    </div>

    {#if loadingConfig}
        <div class="loading-state">{botId ? $t('configPanel.loadingConfig', { botId }) : 'Loading...'}</div>
    {:else if configError}
        <div class="error-state">{configError}</div>
    {:else if !botId}
        <div class="empty-state">{$t('configPanel.selectBot')}</div>
    {:else}
        <div class="tabs">
            <button class:active={activeTab === 'portrait'} on:click={() => activeTab = 'portrait'}>{$t('userOptions.tabs.portrait')}</button>
            <button class:active={activeTab === 'blocklist'} on:click={() => activeTab = 'blocklist'}>{$t('userOptions.tabs.blocklist')}</button>
            <button class:active={activeTab === 'guildPortrait'} on:click={() => activeTab = 'guildPortrait'}>{$t('userOptions.tabs.guildPortrait')}</button>
            <button class:active={activeTab === 'channelPortrait'} on:click={() => activeTab = 'channelPortrait'}>{$t('userOptions.tabs.channelPortrait')}</button>
            <button class:active={activeTab === 'rolePortrait'} on:click={() => activeTab = 'rolePortrait'}>{$t('userOptions.tabs.rolePortrait')}</button>
        </div>

        <div class="tab-content">
            {#if activeTab === 'portrait'}
                <Card title={$t('userPortrait.title')}>
                    <p class="info">{$t('userPortrait.info')}</p>
                    <div class="list-container">
                        {#each $userPersonasArray as persona (persona._key)}
                        <div class="list-item complex-item">
                            <div class="list-item-main very-wide-grid">
                                <input class="id-input" type="text" placeholder={$t('userPortrait.userId')} value={persona.id} on:blur={(e) => updatePersonaId(persona._key, e.target.value)}>
                                <input class="nickname-input" type="text" placeholder={$t('userPortrait.customNicknamePlaceholder')} value={persona.nickname} on:input={(e) => updatePersonaField(persona._key, 'nickname', e.target.value)}>
                                <textarea class="prompt-input" rows="3" placeholder={$t('userPortrait.personaPrompt')} value={persona.prompt} on:input={(e) => updatePersonaField(persona._key, 'prompt', e.target.value)}></textarea>
                                <input class="keywords-input" type="text" placeholder={$t('userPortrait.triggerKeywordsPlaceholder')} value={(persona.trigger_keywords || []).join(', ')} on:input={(e) => updatePersonaKeywords(persona._key, e.target.value)}>
                            </div>
                            <button class="remove-btn" on:click={() => removePersona(persona._key)} title={$t('userOptions.remove')}>×</button>
                        </div>
                        {/each}
                    </div>
                    <button class="add-btn" on:click={addPersona}>{$t('userPortrait.add')}</button>
                </Card>

            {:else if activeTab === 'blocklist'}
                <Card title={$t('userOptions.blocklist.title')}>
                    <p class="info">{$t('userOptions.blocklist.info')}</p>
                    <div class="uo-top-controls">
                        <label class="toggle-switch">
                            <input type="checkbox" checked={$userOptionsConfig.enabled} on:change={(e) => { userOptionsConfig.update(u => ({ ...u, enabled: e.target.checked })); }}>
                            <span class="slider"></span>{$t('userOptions.blocklist.enable')}
                        </label>
                        <div class="uo-timeout-row">
                            <label for="member-search-timeout">{$t('userOptions.blocklist.memberSearchTimeout')}</label>
                            <input id="member-search-timeout" type="number" min="1000" max="30000" step="500" value={$userOptionsConfig.memberSearchTimeoutMs} on:input={(e) => { userOptionsConfig.update(u => ({ ...u, member_search_timeout_ms: Number(e.target.value) || 5000 })); }}>
                            <span class="unit-label">ms</span>
                        </div>
                    </div>
                </Card>

                {#if guildListLoaded && guildList.length === 0}
                    <div class="uo-guild-warning">
                        <span class="uo-warning-icon">&#9888;</span>
                        {$t('userOptions.blocklist.noGuildsWarning')}
                        <button class="uo-inline-link" on:click={loadDiagnostics}>{$t('userOptions.blocklist.diagnostics')}</button>
                    </div>
                {/if}

                <Card title={$t('userOptions.blocklist.rules')}>
                    <div class="uo-rules-container">
                        {#each ruleKeys as rk, idx (rk)}
                        {@const rule = $userOptionsConfig.rules[rk]}
                        <div class="uo-rule-card" class:uo-rule-blacklist={rule.mode === 'blacklist'} class:uo-rule-whitelist={rule.mode === 'whitelist'}>
                            <div class="uo-rule-topbar">
                                <span class="uo-rule-index">#{idx + 1}</span>
                                <span class="uo-scope-badge" class:uo-scope-global={rule.scope_type === 'global'} class:uo-scope-guild={rule.scope_type === 'guild'} class:uo-scope-channel={rule.scope_type === 'channel'} class:uo-scope-dm={rule.scope_type === 'dm'}>
                                    {#if rule.scope_type === 'global'}{$t('userOptions.scopeGlobal')}
                                    {:else if rule.scope_type === 'guild'}{$t('userOptions.scopeGuild')}
                                    {:else if rule.scope_type === 'channel'}{$t('userOptions.scopeChannel')}
                                    {:else}{$t('userOptions.scopeDm', { id: '' })}{/if}
                                </span>
                                {#if rule.scope_type === 'guild' && rule.scope_id}
                                    <span class="uo-scope-detail">{guildList.find(g => g.id === rule.scope_id)?.name || rule.scope_id}</span>
                                {:else if rule.scope_type === 'channel' && rule.scope_id}
                                    <span class="uo-scope-detail">#{rule.scope_id}</span>
                                {:else if rule.scope_type === 'dm' && rule.scope_id}
                                    <span class="uo-scope-detail">@{rule.scope_id}</span>
                                {/if}
                                <div class="uo-rule-spacer"></div>
                                <div class="uo-mode-segmented">
                                    <button class="uo-seg-btn" class:active={rule.mode === 'blacklist'} on:click={() => setRuleMode(rk, 'blacklist')}>
                                        <span class="uo-seg-dot blacklist-dot"></span>{$t('userOptions.blocklist.modeBlacklist')}
                                    </button>
                                    <button class="uo-seg-btn" class:active={rule.mode === 'whitelist'} on:click={() => setRuleMode(rk, 'whitelist')}>
                                        <span class="uo-seg-dot whitelist-dot"></span>{$t('userOptions.blocklist.modeWhitelist')}
                                    </button>
                                </div>
                                <button class="uo-rule-remove-btn" on:click={() => removeRule(rk)} title={$t('userOptions.remove')}>
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>
                                </button>
                            </div>

                            <div class="uo-rule-body">
                                {#if rule.mode === 'whitelist'}
                                    <div class="uo-whitelist-control">
                                        <span class="uo-sub-label">{$t('userOptions.blocklist.whitelistBehavior')}：</span>
                                        <div class="uo-mode-segmented small">
                                            <button class="uo-seg-btn" class:active={rule.whitelist_behavior === 'triggers_only'} on:click={() => setWhitelistBehavior(rk, 'triggers_only')}>
                                                {$t('userOptions.blocklist.wlTriggersOnly')}
                                            </button>
                                            <button class="uo-seg-btn" class:active={rule.whitelist_behavior === 'messages_only'} on:click={() => setWhitelistBehavior(rk, 'messages_only')}>
                                                {$t('userOptions.blocklist.wlMessagesOnly')}
                                            </button>
                                        </div>
                                    </div>
                                {/if}

                                <div class="uo-scope-editor">
                                    <select class="uo-scope-select" value={rule.scope_type} on:change={(e) => updateRuleField(rk, 'scope_type', e.target.value)}>
                                        <option value="global">{$t('userOptions.scopeGlobal')}</option>
                                        <option value="guild">{$t('userOptions.scopeGuild')}</option>
                                        <option value="channel">{$t('userOptions.scopeChannel')}</option>
                                        <option value="dm">{$t('userOptions.scopeDm', { id: '' })}</option>
                                    </select>
                                    {#if rule.scope_type === 'guild'}
                                        <div class="uo-guild-row">
                                            <select class="uo-scope-select" value={rule.scope_id} on:change={(e) => { updateRuleField(rk, 'scope_id', e.target.value); loadChannelsForGuild(e.target.value); }}>
                                                <option value="">{$t('userOptions.blocklist.selectPlaceholder')}</option>
                                                {#each guildList as g}
                                                    <option value={g.id}>{g.name}</option>
                                                {/each}
                                            </select>
                                            <button class="uo-refresh-btn" on:click={refreshGuilds} disabled={isRefreshingGuilds} title={$t('userOptions.blocklist.refreshGuilds')}>
                                                {#if isRefreshingGuilds}
                                                    <span class="uo-spin">&curvearrowright;</span>
                                                {:else}
                                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/></svg>
                                                {/if}
                                            </button>
                                            <button class="uo-diag-btn" on:click={loadDiagnostics} disabled={diagnosticsLoading} title={$t('userOptions.blocklist.diagnostics')}>
                                                {diagnosticsLoading ? '...' : '?'}
                                            </button>
                                        </div>
                                        <div class="uo-manual-guild-row">
                                            <input class="uo-scope-input" type="text" placeholder={$t('userOptions.blocklist.manualGuildPlaceholder')} bind:value={manualGuildIdInput[rk]} on:keydown={(e) => { if (e.key === 'Enter') resolveManualGuild(rk); }}>
                                            <button class="uo-resolve-btn" on:click={() => resolveManualGuild(rk)} disabled={isResolving[rk]}>
                                                {isResolving[rk] ? '...' : $t('userOptions.blocklist.resolve')}
                                            </button>
                                        </div>
                                    {:else if rule.scope_type === 'channel'}
                                        <select class="uo-scope-select" value="" on:change={(e) => loadChannelsForGuild(e.target.value)}>
                                            <option value="">{$t('userOptions.blocklist.selectPlaceholder')}</option>
                                            {#each guildList as g}
                                                <option value={g.id}>{g.name}</option>
                                            {/each}
                                        </select>
                                        <input class="uo-scope-input" type="text" placeholder={$t('userOptions.blocklist.channelIdPlaceholder')} value={rule.scope_id} on:input={(e) => updateRuleField(rk, 'scope_id', e.target.value)}>
                                    {:else if rule.scope_type === 'dm'}
                                        <input class="uo-scope-input" type="text" placeholder="User ID" value={rule.scope_id} on:input={(e) => updateRuleField(rk, 'scope_id', e.target.value)}>
                                    {/if}
                                </div>
                            </div>

                            <div class="uo-users-section">
                                <div class="uo-users-header">
                                    <span class="uo-users-count">{$t('userOptions.blocklist.users')} <strong>{Object.keys(rule.users || {}).length}</strong></span>
                                    {#if rule.scope_type === 'guild' && rule.scope_id}
                                        <div class="uo-member-search">
                                            <svg class="uo-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                                            <input type="text" placeholder={$t('userOptions.blocklist.searchMembers')} bind:value={memberSearchInput[rk]} on:keydown={(e) => { if (e.key === 'Enter') handleMemberSearch(rk, rule.scope_id); }}>
                                            <button class="uo-search-btn" on:click={() => handleMemberSearch(rk, rule.scope_id)} disabled={isSearching[rk]}>
                                                {isSearching[rk] ? '...' : $t('userOptions.blocklist.search')}
                                            </button>
                                        </div>
                                    {/if}
                                </div>

                                {#if searchError[rk]}
                                    <p class="uo-search-error">{searchError[rk]}</p>
                                {/if}
                                {#if searchResults[rk]?.length}
                                    <div class="uo-search-results">
                                        {#each searchResults[rk] as m}
                                            <button class="uo-search-result-item" on:click={() => selectSearchedMember(rk, m)}>
                                                <span class="uo-member-avatar">{m.display_name[0]}</span>
                                                <span class="uo-member-name">{m.display_name}</span>
                                                <span class="uo-member-id">@{m.username}</span>
                                            </button>
                                        {/each}
                                    </div>
                                {/if}

                                <div class="uo-user-grid">
                                    {#each Object.keys(rule.users || {}) as uk (uk)}
                                        {@const user = rule.users[uk]}
                                        <div class="uo-user-card">
                                            <div class="uo-user-card-top">
                                                <span class="uo-user-avatar">{user.user_display_name ? user.user_display_name[0] : '?'}</span>
                                                <div class="uo-user-ids">
                                                    <input class="uo-user-id-input" type="text" placeholder={$t('userPortrait.userId')} value={user.user_id} on:input={(e) => updateRuleUserField(rk, uk, 'user_id', e.target.value)}>
                                                    <input class="uo-user-name-input" type="text" placeholder={$t('userOptions.blocklist.displayName')} value={user.user_display_name} on:input={(e) => updateRuleUserField(rk, uk, 'user_display_name', e.target.value)}>
                                                </div>
                                                <button class="uo-user-remove" on:click={() => removeUserFromRule(rk, uk)} title={$t('userOptions.remove')}>
                                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M18 6L6 18M6 6l12 12"/></svg>
                                                </button>
                                            </div>
                                            {#if rule.mode === 'blacklist'}
                                                <div class="uo-user-blacklist-mode">
                                                    <label class="uo-radio-pill" class:active={user.blacklist_mode === 'deny_response'}>
                                                        <input type="radio" name={`bm-${uk}`} value="deny_response" checked={user.blacklist_mode === 'deny_response'} on:change={(e) => updateRuleUserField(rk, uk, 'blacklist_mode', e.target.value)}>
                                                        <span>{$t('userOptions.blocklist.denyResponse')}</span>
                                                    </label>
                                                    <label class="uo-radio-pill" class:active={user.blacklist_mode === 'block_messages'}>
                                                        <input type="radio" name={`bm-${uk}`} value="block_messages" checked={user.blacklist_mode === 'block_messages'} on:change={(e) => updateRuleUserField(rk, uk, 'blacklist_mode', e.target.value)}>
                                                        <span>{$t('userOptions.blocklist.blockMessages')}</span>
                                                    </label>
                                                    <label class="uo-radio-pill" class:active={user.blacklist_mode === 'negative_portrait'}>
                                                        <input type="radio" name={`bm-${uk}`} value="negative_portrait" checked={user.blacklist_mode === 'negative_portrait'} on:change={(e) => updateRuleUserField(rk, uk, 'blacklist_mode', e.target.value)}>
                                                        <span>{$t('userOptions.blocklist.negativePortrait')}</span>
                                                    </label>
                                                </div>
                                                {#if user.blacklist_mode === 'negative_portrait'}
                                                    <textarea class="uo-negative-portrait-input" rows="3" placeholder={$t('userOptions.blocklist.negativePortraitPlaceholder')} value={user.negative_portrait} on:input={(e) => updateRuleUserField(rk, uk, 'negative_portrait', e.target.value)}></textarea>
                                                {/if}
                                            {/if}
                                        </div>
                                    {/each}
                                </div>

                                <button class="uo-add-user-btn" on:click={() => addUserToRule(rk)}>
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
                                    {$t('userOptions.blocklist.addUser')}
                                </button>
                            </div>
                        </div>
                        {/each}
                    </div>
                    <button class="uo-add-rule-btn" on:click={addRule}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
                        {$t('userOptions.blocklist.addRule')}
                    </button>
                </Card>

            {:else if activeTab === 'guildPortrait'}
                <Card title={$t('scopedPrompts.guilds.title')}>
                    <p class="info">{$t('scopedPrompts.guilds.info')}</p>
                    <div class="list-container">
                        {#each $scopedPromptsObject.guilds as item (item._key)}
                        <div class="list-item complex-item">
                            <div class="list-item-main scoped-prompt-grid">
                                <div class="cell-id">
                                    <label>{$t('scopedPrompts.guilds.id')}</label>
                                    <input type="text" placeholder={$t('scopedPrompts.guilds.idPlaceholder')} value={item.id} on:blur={(e) => updateScopedId('guilds', item._key, e.target.value)}>
                                </div>
                                <div class="cell-toggle">
                                    <label class="toggle-switch">
                                        <input type="checkbox" checked={item.enabled} on:change={(e) => updateScopedField('guilds', item._key, 'enabled', e.target.checked)}>
                                        <span class="slider"></span>{$t('scopedPrompts.enabled')}
                                    </label>
                                </div>
                                <div class="cell-mode">
                                    <div class="group-label">{$t('scopedPrompts.mode.title')}</div>
                                    <div class="radio-group small">
                                        <label><input type="radio" name="mode-guilds-{item._key}" value='override' checked={item.mode==='override'} on:change={(e) => updateScopedField('guilds', item._key, 'mode', e.target.value)}> {$t('scopedPrompts.mode.override')}</label>
                                        <label><input type="radio" name="mode-guilds-{item._key}" value='append' checked={item.mode==='append'} on:change={(e) => updateScopedField('guilds', item._key, 'mode', e.target.value)}> {$t('scopedPrompts.mode.append')}</label>
                                    </div>
                                </div>
                                <div class="cell-prompt">
                                    <label>{$t('scopedPrompts.guilds.prompt')}</label>
                                    <textarea rows="3" placeholder={item.mode==='override' ? $t('scopedPrompts.guilds.overridePlaceholder') : $t('scopedPrompts.guilds.appendPlaceholder')} value={item.prompt} on:input={(e) => updateScopedField('guilds', item._key, 'prompt', e.target.value)}></textarea>
                                </div>
                            </div>
                            <button class="remove-btn" on:click={() => removeScopedItem('guilds', item._key)}>×</button>
                        </div>
                        {/each}
                    </div>
                    <button class="add-btn" on:click={() => addScopedItem('guilds')}>{$t('scopedPrompts.guilds.add')}</button>
                </Card>

            {:else if activeTab === 'channelPortrait'}
                <Card title={$t('scopedPrompts.channels.title')}>
                    <p class="info">{$t('scopedPrompts.channels.info')}</p>
                    <div class="list-container">
                        {#each $scopedPromptsObject.channels as item (item._key)}
                        <div class="list-item complex-item">
                            <div class="list-item-main scoped-prompt-grid">
                                <div class="cell-id">
                                    <label>{$t('scopedPrompts.channels.id')}</label>
                                    <input type="text" placeholder={$t('scopedPrompts.channels.idPlaceholder')} value={item.id} on:blur={(e) => updateScopedId('channels', item._key, e.target.value)}>
                                </div>
                                <div class="cell-toggle">
                                    <label class="toggle-switch">
                                        <input type="checkbox" checked={item.enabled} on:change={(e) => updateScopedField('channels', item._key, 'enabled', e.target.checked)}>
                                        <span class="slider"></span>{$t('scopedPrompts.enabled')}
                                    </label>
                                </div>
                                <div class="cell-mode">
                                    <div class="group-label">{$t('scopedPrompts.mode.title')}</div>
                                    <div class="radio-group small">
                                        <label><input type="radio" name="mode-channels-{item._key}" value='override' checked={item.mode==='override'} on:change={(e) => updateScopedField('channels', item._key, 'mode', e.target.value)}> {$t('scopedPrompts.mode.override')}</label>
                                        <label><input type="radio" name="mode-channels-{item._key}" value='append' checked={item.mode==='append'} on:change={(e) => updateScopedField('channels', item._key, 'mode', e.target.value)}> {$t('scopedPrompts.mode.append')}</label>
                                    </div>
                                </div>
                                <div class="cell-prompt">
                                    <label>{$t('scopedPrompts.channels.prompt')}</label>
                                    <textarea rows="3" placeholder={item.mode==='override' ? $t('scopedPrompts.channels.overridePlaceholder') : $t('scopedPrompts.channels.appendPlaceholder')} value={item.prompt} on:input={(e) => updateScopedField('channels', item._key, 'prompt', e.target.value)}></textarea>
                                </div>
                            </div>
                            <button class="remove-btn" on:click={() => removeScopedItem('channels', item._key)}>×</button>
                        </div>
                        {/each}
                    </div>
                    <button class="add-btn" on:click={() => addScopedItem('channels')}>{$t('scopedPrompts.channels.add')}</button>
                </Card>

            {:else if activeTab === 'rolePortrait'}
                <Card title={$t('roleConfig.title')}>
                    <p class="info">{$t('roleConfig.info')}</p>
                    <div class="list-container">
                        {#each $roleBasedConfigArray as role (role._key)}
                        <div class="list-item complex-item">
                            <div class="list-item-main very-wide-grid">
                                <input class="id-input" type="text" placeholder={$t('roleConfig.roleId')} value={role.id} on:blur={(e) => updateRoleId(role._key, e.target.value)}>
                                <input class="nickname-input" type="text" placeholder={$t('roleConfig.roleTitle')} value={role.title} on:input={(e) => updateRoleField(role._key, 'title', e.target.value)}>
                                <textarea class="prompt-input" rows="3" placeholder={$t('roleConfig.rolePrompt')} value={role.prompt} on:input={(e) => updateRoleField(role._key, 'prompt', e.target.value)}></textarea>
                                <div class="limit-control-group">
                                    <label class="toggle-switch"><input type="checkbox" checked={role.enable_message_limit} on:change={(e) => updateRoleField(role._key, 'enable_message_limit', e.target.checked)}><span class="slider"></span>{$t('roleConfig.enableMsgLimit')}</label>
                                    <div class="limit-group" class:disabled={!role.enable_message_limit}>
                                        <div class="group-label">{$t('roleConfig.totalQuota')}:</div>
                                        <input type="number" min="0" placeholder="0" disabled={!role.enable_message_limit} value={role.message_limit} on:input={(e) => updateRoleField(role._key, 'message_limit', e.target.value)}>
                                        <span>/</span>
                                        <input type="number" min="1" placeholder="60" disabled={!role.enable_message_limit} value={role.message_refresh_minutes} on:input={(e) => updateRoleField(role._key, 'message_refresh_minutes', e.target.value)}>
                                        <span class="unit">{$t('roleConfig.minutes')}</span>
                                    </div>
                                </div>
                                <div class="limit-control-group">
                                    <label class="toggle-switch"><input type="checkbox" checked={role.enable_char_limit} on:change={(e) => updateRoleField(role._key, 'enable_char_limit', e.target.checked)}><span class="slider"></span>{$t('roleConfig.enableTokenLimit')}</label>
                                    <div class="limit-group" class:disabled={!role.enable_char_limit}>
                                        <div class="group-label">{$t('roleConfig.totalQuota')}:</div>
                                        <input type="number" min="0" placeholder="0" disabled={!role.enable_char_limit} value={role.char_limit} on:input={(e) => updateRoleField(role._key, 'char_limit', e.target.value)}>
                                        <span>/</span>
                                        <input type="number" min="1" placeholder="60" disabled={!role.enable_char_limit} value={role.char_refresh_minutes} on:input={(e) => updateRoleField(role._key, 'char_refresh_minutes', e.target.value)}>
                                        <span class="unit">{$t('roleConfig.minutes')}</span>
                                    </div>
                                </div>
                                <div class="setting-row">
                                    <label>{$t('roleConfig.displayColor')}</label>
                                    <input type="color" value={role.display_color} on:input={(e) => updateRoleField(role._key, 'display_color', e.target.value)}>
                                </div>
                            </div>
                            <button class="remove-btn" on:click={() => removeRoleConfig(role._key)}>×</button>
                        </div>
                        {/each}
                    </div>
                    <button class="add-btn" on:click={addRoleConfig}>{$t('roleConfig.add')}</button>
                </Card>
            {/if}
        </div>
    {/if}
</div>

{#if showDiagnostics && diagnosticsData}
    <div class="uo-modal-overlay" on:click|self={() => showDiagnostics = false}>
        <div class="uo-modal">
            <div class="uo-modal-header">
                <h3>{$t('userOptions.blocklist.diagnosticsTitle')}</h3>
                <button class="uo-modal-close" on:click={() => showDiagnostics = false}>&times;</button>
            </div>
            <div class="uo-modal-body">
                <div class="uo-diag-row">
                    <span class="uo-diag-label">{$t('userOptions.blocklist.diagOnline')}</span>
                    <span class="uo-diag-value" class:uo-diag-ok={diagnosticsData.online} class:uo-diag-err={!diagnosticsData.online}>
                        {diagnosticsData.online ? $t('userOptions.blocklist.diagYes') : $t('userOptions.blocklist.diagNo')}
                    </span>
                </div>
                <div class="uo-diag-row">
                    <span class="uo-diag-label">{$t('userOptions.blocklist.diagGuildCount')}</span>
                    <span class="uo-diag-value">{diagnosticsData.guild_count}</span>
                </div>
                {#each Object.entries(diagnosticsData.intents || {}) as [intent, enabled]}
                    <div class="uo-diag-row">
                        <span class="uo-diag-label">Intent: {intent}</span>
                        <span class="uo-diag-value" class:uo-diag-ok={enabled} class:uo-diag-err={!enabled}>
                            {enabled ? $t('userOptions.blocklist.diagEnabled') : $t('userOptions.blocklist.diagDisabled')}
                        </span>
                    </div>
                {/each}
                {#if diagnosticsData.warnings && diagnosticsData.warnings.length}
                    <div class="uo-diag-warnings">
                        <strong>{$t('userOptions.blocklist.diagWarnings')}:</strong>
                        {#each diagnosticsData.warnings as w}
                            <p class="uo-warning-text">&#9888; {w}</p>
                        {/each}
                    </div>
                {/if}
            </div>
        </div>
    </div>
{/if}

<style>
    .user-options-panel {
        padding: 1rem 1.5rem;
        overflow-y: auto;
        flex: 1;
        min-height: 0;
        box-sizing: border-box;
    }
    .config-header {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 1rem; flex-shrink: 0; overflow: hidden; min-width: 0;
    }
    .config-header h2 {
        margin:0; font-size:1.2rem; color:var(--text-color); padding:.6rem 1rem;
        border-radius:10px; background:linear-gradient(135deg, rgba(31,139,214,.1), rgba(24,138,81,.08));
        border:1px solid rgba(15,23,42,.08); box-shadow:var(--shadow-soft); flex:1;
        min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    }
    .save-btn {
        padding:.6rem 1.4rem; background:linear-gradient(135deg, var(--save-color), #1a9156);
        color:#fff; font-size:.95rem; font-weight:600; border-radius:10px; flex-shrink:0;
    }
    .save-btn:disabled { opacity:.6; cursor:not-allowed; }
    .header-actions { display:flex; align-items:center; gap:.5rem; flex-shrink:0; }
    .tabs {
        display:flex; gap:.15rem; margin-bottom:1rem; background:var(--panel-muted-bg);
        border-radius:6px; padding:.15rem; flex-shrink:0; overflow-x:auto;
    }
    .tabs button {
        background:transparent; border:none; color:var(--text-light); padding:.35rem .75rem;
        font-size:.82rem; border-radius:4px; cursor:pointer; white-space:nowrap; box-shadow:none;
        transition:all .2s ease;
    }
    .tabs button:hover { color:var(--text-color); background:var(--panel-hover-bg); }
    .tabs button.active { background:linear-gradient(135deg, var(--primary-color), #0f6fb2); color:#fff; }
    .tab-content { min-height: 0; display: flex; flex-direction: column; gap: 1.25rem; }
    .uo-top-controls { display: flex; align-items: center; gap: 2rem; flex-wrap: wrap; }
    .uo-timeout-row { display: flex; align-items: center; gap: .4rem; font-size: .82rem; color: var(--text-light); }
    .uo-timeout-row input { width: 80px; padding: .25rem .4rem; text-align: center; font-size: .8rem; border: 1px solid var(--floating-border); border-radius: 5px; background: var(--surface-tint); color: var(--text-color); }
    .uo-timeout-row input:focus { outline: none; border-color: var(--primary-color); box-shadow: 0 0 0 2px rgba(31,139,214,.15); }
    .unit-label { font-size: .75rem; }

    /* === Rule Cards === */
    .uo-rules-container { display: flex; flex-direction: column; gap: 1rem; }
    .uo-rule-card {
        background: var(--card-bg);
        border-radius: 12px;
        border: 1px solid var(--floating-border);
        overflow: hidden;
        transition: border-color .2s, box-shadow .2s;
    }
    .uo-rule-card:hover { border-color: rgba(31,139,214,.3); box-shadow: 0 2px 12px rgba(15,23,42,.06); }
    .uo-rule-blacklist { border-left: 4px solid #ef4444; }
    .uo-rule-whitelist { border-left: 4px solid #22c55e; }

    .uo-rule-topbar {
        display: flex; align-items: center; gap: .6rem; padding: .6rem .85rem;
        background: var(--panel-muted-bg); border-bottom: 1px solid var(--floating-border);
    }
    .uo-rule-index { font-size: .72rem; font-weight: 700; color: var(--text-light); min-width: 1.2rem; }
    .uo-scope-badge {
        font-size: .7rem; font-weight: 600; padding: .15rem .55rem; border-radius: 20px;
        letter-spacing: .02em; text-transform: uppercase;
    }
    .uo-scope-global { background: rgba(147,51,234,.12); color: #a78bfa; }
    .uo-scope-guild { background: rgba(37,99,235,.12); color: #60a5fa; }
    .uo-scope-channel { background: rgba(8,145,178,.12); color: #22d3ee; }
    .uo-scope-dm { background: rgba(217,119,6,.12); color: #fbbf24; }
    .uo-scope-detail {
        font-size: .78rem; color: var(--text-light); background: var(--panel-muted-bg);
        padding: .15rem .5rem; border-radius: 4px; font-family: monospace; max-width: 180px;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .uo-rule-spacer { flex: 1; }

    .uo-mode-segmented {
        display: inline-flex; background: var(--panel-muted-bg); border-radius: 7px; padding: 2px; gap: 1px;
    }
    .uo-mode-segmented.small { border-radius: 5px; }
    .uo-seg-btn {
        border: none; background: transparent; padding: .3rem .65rem; font-size: .75rem;
        font-weight: 500; border-radius: 5px; cursor: pointer; color: var(--text-light);
        transition: all .18s; display: flex; align-items: center; gap: .3rem; white-space: nowrap;
        box-shadow: none;
    }
    .uo-mode-segmented.small .uo-seg-btn { padding: .2rem .5rem; font-size: .72rem; }
    .uo-seg-btn:hover { color: var(--text-color); background: rgba(127,127,127,.1); }
    .uo-seg-btn.active { background: var(--card-bg); color: var(--text-color); box-shadow: var(--shadow-soft); }
    .uo-seg-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
    .blacklist-dot { background: #ef4444; }
    .whitelist-dot { background: #22c55e; }

    .uo-rule-remove-btn {
        background: transparent; border: none; color: var(--text-light); cursor: pointer;
        padding: .3rem; border-radius: 6px; transition: all .15s; display: flex; align-items: center; box-shadow: none;
    }
    .uo-rule-remove-btn:hover { background: rgba(239,68,68,.1); color: #ef4444; }

    .uo-rule-body { padding: .6rem .85rem; }
    .uo-whitelist-control { display: flex; align-items: center; gap: .5rem; margin-bottom: .5rem; }
    .uo-sub-label { font-size: .78rem; font-weight: 500; color: var(--text-light); white-space: nowrap; }

    .uo-scope-editor { display: flex; gap: .4rem; flex-wrap: wrap; }
    .uo-scope-select, .uo-scope-input {
        padding: .3rem .45rem; font-size: .78rem; border: 1px solid var(--floating-border);
        border-radius: 5px; background: var(--surface-tint); color: var(--text-color);
    }
    .uo-scope-select { min-width: 120px; }
    .uo-scope-input { min-width: 160px; }
    .uo-scope-select:focus, .uo-scope-input:focus { outline: none; border-color: var(--primary-color); box-shadow: 0 0 0 2px rgba(31,139,214,.12); }

    /* Users section */
    .uo-users-section { padding: .7rem .85rem; border-top: 1px solid var(--floating-border); }
    .uo-users-header { display: flex; align-items: center; justify-content: space-between; gap: .75rem; margin-bottom: .6rem; flex-wrap: wrap; }
    .uo-users-count { font-size: .82rem; color: var(--text-color); font-weight: 600; }
    .uo-users-count strong { color: var(--primary-color); }
    .uo-member-search { display: flex; align-items: center; gap: .3rem; background: var(--surface-tint); border: 1px solid var(--floating-border); border-radius: 7px; padding: .15rem .35rem; }
    .uo-member-search:focus-within { border-color: var(--primary-color); box-shadow: 0 0 0 2px rgba(31,139,214,.12); }
    .uo-search-icon { color: var(--text-light); flex-shrink: 0; }
    .uo-member-search input { border: none; background: transparent; font-size: .78rem; outline: none; flex: 1; min-width: 120px; color: var(--text-color); padding: .2rem 0; }
    .uo-search-btn {
        border: none; background: var(--primary-color); color: #fff; font-size: .72rem; font-weight: 500;
        padding: .2rem .55rem; border-radius: 5px; cursor: pointer; white-space: nowrap; box-shadow: none;
        transition: opacity .15s;
    }
    .uo-search-btn:disabled { opacity: .5; cursor: not-allowed; }
    .uo-search-error { color: #ef4444; font-size: .72rem; margin: .2rem 0; }
    .uo-search-results {
        display: flex; flex-direction: column; gap: 2px; max-height: 160px; overflow-y: auto;
        background: var(--card-bg); border: 1px solid var(--floating-border); border-radius: 7px; margin-bottom: .5rem;
    }
    .uo-search-result-item {
        display: flex; align-items: center; gap: .45rem; padding: .4rem .55rem; border: none;
        background: transparent; cursor: pointer; font-size: .78rem; color: var(--text-color);
        transition: background .12s; width: 100%; text-align: left; box-shadow: none;
    }
    .uo-search-result-item:hover { background: var(--panel-hover-bg); }
    .uo-member-avatar {
        width: 26px; height: 26px; border-radius: 50%; background: var(--primary-color);
        color: #fff; display: flex; align-items: center; justify-content: center;
        font-size: .72rem; font-weight: 600; flex-shrink: 0;
    }
    .uo-search-result-item .uo-member-avatar { width: 22px; height: 22px; font-size: .65rem; }
    .uo-member-name { font-weight: 500; }
    .uo-member-id { color: var(--text-light); font-size: .7rem; }

    .uo-user-grid { display: flex; flex-direction: column; gap: .45rem; margin-bottom: .6rem; }
    .uo-user-card {
        background: var(--surface-tint); border: 1px solid var(--floating-border); border-radius: 8px;
        padding: .55rem .65rem; transition: border-color .15s;
    }
    .uo-user-card:hover { border-color: rgba(31,139,214,.25); }
    .uo-user-card-top { display: flex; align-items: center; gap: .5rem; }
    .uo-user-avatar {
        width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, var(--primary-color), #0f6fb2);
        color: #fff; display: flex; align-items: center; justify-content: center;
        font-size: .78rem; font-weight: 700; flex-shrink: 0;
    }
    .uo-user-ids { display: flex; flex-direction: column; gap: 2px; flex: 1; min-width: 0; }
    .uo-user-id-input, .uo-user-name-input {
        border: 1px solid transparent; background: transparent; font-size: .78rem;
        padding: .15rem .3rem; border-radius: 4px; width: 100%; box-sizing: border-box; color: var(--text-color);
        transition: border-color .15s, background .15s;
    }
    .uo-user-id-input { font-family: monospace; color: var(--text-light); font-size: .72rem; }
    .uo-user-id-input:hover, .uo-user-name-input:hover { background: var(--panel-muted-bg); }
    .uo-user-id-input:focus, .uo-user-name-input:focus {
        outline: none; border-color: var(--primary-color); background: var(--panel-muted-bg);
    }
    .uo-user-remove {
        background: transparent; border: none; color: var(--text-light); cursor: pointer;
        padding: .25rem; border-radius: 4px; flex-shrink: 0; box-shadow: none; transition: all .12s;
    }
    .uo-user-remove:hover { background: rgba(239,68,68,.1); color: #ef4444; }

    .uo-user-blacklist-mode { display: flex; gap: .25rem; margin-top: .45rem; flex-wrap: wrap; }
    .uo-radio-pill { position: relative; }
    .uo-radio-pill input { position: absolute; opacity: 0; width: 0; height: 0; }
    .uo-radio-pill span {
        display: block; padding: .2rem .55rem; font-size: .72rem; border-radius: 5px;
        cursor: pointer; border: 1px solid var(--floating-border); background: var(--panel-muted-bg);
        color: var(--text-light); transition: all .15s; white-space: nowrap;
    }
    .uo-radio-pill:hover span { border-color: var(--primary-color); opacity: .8; }
    .uo-radio-pill.active span { background: rgba(31,139,214,.12); border-color: var(--primary-color); color: var(--primary-color); font-weight: 500; }

    .uo-negative-portrait-input {
        margin-top: .4rem; width: 100%; box-sizing: border-box; padding: .35rem .45rem;
        font-size: .78rem; border: 1px solid var(--floating-border); border-radius: 5px;
        resize: vertical; min-height: 48px; color: var(--text-color); background: var(--panel-muted-bg);
        font-family: inherit;
    }
    .uo-negative-portrait-input:focus { outline: none; border-color: var(--primary-color); box-shadow: 0 0 0 2px rgba(31,139,214,.1); }

    .uo-add-user-btn {
        display: inline-flex; align-items: center; gap: .3rem; border: 1px dashed var(--floating-border);
        background: transparent; color: var(--primary-color); font-size: .75rem; font-weight: 500;
        padding: .3rem .7rem; border-radius: 6px; cursor: pointer; transition: all .15s; box-shadow: none;
    }
    .uo-add-user-btn:hover { background: var(--panel-hover-bg); border-color: var(--primary-color); }

    .uo-add-rule-btn {
        display: inline-flex; align-items: center; gap: .35rem; margin-top: .75rem;
        border: 2px dashed var(--floating-border); background: transparent; color: var(--primary-color);
        font-size: .82rem; font-weight: 600; padding: .5rem 1.2rem; border-radius: 8px; cursor: pointer;
        transition: all .15s; box-shadow: none;
    }
    .uo-add-rule-btn:hover { background: var(--panel-hover-bg); border-color: var(--primary-color); }

    .uo-radio-pill input:focus-visible + span { box-shadow: 0 0 0 2px rgba(31,139,214,.3); }
    .scoped-prompt-grid { display:grid; grid-template-columns:1fr; gap:.35rem; }
    .scoped-prompt-grid .cell-id label,
    .scoped-prompt-grid .cell-prompt label { font-size:.75rem; color:var(--text-light); display:block; margin-bottom:.1rem; }
    .add-btn {
        margin-top:.5rem; padding:.4rem 1rem; font-size:.82rem;
        background:var(--panel-muted-bg); color:var(--primary-color); border:1px dashed var(--floating-border);
        border-radius:4px; cursor:pointer; box-shadow:none;
    }
    .add-btn:hover { background:var(--panel-hover-bg); }
    .remove-btn {
        background:transparent; border:none; color:var(--danger-color); font-size:1.2rem;
        cursor:pointer; padding:.1rem .3rem; box-shadow:none;
    }
    .info { font-size:.82rem; color:var(--text-light); margin-bottom:.75rem; line-height:1.5; }
    .group-label { font-size:.82rem; color:var(--text-color); font-weight:600; margin:.3rem 0 .2rem; }
    .radio-group { display:flex; gap:1rem; flex-wrap:wrap; }
    .radio-group.small { gap:.5rem; }
    .radio-group label { display:flex; align-items:center; gap:.3rem; font-size:.82rem; cursor:pointer; }
    .limit-control-group { margin:.3rem 0; }
    .limit-group { display:flex; align-items:center; gap:.35rem; margin-left:1rem; }
    .limit-group.disabled { opacity:.5; pointer-events:none; }
    .limit-group .group-label { margin:0; font-size:.78rem; }
    .limit-group input { width:60px; padding:.2rem .3rem; font-size:.78rem; }
    .limit-group .unit { font-size:.75rem; color:var(--text-light); }
    .loading-state, .error-state, .empty-state { padding:2rem; text-align:center; color:var(--text-light); }

    .uo-guild-warning {
        background: rgba(234,179,8,.1); border: 1px solid rgba(234,179,8,.3);
        border-radius: 6px; padding: .55rem .75rem; margin-bottom: .75rem;
        font-size: .78rem; color: var(--text-color); display: flex; align-items: center;
        gap: .4rem;
    }
    .uo-warning-icon { font-size: 1rem; }
    .uo-inline-link { background: none; border: none; color: var(--primary-color); cursor: pointer; font-size: .78rem; text-decoration: underline; padding: 0; box-shadow: none; }

    .uo-guild-row { display: flex; align-items: center; gap: .3rem; }
    .uo-guild-row .uo-scope-select { flex: 1; }
    .uo-refresh-btn, .uo-diag-btn {
        display: inline-flex; align-items: center; justify-content: center;
        width: 28px; height: 28px; border: 1px solid var(--floating-border);
        border-radius: 4px; background: var(--panel-muted-bg); color: var(--text-light);
        cursor: pointer; padding: 0; box-shadow: none; transition: all .15s;
    }
    .uo-refresh-btn:hover, .uo-diag-btn:hover { background: var(--panel-hover-bg); color: var(--text-color); }
    .uo-refresh-btn:disabled, .uo-diag-btn:disabled { opacity: .5; cursor: not-allowed; }
    .uo-diag-btn { font-size: .85rem; font-weight: 700; }

    .uo-manual-guild-row { display: flex; align-items: center; gap: .3rem; margin-top: .3rem; }
    .uo-manual-guild-row .uo-scope-input { flex: 1; }
    .uo-resolve-btn {
        padding: .25rem .55rem; font-size: .72rem; border: 1px solid var(--floating-border);
        border-radius: 4px; background: var(--panel-muted-bg); color: var(--text-color);
        cursor: pointer; box-shadow: none; transition: all .15s; white-space: nowrap;
    }
    .uo-resolve-btn:hover { background: var(--panel-hover-bg); border-color: var(--primary-color); }
    .uo-resolve-btn:disabled { opacity: .5; cursor: not-allowed; background: var(--panel-muted-bg); }

    .uo-modal-overlay {
        position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 1000;
        display: flex; align-items: center; justify-content: center;
    }
    .uo-modal {
        background: var(--card-bg); border: 1px solid var(--floating-border);
        border-radius: 10px; width: 90%; max-width: 420px; max-height: 80vh;
        overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,.3);
    }
    .uo-modal-header {
        display: flex; justify-content: space-between; align-items: center;
        padding: .75rem 1rem; border-bottom: 1px solid var(--floating-border);
    }
    .uo-modal-header h3 { margin: 0; font-size: .95rem; color: var(--text-color); }
    .uo-modal-close {
        background: none; border: none; color: var(--text-light); font-size: 1.3rem;
        cursor: pointer; padding: 0 .2rem; line-height: 1; box-shadow: none;
    }
    .uo-modal-close:hover { color: var(--danger-color); }
    .uo-modal-body { padding: .75rem 1rem; }
    .uo-diag-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: .35rem 0; border-bottom: 1px solid var(--floating-border);
        font-size: .8rem;
    }
    .uo-diag-label { color: var(--text-light); }
    .uo-diag-value { font-weight: 600; color: var(--text-color); }
    .uo-diag-ok { color: #22c55e; }
    .uo-diag-err { color: var(--danger-color); }
    .uo-diag-warnings { margin-top: .5rem; padding: .5rem; background: rgba(234,179,8,.08); border-radius: 4px; }
    .uo-diag-warnings strong { font-size: .78rem; color: var(--text-color); }
    .uo-warning-text { font-size: .76rem; color: #eab308; margin: .2rem 0 0; }
    .uo-spin { display: inline-block; animation: uoSpin 1s linear infinite; font-size: 1.1rem; }
    @keyframes uoSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
