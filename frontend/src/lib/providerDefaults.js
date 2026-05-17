export const PROVIDER_DEFAULTS = {
    deepseek: {
        baseUrl: 'https://api.deepseek.com',
        models: [
            { id: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
            { id: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' }
        ]
    },
    siliconflow: {
        baseUrl: 'https://api.siliconflow.cn/v1',
        models: [
            { id: 'deepseek-ai/DeepSeek-V4-Flash', label: 'DeepSeek V4 Flash' },
            { id: 'deepseek-ai/DeepSeek-V3.2', label: 'DeepSeek V3.2' },
            { id: 'deepseek-ai/DeepSeek-R1', label: 'DeepSeek R1' },
            { id: 'Pro/zai-org/GLM-5', label: 'GLM-5' },
            { id: 'Pro/zai-org/GLM-4.7', label: 'GLM-4.7' },
            { id: 'Qwen/Qwen3-235B-A22B', label: 'Qwen3 235B' },
            { id: 'Qwen/Qwen3-32B', label: 'Qwen3 32B' }
        ]
    },
    volcengine: {
        baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
        models: [
            { id: 'doubao-1.5-pro-32k', label: 'Doubao 1.5 Pro' },
            { id: 'doubao-1.5-lite-32k', label: 'Doubao 1.5 Lite' },
            { id: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
            { id: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' }
        ]
    },
    dashscope: {
        baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        models: [
            { id: 'qwen3.6-max-preview', label: 'Qwen3.6 Max' },
            { id: 'qwen3.6-plus', label: 'Qwen3.6 Plus' },
            { id: 'qwen3.6-flash', label: 'Qwen3.6 Flash' },
            { id: 'qwen-plus', label: 'Qwen Plus' },
            { id: 'qwen-max', label: 'Qwen Max' },
            { id: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
            { id: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' }
        ]
    },
    moonshot: {
        baseUrl: 'https://api.moonshot.cn/v1',
        models: [
            { id: 'kimi-k2.6', label: 'Kimi K2.6' },
            { id: 'moonshot-v1-8k', label: 'Moonshot V1 8K' },
            { id: 'moonshot-v1-32k', label: 'Moonshot V1 32K' },
            { id: 'moonshot-v1-128k', label: 'Moonshot V1 128K' }
        ]
    },
    zhipu: {
        baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
        models: [
            { id: 'glm-5.1', label: 'GLM-5.1' },
            { id: 'glm-5', label: 'GLM-5' },
            { id: 'glm-5-turbo', label: 'GLM-5 Turbo' },
            { id: 'glm-4.7', label: 'GLM-4.7' },
            { id: 'glm-4.6', label: 'GLM-4.6' },
            { id: 'glm-4.5', label: 'GLM-4.5' },
            { id: 'glm-4.7-flash', label: 'GLM-4.7 Flash' }
        ]
    },
    stepfun: {
        baseUrl: 'https://api.stepfun.com/v1',
        models: [
            { id: 'step-3.5-flash', label: 'Step 3.5 Flash' },
            { id: 'step-2-16k', label: 'Step 2 16K' },
            { id: 'step-1-8k', label: 'Step 1 8K' },
            { id: 'step-1-32k', label: 'Step 1 32K' }
        ]
    }
};

export const KNOWN_PROVIDERS = new Set(Object.keys(PROVIDER_DEFAULTS));

export function getProviderBaseUrl(coreConfig) {
    if (coreConfig.llm_provider === 'grok') return coreConfig.grok_base_url || '';
    if (coreConfig.llm_provider === 'anthropic') return coreConfig.anthropic_base_url || '';
    return coreConfig.openai_base_url || '';
}

export function providerForPlaceholder(provider) {
    if (provider === 'openai' || provider === 'openai_compatible' || provider === 'deepseek' ||
        provider === 'siliconflow' || provider === 'volcengine' || provider === 'dashscope' ||
        provider === 'moonshot' || provider === 'zhipu' || provider === 'stepfun') return 'openai';
    if (provider === 'grok') return 'grok';
    if (provider === 'gemini') return 'google';
    return 'anthropic';
}
