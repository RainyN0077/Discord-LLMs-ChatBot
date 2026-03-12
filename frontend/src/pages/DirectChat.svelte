<script>
    import { tick } from 'svelte';
    import { t } from '../i18n.js';
    import { coreConfig } from '../lib/stores.js';
    import { directChat } from '../lib/api.js';

    let includeSystemPrompt = true;
    let inputText = '';
    let isSending = false;
    let errorMessage = '';
    let usageText = '';
    let messages = [];
    let messagesContainer;

    function clearChat() {
        messages = [];
        inputText = '';
        errorMessage = '';
        usageText = '';
    }

    async function scrollToBottom() {
        await tick();
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    async function sendMessage() {
        const content = inputText.trim();
        if (!content || isSending) return;

        errorMessage = '';
        usageText = '';
        messages = [...messages, { role: 'user', content }];
        inputText = '';
        await scrollToBottom();

        isSending = true;
        try {
            const payloadMessages = messages.map((m) => ({ role: m.role, content: m.content }));
            const result = await directChat(payloadMessages, includeSystemPrompt);
            const assistantReply = (result?.response || '').trim();
            messages = [...messages, { role: 'assistant', content: assistantReply || '...' }];

            if (result?.usage) {
                const inputTokens = result.usage.input_tokens ?? 0;
                const outputTokens = result.usage.output_tokens ?? 0;
                usageText = `${$t('directChat.usage')}: in ${inputTokens} / out ${outputTokens}`;
            }
        } catch (e) {
            errorMessage = `${$t('directChat.sendFailed')}${e.message}`;
        } finally {
            isSending = false;
            await scrollToBottom();
        }
    }

    function onInputKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }
</script>

<div class="chat-page">
    <div class="page-head">
        <h1>{$t('directChat.title')}</h1>
        <div class="meta">
            <span>{$t('directChat.provider')}: <strong>{$coreConfig.llm_provider}</strong></span>
            <span>{$t('directChat.model')}: <strong>{$coreConfig.model_name || '-'}</strong></span>
        </div>
    </div>

    <div class="toolbar">
        <label class="checkbox">
            <input type="checkbox" bind:checked={includeSystemPrompt} />
            {$t('directChat.includeSystemPrompt')}
        </label>
        <button class="secondary" on:click={clearChat}>{$t('directChat.clear')}</button>
    </div>

    <div class="messages" bind:this={messagesContainer}>
        {#if messages.length === 0}
            <div class="empty">{$t('directChat.empty')}</div>
        {/if}
        {#each messages as m, idx (idx)}
            <div class="msg {m.role}">
                <div class="role">{m.role === 'assistant' ? $t('directChat.assistant') : $t('directChat.you')}</div>
                <pre>{m.content}</pre>
            </div>
        {/each}
    </div>

    {#if errorMessage}
        <div class="error">{errorMessage}</div>
    {/if}
    {#if usageText}
        <div class="usage">{usageText}</div>
    {/if}

    <div class="composer">
        <textarea
            rows="3"
            bind:value={inputText}
            on:keydown={onInputKeydown}
            placeholder={$t('directChat.inputPlaceholder')}
            disabled={isSending}
        ></textarea>
        <button on:click={sendMessage} disabled={isSending || !inputText.trim()}>
            {isSending ? $t('directChat.sending') : $t('directChat.send')}
        </button>
    </div>
</div>

<style>
    .chat-page {
        max-width: 1100px;
        margin: 0 auto;
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }
    .page-head h1 {
        margin: .2rem 0 .2rem;
    }
    .meta {
        display: flex;
        gap: 1rem;
        color: var(--text-light);
        font-size: .92rem;
    }
    .toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        background: #fff;
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: .7rem .9rem;
    }
    .messages {
        min-height: 420px;
        max-height: calc(100vh - 300px);
        overflow: auto;
        background: #fff;
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: .9rem;
        display: flex;
        flex-direction: column;
        gap: .8rem;
    }
    .empty {
        color: var(--text-light);
    }
    .msg {
        border-radius: 12px;
        padding: .7rem .8rem;
    }
    .msg.user {
        background: rgba(31, 139, 214, .1);
        border: 1px solid rgba(31, 139, 214, .22);
    }
    .msg.assistant {
        background: rgba(24, 138, 81, .1);
        border: 1px solid rgba(24, 138, 81, .22);
    }
    .role {
        font-size: .78rem;
        color: var(--text-light);
        margin-bottom: .35rem;
    }
    pre {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        font-family: inherit;
        line-height: 1.5;
    }
    .composer {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: .7rem;
    }
    textarea {
        resize: vertical;
    }
    button.secondary {
        background: rgba(15, 23, 42, .07);
        color: var(--text-color);
    }
    .error {
        color: var(--error-text);
        background: var(--error-bg);
        border: 1px solid rgba(194, 24, 91, .2);
        border-radius: 10px;
        padding: .7rem .9rem;
    }
    .usage {
        color: var(--text-light);
        font-size: .9rem;
    }
    @media (max-width: 900px) {
        .composer {
            grid-template-columns: 1fr;
        }
        .meta {
            flex-direction: column;
            gap: .2rem;
        }
    }
</style>
