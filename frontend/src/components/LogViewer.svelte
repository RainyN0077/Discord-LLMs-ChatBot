<!-- src/components/LogViewer.svelte -->
<script>
    import { onMount, onDestroy, afterUpdate } from 'svelte';
    import { t } from '../i18n.js';
    import { rawLogs, timezoneStore } from '../lib/stores.js';
    import { fetchLogs } from '../lib/api.js';
    import UsageDashboard from './UsageDashboard.svelte';

    let logLevelFilter = 'ALL';
    const logLevels = ['ALL', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
    let autoScroll = true;
    let logOutputElement;
    let logInterval;
    
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
        return ($rawLogs || '').split('\n').filter(line => line.trim() !== '').map(line => {
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
        </div>
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
        height: 100%;
        gap: 2rem;
    }
    
    .log-section {
        height: 60vh;
        display: flex;
        flex-direction: column;
        background-color: var(--card-bg);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        box-shadow: var(--shadow);
    }
    
    .usage-section {
        height: 40vh;
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
    }
    
    .log-filter-group span {
        color: var(--text-light);
        font-size: 0.9rem;
    }
    
    .log-filter-group button {
        background: #f0f2f5;
        color: #555;
        padding: 0.3rem 0.8rem;
        font-size: 0.85rem;
        border: 1px solid var(--border-color);
    }
    
    .log-filter-group button.active {
        background-color: var(--primary-color);
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
            flex-direction: column;
        }
        
        .usage-section {
            flex: 0 0 300px;
        }
    }
</style>
