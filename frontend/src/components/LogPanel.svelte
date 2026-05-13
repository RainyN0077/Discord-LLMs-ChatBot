<!-- src/components/LogPanel.svelte -->
<script>
    import { onMount, onDestroy, afterUpdate } from 'svelte';
    import { t } from '../i18n.js';
    import { rawLogs, timezoneStore } from '../lib/stores.js';
    import { fetchBotLogs, fetchLogs } from '../lib/api.js';

    export let botId = null;

    let collapsed = false;
    let logLevelFilter = 'ALL';
    const logLevels = ['ALL', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
    const LOG_LINE_LIMIT_OPTIONS = [200, 500, 1000, 2000];
    let autoScroll = true;
    let logOutputElement;
    let logInterval;
    let renderedLogLimit = 1000;
    let hiddenLogCount = 0;
    let panelHeight = 280;
    let isDragging = false;

    const formatTimestamp = (utcString, timeZone) => {
        if (!utcString) return '...';
        try {
            return new Intl.DateTimeFormat('sv-SE', {
                year: 'numeric', month: '2-digit', day: '2-digit',
                hour: '2-digit', minute: '2-digit', second: '2-digit',
                hour12: false, timeZone: timeZone
            }).format(new Date(utcString));
        } catch (e) {
            return utcString.replace('T', ' ').substring(0, 19);
        }
    };

    const timestampRegex = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)/;
    const levelRegex = /\]\s+-\s+(INFO|WARNING|ERROR|CRITICAL)\s+-\s+/;

    $: _rawLogs = $rawLogs;
    $: _timezone = $timezoneStore;
    $: _limit = renderedLogLimit;

    $: parsedLogs = (() => {
        const allLines = (_rawLogs || '').split('\n').filter(line => line.trim() !== '');
        hiddenLogCount = Math.max(0, allLines.length - _limit);
        const visibleLines = hiddenLogCount > 0 ? allLines.slice(-_limit) : allLines;
        return visibleLines.map(line => {
            const tsMatch = line.match(timestampRegex);
            const lvMatch = line.match(levelRegex);
            const originalTimestamp = tsMatch ? tsMatch[1] : null;
            const level = lvMatch ? lvMatch[1] : 'UNKNOWN';
            let messageText = line;
            if (lvMatch) {
                messageText = line.substring(lvMatch.index + lvMatch[0].length);
            } else if (tsMatch) {
                messageText = line.substring(tsMatch[0].length).trim();
            }
            return {
                level, message: messageText,
                originalLine: line,
                formattedTimestamp: originalTimestamp ? formatTimestamp(originalTimestamp, _timezone) : '...'
            };
        });
    })();

    $: filteredLogs = logLevelFilter === 'ALL' ? parsedLogs : parsedLogs.filter(log => log.level === logLevelFilter);

    async function getLogs() {
        try {
            let logsText;
            if (botId) {
                const result = await fetchBotLogs(botId);
                if (Array.isArray(result)) {
                    logsText = result.join('\n');
                } else if (result && typeof result === 'object' && Array.isArray(result.logs)) {
                    logsText = result.logs.join('\n');
                } else if (typeof result === 'string') {
                    logsText = result;
                } else {
                    logsText = '';
                }
            } else {
                logsText = await fetchLogs();
            }
            rawLogs.set(logsText);
        } catch(e) {
            console.error('Log fetch error:', e);
        }
    }

    onMount(() => {
        try {
            const savedLimit = Number(localStorage.getItem('logPanel.maxLines'));
            if (LOG_LINE_LIMIT_OPTIONS.includes(savedLimit)) renderedLogLimit = savedLimit;
            const savedHeight = Number(localStorage.getItem('logPanel.height'));
            if (savedHeight > 100 && savedHeight < 800) panelHeight = savedHeight;
        } catch (e) {}

        getLogs();
        logInterval = setInterval(getLogs, 5000);
    });

    $: if (typeof window !== 'undefined' && LOG_LINE_LIMIT_OPTIONS.includes(renderedLogLimit)) {
        localStorage.setItem('logPanel.maxLines', String(renderedLogLimit));
    }

    onDestroy(() => {
        if (logInterval) clearInterval(logInterval);
    });

    afterUpdate(() => {
        if (logOutputElement && autoScroll) {
            logOutputElement.scrollTop = logOutputElement.scrollHeight;
        }
    });

    function handleDragStart(e) {
        isDragging = true;
        document.addEventListener('mousemove', handleDragMove);
        document.addEventListener('mouseup', handleDragEnd);
        e.preventDefault();
    }

    function handleDragMove(e) {
        if (!isDragging) return;
        const newHeight = window.innerHeight - e.clientY;
        panelHeight = Math.max(120, Math.min(800, newHeight));
    }

    function handleDragEnd() {
        isDragging = false;
        document.removeEventListener('mousemove', handleDragMove);
        document.removeEventListener('mouseup', handleDragEnd);
        localStorage.setItem('logPanel.height', String(panelHeight));
    }
