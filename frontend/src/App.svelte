<!-- src/App.svelte -->
<script>
    import { onMount, onDestroy } from 'svelte';
    import { fade, fly } from 'svelte/transition';
    import { loadFromIndexedDB } from './lib/fontStorage.js';
    import { t, setLang, lang, get as t_get } from './i18n.js';
    import { customFontName, activePage } from './lib/commonStores.js';
    import { setApiSecretKey } from './lib/api.js';
    import { initTheme, startThemeSync, stopThemeSync, animationsEnabled } from './lib/themeStore.js';
    import './styles/typography.css';
    import Sidebar from './components/Sidebar.svelte';
    import LogPanel from './components/LogPanel.svelte';

    // --- Lazy page loaders (code-split each page into its own chunk) ---
    const pageLoaders = {
        config: () => import('./pages/ConfigPanel.svelte'),
        models: () => import('./pages/ModelSettings.svelte'),
        appearance: () => import('./pages/AppearanceSettings.svelte'),
        debug: () => import('./pages/Debugger.svelte'),
        userOptions: () => import('./pages/UserOptions.svelte'),
        promptStudio: () => import('./pages/PromptStudio.svelte'),
    };
    let configPromise;
    let modelsPromise;
    let appearancePromise;
    let debugPromise;
    let userOptionsPromise;
    let promptStudioPromise;

    const pageCache = {};

    function loadPage(key) {
        if (!pageCache[key]) {
            pageCache[key] = pageLoaders[key]().catch(err => {
                delete pageCache[key]; // allow retry on next navigation
                throw err;
            });
        }
        return pageCache[key];
    }

    $: {
        // Only load the currently active page — do NOT preload all pages
        const page = $activePage;
        if (pageLoaders[page]) {
            const promise = loadPage(page);
            switch (page) {
                case 'config': configPromise = promise; break;
                case 'models': modelsPromise = promise; break;
                case 'appearance': appearancePromise = promise; break;
                case 'debug': debugPromise = promise; break;
                case 'userOptions': userOptionsPromise = promise; break;
                case 'promptStudio': promptStudioPromise = promise; break;
            }
        }
    }

    let selectedBotId = null;
    let sidebarVisible = true;

    function handleBotSelect(event) {
        selectedBotId = event.detail;
        if (window.innerWidth < 768) sidebarVisible = false;
    }

    function applyFont(fontDataUrl, fontName) {
        // Validate font URL: must be a data:, blob:, https:, or http: URL
        if (typeof fontDataUrl !== 'string' || !/^(data:|blob:|https?:)\/\//i.test(fontDataUrl)) {
            console.error('Invalid font URL: rejected for security.');
            return;
        }
        const styleId = 'custom-font-style';
        let styleElement = document.getElementById(styleId);
        if (!styleElement) {
            styleElement = document.createElement('style');
            styleElement.id = styleId;
            document.head.appendChild(styleElement);
        }
        styleElement.textContent = `
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

    // Sync <html lang> attribute with current language
    $: if (typeof document !== 'undefined') {
        document.documentElement.lang = $lang === 'zh' ? 'zh-CN' : 'en';
    }

    onMount(async () => {
        try {
            const response = await fetch('/api/config');
            if (response.ok) {
                const config = await response.json();
                if (config.api_secret_key) {
                    setApiSecretKey(config.api_secret_key);
                }
            }
        } catch (e) {
            console.warn('Could not pre-fetch config:', e);
        }

        initTheme();
        startThemeSync();

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

    function toggleSidebar() {
        sidebarVisible = !sidebarVisible;
    }

    onDestroy(() => {
        stopThemeSync();
    });

    $: animOn = $animationsEnabled;
</script>

<div class="app-shell">
    <header class="app-header">
        <div class="header-left">
            <button class="hamburger-btn" on:click={toggleSidebar} aria-label="Toggle sidebar">
                ☰
            </button>
            <span class="app-logo">BOT Manager</span>
        </div>
        <div class="header-actions">
            <nav class="page-nav" aria-label="Main navigation">
                <button class:active={$activePage === 'config'} on:click={() => activePage.set('config')}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                    {$t('tabs.core')}
                </button>
                <button class:active={$activePage === 'models'} on:click={() => activePage.set('models')}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a4 4 0 0 1 4 4v1h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2V6a4 4 0 0 1 4-4z"/><path d="M9 7h6"/></svg>
                    {$t('appNav.modelSettings')}
                </button>
                <button class:active={$activePage === 'appearance'} on:click={() => activePage.set('appearance')}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 1 0 20"/><path d="M2 12h20"/></svg>
                    {$t('appNav.appearance')}
                </button>
                <button class:active={$activePage === 'debug'} on:click={() => activePage.set('debug')}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                    {$t('debugger.title')}
                </button>
                <button class:active={$activePage === 'userOptions'} on:click={() => activePage.set('userOptions')}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                    {$t('appNav.userOptions')}
                </button>
                <button class:active={$activePage === 'promptStudio'} on:click={() => activePage.set('promptStudio')}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                    </svg>
                    {$t('appNav.promptStudio')}
                </button>
            </nav>
            <div class="lang-switcher">
                <button class:active={$lang === 'zh'} on:click={() => setLang('zh')}>ZH</button>
                <button class:active={$lang === 'en'} on:click={() => setLang('en')}>EN</button>
            </div>
        </div>
    </header>

    <div class="app-body">
        {#if sidebarVisible}
            <Sidebar bind:selectedBotId on:select={handleBotSelect} />
        {/if}
        <main class="main-content">
            {#key $activePage}
                {#if $activePage === 'config'}
                    <div in:fly={{ x: 12, duration: animOn ? 180 : 0, opacity: 0 }} out:fade={{ duration: animOn ? 120 : 0 }} style="flex:1;display:flex;flex-direction:column;min-height:0;overflow:hidden;">
                        {#await configPromise}
                            <div class="page-loader"><div class="page-spinner" /><span>{$t('generic.loading') || 'Loading…'}</span></div>
                        {:then Module}
                            <svelte:component this={Module.default} {applyFont} botId={selectedBotId} />
                        {:catch err}
                            <div class="page-error" role="alert"><p>Failed to load page.</p><pre>{err.message}</pre></div>
                        {/await}
                    </div>
                {:else if $activePage === 'models'}
                    <div in:fly={{ x: 12, duration: animOn ? 180 : 0, opacity: 0 }} out:fade={{ duration: animOn ? 120 : 0 }} style="flex:1;display:flex;flex-direction:column;min-height:0;overflow:auto;">
                        {#await modelsPromise}
                            <div class="page-loader"><div class="page-spinner" /><span>{$t('generic.loading') || 'Loading…'}</span></div>
                        {:then Module}
                            <svelte:component this={Module.default} botId={selectedBotId} />
                        {:catch err}
                            <div class="page-error" role="alert"><p>Failed to load page.</p><pre>{err.message}</pre></div>
                        {/await}
                    </div>
                {:else if $activePage === 'appearance'}
                    <div in:fly={{ x: 12, duration: animOn ? 180 : 0, opacity: 0 }} out:fade={{ duration: animOn ? 120 : 0 }} style="flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;">
                        {#await appearancePromise}
                            <div class="page-loader"><div class="page-spinner" /><span>{$t('generic.loading') || 'Loading…'}</span></div>
                        {:then Module}
                            <svelte:component this={Module.default} />
                        {:catch err}
                            <div class="page-error" role="alert"><p>Failed to load page.</p><pre>{err.message}</pre></div>
                        {/await}
                    </div>
                {:else if $activePage === 'debug'}
                    <div in:fly={{ x: 12, duration: animOn ? 180 : 0, opacity: 0 }} out:fade={{ duration: animOn ? 120 : 0 }} style="flex:1;display:flex;flex-direction:column;min-height:0;overflow:auto;">
                        {#await debugPromise}
                            <div class="page-loader"><div class="page-spinner" /><span>{$t('generic.loading') || 'Loading…'}</span></div>
                        {:then Module}
                            <svelte:component this={Module.default} />
                        {:catch err}
                            <div class="page-error" role="alert"><p>Failed to load page.</p><pre>{err.message}</pre></div>
                        {/await}
                    </div>
                {:else if $activePage === 'userOptions'}
                    <div in:fly={{ x: 12, duration: animOn ? 180 : 0, opacity: 0 }} out:fade={{ duration: animOn ? 120 : 0 }} style="flex:1;display:flex;flex-direction:column;min-height:0;overflow:auto;">
                        {#await userOptionsPromise}
                            <div class="page-loader"><div class="page-spinner" /><span>{$t('generic.loading') || 'Loading…'}</span></div>
                        {:then Module}
                            <svelte:component this={Module.default} botId={selectedBotId} />
                        {:catch err}
                            <div class="page-error" role="alert"><p>Failed to load page.</p><pre>{err.message}</pre></div>
                        {/await}
                    </div>
                {:else if $activePage === 'promptStudio'}
                    <div in:fly={{ x: 12, duration: animOn ? 180 : 0, opacity: 0 }} out:fade={{ duration: animOn ? 120 : 0 }} style="flex:1;display:flex;flex-direction:column;min-height:0;overflow:auto;">
                        {#await promptStudioPromise}
                            <div class="page-loader"><div class="page-spinner" /><span>{$t('generic.loading') || 'Loading…'}</span></div>
                        {:then Module}
                            <svelte:component this={Module.default} botId={selectedBotId} />
                        {:catch err}
                            <div class="page-error" role="alert"><p>Failed to load page.</p><pre>{err.message}</pre></div>
                        {/await}
                    </div>
                {/if}
            {/key}
            {#if $activePage !== 'appearance'}
                <LogPanel botId={selectedBotId} />
            {/if}
        </main>
    </div>
</div>

<style>
    :global(*) {
        margin: 0;
        box-sizing: border-box;
    }

    :global(html) {
        overflow: hidden;
    }

    :global(body) {
        overflow: hidden;
        padding-top: 0;
        padding-left: 0;
        padding-right: 0;
    }

    .app-shell {
        display: flex;
        flex-direction: column;
        height: 100vh;
        width: 100%;
        overflow: hidden;
    }

    .app-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: .5rem 1rem;
        background: var(--floating-bg);
        border-bottom: 1px solid var(--floating-border);
        -webkit-backdrop-filter: blur(8px);
        backdrop-filter: blur(8px);
        z-index: 100;
        flex-shrink: 0;
        height: 46px;
        overflow: hidden;
    }

    .header-left {
        display: flex;
        align-items: center;
        gap: .5rem;
    }

    .hamburger-btn {
        display: none;
        background: transparent;
        border: none;
        color: var(--text-light);
        font-size: 1.2rem;
        cursor: pointer;
        padding: .2rem .35rem;
        border-radius: 4px;
        box-shadow: none;
    }

    .hamburger-btn:hover {
        color: var(--text-color);
        background: var(--panel-muted-bg);
    }

    .app-logo {
        font-weight: 800;
        font-size: 1.1rem;
        color: var(--primary-color);
        letter-spacing: -0.02em;
    }

    .header-actions {
        display: flex;
        align-items: center;
        gap: .5rem;
    }

    .page-nav {
        display: flex;
        gap: .15rem;
        background: var(--panel-muted-bg);
        border-radius: 6px;
        padding: .15rem;
        margin-right: .25rem;
    }

    .page-nav button {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        background: transparent;
        border: none;
        color: var(--text-light);
        padding: .25rem .55rem;
        font-size: .78rem;
        border-radius: 4px;
        cursor: pointer;
        box-shadow: none;
        white-space: nowrap;
        transition: all 0.2s ease;
    }

    .page-nav button:hover {
        color: var(--text-color);
        background: var(--panel-hover-bg);
    }

    .page-nav button.active {
        background: linear-gradient(135deg, var(--primary-color), #0f6fb2);
        color: #fff;
    }

    .page-nav button svg {
        flex-shrink: 0;
    }

    .lang-switcher {
        display: flex;
        gap: .15rem;
        background: var(--panel-muted-bg);
        border-radius: 6px;
        padding: .15rem;
    }

    .lang-switcher button {
        background: transparent;
        border: none;
        color: var(--text-light);
        padding: .25rem .45rem;
        font-size: .78rem;
        border-radius: 4px;
        cursor: pointer;
        box-shadow: none;
    }

    .lang-switcher button.active {
        background: linear-gradient(135deg, var(--primary-color), #0f6fb2);
        color: #fff;
    }

    :root[data-theme='neon'] .app-header {
        border-bottom-color: rgba(0, 229, 255, .35);
        border-bottom-width: 2px;
        background: linear-gradient(180deg, rgba(0, 229, 255, .06), rgba(6, 6, 13, .92));
    }

    :root[data-theme='neon'] .app-logo {
        color: #00e5ff;
        text-shadow: 0 0 12px rgba(0, 229, 255, .3);
    }

    .app-body {
        display: flex;
        flex: 1;
        overflow: hidden;
    }

    .main-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: var(--bg-color);
        min-width: 0;
        min-height: 0;
    }

    @media (max-width: 768px) {
        .app-header {
            padding: .4rem .65rem;
            height: 40px;
        }

        .hamburger-btn {
            display: block;
        }

        .app-logo {
            font-size: .92rem;
        }

        .page-nav button {
            padding: .18rem .35rem;
            font-size: .7rem;
            gap: .2rem;
        }

        .page-nav button svg {
            width: 12px;
            height: 12px;
        }

        .lang-switcher button {
            padding: .18rem .3rem;
            font-size: .7rem;
        }
    }

    @media (max-width: 480px) {
        .app-header {
            padding: .3rem .5rem;
            height: 38px;
        }

        .app-logo {
            font-size: .82rem;
        }

        .lang-switcher button {
            padding: .15rem .25rem;
            font-size: .65rem;
        }

        .header-actions {
            gap: .25rem;
        }
    }

    /* --- Lazy page loading states --- */
    .page-loader {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        padding: 3rem 1rem;
        color: var(--text-light);
        font-size: 0.85rem;
        flex: 1;
    }
    .page-spinner {
        width: 28px;
        height: 28px;
        border: 3px solid var(--border-color);
        border-top-color: var(--primary-color);
        border-radius: 50%;
        animation: page-spin 0.7s linear infinite;
    }
    @keyframes page-spin {
        to { transform: rotate(360deg); }
    }
    .page-error {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.75rem;
        padding: 2rem 1rem;
        color: var(--error-text);
        text-align: center;
        flex: 1;
    }
    .page-error pre {
        font-size: 0.75rem;
        max-width: 100%;
        overflow-x: auto;
        color: var(--text-light);
    }
</style>
