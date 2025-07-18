<!-- src/components/LogViewer.svelte (FINAL & CORRECT) -->
<script>
    import { onMount, onDestroy, afterUpdate } from 'svelte';
    import { t } from '../i18n.js';
    import { rawLogs } from '../lib/stores.js';
    import { fetchLogs } from '../lib/api.js';

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