</script>

<div class="log-panel" class:collapsed style="height: {collapsed ? '44px' : panelHeight + 'px'}">
    <div class="log-header">
        <button class="log-collapse-btn" on:click={() => collapsed = !collapsed}>
            <span>{collapsed ? '▸' : '▾'}</span>
            <span>Logs</span>
            {#if botId}
                <span class="log-bot-tag">{botId}</span>
            {/if}
        </button>
        {#if !collapsed}
            <div class="log-controls">
                <div class="log-filter-group">
                    {#each logLevels as level}
                        <button class:active={logLevelFilter === level} on:click={() => { logLevelFilter = level; autoScroll = true; }}>
                            {level}
                        </button>
                    {/each}
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" bind:checked={autoScroll}>
                    <span class="slider"></span>Auto
                </label>
                <label class="line-limit-control">
                    <select value={renderedLogLimit} on:change={(e) => { const n = Number(e.target.value); if (LOG_LINE_LIMIT_OPTIONS.includes(n)) renderedLogLimit = n; }}>
                        {#each LOG_LINE_LIMIT_OPTIONS as option}
                            <option value={option}>{option}</option>
                        {/each}
                    </select>
                </label>
            </div>
        {/if}
    </div>

    {#if !collapsed}
        <div class="resize-handle" role="separator" on:mousedown={handleDragStart}></div>
        {#if hiddenLogCount > 0}
            <div class="log-limit-note">Showing last {renderedLogLimit} lines ({hiddenLogCount} hidden)</div>
        {/if}
        <div class="log-output-wrapper">
            <pre bind:this={logOutputElement}><code>{#each filteredLogs as log, i (log.originalLine + i)}<span class="log-line {log.level}"><span class="timestamp">{log.formattedTimestamp}</span>{log.message}</span>{/each}</code></pre>
        </div>
    {/if}
</div>

<style>
    .log-panel {
        border-top: 1px solid var(--sidebar-border, rgba(140, 167, 193, .12));
        background: var(--log-shell-bg, #1e1e1e);
        display: flex;
        flex-direction: column;
        transition: height .2s ease;
        overflow: hidden;
    }

    .log-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: .35rem .75rem;
        background: rgba(0, 0, 0, .3);
        border-bottom: 1px solid rgba(255, 255, 255, .06);
        flex-shrink: 0;
        min-height: 44px;
        flex-wrap: wrap;
        gap: .35rem;
    }

    .log-collapse-btn {
        background: transparent;
        border: none;
        color: #b8c8da;
        cursor: pointer;
        font-size: .82rem;
        display: flex;
        align-items: center;
        gap: .4rem;
        padding: .3rem .5rem;
        border-radius: 6px;
        box-shadow: none;
        transition: background .18s ease, color .18s ease;
    }

    .log-collapse-btn:hover {
        background: rgba(255, 255, 255, .08);
        color: #e0e6ef;
    }

    .log-panel.collapsed .log-header {
        cursor: pointer;
        background: rgba(0, 0, 0, .25);
        transition: background .18s ease;
        padding: 0;
    }

    .log-panel.collapsed .log-header:hover {
        background: rgba(0, 0, 0, .4);
    }

    .log-panel.collapsed .log-collapse-btn {
        flex: 1;
        padding: 0 .85rem;
        border-radius: 0;
        min-height: 44px;
        justify-content: flex-start;
    }

    .log-bot-tag {
        font-size: .7rem;
        padding: .08rem .35rem;
        border-radius: 4px;
        background: rgba(69, 163, 230, .2);
        color: #88d1ff;
    }

    .log-controls {
        display: flex;
        align-items: center;
        gap: .5rem;
        flex-wrap: wrap;
    }

    .log-filter-group {
        display: flex;
        gap: .15rem;
        background: rgba(148, 163, 184, .1);
        border-radius: 6px;
        padding: .15rem .25rem;
    }

    .log-filter-group button {
        background: transparent;
        color: #90a4ae;
        padding: .15rem .45rem;
        font-size: .72rem;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        box-shadow: none;
    }

    .log-filter-group button.active {
        background: rgba(69, 163, 230, .35);
        color: #88d1ff;
    }

    .toggle-switch {
        display: inline-flex;
        align-items: center;
        gap: .3rem;
        font-size: .75rem;
        color: #90a4ae;
        cursor: pointer;
    }

    .toggle-switch input[type="checkbox"] {
        width: 14px;
        height: 14px;
    }

    .line-limit-control select {
        padding: .15rem .3rem;
        font-size: .72rem;
        background: rgba(148, 163, 184, .1);
        color: #90a4ae;
        border: 1px solid rgba(148, 163, 184, .15);
        border-radius: 4px;
    }

    .resize-handle {
        height: 4px;
        background: rgba(255, 255, 255, .04);
        cursor: ns-resize;
        flex-shrink: 0;
    }

    .resize-handle:hover {
        background: rgba(69, 163, 230, .4);
    }

    .log-limit-note {
        color: #90a4ae;
        font-size: .72rem;
        padding: .15rem .75rem;
        flex-shrink: 0;
    }

    .log-output-wrapper {
        flex: 1;
        overflow: hidden;
    }

    .log-output-wrapper pre {
        height: 100%;
        margin: 0;
        overflow-y: auto;
        padding: .5rem .75rem;
        box-sizing: border-box;
        font-family: 'Fira Code', 'Courier New', monospace;
        font-size: .78rem;
        line-height: 1.6;
        color: #d4d4d4;
        white-space: pre-wrap;
        word-break: break-all;
    }

    .timestamp {
        color: #9e9e9e;
        margin-right: 1em;
    }

    .log-line { display: block; }
    .log-line.INFO { color: #81c784; }
    .log-line.WARNING { color: #ffd54f; }
    .log-line.ERROR { color: #e57373; }
    .log-line.CRITICAL { color: #ff8a65; font-weight: 700; }
    .log-line.UNKNOWN { color: #90a4ae; }

    .log-line:hover {
        background: rgba(255, 255, 255, .04);
    }

    .log-output-wrapper pre::-webkit-scrollbar {
        width: 6px;
    }

    .log-output-wrapper pre::-webkit-scrollbar-thumb {
        background: rgba(148, 163, 184, .25);
        border-radius: 6px;
    }

    .log-output-wrapper pre::-webkit-scrollbar-track {
        background: transparent;
    }

    .log-output-wrapper pre {
        scrollbar-width: thin;
        scrollbar-color: rgba(148, 163, 184, .25) transparent;
    }

    @media (max-width: 900px) {
        .log-header {
            padding: .25rem .5rem;
        }

        .log-collapse-btn {
            font-size: .75rem;
        }

        .log-filter-group button {
            padding: .1rem .35rem;
            font-size: .65rem;
        }

        .log-output-wrapper pre {
            font-size: .7rem;
            padding: .35rem .5rem;
        }

        .log-controls {
            gap: .3rem;
        }
    }

    @media (max-width: 600px) {
        .log-header {
            flex-direction: column;
            align-items: flex-start;
            gap: .25rem;
            padding: .2rem .4rem;
        }

        .log-filter-group {
            flex-wrap: wrap;
        }

        .log-output-wrapper pre {
            font-size: .65rem;
            padding: .25rem .35rem;
        }
    }
</style>
