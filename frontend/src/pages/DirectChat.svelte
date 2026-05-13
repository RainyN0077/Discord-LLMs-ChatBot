<script>
    import { tick } from 'svelte';
    import { t } from '../i18n.js';
    import { coreConfig } from '../lib/stores.js';
    import { directChat, fetchDebugCaptures, fetchDebugCaptureDetail, sanitizeDebugText } from '../lib/api.js';

    let activeSection = 'chat';
    let includeSystemPrompt = true;
    let debugMode = false;
    let debugContext = {
        user_id: '100000000000000001',
        channel_id: '100000000000000002',
        guild_id: '',
        role_id: ''
    };
    let inputText = '';
    let isSending = false;
    let errorMessage = '';
    let usageText = '';
    let messages = [];
    let messagesContainer;
    let captureError = '';
    let captures = [];
    let isLoadingCaptures = false;
    let selectedCapture = null;
    let captureChannelFilter = '';
    let captureLimit = 30;
    let sanitizeInput = '';
    let sanitizeOutput = '';
    let isSanitizing = false;
    let pendingFiles = [];
    let fileInput;

    function clearChat() {
        messages = [];
        inputText = '';
        errorMessage = '';
        usageText = '';
        pendingFiles = [];
        if (fileInput) fileInput.value = '';
    }

    async function scrollToBottom() {
        await tick();
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    async function sendMessage() {
        const content = inputText.trim();
        const attachments = pendingFiles.map((file) => ({ ...file }));
        if ((!content && attachments.length === 0) || isSending) return;

        errorMessage = '';
        usageText = '';
        messages = [...messages, { role: 'user', content, attachmentNames: attachments.map((file) => file.name) }];
        inputText = '';
        pendingFiles = [];
        if (fileInput) fileInput.value = '';
        await scrollToBottom();

        isSending = true;
        try {
            const payloadMessages = messages.map((m) => ({ role: m.role, content: m.content }));
            const result = await directChat(
                payloadMessages,
                attachments,
                includeSystemPrompt,
                debugMode,
                debugMode ? debugContext : null
            );
            const assistantReply = (result?.response || '').trim();
            const formattedUserMessages = Array.isArray(result?.formatted_user_messages) ? result.formatted_user_messages : [];
            const latestFormattedInput = formattedUserMessages.length > 0 ? formattedUserMessages[formattedUserMessages.length - 1] : '';
            const debugUserDetails = Array.isArray(result?.debug_user_details) ? result.debug_user_details : [];
            const latestDebugDetail = debugUserDetails.length > 0 ? debugUserDetails[debugUserDetails.length - 1] : null;
            messages = [
                ...messages,
                {
                    role: 'assistant',
                    content: assistantReply || '...',
                    debugFormattedInput: debugMode ? (latestDebugDetail?.formatted_content || latestFormattedInput) : '',
                    debugOcrOutput: debugMode ? (latestDebugDetail?.ocr_output || '') : '',
                    debugAttachmentContext: debugMode ? (latestDebugDetail?.attachment_context || '') : '',
                    debugAttachmentNames: debugMode ? (latestDebugDetail?.attachment_names || []) : [],
                    debugUsedMultimodalImages: debugMode ? !!latestDebugDetail?.used_multimodal_images : false
                }
            ];

            if (result?.usage) {
                const inputTokens = result.usage.input_tokens ?? 0;
                const outputTokens = result.usage.output_tokens ?? 0;
                usageText = `${$t('directChat.usage')}: in ${inputTokens} / out ${outputTokens}`;
            }
        } catch (e) {
            errorMessage = `${$t('directChat.sendFailed')}${e.message}`;
            pendingFiles = attachments;
        } finally {
            isSending = false;
            await scrollToBottom();
        }
    }

    function readFileAsDataUrl(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ''));
            reader.onerror = () => reject(new Error(`Failed to read file: ${file.name}`));
            reader.readAsDataURL(file);
        });
    }

    async function handleFileChange(event) {
        const files = Array.from(event.target.files || []);
        if (files.length === 0) return;

        try {
            const decodedFiles = await Promise.all(files.map(async (file) => {
                const dataUrl = await readFileAsDataUrl(file);
                const data_base64 = dataUrl.includes(',') ? dataUrl.split(',', 2)[1] : dataUrl;
                return {
                    name: file.name,
                    content_type: file.type || 'application/octet-stream',
                    size: file.size,
                    data_base64
                };
            }));
            pendingFiles = [...pendingFiles, ...decodedFiles];
        } catch (e) {
            errorMessage = `${$t('directChat.sendFailed')}${e.message}`;
        } finally {
            if (fileInput) fileInput.value = '';
        }
    }

    function removePendingFile(index) {
        pendingFiles = pendingFiles.filter((_, currentIndex) => currentIndex !== index);
    }

    function openFilePicker() {
        fileInput?.click();
    }

    function onInputKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }

    async function loadCaptures() {
        isLoadingCaptures = true;
        captureError = '';
        selectedCapture = null;
        try {
            captures = await fetchDebugCaptures(captureLimit, captureChannelFilter);
        } catch (e) {
            captureError = `${$t('directChat.captureLoadFailed')}${e.message}`;
        } finally {
            isLoadingCaptures = false;
        }
    }

    async function openCapture(captureId) {
        captureError = '';
        try {
            selectedCapture = await fetchDebugCaptureDetail(captureId);
        } catch (e) {
            captureError = `${$t('directChat.captureDetailFailed')}${e.message}`;
        }
    }

    function useCaptureInput() {
        if (!selectedCapture?.raw_user_message) return;
        activeSection = 'chat';
        inputText = selectedCapture.raw_user_message;
    }

    function openCaptureSection() {
        activeSection = 'capture';
        loadCaptures();
    }

    async function runSanitizeTest() {
        isSanitizing = true;
        captureError = '';
        try {
            const result = await sanitizeDebugText(sanitizeInput);
            sanitizeOutput = result?.sanitized_text || '';
        } catch (e) {
            captureError = `${$t('directChat.sanitizeFailed')}${e.message}`;
        } finally {
            isSanitizing = false;
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
        <div class="section-switcher">
            <button class:active={activeSection === 'chat'} on:click={() => activeSection = 'chat'}>{$t('directChat.chatTab')}</button>
            <button class:active={activeSection === 'capture'} on:click={openCaptureSection}>{$t('directChat.captureTab')}</button>
        </div>
        <label class="checkbox">
            <input type="checkbox" bind:checked={includeSystemPrompt} disabled={debugMode} />
            {$t('directChat.includeSystemPrompt')}
        </label>
        <label class="checkbox">
            <input type="checkbox" bind:checked={debugMode} />
            {$t('directChat.debugMode')}
        </label>
        <button class="secondary" on:click={clearChat}>{$t('directChat.clear')}</button>
    </div>

    {#if activeSection === 'chat' && debugMode}
        <div class="debug-panel">
            <div class="debug-hint">{$t('directChat.debugHint')}</div>
            <div class="debug-grid">
                <input type="text" bind:value={debugContext.user_id} placeholder={$t('directChat.debugUserId')} />
                <input type="text" bind:value={debugContext.channel_id} placeholder={$t('directChat.debugChannelId')} />
                <input type="text" bind:value={debugContext.guild_id} placeholder={$t('directChat.debugGuildId')} />
                <input type="text" bind:value={debugContext.role_id} placeholder={$t('directChat.debugRoleId')} />
            </div>
        </div>
    {/if}

    {#if activeSection === 'chat'}
        <div class="messages" bind:this={messagesContainer}>
            {#if messages.length === 0}
                <div class="empty">{$t('directChat.empty')}</div>
            {/if}
            {#each messages as m, idx (idx)}
                <div class="msg {m.role}">
                    <div class="role">{m.role === 'assistant' ? $t('directChat.assistant') : $t('directChat.you')}</div>
                    <pre>{m.content}</pre>
                    {#if m.attachmentNames?.length}
                        <div class="debug-input">
                            <div class="debug-label">{$t('directChat.attachments')}</div>
                            <pre>{m.attachmentNames.join('\n')}</pre>
                        </div>
                    {/if}
                    {#if m.role === 'assistant' && m.debugFormattedInput}
                        <div class="debug-input">
                            <div class="debug-label">{$t('directChat.formattedInput')}</div>
                            <pre>{m.debugFormattedInput}</pre>
                        </div>
                    {/if}
                    {#if m.role === 'assistant' && m.debugOcrOutput}
                        <div class="debug-input">
                            <div class="debug-label">{$t('directChat.debugOcrOutput')}</div>
                            <pre>{m.debugOcrOutput}</pre>
                        </div>
                    {/if}
                    {#if m.role === 'assistant' && m.debugAttachmentContext}
                        <div class="debug-input">
                            <div class="debug-label">{$t('directChat.debugAttachmentContext')}</div>
                            <pre>{m.debugAttachmentContext}</pre>
                        </div>
                    {/if}
                    {#if m.role === 'assistant' && m.debugUsedMultimodalImages}
                        <div class="debug-input">
                            <div class="debug-label">{$t('directChat.debugMultimodalImages')}</div>
                            <pre>{$t('directChat.debugMultimodalImagesUsed')}</pre>
                        </div>
                    {/if}
                </div>
            {/each}
        </div>
    {:else}
        <div class="capture-layout">
            <div class="capture-list">
                <div class="sanitize-box">
                    <div class="debug-label">{$t('directChat.sanitizeTitle')}</div>
                    <textarea
                        rows="5"
                        bind:value={sanitizeInput}
                        placeholder={$t('directChat.sanitizeInputPlaceholder')}
                    ></textarea>
                    <button on:click={runSanitizeTest} disabled={isSanitizing || !sanitizeInput.trim()}>
                        {isSanitizing ? $t('directChat.sanitizing') : $t('directChat.sanitizeRun')}
                    </button>
                    {#if sanitizeOutput}
                        <div class="debug-input">
                            <div class="debug-label">{$t('directChat.sanitizeOutput')}</div>
                            <pre>{sanitizeOutput}</pre>
                        </div>
                    {/if}
                </div>
                <div class="capture-toolbar">
                    <input type="text" bind:value={captureChannelFilter} placeholder={$t('directChat.captureChannelFilter')} />
                    <input type="number" min="1" max="100" bind:value={captureLimit} />
                    <button on:click={loadCaptures} disabled={isLoadingCaptures}>
                        {isLoadingCaptures ? $t('directChat.captureLoading') : $t('directChat.captureRefresh')}
                    </button>
                </div>
                {#if captures.length === 0}
                    <div class="empty">{$t('directChat.captureEmpty')}</div>
                {/if}
                {#each captures as item (item.id)}
                    <button class="capture-item" on:click={() => openCapture(item.id)}>
                        <div><strong>{item.user_display_name || item.user_name}</strong> · #{item.channel_id}</div>
                        <div class="capture-meta">{item.provider}/{item.model}</div>
                        <div class="capture-text">{item.raw_user_message}</div>
                    </button>
                {/each}
            </div>
            <div class="capture-detail">
                {#if selectedCapture}
                    <div class="capture-detail-head">
                        <strong>{selectedCapture.user_display_name || selectedCapture.user_name}</strong>
                        <button class="secondary" on:click={useCaptureInput}>{$t('directChat.captureUseInput')}</button>
                    </div>
                    <div class="debug-input">
                        <div class="debug-label">{$t('directChat.captureRawInput')}</div>
                        <pre>{selectedCapture.raw_user_message}</pre>
                    </div>
                    <div class="debug-input">
                        <div class="debug-label">{$t('directChat.captureFormattedInput')}</div>
                        <pre>{selectedCapture.formatted_user_request}</pre>
                    </div>
                    {#if selectedCapture.plugin_outputs?.length}
                        <div class="debug-input">
                            <div class="debug-label">{$t('directChat.capturePluginOutputs')}</div>
                            <pre>{selectedCapture.plugin_outputs.join('\n\n')}</pre>
                        </div>
                    {/if}
                    {#if selectedCapture.intermediate_llm_responses?.length}
                        <div class="debug-input">
                            <div class="debug-label">{$t('directChat.captureIntermediateOutputs')}</div>
                            <pre>{selectedCapture.intermediate_llm_responses.join('\n\n---\n\n')}</pre>
                        </div>
                    {/if}
                    <div class="debug-input">
                        <div class="debug-label">{$t('directChat.captureRawOutput')}</div>
                        <pre>{selectedCapture.raw_llm_response}</pre>
                    </div>
                    <div class="debug-input">
                        <div class="debug-label">{$t('directChat.captureCleanedOutput')}</div>
                        <pre>{selectedCapture.cleaned_llm_response}</pre>
                    </div>
                    <div class="debug-input">
                        <div class="debug-label">{$t('directChat.captureSystemPrompt')}</div>
                        <pre>{selectedCapture.system_prompt}</pre>
                    </div>
                    <div class="debug-input">
                        <div class="debug-label">{$t('directChat.captureLlmMessages')}</div>
                        <pre>{JSON.stringify(selectedCapture.llm_messages || [], null, 2)}</pre>
                    </div>
                {:else}
                    <div class="empty">{$t('directChat.captureSelectHint')}</div>
                {/if}
            </div>
        </div>
    {/if}

    {#if errorMessage}
        <div class="error">{errorMessage}</div>
    {/if}
    {#if captureError}
        <div class="error">{captureError}</div>
    {/if}
    {#if usageText}
        <div class="usage">{usageText}</div>
    {/if}

    {#if activeSection === 'chat'}
        <div class="composer">
            <div class="composer-main">
                <div class="file-toolbar">
                    <input bind:this={fileInput} type="file" multiple on:change={handleFileChange} hidden />
                    <button type="button" class="secondary" on:click={openFilePicker} disabled={isSending}>
                        {$t('directChat.attachFiles')}
                    </button>
                    {#if pendingFiles.length > 0}
                        <span class="file-count">{$t('directChat.selectedFiles', { count: pendingFiles.length })}</span>
                    {/if}
                </div>
                {#if pendingFiles.length > 0}
                    <div class="pending-files">
                        {#each pendingFiles as file, index}
                            <div class="pending-file">
                                <span>{file.name} ({Math.max(1, Math.round(file.size / 1024))} KB)</span>
                                <button type="button" class="secondary" on:click={() => removePendingFile(index)} disabled={isSending}>
                                    {$t('directChat.removeFile')}
                                </button>
                            </div>
                        {/each}
                    </div>
                {/if}
                <textarea
                    rows="3"
                    bind:value={inputText}
                    on:keydown={onInputKeydown}
                    placeholder={$t('directChat.inputPlaceholder')}
                    disabled={isSending}
                ></textarea>
            </div>
            <button on:click={sendMessage} disabled={isSending || (!inputText.trim() && pendingFiles.length === 0)}>
                {isSending ? $t('directChat.sending') : $t('directChat.send')}
            </button>
        </div>
    {/if}
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
        justify-content: flex-start;
        align-items: center;
        flex-wrap: wrap;
        gap: 1rem;
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: .7rem .9rem;
    }
    .section-switcher {
        display: flex;
        gap: .45rem;
    }
    .section-switcher button.active {
        background: linear-gradient(135deg, var(--primary-color), #0f6fb2);
        color: #fff;
    }
    .debug-panel {
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: .7rem .9rem;
        display: flex;
        flex-direction: column;
        gap: .6rem;
    }
    .debug-hint {
        color: var(--text-light);
        font-size: .86rem;
    }
    .debug-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(220px, 1fr));
        gap: .6rem;
    }
    .messages {
        min-height: 420px;
        max-height: calc(100vh - 300px);
        overflow: auto;
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: .9rem;
        display: flex;
        flex-direction: column;
        gap: .8rem;
    }
    .capture-layout {
        min-height: 420px;
        max-height: calc(100vh - 300px);
        display: grid;
        grid-template-columns: 360px 1fr;
        gap: .8rem;
    }
    .capture-list, .capture-detail {
        overflow: auto;
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: .9rem;
        display: flex;
        flex-direction: column;
        gap: .7rem;
    }
    .capture-toolbar {
        display: grid;
        grid-template-columns: 1fr 90px auto;
        gap: .5rem;
    }
    .sanitize-box {
        display: flex;
        flex-direction: column;
        gap: .5rem;
        background: var(--panel-muted-bg);
        border: 1px solid var(--panel-muted-border);
        border-radius: 10px;
        padding: .65rem;
    }
    .capture-item {
        text-align: left;
        background: var(--panel-muted-bg);
        border: 1px solid var(--panel-muted-border);
        border-radius: 10px;
        padding: .55rem .65rem;
        color: var(--text-color);
    }
    .capture-item:hover {
        border-color: var(--primary-color);
    }
    .capture-meta {
        color: var(--text-light);
        font-size: .78rem;
        margin-top: .2rem;
    }
    .capture-text {
        margin-top: .35rem;
        color: var(--text-color);
        font-size: .9rem;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .capture-detail-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: .7rem;
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
    .debug-input {
        margin-top: .65rem;
        background: rgba(0, 0, 0, .03);
        border: 1px dashed var(--border-color);
        border-radius: 10px;
        padding: .55rem .65rem;
    }
    .debug-label {
        font-size: .76rem;
        color: var(--text-light);
        margin-bottom: .3rem;
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
    .composer-main {
        display: flex;
        flex-direction: column;
        gap: .6rem;
    }
    .file-toolbar {
        display: flex;
        flex-wrap: wrap;
        gap: .6rem;
        align-items: center;
    }
    .file-count {
        color: var(--text-light);
        font-size: .86rem;
    }
    .pending-files {
        display: flex;
        flex-direction: column;
        gap: .45rem;
        padding: .7rem;
        border-radius: 10px;
        border: 1px solid var(--panel-muted-border);
        background: var(--panel-muted-bg);
    }
    .pending-file {
        display: flex;
        justify-content: space-between;
        gap: .75rem;
        align-items: center;
    }
    textarea {
        resize: vertical;
    }
    button.secondary {
        background: var(--control-bg);
        color: var(--text-color);
        border: 1px solid var(--panel-muted-border);
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
        .capture-layout {
            grid-template-columns: 1fr;
        }
        .debug-grid {
            grid-template-columns: 1fr;
        }
        .capture-toolbar {
            grid-template-columns: 1fr;
        }
    }
</style>
