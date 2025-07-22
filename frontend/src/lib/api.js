// frontend/src/lib/api.js
import { get } from 'svelte/store';
import { timezoneStore } from './stores.js';

const BASE_URL = '/api';

let apiSecretKey = null;

export function setApiSecretKey(key) {
    apiSecretKey = key;
    // 额外步骤：也将其存储在localStorage中以便在页面刷新时保留
    try {
        const config = JSON.parse(localStorage.getItem('llmConfig') || '{}');
        config.api_secret_key = key;
        localStorage.setItem('llmConfig', JSON.stringify(config));
    } catch(e) {
        console.error("无法向localStorage保存API密钥:", e);
    }
}

function getApiSecretKey() {
    if (apiSecretKey) return apiSecretKey;
    try {
        const configStr = localStorage.getItem('llmConfig');
        if (configStr) {
            const config = JSON.parse(configStr);
            apiSecretKey = config.api_secret_key || null;
            return apiSecretKey;
        }
    } catch (e) {
        console.error("无法从localStorage解析配置:", e);
    }
    return null;
}


// [SECURITY] Centralized fetch function to handle API key authentication
async function apiFetch(url, options = {}) {
    let key = getApiSecretKey();

    // If no key and this is not a config fetch, try to fetch config first.
    if (!key && !url.endsWith('/api/config')) {
        try {
            console.log("No API key found, attempting to fetch config first...");
            await fetchConfig();
            key = getApiSecretKey(); // Try getting the key again
        } catch (e) {
            console.error("Failed to fetch config automatically:", e);
            // We still proceed, letting the original request fail, which provides a clear error to the user.
        }
    }
    
    const headers = {
        ...options.headers,
        'Content-Type': 'application/json',
    };

    // Only add the API key if it exists.
    if (key) {
        headers['X-API-Key'] = key;
    }

    const response = await fetch(url, { ...options, headers });
    return handleResponse(response);
}

async function handleResponse(response) {
    // Special handling for fetching logs, which returns plain text
    if (response.url.endsWith('/api/logs')) {
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(JSON.parse(errorText).detail || 'Failed to fetch logs');
        }
        return response.text();
    }

    // Standard JSON response handling for all other API requests
    if (!response.ok) {
        let errorDetail = 'An unknown error occurred.';
        try {
            const errorJson = await response.json();
            errorDetail = errorJson.detail || JSON.stringify(errorJson);
        } catch (e) {
            errorDetail = `Request failed with status ${response.status}: ${await response.text()}`;
        }
        console.error('API Error:', response.status, errorDetail);
        throw new Error(errorDetail);
    }
    
    // For 204 No Content responses, return a success indicator
    if (response.status === 204) {
        return { success: true };
    }

    return response.json();
}

export async function fetchConfig() {
    console.log('Fetching config from backend...');
    // Initial fetch might not have the key, so we handle it specially
    const tempKey = getApiSecretKey();
    const headers = {};
    if (tempKey) {
        headers['X-API-Key'] = tempKey;
    }

    const response = await fetch(`${BASE_URL}/config`, { headers });
    const result = await handleResponse(response);

    // After a successful fetch, we MUST set the key for subsequent requests.
    if (result.api_secret_key) {
        setApiSecretKey(result.api_secret_key);
    }
    console.log('Config fetched successfully.');
    return result;
}

export async function saveConfig(configData) {
    console.log('Saving config to backend...');
    const result = await apiFetch(`${BASE_URL}/config`, {
        method: 'POST',
        body: JSON.stringify(configData),
    });
    console.log('Config saved successfully:', result);
    return result;
}

export async function clearMemory(channelId) {
    return apiFetch(`${BASE_URL}/memory/clear`, {
        method: 'POST',
        body: JSON.stringify({ channel_id: channelId }),
    });
}

export async function fetchLogs() {
    // apiFetch handles the headers, handleResponse handles the text response
    return apiFetch(`${BASE_URL}/logs`);
}

export async function simulateDebug(payload) {
    return apiFetch(`${BASE_URL}/debug/simulate`, {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export async function fetchAvailableModels(provider, apiKey, baseUrl) {
    return apiFetch(`${BASE_URL}/models/list`, {
        method: 'POST',
        body: JSON.stringify({ provider, api_key: apiKey, base_url: baseUrl }),
    });
}

export async function testModel(provider, apiKey, baseUrl, modelName) {
    return apiFetch(`${BASE_URL}/models/test`, {
        method: 'POST',
        body: JSON.stringify({
            provider,
            api_key: apiKey,
            base_url: baseUrl,
            model_name: modelName
        }),
    });
}

export async function fetchPluginConfig(pluginName) {
    console.log(`Fetching config for plugin: ${pluginName}`);
    const result = await apiFetch(`${BASE_URL}/plugins/${pluginName}/config`);
    console.log(`Config for ${pluginName} fetched successfully:`, result);
    return result;
}

// --- Knowledge Base API ---

// The new apiFetch function replaces the need for a separate authenticatedFetch

// Memory Functions
export async function fetchMemoryItems() {
    return apiFetch(`${BASE_URL}/memory`);
}

export async function addMemoryItem(content) {
    const timestamp = new Date().toISOString();
    return apiFetch(`${BASE_URL}/memory`, {
        method: 'POST',
        body: JSON.stringify({ content, timestamp }),
    });
}

export async function deleteMemoryItem(itemId) {
    return apiFetch(`${BASE_URL}/memory/${itemId}`, {
        method: 'DELETE',
    });
}

// World Book Functions
export async function fetchWorldBookItems() {
    return apiFetch(`${BASE_URL}/worldbook`);
}

export async function addWorldBookItem(item) {
    return apiFetch(`${BASE_URL}/worldbook`, {
        method: 'POST',
        body: JSON.stringify(item),
    });
}

export async function updateWorldBookItem(itemId, item) {
    return apiFetch(`${BASE_URL}/worldbook/${itemId}`, {
        method: 'PUT',
        body: JSON.stringify(item),
    });
}

export async function deleteWorldBookItem(itemId) {
    return apiFetch(`${BASE_URL}/worldbook/${itemId}`, {
        method: 'DELETE',
    });
}

export async function savePluginConfig(pluginName, configData) {
    console.log(`Saving config for plugin: ${pluginName}`, configData);
    const result = await apiFetch(`${BASE_URL}/plugins/${pluginName}/config`, {
        method: 'POST',
        body: JSON.stringify(configData),
    });
    console.log(`Config for ${pluginName} saved successfully:`, result);
    return result;
}

// --- Usage & Pricing API ---
export async function fetchUsageStats(period, view) {
    const userTimezone = get(timezoneStore);
    return apiFetch(`${BASE_URL}/usage/stats?period=${period}&view=${view}`, {
        headers: {
            'X-Timezone': userTimezone || 'UTC'
        }
    });
}

export async function fetchPricingConfig() {
    return apiFetch(`${BASE_URL}/usage/pricing`);
}

export async function savePricingConfig(pricingData) {
    return apiFetch(`${BASE_URL}/usage/pricing`, {
        method: 'POST',
        body: JSON.stringify(pricingData),
    });
}
