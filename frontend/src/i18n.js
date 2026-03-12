// src/i18n.js
import { writable, derived } from 'svelte/store';
import en from './locales/en.js';
import zh from './locales/zh.js';

function mergeDeep(base, extra) {
    if (typeof base !== 'object' || base === null) return extra;
    if (typeof extra !== 'object' || extra === null) return base;
    const out = { ...base };
    for (const [k, v] of Object.entries(extra)) {
        if (typeof v === 'object' && v !== null && typeof out[k] === 'object' && out[k] !== null) {
            out[k] = mergeDeep(out[k], v);
        } else {
            out[k] = v;
        }
    }
    return out;
}

const zhOverrides = {
    status: {
        waitingBackend: '后端启动中，正在等待连接...（{attempt}/{max}）',
    },
    contextControl: {
        unlimitedContextLength: '不限制上下文长度',
        unlimitedHistoryMessages: '不限制历史消息数量',
    },
    appNav: {
        controlPanel: '控制面板',
        directChat: '直接对话',
        personaHub: '身份管理',
        themeDark: '切换到深色模式',
        themeLight: '切换到浅色模式',
    },
    modelProviders: {
        openai: 'OpenAI',
        openaiCompatible: 'OpenAI 兼容',
        gemini: 'Gemini',
        anthropic: 'Anthropic',
        anthropicCompatible: 'Anthropic 兼容',
    },
    embeddingSettings: {
        title: 'Embedding 设置',
        provider: 'Embedding 提供方',
        apiKey: 'Embedding API Key',
        baseUrl: 'Embedding 接口地址',
        port: 'Embedding 端口',
        modelName: 'Embedding 模型',
        dimensions: '向量维度',
    },
    rerankSettings: {
        title: 'Rerank 设置',
        provider: 'Rerank 提供方',
        apiKey: 'Rerank API Key',
        baseUrl: 'Rerank 接口地址',
        port: 'Rerank 端口',
        modelName: 'Rerank 模型',
    },
    personaHub: {
        title: '身份管理中心',
        sections: {
            users: '用户',
            channels: '频道',
            guilds: '服务器',
            roles: '身份组',
        },
        discoveredUsersTitle: '已读取用户',
        allChannels: '全部频道',
        channelFallback: '频道',
        searchPlaceholder: '按显示名、用户名或 ID 搜索',
        refresh: '刷新',
        refreshing: '刷新中...',
        noDiscoveredUsers: '当前范围内暂无可管理用户。',
        addPortrait: '新增肖像',
        editPortrait: '编辑肖像',
        loadFailed: '加载已读取用户失败：{error}',
        helpLink: 'Help',
        helpTitle: '页面说明',
        helpBody: '身份管理中心用于集中维护身份相关配置。你可以快速筛选频道内已读取用户并编辑其用户肖像，也可以统一管理频道/服务器指令和身份组规则。',
        commonIssuesTitle: '常见问题',
        commonIssue1: '看不到已读取用户：当前范围内尚未产生可用 usage 元数据。',
        commonIssue2: '能看到用户但 @ 不正确：昵称应仅作称呼风格，不应替代真实 mention。',
        commonIssue3: '频道列表为空：最近可能没有被记录的交互数据。',
        commonIssue4: '改了肖像但效果不明显：可能尚未保存配置或后端未重载。',
        commonIssue5: '搜索不到目标用户：优先尝试直接输入完整用户 ID。',
        quickCheckTitle: '快速排查',
        quickCheck1: '点击本页刷新按钮，先拉取最新元数据。',
        quickCheck2: '将频道筛选切到“全部频道”，确认是否全局可见。',
        quickCheck3: '检查用户肖像中的 ID 是否正确且没有重复。',
        quickCheck4: '保存配置后确认后端已成功重启。',
        quickCheck5: '在 Discord 发一条测试消息，触发新一轮 usage 记录。',
        quickCheck6: '若仍异常，查看日志中 usage tracker 或 persona 解析错误。',
        helpClose: '关闭',
    },
    directChat: {
        title: 'LLM 直接对话',
        provider: '服务商',
        model: '模型',
        includeSystemPrompt: '附带当前系统提示词',
        clear: '清空对话',
        empty: '现在可以不借助 Discord，直接和当前配置的 LLM 对话。',
        you: '你',
        assistant: '助手',
        inputPlaceholder: '输入消息...（Enter 发送，Shift+Enter 换行）',
        send: '发送',
        sending: '发送中...',
        sendFailed: '发送失败：',
        usage: 'Token 用量',
    },
    usage: {
        periodLabel: '周期',
    },
    searchSettings: {
        getApiKey: '获取 Tavily API Key',
        maxResults: '最大搜索结果数',
        requireMainTrigger: '需要同时命中 Bot 触发',
        rewriteQueryWithLlm: '搜索前先用 LLM 整理查询词',
        usageGuide: {
            link: '触发说明',
            title: '搜索触发使用说明',
            intro: '搜索功能支持命令触发和关键词触发。请二选一配置并明确规则。',
            commandTitle: '命令触发',
            command1: '将触发模式设为命令，然后设置命令词，如 !search。',
            command2: '使用示例：!search 今天的 AI 新闻',
            command3: '命令必须出现在消息开头。',
            keywordTitle: '关键词触发',
            keyword1: '将触发模式设为关键词，并填写逗号分隔的关键词列表。',
            keyword2: '消息中出现任意关键词就会触发搜索。',
            keyword3: '关键词模式下会把整条消息作为搜索查询。',
            troubleshootTitle: '快速排查',
            troubleshoot1: '确认“启用搜索”已开启。',
            troubleshoot2: '检查 Tavily API Key 和 API URL 是否正确。',
            troubleshoot3: '触发模式只能选一种，不要混用。',
            troubleshoot4: '修改后请保存配置并等待 Bot 重启完成。',
            close: '关闭',
        },
    },
    knowledge: {
        tabs: {
            candidates: '记忆候选',
        },
        worldBook: {
            searchPlaceholder: '按关键词搜索...',
            noResults: '未找到匹配的世界书条目。',
        },
        confirmDeleteMemoryCandidate: '确定要删除这条记忆候选吗？',
        error: {
            loadMemoryCandidates: '加载记忆候选失败',
            promoteMemoryCandidate: '提升记忆候选失败',
            deleteMemoryCandidate: '删除记忆候选失败',
        },
        candidates: {
            title: '记忆候选',
            showPromoted: '显示已提升候选',
            refresh: '刷新',
            noResults: '暂无候选记录。',
            seenCount: '出现次数',
            distinctUsers: '用户数',
            lastSeen: '最后出现',
            status: '状态',
            promoted: '已提升',
            staged: '待提升',
            promote: '提升',
            delete: '删除',
        },
    },
};

