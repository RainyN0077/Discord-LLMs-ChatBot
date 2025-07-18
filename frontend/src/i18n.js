// src/i18n.js (FINAL, VERIFIED & CORRECTED)
import { writable, derived } from 'svelte/store';
import en from './locales/en.js';
import zh from './locales/zh.js';

const translations = { en, zh };

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
    
    let text = translations[currentLang];
    
    const keys = key.split('.');
    for (const k of keys) {
        if (text && typeof text === 'object' && k in text) {
            text = text[k];
        } else {
            return key; // Fallback to key if not found
        }
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
