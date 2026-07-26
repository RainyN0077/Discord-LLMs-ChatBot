// frontend/src/lib/commonStores.js
// General-purpose Svelte stores shared across the app.
// Extracted from stores.js to break the api.js ↔ stores.js circular dependency.
import { writable } from 'svelte/store';

// --- Navigation ---
export const activePage = writable('config');

// --- Status & Loading ---
export const statusMessage = writable('');
export const statusType = writable('info');
export const isLoading = writable(false);
export const customFontName = writable('');

// --- Logs ---
export const rawLogs = writable('');

// --- Templates ---
export const promptTemplates = writable({});

// --- Timezone Store ---
const getInitialTimezone = () => {
    if (typeof window !== 'undefined') {
        const savedTimezone = localStorage.getItem('timezone');
        if (savedTimezone) return savedTimezone;
        return Intl.DateTimeFormat().resolvedOptions().timeZone;
    }
    return 'UTC';
};
export const timezoneStore = writable(getInitialTimezone());
if (typeof window !== 'undefined') {
    timezoneStore.subscribe(value => {
        localStorage.setItem('timezone', value);
    });
}

// --- Global Status Actions ---
let statusTimeout;
export function showStatus(message, type = 'info', duration = 5000) {
    clearTimeout(statusTimeout);
    statusMessage.set(message);
    statusType.set(type);
    if (type !== 'info' && type !== 'loading-special' && duration > 0) {
        statusTimeout = setTimeout(() => {
            statusMessage.update(current => (current === message ? '' : current));
        }, duration);
    }
}
