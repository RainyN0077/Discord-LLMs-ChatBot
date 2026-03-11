<!-- src/components/LogViewer.svelte -->
<script>
    import { onMount, onDestroy, afterUpdate } from 'svelte';
    import { t } from '../i18n.js';
    import { rawLogs, timezoneStore } from '../lib/stores.js';
    import { fetchLogs } from '../lib/api.js';
    import UsageDashboard from './UsageDashboard.svelte';

    let logLevelFilter = 'ALL';
    const logLevels = ['ALL', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
    const LOG_LINE_LIMIT_OPTIONS = [200, 500, 1000, 2000];
    let autoScroll = true;
    let logOutputElement;
    let logInterval;
    let renderedLogLimit = 1000;
    let hiddenLogCount = 0;
    
    // The 'sv-SE' locale is a trick to get the YYYY-MM-DD format easily.
    const formatTimestamp = (utcString, timeZone) => {
        if (!utcString) return '...';
        try {
            return new Intl.DateTimeFormat('sv-SE', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false,
                timeZone: timeZone
            }).format(new Date(utcString));
        } catch (e) {
            console.error(`Invalid timezone: ${timeZone}`, e);
            // Fallback to plain UTC string if timezone is invalid
            return utcString.replace('T', ' ').substring(0, 19);
        }
    };
    
    $: parsedLogs = (($rawLogs, $timezoneStore), () => {
        const allLines = ($rawLogs || '').split('\n').filter(line => line.trim() !== '');
        hiddenLogCount = Math.max(0, allLines.length - renderedLogLimit);
        const visibleLines = hiddenLogCount > 0 ? allLines.slice(-renderedLogLimit) : allLines;

        return visibleLines.map(line => {
            // Regex for ISO 8601 format: 2025-07-21T06:46:12.067Z
            const timestampMatch = line.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)/);
            const levelMatch = line.match(/ - (INFO|WARNING|ERROR|CRITICAL) - /);

            const originalTimestamp = timestampMatch ? timestampMatch[1] : null;
            const level = levelMatch ? levelMatch[1] : 'UNKNOWN';

            let messageText = line;
            // Extract the actual message content, removing timestamp, module, and level.
            if (levelMatch) {
                messageText = line.substring(levelMatch.index + levelMatch[0].length);
            } else if (timestampMatch) {
                messageText = line.substring(timestampMatch[0].length).trim();
            }

            return {
                level: level,
                message: messageText,
                originalLine: line, // Use a different name to avoid confusion and for keys
                formattedTimestamp: formatTimestamp(originalTimestamp, $timezoneStore)
            };
        });
    })();

    $: filteredLogs = logLevelFilter === 'ALL' ? parsedLogs : parsedLogs.filter(log => log.level === logLevelFilter);

    onMount(() => {
        try {
            const savedLimit = Number(localStorage.getItem('logViewer.maxLines'));
            if (LOG_LINE_LIMIT_OPTIONS.includes(savedLimit)) {
                renderedLogLimit = savedLimit;
            }
        } catch (e) {
            console.warn('Failed to restore logViewer.maxLines from localStorage', e);
        }

        const getLogs = async () => {
            try {
                const logsText = await fetchLogs();
                rawLogs.set(logsText);
            } catch(e) {
                rawLogs.set(`Error fetching logs: ${e.message}`);
                console.error(e);
            }
        };
        getLogs();
        logInterval = setInterval(getLogs, 5000);
    });

    $: if (typeof window !== 'undefined' && LOG_LINE_LIMIT_OPTIONS.includes(renderedLogLimit)) {
        localStorage.setItem('logViewer.maxLines', String(renderedLogLimit));
    }

    onDestroy(() => {
        if (logInterval) clearInterval(logInterval);
    });
    
    afterUpdate(() => {
      if (logOutputElement && autoScroll) {
        logOutputElement.scrollTop = logOutputElement.scrollHeight;
      }
    });
</script>

