// frontend/src/lib/botConfigActions.js
// Shared config loading and save handlers for bot configuration pages.
// Extracts the repeated loadInstanceConfig + configLoadSeq guard pattern
// and the handleSave try/catch/finally + showStatus pattern.

import { writable } from 'svelte/store';
import { loadBotConfigToStores, saveConfig } from './stores.js';
import { showStatus } from './commonStores.js';

/**
 * Creates a config loader with seq guard pattern.
 *
 * Encapsulates the reactive loading/error states and the seq-based guard
 * that prevents stale responses when botId changes rapidly.
 *
 * @param {() => string|null} getBotId - getter returning the current botId
 * @returns {{ isLoading: import('svelte/store').Writable<boolean>, error: import('svelte/store').Writable<string>, trigger: () => void }}
 *
 * Usage in a Svelte component:
 *   const loader = createConfigLoader(() => botId);
 *   $: if (botId) loader.trigger();
 *   Template: {$isLoading} {$error}
 */
export function createConfigLoader(getBotId) {
    const isLoading = writable(false);
    const error = writable('');
    let configLoadSeq = 0;

    async function loadInstanceConfig(seq) {
        if (seq !== configLoadSeq) return;
        const botId = getBotId();
        if (!botId) return;
        isLoading.set(true);
        error.set('');
        try {
            await loadBotConfigToStores(botId);
        } catch (e) {
            error.set(String(e.message || e));
        } finally {
            isLoading.set(false);
        }
    }

    function trigger() {
        const seq = ++configLoadSeq;
        loadInstanceConfig(seq);
    }

    return { isLoading, error, trigger };
}

/**
 * Creates a save handler with try/catch/finally and status notifications.
 *
 * @param {() => string|null} getBotId - getter returning the current botId
 * @returns {{ isSaving: import('svelte/store').Writable<boolean>, save: () => Promise<void> }}
 *
 * Usage in a Svelte component:
 *   const saver = createSaveHandler(() => botId);
 *   Template: <button disabled={$isSaving} on:click={saver.save}>
 */
export function createSaveHandler(getBotId) {
    const isSaving = writable(false);

    async function save() {
        const botId = getBotId();
        if (!botId) return;
        isSaving.set(true);
        showStatus('Saving...', 'info');
        try {
            await saveConfig(botId);
            showStatus('Configuration saved and bot restarted!', 'success');
        } catch (e) {
            showStatus('Save failed: ' + e.message, 'error');
        } finally {
            isSaving.set(false);
        }
    }

    return { isSaving, save };
}
