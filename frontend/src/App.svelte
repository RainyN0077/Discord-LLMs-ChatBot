<!-- src/App.svelte -->
<script>
    import { onMount } from 'svelte';
    import { loadFromIndexedDB } from './lib/fontStorage.js';
    import { t, setLang, lang } from './i18n.js';
    import { fetchConfig, saveConfig, statusMessage, statusType, isLoading, customFontName } from './lib/stores.js';
    import ControlPanel from './pages/ControlPanel.svelte';
    import DirectChat from './pages/DirectChat.svelte';

    let activePage = 'panel';

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
        fetchConfig({ startup: true });

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

<div class="page-switcher">
    <button class:active={activePage === 'panel'} on:click={() => activePage = 'panel'}>
        {$t('appNav.controlPanel')}
    </button>
    <button class:active={activePage === 'chat'} on:click={() => activePage = 'chat'}>
        {$t('appNav.directChat')}
    </button>
</div>

<div class="lang-switcher">
    <button class:active={$lang === 'zh'} on:click={() => setLang('zh')}>ZH</button>
    <button class:active={$lang === 'en'} on:click={() => setLang('en')}>EN</button>
</div>

{#if activePage === 'panel'}
    <ControlPanel {applyFont} />
{:else}
    <DirectChat />
{/if}

{#if activePage === 'panel'}
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
{/if}

<style>
    .page-switcher {
        position: fixed;
        top: .9rem;
        left: .9rem;
        display: flex;
        gap: .5rem;
        background-color: rgba(255, 255, 255, .86);
        padding: .4rem;
        border-radius: 12px;
        box-shadow: var(--shadow);
        border: 1px solid rgba(15, 23, 42, .08);
        -webkit-backdrop-filter: blur(8px);
        backdrop-filter: blur(8px);
        z-index: 1000;
    }

    .page-switcher button {
        background-color: transparent;
        color: var(--text-light);
        padding: .5rem .95rem;
        box-shadow: none;
    }

    .page-switcher button.active {
        color: #fff;
        font-weight: 700;
        background: linear-gradient(135deg, var(--primary-color), #0f6fb2);
    }

    .lang-switcher {
        position: fixed;
        top: .9rem;
        right: .9rem;
        display: flex;
        gap: .5rem;
        background-color: rgba(255, 255, 255, .86);
        padding: .4rem;
        border-radius: 12px;
        box-shadow: var(--shadow);
        border: 1px solid rgba(15, 23, 42, .08);
        -webkit-backdrop-filter: blur(8px);
        backdrop-filter: blur(8px);
        z-index: 1000;
    }

    .lang-switcher button {
        background-color: transparent;
        color: var(--text-light);
        padding: .5rem .8rem;
        box-shadow: none;
    }

    .lang-switcher button.active {
        color: #fff;
        font-weight: 700;
        background: linear-gradient(135deg, var(--primary-color), #0f6fb2);
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
        padding: .85rem clamp(1rem, 2.4vw, 2rem);
        background: rgba(255, 255, 255, 0.86);
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
        border-radius: 10px;
        border: 1px solid transparent;
        box-shadow: var(--shadow-soft);
    }

    .status.success {
        background-color: var(--success-bg);
        color: var(--success-text);
        border-color: rgba(0, 121, 107, .18);
    }

    .status.error {
        background-color: var(--error-bg);
        color: var(--error-text);
        border-color: rgba(194, 24, 91, .18);
    }

    .status.info,
    .status.loading-special {
        background-color: var(--info-bg);
        color: var(--info-text);
        border-color: rgba(2, 119, 189, .18);
    }

    .save-button {
        font-size: 1.1rem;
        padding: .72rem 1.4rem;
        background: linear-gradient(135deg, var(--save-color), #1a9156);
        color: #fff;
    }

    @media (max-width: 880px) {
        .page-switcher {
            top: .65rem;
            left: .65rem;
        }

        .page-switcher button,
        .lang-switcher button {
            padding: .45rem .7rem;
            font-size: .9rem;
        }

        .lang-switcher {
            top: .65rem;
            right: .65rem;
        }

        .save-footer {
            justify-content: space-between;
            gap: .75rem;
            padding: .7rem 1rem;
        }

        .status {
            font-size: .88rem;
            padding: .6rem .85rem;
        }

        .save-button {
            font-size: .95rem;
            white-space: nowrap;
        }
    }
</style>
