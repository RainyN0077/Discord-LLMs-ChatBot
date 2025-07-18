<script>
    import { t } from '../i18n.js';
    import { simulateDebug } from '../lib/api.js';
    import Card from '../components/Card.svelte';
    import { roleBasedConfigArray, showStatus } from '../lib/stores.js';

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
</script>

<div class="debugger-container">
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
</div>

<style>
    .debugger-container { max-width: 900px; margin: 2rem auto; display: flex; flex-direction: column; gap: 2rem;}
    .debugger-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem 1.5rem; align-items: center; }
    .message-input { grid-column: 1 / -1; }
    .action-btn { margin-top: 1rem; }
    .result-box { background-color: #f7f9fc; border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem; font-family: monospace; white-space: pre-wrap; word-break: break-all; max-height: 400px; overflow-y: auto; }
    .result-box.response { font-family: inherit; white-space: normal;}
</style>
