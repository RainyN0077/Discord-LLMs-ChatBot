// frontend/src/lib/api.js
import { get } from 'svelte/store';
import { timezoneStore } from './commonStores.js';

const BASE_URL = '/api';

const API_KEY_STORAGE_KEY = '_ak';

export function setApiSecretKey(key) {
    try {
        sessionStorage.setItem(API_KEY_STORAGE_KEY, key ? btoa(key) : '');
    } catch (e) { /* sessionStorage不可用时降级 */ }
}

export function getApiSecretKey() {
    try {
        const encoded = sessionStorage.getItem(API_KEY_STORAGE_KEY);
        return encoded ? atob(encoded) : null;
    } catch (e) { return null; }
}

export function clearApiSecretKey() {
    try { sessionStorage.removeItem(API_KEY_STORAGE_KEY); } catch (e) {}
}


// [SECURITY] Centralized fetch function to handle API key authentication
async function apiFetch(url, options = {}) {
    let key = getApiSecretKey();

    // If no key and this is not a config fetch, try to fetch config first.
    if (!key && !url.endsWith('/api/config')) {
        try {
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

    if (response.status === 403 && key && !options._noRetry) {
        console.warn('Received 403 with current key, clearing and retrying without key...');
        clearApiSecretKey();
        await fetchConfig();
        const newKey = getApiSecretKey();
        if (newKey) {
            headers['X-API-Key'] = newKey;
            const retryResponse = await fetch(url, { ...options, headers, _noRetry: true });
            return handleResponse(retryResponse);
        }
    }

    return handleResponse(response);
}

async function handleResponse(response) {
    // Special handling for fetching logs, which returns plain text
    if (response.url.endsWith('/api/logs') || /\/api\/bots\/.+\/logs$/.test(response.url)) {
        if (!response.ok) {
            const errorText = await response.text();
            let logError;
            try { logError = JSON.parse(errorText).detail || 'Failed to fetch logs'; }
            catch (_) { logError = errorText || 'Failed to fetch logs'; }
            throw new Error(logError);
        }
        return response.text();
    }

    // Standard JSON response handling for all other API requests
    if (!response.ok) {
        let errorDetail = `Request failed with status ${response.status}`;
        // Clone the response to allow reading the body twice
        const responseClone = response.clone();
        try {
            // Try to parse as JSON first
            const errorJson = await response.json();
            errorDetail = errorJson.detail || JSON.stringify(errorJson);
            console.error('API Error JSON detail:', errorJson.detail || response.statusText);
        } catch (e) {
            // If JSON parsing fails, read as text from the clone
            try {
                const errorText = await responseClone.text();
                errorDetail = errorText || errorDetail;
                console.error('API Error Text:', errorDetail);
            } catch (textErr) {
                // If reading as text also fails, stick with the status code
            }
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
    let tempKey = getApiSecretKey();
    const headers = {};
    if (!tempKey) {
        // 无 key 时先尝试自动认证：localhost 部署下后端直接下发密钥（傻瓜式启动），
        // 免去手动复制 api_secret_key 的步骤。
        try {
            const statusRes = await fetch(`${BASE_URL}/auth/status`);
            if (statusRes.ok) {
                const statusData = await statusRes.json();
                if (statusData && statusData.api_secret_key) {
                    tempKey = statusData.api_secret_key;
                    setApiSecretKey(tempKey);
                }
            }
        } catch (e) { /* 后端不可达等场景忽略，走下方原有 401/403 流程 */ }
    }
    if (tempKey) {
        headers['X-API-Key'] = tempKey;
    }

    const response = await fetch(`${BASE_URL}/config`, { headers });
    const result = await handleResponse(response);

    if (result && result.api_secret_key) {
        setApiSecretKey(result.api_secret_key);
    } else {
        console.warn('Config response missing api_secret_key, key will remain unset');
    }
    return result;
}

export async function saveConfig(configData) {
    const result = await apiFetch(`${BASE_URL}/config`, {
        method: 'POST',
        body: JSON.stringify(configData),
    });
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

export async function fetchDebugCaptures(limit = 30, channelId = '') {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    if (channelId && String(channelId).trim()) {
        params.set('channel_id', String(channelId).trim());
    }
    return apiFetch(`${BASE_URL}/debug/captures?${params.toString()}`);
}

export async function fetchDebugCaptureDetail(captureId) {
    return apiFetch(`${BASE_URL}/debug/captures/${captureId}`);
}

export async function sanitizeDebugText(text) {
    return apiFetch(`${BASE_URL}/debug/sanitize`, {
        method: 'POST',
        body: JSON.stringify({ text }),
    });
}

export async function fetchAvailableModels(provider, apiKey, baseUrl, task = 'chat') {
    return apiFetch(`${BASE_URL}/models/list`, {
        method: 'POST',
        body: JSON.stringify({ provider, api_key: apiKey, base_url: baseUrl, task }),
    });
}

export async function testModel(provider, apiKey, baseUrl, modelName, task = 'chat', extra = {}) {
    return apiFetch(`${BASE_URL}/models/test`, {
        method: 'POST',
        body: JSON.stringify({
            provider,
            api_key: apiKey,
            base_url: baseUrl,
            model_name: modelName,
            task,
            ...extra
        }),
    });
}

export async function fetchPluginConfig(pluginName) {
    const result = await apiFetch(`${BASE_URL}/plugins/${encodeURIComponent(pluginName)}/config`);
    return result;
}

// --- Knowledge Base API ---

// The new apiFetch function replaces the need for a separate authenticatedFetch

// Memory Functions
export async function fetchMemoryItems() {
    return apiFetch(`${BASE_URL}/memory`);
}

export async function addMemoryItem(itemData) {
    // The component now prepares the full object, including optional timestamp, userid, and timezone.
    // We just need to pass it along.
    return apiFetch(`${BASE_URL}/memory`, {
        method: 'POST',
        body: JSON.stringify(itemData),
    });
}

export async function deleteMemoryItem(itemId) {
    return apiFetch(`${BASE_URL}/memory/${itemId}`, {
        method: 'DELETE',
    });
}

export async function updateMemoryItem(itemId, content) {
    return apiFetch(`${BASE_URL}/memory/${itemId}`, {
        method: 'PUT',
        body: JSON.stringify({ content }),
    });
}

export async function directChat(messages, attachments = [], includeSystemPrompt = true, debugMode = false, debugContext = null, botId = null) {
    return apiFetch(`${BASE_URL}/chat/direct`, {
        method: 'POST',
        body: JSON.stringify({
            messages,
            attachments,
            include_system_prompt: includeSystemPrompt,
            debug_mode: debugMode,
            debug_context: debugContext,
            bot_id: botId
        }),
    });
}

export async function fetchMemoryCandidates(includePromoted = false, limit = 200) {
    return apiFetch(`${BASE_URL}/memory/candidates?include_promoted=${includePromoted ? 'true' : 'false'}&limit=${limit}`);
}

export async function promoteMemoryCandidate(candidateId) {
    return apiFetch(`${BASE_URL}/memory/candidates/${candidateId}/promote`, {
        method: 'POST',
    });
}

export async function deleteMemoryCandidate(candidateId) {
    return apiFetch(`${BASE_URL}/memory/candidates/${candidateId}`, {
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
    const result = await apiFetch(`${BASE_URL}/plugins/${encodeURIComponent(pluginName)}/config`, {
        method: 'POST',
        body: JSON.stringify(configData),
    });
    return result;
}

// --- Usage & Pricing API ---
export async function fetchUsageStats(period, view, signal) {
    const userTimezone = get(timezoneStore);
    return apiFetch(`${BASE_URL}/usage/stats?period=${period}&view=${view}`, {
        headers: {
            'X-Timezone': userTimezone || 'UTC'
        },
        signal,
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

// --- Bot Manager API ---
export async function fetchBots() {
    return apiFetch(`${BASE_URL}/bots`);
}

export async function createBot(config) {
    return apiFetch(`${BASE_URL}/bots`, {
        method: 'POST',
        body: JSON.stringify(config),
    });
}

export async function deleteBot(botId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}`, {
        method: 'DELETE',
    });
}

export async function renameBot(botId, newId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/rename`, {
        method: 'PUT',
        body: JSON.stringify({ new_id: newId }),
    });
}

export async function startBot(botId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/start`, {
        method: 'POST',
    });
}

export async function stopBot(botId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/stop`, {
        method: 'POST',
    });
}

export async function restartBot(botId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/restart`, {
        method: 'POST',
    });
}

export async function fetchBotConfig(botId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/config`);
}

export async function updateBotConfig(botId, config) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/config`, {
        method: 'PUT',
        body: JSON.stringify(config),
    });
}

export async function fetchBotLogs(botId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/logs`);
}

export async function exportBotConfig(botId) {
    const url = `${BASE_URL}/bots/${encodeURIComponent(botId)}/export`;
    const key = getApiSecretKey();
    const headers = {};
    if (key) headers['X-API-Key'] = key;

    const response = await fetch(url, { headers });
    if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Export failed' }));
        throw new Error(err.detail || 'Export failed');
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const filenameMatch = disposition.match(/filename="?(.+?)"?$/);
    const filename = filenameMatch ? filenameMatch[1] : `${botId}-config.json`;

    const downloadUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(downloadUrl);
}

export async function importBotConfig(file, overwrite = false) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('overwrite', String(overwrite));

    const key = getApiSecretKey();
    const headers = {};
    if (key) headers['X-API-Key'] = key;

    const response = await fetch(`${BASE_URL}/bots/import`, {
        method: 'POST',
        headers,
        body: formData,
    });
    if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Import failed' }));
        throw new Error(err.detail || 'Import failed');
    }
    return response.json();
}

export async function fetchBotGuilds(botId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/guilds`);
}

export async function fetchGuildChannels(botId, guildId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/guilds/${encodeURIComponent(guildId)}/channels`);
}

export async function fetchGuildRoles(botId, guildId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/guilds/${encodeURIComponent(guildId)}/roles`);
}

export async function searchGuildMembers(botId, guildId, query, timeoutMs = 5000) {
    const params = new URLSearchParams();
    if (query) params.set('query', query);
    params.set('timeout_ms', String(timeoutMs));
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/guilds/${encodeURIComponent(guildId)}/members?${params.toString()}`);
}

