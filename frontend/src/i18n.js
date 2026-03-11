// src/i18n.js (FINAL, VERIFIED & CORRECTED)
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
            noResults: '暂无候选记忆',
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

// --- Language Management ---
const getInitialLang = () => {
    if (typeof window === 'undefined') return 'en'; // For SSR
    const browserLang = navigator.language.split('-')[0];
    return translations[browserLang] ? browserLang : 'en';
};

const storedLang = typeof window !== 'undefined' ? localStorage.getItem('lang') : null;
export const lang = writable(storedLang || getInitialLang());

lang.subscribe(value => {
    if (typeof window !== 'undefined') {
        localStorage.setItem('lang', value);
    }
});

export function setLang(newLang) {
    if (translations[newLang]) {
        lang.set(newLang);
    }
}

// --- Translation Logic ---
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

    // Primary language -> English fallback -> raw key.
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

    // Replace placeholders
    return text.replace(/\{(\w+)\}/g, (match, placeholder) => {
        return vars[placeholder] !== undefined ? vars[placeholder] : match;
    });
}

// --- Svelte Store Export ---

// ========= THIS IS THE CORRECTED LINE =========
export const t = derived(lang, ($lang) => (key, vars) => translate($lang, key, vars));
// ============================================

// Getter for non-Svelte JS files (like stores.js)
export const get = (key, vars) => {
    let currentLang;
    lang.subscribe(value => { currentLang = value; })(); // Get current value synchronously
    return translate(currentLang, key, vars);
};

// Also export as t_get for backward compatibility if you've used it
export { get as t_get };
