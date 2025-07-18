// frontend/src/lib/api.js
const BASE_URL = '/api';

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
