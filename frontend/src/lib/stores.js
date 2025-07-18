// src/lib/stores.js
import { writable, derived } from 'svelte/store';
import { get as t_get } from '../i18n.js';
import { saveConfig as apiSaveConfig, fetchConfig as apiFetchConfig } from './api.js';

// --- Default State ---
const defaultConfig = {
    discord_token: '', 
    llm_provider: 'openai', 
    api_key: '', 
    base_url: '', 
    model_name: 'gpt-4o', 
    system_prompt: '', 
    blocked_prompt_response: '',
    trigger_keywords: [],
    stream_response: true, 
    user_personas: {},
    role_based_config: {},
    scoped_prompts: { guilds: {}, channels: {} },
    context_mode: 'channel',
    channel_context_settings: { message_limit: 10, char_limit: 4000 },
    memory_context_settings: { message_limit: 15, char_limit: 6000 },
    custom_parameters: [],
    plugins: {},
    api_secret_key: ''
};

// --- Writable Stores ---
export const config = writable(JSON.parse(JSON.stringify(defaultConfig)));
export const statusMessage = writable('');
export const statusType = writable('info');
export const isLoading = writable(false);
export const customFontName = writable('');
export const rawLogs = writable('');

// --- Derived Stores ---
export const roleBasedConfigArray = derived(config, $config => 
    Object.entries($config.role_based_config || {}).map(([key, value]) => ({ ...value, _key: key }))
);
export const userPersonasArray = derived(config, $config => 
    Object.entries($config.user_personas || {}).map(([key, value]) => ({ ...value, _key: key }))
);
export const pluginsArray = derived(config, $config => 
    Object.entries($config.plugins || {}).map(([key, value]) => ({ ...value, _key: key }))
);
export const scopedPromptsObject = derived(config, $config => ({
    guilds: Object.entries($config.scoped_prompts?.guilds || {}).map(([key, s]) => ({ ...s, _key: key })),
    channels: Object.entries($config.scoped_prompts?.channels || {}).map(([key, s]) => ({ ...s, _key: key }))
}));
export const keywordsInput = derived(config, $config => ($config.trigger_keywords || []).join(', '));

export function setKeywords(value) {
    config.update(c => ({...c, trigger_keywords: value.split(',').map(k => k.trim()).filter(Boolean)}));
}

// --- Data Manipulation Functions ---
export function updateConfigField(path, value) {
    config.update(c => {
        const keys = path.split('.');
        let current = c;
        for (let i = 0; i < keys.length - 1; i++) {
            if (current[keys[i]] === undefined || current[keys[i]] === null) {
                current[keys[i]] = {};
            }
            current = current[keys[i]];
        }
        current[keys[keys.length - 1]] = value;
        return c;
    });
}

// --- Global Actions ---
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

export async function fetchConfig() {
    isLoading.set(true);
    showStatus(t_get('status.loading'), 'info');
    try {
        console.log('Starting config fetch...');
        const loadedConfig = await apiFetchConfig();
        console.log('Raw config from backend:', loadedConfig);
        
        // 合并配置，确保所有必需的字段都存在
        const mergedConfig = { ...defaultConfig };
        
        // 递归合并函数
        const deepMerge = (target, source) => {
            for (const key in source) {
                if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                    if (!target[key]) target[key] = {};
                    deepMerge(target[key], source[key]);
                } else {
                    target[key] = source[key];
                }
            }
        };
        
        deepMerge(mergedConfig, loadedConfig);
        
        // 确保嵌套对象存在
        mergedConfig.scoped_prompts = mergedConfig.scoped_prompts || {};
        mergedConfig.scoped_prompts.guilds = mergedConfig.scoped_prompts.guilds || {};
        mergedConfig.scoped_prompts.channels = mergedConfig.scoped_prompts.channels || {};
        
        console.log('Merged config:', mergedConfig);
        config.set(mergedConfig);
        showStatus('', 'info');
    } catch (e) {
        console.error('Config fetch error:', e);
        showStatus(t_get('status.loadFailed', { error: e.message }), 'error');
    } finally {
        isLoading.set(false);
    }
}

export async function saveConfig() {
    isLoading.set(true);
    showStatus(t_get('status.saving'), 'info');

    let currentConfig;
    config.subscribe(value => { currentConfig = value; })();

    const finalConfig = JSON.parse(JSON.stringify(currentConfig));

    // 预处理数据
    finalConfig.custom_parameters = (finalConfig.custom_parameters || []).map(p => {
        let value = p.value;
        if (p.type === 'number') value = parseFloat(p.value) || 0;
        if (p.type === 'boolean') value = (p.value === 'true' || p.value === true);
        return { ...p, value };
    });
    
    // 清理临时前端键
    const cleanup = (obj) => {
        if (typeof obj !== 'object' || obj === null) return;
        Object.values(obj).forEach(item => {
            if (typeof item === 'object' && item !== null) delete item._key;
        });
    };
    cleanup(finalConfig.plugins);
    cleanup(finalConfig.role_based_config);
    cleanup(finalConfig.user_personas);
    if(finalConfig.scoped_prompts) {
      cleanup(finalConfig.scoped_prompts.guilds);
      cleanup(finalConfig.scoped_prompts.channels);
    }

    console.log('Final config to save:', finalConfig);

    try {
        await apiSaveConfig(finalConfig);
        await fetchConfig(); // 重新同步
        showStatus(t_get('status.saveSuccess'), 'success');
    } catch (e) {
        console.error('Save error:', e);
        showStatus(t_get('status.saveFailed', { error: e.message }), 'error');
    } finally {
        isLoading.set(false);
    }
}