const translations = { en, zh: mergeDeep(zh, zhOverrides) };

const getInitialLang = () => {
    if (typeof window === 'undefined') return 'en';
    const browserLang = navigator.language.split('-')[0];
    return translations[browserLang] ? browserLang : 'en';
};

const storedLang = typeof window !== 'undefined' ? localStorage.getItem('lang') : null;
export const lang = writable(storedLang || getInitialLang());

lang.subscribe((value) => {
    if (typeof window !== 'undefined') {
        localStorage.setItem('lang', value);
    }
});

export function setLang(newLang) {
    if (translations[newLang]) {
        lang.set(newLang);
    }
}

function translate(currentLang, key, vars = {}) {
    if (!currentLang || !key) {
        return '';
    }

    const readKey = (langCode) => {
        let value = translations[langCode];
        const keys = key.split('.');
        for (const k of keys) {
            if (value && typeof value === 'object' && k in value) {
                value = value[k];
            } else {
                return null;
            }
        }
        return value;
    };

    let text = readKey(currentLang);
    if (text == null && currentLang !== 'en') {
        text = readKey('en');
    }
    if (text == null) {
        return key;
    }

    if (typeof text !== 'string') {
        return key;
    }

    return text.replace(/\{(\w+)\}/g, (match, placeholder) => {
        return vars[placeholder] !== undefined ? vars[placeholder] : match;
    });
}

export const t = derived(lang, ($lang) => (key, vars) => translate($lang, key, vars));

export const get = (key, vars) => {
    let currentLang;
    lang.subscribe((value) => {
        currentLang = value;
    })();
    return translate(currentLang, key, vars);
};

export { get as t_get };
