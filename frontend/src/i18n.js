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
    appNav: {
        controlPanel: '控制面板',
        directChat: '直接对话',
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
    knowledge: {
        tabs: {
            candidates: '记忆候选',
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