<div class="right-panel">
    <div class="log-section">
        <h2>{$t('logViewer.title')}</h2>
        <div class="log-controls">
            <div class="log-filter-group">
                <span>{$t('logViewer.filterLevel')}:</span>
                {#each logLevels as level}
                    <button class:active={logLevelFilter === level} on:click={() => {logLevelFilter = level; autoScroll = true;}}>
                        {level}
                    </button>
                {/each}
            </div>
            <label class="toggle-switch">
                <input type="checkbox" bind:checked={autoScroll}>
                <span class="slider"></span>{$t('logViewer.autoscroll')}
            </label>
            <label class="line-limit-control">
                <span>{$t('logViewer.maxLines')}:</span>
                <select
                    value={renderedLogLimit}
                    on:change={(e) => {
                        const next = Number(e.target.value);
                        if (LOG_LINE_LIMIT_OPTIONS.includes(next)) {
                            renderedLogLimit = next;
                        }
                    }}
                >
                    {#each LOG_LINE_LIMIT_OPTIONS as option}
                        <option value={option}>{option}</option>
                    {/each}
                </select>
            </label>
        </div>
        {#if hiddenLogCount > 0}
            <div class="log-limit-note">
                {$t('logViewer.limitNotice', { limit: renderedLogLimit, hidden: hiddenLogCount })}
            </div>
        {/if}
        <div class="log-output-wrapper">
            <pre bind:this={logOutputElement}><code>{#each filteredLogs as log, i (log.originalLine + i)}<span class="log-line {log.level}"><span class="timestamp">{log.formattedTimestamp}</span>{log.message}</span>{'\n'}{/each}</code></pre>
        </div>
    </div>
    
    <div class="usage-section">
        <UsageDashboard />
    </div>
</div>

<style>
    .right-panel {
        display: flex;
        flex-direction: column;
        height: clamp(620px, 82vh, 920px);
        max-height: calc(100vh - 2rem);
        gap: 1rem;
    }
    
    .log-section {
        min-height: 320px;
        display: flex;
        flex: 1 1 auto;
        flex-direction: column;
        background:
            linear-gradient(160deg, rgba(31, 139, 214, .06), transparent 36%),
            var(--card-bg);
        border-radius: 14px;
        padding: 1rem 1.15rem;
        box-shadow: var(--shadow);
        border: 1px solid rgba(15, 23, 42, .06);
    }
    
    .usage-section {
        flex: 1 1 40%;
        min-height: 260px;
    }
    
    h2 {
        font-size: 1.25rem;
        margin: 0 0 1rem 0;
    }
    
    .log-controls {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
        flex-shrink: 0;
        flex-wrap: wrap;
    }
    
    .log-filter-group {
        display: flex;
        gap: 0.5rem;
        align-items: center;
        background: rgba(15, 23, 42, .04);
        border: 1px solid rgba(15, 23, 42, .08);
        border-radius: 12px;
        padding: .35rem .45rem;
    }
    
    .log-filter-group span {
        color: var(--text-light);
        font-size: 0.9rem;
    }
    
    .log-filter-group button {
        background: transparent;
        color: #555;
        padding: 0.35rem 0.75rem;
        font-size: 0.85rem;
        border: 1px solid transparent;
        box-shadow: none;
    }
    
    .log-filter-group button.active {
        background: linear-gradient(135deg, var(--primary-color), #166ea9);
        color: #fff;
        border-color: var(--primary-color);
    }
    
    
    .log-output-wrapper {
        flex-grow: 1;
        overflow: hidden;
        background-color: #1e1e1e;
        border-radius: 8px;
        position: relative;
    }

    .log-limit-note {
        color: var(--text-light);
        font-size: 0.82rem;
        margin: -.2rem 0 .6rem 0;
    }

    .line-limit-control {
        display: inline-flex;
        align-items: center;
        gap: .45rem;
        color: var(--text-light);
        font-size: .9rem;
    }

    .line-limit-control select {
        min-width: 92px;
        padding: .25rem .45rem;
        font-size: .85rem;
    }
    
    .log-output-wrapper pre {
        height: 100%;
        margin: 0;
        overflow-y: auto;
        padding: 1rem;
        box-sizing: border-box;
        font-family: 'Fira Code', 'Courier New', monospace;
        font-size: 0.8rem;
        line-height: 1.6;
        color: #d4d4d4;
        white-space: pre-wrap;
        word-break: break-all;
    }
    
    .log-output-wrapper code {
        display: block;
    }

    .timestamp {
        color: #9e9e9e; /* Light grey for timestamp */
        margin-right: 1em;
    }
    
    .log-line.INFO {
        color: #81c784;
    }
    
    .log-line.WARNING {
        color: #ffd54f;
    }
    
    .log-line.ERROR {
        color: #e57373;
    }
    
    .log-line.CRITICAL {
        color: #ff8a65;
        font-weight: 700;
    }
    
    .log-line.UNKNOWN {
        color: #90a4ae;
    }
    
    @media (max-width: 1400px) {
        .right-panel {
            height: clamp(520px, 72vh, 760px);
            max-height: calc(100vh - 3rem);
        }
    }

    @media (max-width: 900px) {
        .right-panel {
            height: clamp(420px, 60vh, 620px);
            max-height: calc(100vh - 4rem);
            gap: .75rem;
        }

        .log-section {
            min-height: 240px;
            padding: .8rem .85rem;
        }

        .usage-section {
            min-height: 180px;
        }

        .log-controls {
            margin-bottom: .6rem;
        }
    }
</style>
