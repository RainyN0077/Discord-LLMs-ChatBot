import { writable, derived } from 'svelte/store';
import en from './locales/en.js';
import zh from './locales/zh.js';

const translations = { en, zh };

// Store to hold the current language
export const lang = writable('zh');

// Function to change the language
export function setLang(newLang) {
    if (translations[newLang]) {
        lang.set(newLang);
    }
}

function translate(lang, key) {
    let keys = key.split('.');
    let text = translations[lang];
    for (const k of keys) {
        if (text && typeof text === 'object' && k in text) {
            text = text[k];
        } else {
            return key; // Return key if not found
        }
    }
    return text;
}

// Derived store that provides the t() function
export const t = derived(lang, ($lang) => (key) => translate($lang, key));
