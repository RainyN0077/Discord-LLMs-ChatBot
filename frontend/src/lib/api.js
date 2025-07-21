// frontend/src/lib/api.js
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


async function handleResponse(response) {
  // 对 fetchLogs 的特殊处理
  if (response.url.endsWith('/api/logs')) {
      if (!response.ok) {
          throw new Error('Failed to fetch logs');
      }
      return response.text();
  }

  // 对所有其他API请求的处理
  if (!response.ok) {
    let errorDetail = 'An unknown error occurred.';
    const errorText = await response.text();
    try {
      const errorJson = JSON.parse(errorText);
      errorDetail = errorJson.detail || JSON.stringify(errorJson);
    } catch (e) {
      errorDetail = errorText || `Request failed with status ${response.status}`;
    }
    console.error('API Error:', response.status, errorDetail);
    throw new Error(errorDetail);
  }
  
  return response.json();
}

export async function fetchConfig() {
  console.log('Fetching config from backend...');
  const response = await fetch(`${BASE_URL}/config`);
  const result = await handleResponse(response);
  if (result.api_secret_key) {
      setApiSecretKey(result.api_secret_key);
  }
  console.log('Config fetched successfully:', result);
  return result;
}

export async function saveConfig(configData) {
  console.log('Saving config to backend:', configData);
  const response = await fetch(`${BASE_URL}/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(configData),
  });
  const result = await handleResponse(response);
  console.log('Config saved successfully:', result);
  return result;
}

export async function clearMemory(channelId) {
  const response = await fetch(`${BASE_URL}/memory/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel_id: channelId }),
  });
  return handleResponse(response);
}

export async function fetchLogs() {
  const response = await fetch(`${BASE_URL}/logs`);
  return handleResponse(response);
}

export async function simulateDebug(payload) {
  const response = await fetch(`${BASE_URL}/debug/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

export async function fetchAvailableModels(provider, apiKey, baseUrl) {
  const response = await fetch(`${BASE_URL}/models/list`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, api_key: apiKey, base_url: baseUrl }),
  });
  return handleResponse(response);
}

export async function testModel(provider, apiKey, baseUrl, modelName) {
  const response = await fetch(`${BASE_URL}/models/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      provider, 
      api_key: apiKey, 
      base_url: baseUrl,
      model_name: modelName 
    }),
  });
  return handleResponse(response);
}

export async function fetchPluginConfig(pluginName) {
    console.log(`Fetching config for plugin: ${pluginName}`);
    const apiKey = getApiSecretKey();
    if (!apiKey) return Promise.reject("API Secret Key not found.");

    const response = await fetch(`${BASE_URL}/plugins/${pluginName}/config`, {
        headers: { 'X-API-Key': apiKey }
    });
    const result = await handleResponse(response);
    console.log(`Config for ${pluginName} fetched successfully:`, result);
    return result;
}

// --- Knowledge Base API ---

async function authenticatedFetch(url, options = {}) {
    const key = getApiSecretKey();
    if (!key) {
        return Promise.reject(new Error("API Secret Key not found. Please refresh the page or re-login."));
    }

    const headers = {
        ...options.headers,
        'Content-Type': 'application/json',
        'X-API-Key': key,
    };

    const response = await fetch(url, { ...options, headers });
    return handleResponse(response);
}

// Memory Functions
export async function fetchMemoryItems() {
    return authenticatedFetch(`${BASE_URL}/memory`);
}

export async function addMemoryItem(content) {
    const timestamp = new Date().toISOString();
    return authenticatedFetch(`${BASE_URL}/memory`, {
        method: 'POST',
        body: JSON.stringify({ content, timestamp }),
    });
}

export async function deleteMemoryItem(itemId) {
    return authenticatedFetch(`${BASE_URL}/memory/${itemId}`, {
        method: 'DELETE',
    });
}

// World Book Functions
export async function fetchWorldBookItems() {
    return authenticatedFetch(`${BASE_URL}/worldbook`);
}

export async function addWorldBookItem(item) {
    return authenticatedFetch(`${BASE_URL}/worldbook`, {
        method: 'POST',
        body: JSON.stringify(item),
    });
}

export async function updateWorldBookItem(itemId, item) {
    return authenticatedFetch(`${BASE_URL}/worldbook/${itemId}`, {
        method: 'PUT',
        body: JSON.stringify(item),
    });
}

export async function deleteWorldBookItem(itemId) {
    return authenticatedFetch(`${BASE_URL}/worldbook/${itemId}`, {
        method: 'DELETE',
    });
}

export async function savePluginConfig(pluginName, configData) {
    console.log(`Saving config for plugin: ${pluginName}`, configData);
    const apiKey = getApiSecretKey();
    if (!apiKey) return Promise.reject("API Secret Key not found.");

    const response = await fetch(`${BASE_URL}/plugins/${pluginName}/config`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Key': apiKey
        },
        body: JSON.stringify(configData),
    });
    const result = await handleResponse(response);
    console.log(`Config for ${pluginName} saved successfully:`, result);
    return result;
}
