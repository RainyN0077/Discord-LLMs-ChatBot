<!-- src/App.svelte (FINAL & CORRECT) -->
<script>
    import { onMount } from 'svelte';
import { loadFromIndexedDB } from './lib/fontStorage.js';
    import { t, setLang, lang } from './i18n.js';
    import { fetchConfig, saveConfig, statusMessage, statusType, isLoading, customFontName } from './lib/stores.js';
    import ControlPanel from './pages/ControlPanel.svelte';

    function applyFont(fontDataUrl, fontName) {
        const styleId = 'custom-font-style';
        let styleElement = document.getElementById(styleId);
        if (!styleElement) {
            styleElement = document.createElement('style');
            styleElement.id = styleId;
            document.head.appendChild(styleElement);
        }
        styleElement.innerHTML = `
            @font-face {
                font-family: 'CustomUserFont';
                src: url(${fontDataUrl});
            }
            body {
                font-family: 'CustomUserFont', -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei UI", "Microsoft YaHei", Segoe UI, Roboto, Oxygen, Ubuntu, Cantarell, "Fira Sans", "Droid Sans", Helvetica Neue, sans-serif;
            }
        `;
        customFontName.set(fontName);
    }

    onMount(async () => {
    fetchConfig();
    
    try {
        const fontDataUrl = await loadFromIndexedDB('customFontDataUrl');
        const fontName = await loadFromIndexedDB('customFontName');
        if (fontDataUrl && fontName) {
            applyFont(fontDataUrl, fontName);
        }
    } catch (e) {
        console.error('Failed to load font from IndexedDB:', e);
    }
});

</script>

<div class="lang-switcher">
    <button class:active={$lang === 'zh'} on:click={() => setLang('zh')}>中文</button>
    <button class:active={$lang === 'en'} on:click={() => setLang('en')}>English</button>
</div>

<ControlPanel {applyFont} />

<div class="save-footer">
    <div class="status-container">
        <div class="status {$statusType}" style:visibility={$statusMessage ? 'visible' : 'hidden'}>
            {$statusMessage || '...'}
        </div>
    </div>
    <button class="save-button" on:click={saveConfig} disabled={$isLoading}>
        {$isLoading ? $t('buttons.saving') : $t('buttons.save')}
    </button>
</div>

<style>
    /* Most styles have been moved to src/styles/global.css or component-specific files */

    .lang-switcher {
        position: fixed;
        top: 1rem;
        right: 1rem;
        display: flex;
        gap: .5rem;
        background-color: var(--card-bg);
        padding: .5rem;
        border-radius: 8px;
        box-shadow: var(--shadow);
        z-index: 1000;
    }
    .lang-switcher button {
        background-color: transparent;
        color: var(--text-light);
        padding: .5rem 1rem;
    }
    .lang-switcher button.active {
        color: var(--primary-color);
        font-weight: 700;
    }

    .save-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 1.5rem;
        padding: 1rem 2rem;
        background: rgba(255, 255, 255, 0.8);
        -webkit-backdrop-filter: blur(8px);
        backdrop-filter: blur(8px);
        border-top: 1px solid var(--border-color);
        z-index: 1001;
    }

    .status-container {
        flex-grow: 1;
        min-height: 0;
        padding: 0;
        margin: 0;
        display: block;
    }

    .status {
        width: auto;
        display: inline-block;
        margin: 0;
        padding: 0.75rem 1.25rem;
        text-align: left;
    }

    .status.success {
        background-color: var(--success-bg);
        color: var(--success-text);
    }
    .status.error {
        background-color: var(--error-bg);
        color: var(--error-text);
    }
    .status.info,
    .status.loading-special {
        background-color: var(--info-bg);
        color: var(--info-text);
    }

    .save-button {
        font-size: 1.1rem;
        padding: 0.8rem 2rem;
        background-color: var(--save-color);
        color: #fff;
    }
    .save-button:hover:not(:disabled) {
        background-color: var(--save-hover);
    }
</style>
