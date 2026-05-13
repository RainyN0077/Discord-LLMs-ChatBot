<!-- src/App.svelte -->
<script>
    import { onMount } from 'svelte';
    import { loadFromIndexedDB } from './lib/fontStorage.js';
    import { t, setLang, lang } from './i18n.js';
    import { customFontName } from './lib/stores.js';
    import { setApiSecretKey } from './lib/api.js';
    import Sidebar from './components/Sidebar.svelte';
    import ConfigPanel from './pages/ConfigPanel.svelte';
    import LogPanel from './components/LogPanel.svelte';

    let selectedBotId = null;
    let theme = 'light';
    let sidebarVisible = true;

    function handleBotSelect(event) {
        selectedBotId = event.detail;
        if (window.innerWidth < 768) sidebarVisible = false;
    }

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

        const storedTheme = localStorage.getItem('theme');
        if (storedTheme === 'dark' || storedTheme === 'light') {
            theme = storedTheme;
        } else {
            theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        applyTheme(theme);

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

    function applyTheme(nextTheme) {
        theme = nextTheme;
        document.documentElement.setAttribute('data-theme', nextTheme);
        localStorage.setItem('theme', nextTheme);
    }

    function toggleTheme() {
        applyTheme(theme === 'dark' ? 'light' : 'dark');
    }

    function toggleSidebar() {
        sidebarVisible = !sidebarVisible;
    }
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
            <div class="lang-switcher">
                <button class:active={$lang === 'zh'} on:click={() => setLang('zh')}>ZH</button>
                <button class:active={$lang === 'en'} on:click={() => setLang('en')}>EN</button>
            </div>
            <button class="theme-toggle" on:click={toggleTheme} title={$t(theme === 'dark' ? 'appNav.themeLight' : 'appNav.themeDark')}>
                {theme === 'dark' ? '☀' : '☾'}
            </button>
        </div>
    </header>

    <div class="app-body">
        {#if sidebarVisible}
            <Sidebar bind:selectedBotId on:select={handleBotSelect} />
        {/if}
        <main class="main-content">
            <ConfigPanel {applyFont} botId={selectedBotId} />
            <LogPanel botId={selectedBotId} />
        </main>
    </div>
</div>

<style>
    :global(*) {
        margin: 0;
        box-sizing: border-box;
    }

    :global(body) {
        overflow: hidden;
    }

    .app-shell {
        display: flex;
        flex-direction: column;
        height: 100vh;
        width: 100vw;
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

    .theme-toggle {
        background: transparent;
        border: 1px solid var(--border-color);
        color: var(--text-light);
        padding: .25rem .55rem;
        border-radius: 6px;
        cursor: pointer;
        font-size: .85rem;
        box-shadow: none;
    }

    .theme-toggle:hover {
        color: var(--text-color);
        border-color: var(--primary-color);
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

        .lang-switcher button {
            padding: .18rem .3rem;
            font-size: .7rem;
        }

        .theme-toggle {
            padding: .2rem .4rem;
            font-size: .75rem;
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
</style>
