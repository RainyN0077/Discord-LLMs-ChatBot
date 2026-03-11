// src/lib/stores.js
import { writable, derived, get } from 'svelte/store';
import { get as t_get } from '../i18n.js';
import { saveConfig as apiSaveConfig, fetchConfig as apiFetchConfig } from './api.js';

// --- Default State ---
const defaultConfig = {
    discord_token: '', 
    llm_provider: 'openai', 
    api_key: '', 
    base_url: '', 
    openai_base_url: '',
    anthropic_base_url: '',
    model_name: 'gpt-4o', 
    system_prompt: '', 
    blocked_prompt_response: '',
    trigger_keywords: [],
    trigger_match_mode: 'contains',
    trigger_case_sensitive: false,
    auto_interject_enabled: false,
    auto_interject_interval: 20,
    auto_interject_min_length: 0,
    repeat_parrot_enabled: false,
    repeat_parrot_threshold: 3,
    repeat_parrot_case_sensitive: false,
    repeat_parrot_trim_whitespace: true,
    repeat_parrot_min_length: 2,
    repeat_parrot_require_multiple_users: true,
    stream_response: true, 
    auto_memory_enabled: true,
    auto_memory_min_length: 8,
    auto_memory_cooldown_seconds: 45,
    auto_memory_promote_min_observations: 2,
    auto_memory_promote_min_distinct_users: 1,
    auto_memory_quality_threshold: 0.55,
    auto_memory_direct_promote_ai_tag: false,
    auto_memory_recall_top_k: 12,
    auto_memory_recall_char_limit: 2200,
    auto_memory_recall_max_age_days: 365,
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


// --- NEW: Granular, Independent Stores ---
export const coreConfig = writable({
    discord_token: '',
    llm_provider: 'openai',
    api_key: '',
    base_url: '',
    openai_base_url: '',
    anthropic_base_url: '',
    model_name: 'gpt-4o',
    api_secret_key: ''
});

export const behaviorConfig = writable({
    bot_nickname: 'Endless',
    system_prompt: '',
    blocked_prompt_response: '',
    trigger_keywords: [],
    trigger_match_mode: 'contains',
    trigger_case_sensitive: false,
    auto_interject_enabled: false,
    auto_interject_interval: 20,
    auto_interject_min_length: 0,
    repeat_parrot_enabled: false,
    repeat_parrot_threshold: 3,
    repeat_parrot_case_sensitive: false,
    repeat_parrot_trim_whitespace: true,
    repeat_parrot_min_length: 2,
    repeat_parrot_require_multiple_users: true,
    stream_response: true,
    memory_dedup_threshold: 0.0,
    world_book_dedup_threshold: 0.0,
    auto_memory_enabled: true,
    auto_memory_min_length: 8,
    auto_memory_cooldown_seconds: 45,
    auto_memory_promote_min_observations: 2,
    auto_memory_promote_min_distinct_users: 1,
    auto_memory_quality_threshold: 0.55,
    auto_memory_direct_promote_ai_tag: false,
    auto_memory_recall_top_k: 12,
    auto_memory_recall_char_limit: 2200,
    auto_memory_recall_max_age_days: 365
});

export const contextConfig = writable({
    context_mode: 'channel',
    channel_context_settings: { message_limit: 10, char_limit: 4000 },
    memory_context_settings: { message_limit: 15, char_limit: 6000 }
});

export const pluginsConfig = writable({});
export const userPersonas = writable({});
export const roleConfigs = writable({});
export const scopedPrompts = writable({ guilds: {}, channels: {} });
export const customParameters = writable([]);


// --- General Purpose Stores (Unchanged) ---
export const statusMessage = writable('');
export const statusType = writable('info');
export const isLoading = writable(false);
export const customFontName = writable('');
export const rawLogs = writable('');

// --- Timezone Store (Unchanged) ---
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

// --- NEW: Refactored Derived Stores ---
// These now depend on smaller stores, reducing computation
export const roleBasedConfigArray = derived(roleConfigs, $rc => 
    Object.entries($rc || {}).map(([key, value]) => ({ ...value, _key: key }))
);
export const userPersonasArray = derived(userPersonas, $up => 
    Object.entries($up || {}).map(([key, value]) => ({ ...value, _key: key }))
);
export const pluginsArray = derived(pluginsConfig, $pc => 
    Object.entries($pc || {}).map(([key, value]) => ({ ...value, _key: key }))
);
export const scopedPromptsObject = derived(scopedPrompts, $sp => ({
    guilds: Object.entries($sp?.guilds || {}).map(([key, s]) => ({ ...s, _key: key })),
    channels: Object.entries($sp?.channels || {}).map(([key, s]) => ({ ...s, _key: key }))
}));
export const keywordsInput = derived(behaviorConfig, $bc => ($bc.trigger_keywords || []).join(', '));

export function setKeywords(value) {
    behaviorConfig.update(c => ({...c, trigger_keywords: value.split(',').map(k => k.trim()).filter(Boolean)}));
}

// --- Global Actions (Status Message) ---
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

// --- REFACTORED: Data Fetching and Saving ---
export async function fetchConfig() {
    isLoading.set(true);
    showStatus(t_get('status.loading'), 'info');
    try {
        const loadedConfig = await apiFetchConfig();
        const mergedConfig = { ...defaultConfig, ...loadedConfig };

        // Distribute fetched data into the new granular stores
        coreConfig.set({
            discord_token: mergedConfig.discord_token,
            llm_provider: mergedConfig.llm_provider,
            api_key: mergedConfig.api_key,
            base_url: mergedConfig.base_url,
            openai_base_url: mergedConfig.openai_base_url || mergedConfig.base_url || '',
            anthropic_base_url: mergedConfig.anthropic_base_url || '',
            model_name: mergedConfig.model_name,
            api_secret_key: mergedConfig.api_secret_key
        });
        behaviorConfig.set({
            bot_nickname: mergedConfig.bot_nickname,
            system_prompt: mergedConfig.system_prompt,
            blocked_prompt_response: mergedConfig.blocked_prompt_response,
            trigger_keywords: mergedConfig.trigger_keywords,
            trigger_match_mode: mergedConfig.trigger_match_mode || 'contains',
            trigger_case_sensitive: !!mergedConfig.trigger_case_sensitive,
            auto_interject_enabled: !!mergedConfig.auto_interject_enabled,
            auto_interject_interval: mergedConfig.auto_interject_interval ?? 20,
            auto_interject_min_length: mergedConfig.auto_interject_min_length ?? 0,
            repeat_parrot_enabled: !!mergedConfig.repeat_parrot_enabled,
            repeat_parrot_threshold: mergedConfig.repeat_parrot_threshold ?? 3,
            repeat_parrot_case_sensitive: !!mergedConfig.repeat_parrot_case_sensitive,
            repeat_parrot_trim_whitespace: mergedConfig.repeat_parrot_trim_whitespace !== false,
            repeat_parrot_min_length: mergedConfig.repeat_parrot_min_length ?? 2,
            repeat_parrot_require_multiple_users: mergedConfig.repeat_parrot_require_multiple_users !== false,
            stream_response: mergedConfig.stream_response,
            memory_dedup_threshold: mergedConfig.memory_dedup_threshold ?? 0.0,
            world_book_dedup_threshold: mergedConfig.world_book_dedup_threshold ?? 0.0,
            auto_memory_enabled: mergedConfig.auto_memory_enabled !== false,
            auto_memory_min_length: mergedConfig.auto_memory_min_length ?? 8,
            auto_memory_cooldown_seconds: mergedConfig.auto_memory_cooldown_seconds ?? 45,
            auto_memory_promote_min_observations: mergedConfig.auto_memory_promote_min_observations ?? 2,
            auto_memory_promote_min_distinct_users: mergedConfig.auto_memory_promote_min_distinct_users ?? 1,
            auto_memory_quality_threshold: mergedConfig.auto_memory_quality_threshold ?? 0.55,
            auto_memory_direct_promote_ai_tag: !!mergedConfig.auto_memory_direct_promote_ai_tag,
            auto_memory_recall_top_k: mergedConfig.auto_memory_recall_top_k ?? 12,
            auto_memory_recall_char_limit: mergedConfig.auto_memory_recall_char_limit ?? 2200,
            auto_memory_recall_max_age_days: mergedConfig.auto_memory_recall_max_age_days ?? 365
        });
        contextConfig.set({
            context_mode: mergedConfig.context_mode,
            channel_context_settings: mergedConfig.channel_context_settings,
            memory_context_settings: mergedConfig.memory_context_settings
        });
        pluginsConfig.set(mergedConfig.plugins || {});
        userPersonas.set(mergedConfig.user_personas || {});
        roleConfigs.set(mergedConfig.role_based_config || {});
        scopedPrompts.set(mergedConfig.scoped_prompts || { guilds: {}, channels: {} });
        customParameters.set(mergedConfig.custom_parameters || []);

        showStatus('', 'info');
    } catch (e) {
        console.error('Config fetch error in store:', e);
        showStatus(t_get('status.loadFailed', { error: e.message }), 'error');
    } finally {
        isLoading.set(false);
    }
}

export async function saveConfig() {
    isLoading.set(true);
    showStatus(t_get('status.saving'), 'info');

    // Gather data from all granular stores to build the final config object
    const finalConfig = {
        ...get(coreConfig),
        ...get(behaviorConfig),
        ...get(contextConfig),
        plugins: get(pluginsConfig),
        user_personas: get(userPersonas),
        role_based_config: get(roleConfigs),
        scoped_prompts: get(scopedPrompts),
        custom_parameters: get(customParameters).map(p => {
            let value = p.value;
            if (p.type === 'number') value = parseFloat(p.value) || 0;
            if (p.type === 'boolean') value = (p.value === 'true' || p.value === true);
            return { ...p, value };
        })
    };

    // Backward compatibility: keep legacy base_url aligned with OpenAI custom endpoint.
    finalConfig.base_url = finalConfig.openai_base_url || '';

    // Process user_personas to convert trigger_keywords from string to array
    if (finalConfig.user_personas) {
        Object.values(finalConfig.user_personas).forEach(persona => {
            if (typeof persona.trigger_keywords === 'string') {
                persona.trigger_keywords = persona.trigger_keywords.split(',').map(k => k.trim()).filter(Boolean);
            }
        });
    }
    
    // Cleanup logic remains the same
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
        await fetchConfig(); // Resync after saving
        showStatus(t_get('status.saveSuccess'), 'success');
    } catch (e) {
        console.error('Save error:', e);
        showStatus(t_get('status.saveFailed', { error: e.message }), 'error');
    } finally {
        isLoading.set(false);
    }
}
