<!-- src/components/LogViewer.svelte -->
<script>
    import { onMount, onDestroy, afterUpdate } from 'svelte';
    import { t } from '../i18n.js';
    import { rawLogs } from '../lib/stores.js';
    import { fetchLogs } from '../lib/api.js';
    import UsageDashboard from './UsageDashboard.svelte';

    let logLevelFilter = 'ALL';
    const logLevels = ['ALL', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
    let autoScroll = true;
    let logOutputElement;
    let logInterval;
    
    $: parsedLogs = ($rawLogs || '').split('\n').filter(line => line.trim() !== '').map(line => {
        const match = line.match(/ - (INFO|WARNING|ERROR|CRITICAL) - /);
        return {
            level: match ? match[1] : 'UNKNOWN',
            message: line
        };
    });

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
            <label class="autoscroll-toggle">
                <input type="checkbox" bind:checked={autoScroll}>
                <span>{$t('logViewer.autoscroll')}</span>
            </label>
        </div>
        <div class="log-output-wrapper">
            <pre bind:this={logOutputElement}><code>{#each filteredLogs as log, i (log.message + i)}<span class="log-line {log.level}">{log.message}</span>{'\n'}{/each}</code></pre>
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
        gap: 1rem;
    }
    
    .log-section {
        flex: 1;
        min-height: 0;
        display: flex;
        flex-direction: column;
        background-color: var(--card-bg);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        box-shadow: var(--shadow);
    }
    
    .usage-section {
        flex: 0 0 400px;
        min-height: 0;
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
    
    .autoscroll-toggle {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: var(--text-light);
        font-size: 0.9rem;
        cursor: pointer;
        user-select: none;
    }
    
    .autoscroll-toggle input {
        width: auto;
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