export async function fetchBotDiagnostics(botId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/diagnostics`);
}

// --- Provider Management API ---
export async function fetchProviders(botId) {
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/providers`);
}

export async function switchProvider(botId, payload) {
    // 后端 ProviderSwitchRequest 字段为 { provider, model, api_key, base_url? }
    return apiFetch(`${BASE_URL}/bots/${encodeURIComponent(botId)}/providers/switch`, {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

// --- Interaction History API ---
export async function fetchInteractionTree(botId, filters = {}) {
    const params = new URLSearchParams();
    if (filters.guild_id) params.set('guild_id', filters.guild_id);
    if (filters.role_id) params.set('role_id', filters.role_id);
    if (filters.channel_id) params.set('channel_id', filters.channel_id);
    if (filters.member_id) params.set('member_id', filters.member_id);
    return apiFetch(`${BASE_URL}/interactions/${encodeURIComponent(botId)}/tree?${params.toString()}`);
}

export async function fetchInteractionMembers(botId, guildId) {
    return apiFetch(`${BASE_URL}/interactions/${encodeURIComponent(botId)}/members?guild_id=${encodeURIComponent(guildId)}`);
}

export async function fetchInteractionMessages(botId, guildId, roleId, channelId, memberId, date) {
    return apiFetch(`${BASE_URL}/interactions/${encodeURIComponent(botId)}/messages?guild_id=${encodeURIComponent(guildId)}&role_id=${encodeURIComponent(roleId)}&channel_id=${encodeURIComponent(channelId)}&member_id=${encodeURIComponent(memberId)}&date=${encodeURIComponent(date)}`);
}

export async function fetchInteractionImages(botId, guildId, roleId, channelId, memberId, date) {
    return apiFetch(`${BASE_URL}/interactions/${encodeURIComponent(botId)}/images?guild_id=${encodeURIComponent(guildId)}&role_id=${encodeURIComponent(roleId)}&channel_id=${encodeURIComponent(channelId)}&member_id=${encodeURIComponent(memberId)}&date=${encodeURIComponent(date)}`);
}

export async function fetchInteractionImageFile(botId, guildId, roleId, channelId, memberId, date, filename) {
    return apiFetch(`${BASE_URL}/interactions/${encodeURIComponent(botId)}/image-file?guild_id=${encodeURIComponent(guildId)}&role_id=${encodeURIComponent(roleId)}&channel_id=${encodeURIComponent(channelId)}&member_id=${encodeURIComponent(memberId)}&date=${encodeURIComponent(date)}&filename=${encodeURIComponent(filename)}`);
}

export async function fetchInteractionUsage(botId) {
    return apiFetch(`${BASE_URL}/interactions/${encodeURIComponent(botId)}/usage`);
}

export async function deleteInteractionRecords(botId, filters = {}) {
    const params = new URLSearchParams();
    if (filters.guild_id) params.set('guild_id', filters.guild_id);
    if (filters.channel_id) params.set('channel_id', filters.channel_id);
    if (filters.member_id) params.set('member_id', filters.member_id);
    if (filters.date) params.set('date', filters.date);
    return apiFetch(`${BASE_URL}/interactions/${encodeURIComponent(botId)}/delete?${params.toString()}`, {
        method: 'DELETE',
    });
}

export async function pruneInteractions(botId) {
    return apiFetch(`${BASE_URL}/interactions/${encodeURIComponent(botId)}/prune`, {
        method: 'POST',
    });
}

export async function reconstructContext(botId, guildId, roleId, channelId, memberId, date) {
    return apiFetch(`${BASE_URL}/interactions/${encodeURIComponent(botId)}/context?guild_id=${encodeURIComponent(guildId)}&role_id=${encodeURIComponent(roleId)}&channel_id=${encodeURIComponent(channelId)}&member_id=${encodeURIComponent(memberId)}&date=${encodeURIComponent(date)}`, {
        method: 'POST',
    });
}
