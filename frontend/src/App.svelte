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
    
    // 从 localStorage 获取字体名称（作为标记）
    const savedFontName = localStorage.getItem('customFontName');
    if (savedFontName) {
        console.log('Found saved font name:', savedFontName); // 调试日志
        try {
            // 从 IndexedDB 加载字体数据
            const fontDataUrl = await loadFromIndexedDB('customFontDataUrl');
            const fontName = await loadFromIndexedDB('customFontName');
            if (fontDataUrl && fontName) {
                console.log('Loading font from IndexedDB:', fontName); // 调试日志
                applyFont(fontDataUrl, fontName);
            } else {
                console.log('Font data not found in IndexedDB'); // 调试日志
            }
        } catch (e) {
            console.error('Failed to load font from IndexedDB:', e);
            // 尝试从 localStorage 降级加载（兼容旧数据）
            const savedFontData = localStorage.getItem('customFontDataUrl');
            if (savedFontData && savedFontName) {
                console.log('Loading font from localStorage (fallback)'); // 调试日志
                applyFont(savedFontData, savedFontName);
            }
        }
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
    /* 粘贴旧 App.svelte 的完整样式块，并进行微调 */
    :root{--bg-color:#f7f9fc;--card-bg:#fff;--text-color:#2c3e50;--text-light:#7f8c8d;--primary-color:#3498db;--primary-hover:#2980b9;--border-color:#e4e7eb;--success-bg:#e0f2f1;--success-text:#00796b;--error-bg:#fce4ec;--error-text:#c2185b;--info-bg:#e1f5fe;--info-text:#0277bd;--save-color:#2ecc71;--save-hover:#27ae60;--shadow:0 4px 6px rgba(0,0,0,.05)}
    :global(body){background-color:var(--bg-color);color:var(--text-color);margin:0;padding:2rem 2rem 120px 2rem;-webkit-font-smoothing:antialiased; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei UI","Microsoft YaHei",Segoe UI,Roboto,Oxygen,Ubuntu,Cantarell,"Fira Sans","Droid Sans",Helvetica Neue,sans-serif;}
    :global(.page-container){display:flex;align-items:flex-start;gap:2rem;max-width:1600px;margin:0 auto}
    :global(main){flex:1;min-width:600px;display:flex;flex-direction:column;gap:2rem}
    :global(h1){color:var(--primary-color);text-align:center;font-weight:300;letter-spacing:1px;margin-bottom:0}
    :global(h2){color:var(--text-color);font-weight:600;border-bottom:1px solid var(--border-color);padding-bottom:.5rem;margin-top:0}
    :global(.card){background:var(--card-bg);border-radius:12px;padding:1.5rem 2rem;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:1.2rem}
    :global(label){font-weight:500;color:var(--text-light)}
    :global(input),:global(select),:global(textarea){width:100%;padding:.8rem 1rem;border:1px solid var(--border-color);border-radius:8px;font-size:1rem;box-sizing:border-box;background-color:#fcfdfe;transition:all .2s ease}
    :global(input:focus),:global(select:focus),:global(textarea:focus){outline:0;border-color:var(--primary-color);box-shadow:0 0 0 3px rgba(52,152,219,.2)}
    :global(textarea){resize:vertical;font-family:inherit}
    :global(button){border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;transition:all .2s ease;padding:.8rem 1.5rem}
    :global(button:disabled){cursor:not-allowed;opacity:.6}
    /* Hide old save container */
    :global(.save-container){ display: none !important; }
    :global(.radio-group){display:flex;flex-wrap:wrap;gap:1.5rem}
    :global(.radio-group label){display:flex;align-items:center;gap:.5rem;font-weight:400;color:var(--text-color);cursor:pointer}
    :global(.info){font-size:.9rem;color:var(--text-light);margin:0;padding-bottom:.5rem}
    :global(.list-container){display:flex;flex-direction:column;gap:1.5rem}
    :global(.list-item){display:flex;gap:.5rem;align-items:flex-start}
    :global(.list-item-main){display:grid;grid-template-columns:2fr 1.5fr;grid-template-rows:auto auto;gap:.5rem;flex-grow:1}
    :global(.id-input){grid-column:1/2}
    :global(.nickname-input){grid-column:2/3}
    :global(.prompt-input){grid-column:1/3}
    :global(.remove-btn){background-color:transparent;color:var(--text-light);padding:0;width:44px;height:44px;line-height:44px;text-align:center;font-size:1.5rem;flex-shrink:0;border-radius:50%}
    :global(.remove-btn:hover){background-color:var(--error-bg);color:var(--error-text)}
    :global(.add-btn){background-color:var(--info-bg);color:var(--info-text);align-self:flex-start;padding:.6rem 1.2rem;font-weight:500}
    :global(.add-btn:hover){background-color:#d1ecfa}
    :global(.control-grid){display:grid;grid-template-columns:auto 1fr;gap:1rem;align-items:center}
    :global(.slider-container){display:flex;align-items:center;gap:1rem}
    :global(.slider-container input[type=range]){flex-grow:1;accent-color:var(--primary-color)}
    :global(.slider-container span){min-width:110px;font-weight:500;text-align:right}
    :global(.context-settings){border-top:1px solid var(--border-color);margin-top:1rem;padding-top:1.5rem}
    .lang-switcher{position:fixed;top:1rem;right:1rem;display:flex;gap:.5rem;background-color:var(--card-bg);padding:.5rem;border-radius:8px;box-shadow:var(--shadow);z-index:1000}
    .lang-switcher button{background-color:transparent;color:var(--text-light);padding:.5rem 1rem}
    .lang-switcher button.active{color:var(--primary-color);font-weight:700}
    :global(.dark-theme){background-color:#202123;border:1px solid #444654;color:#ececf1}
    :global(.dark-theme h2),:global(.dark-theme label){color:#ececf1;border-color:#444654}
    :global(.dark-theme input),:global(.dark-theme select),:global(.dark-theme textarea){background-color:#40414f;border:1px solid #565869;color:#ececf1}
    :global(.dark-theme input::placeholder),:global(.dark-theme textarea::placeholder){color:#8e8ea0}
    :global(.dark-theme .remove-btn){color:#acacbe}
    :global(.dark-theme .remove-btn:hover){background-color:rgba(239,68,68,.2);color:#ef4444}
    :global(.dark-theme .add-btn){color:#ececf1;background-color:#40414f;border:1px solid #565869}
    :global(.dark-theme .add-btn:hover){background-color:#4d4e5a}
    :global(.param-item){display:grid;grid-template-columns:1.5fr 1fr 2fr auto;gap:1rem;align-items:center}
    :global(.param-select.wide),:global(.param-textarea){grid-column:3/4;resize:vertical;min-height:44px;font-family:monospace}
    :global(.param-item>.remove-btn){justify-self:center}
    :global(.action-container){display:flex;gap:1rem;align-items:center}
    :global(.log-viewer){width:600px;flex-shrink:0;background-color:var(--card-bg);border-radius:12px;padding:1rem 1.5rem;box-shadow:var(--shadow);position:sticky;top:2rem;height:calc(100vh - 4rem);display:flex;flex-direction:column}
    :global(.log-viewer h2){font-size:1.25rem}
    :global(.log-controls){display:flex;justify-content:space-between;align-items:center;gap:1rem;margin-bottom:1rem;flex-shrink:0;flex-wrap:wrap}
    :global(.log-filter-group){display:flex;gap:.5rem;align-items:center}
    :global(.log-filter-group span){color:var(--text-light);font-size:.9rem}
    :global(.log-filter-group button){background:#f0f2f5;color:#555;padding:.3rem .8rem;font-size:.85rem;border:1px solid var(--border-color)}
    :global(.log-filter-group button.active){background-color:var(--primary-color);color:#fff;border-color:var(--primary-color)}
    :global(.autoscroll-toggle){display:flex;align-items:center;gap:.5rem;color:var(--text-light);font-size:.9rem;cursor:pointer;user-select:none}
    :global(.autoscroll-toggle input){width:auto}
    :global(.log-output-wrapper){flex-grow:1;overflow:hidden;background-color:#1e1e1e;border-radius:8px;position:relative}
    :global(.log-output-wrapper pre){height:100%;margin:0;overflow-y:auto;padding:1rem;box-sizing:border-box;font-family:'Fira Code','Courier New',monospace;font-size:.8rem;line-height:1.6;color:#d4d4d4;white-space:pre-wrap;word-break:break-all}
    :global(.log-output-wrapper code){display:block}
    :global(.log-line.INFO){color:#81c784}
    :global(.log-line.WARNING){color:#ffd54f}
    :global(.log-line.ERROR){color:#e57373}
    :global(.log-line.CRITICAL){color:#ff8a65;font-weight:700}
    :global(.log-line.UNKNOWN){color:#90a4ae}
    :global(.very-wide-grid){display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto auto auto auto;gap:1rem 1.5rem;width:100%}
    :global(.toggle-switch){position:relative;display:inline-flex;align-items:center;cursor:pointer;font-weight:500;font-size:.9rem}
    :global(.toggle-switch input){opacity:0;width:0;height:0}
    :global(.toggle-switch .slider){width:44px;height:24px;background-color:#ccc;border-radius:12px;transition:.4s;position:relative;margin-right:10px}
    :global(.toggle-switch .slider:before){position:absolute;content:"";height:18px;width:18px;left:3px;bottom:3px;background-color:#fff;transition:.4s;border-radius:50%}
    :global(.toggle-switch input:checked+.slider){background-color:var(--primary-color)}
    :global(.toggle-switch input:checked+.slider:before){transform:translateX(20px)}
    /*... paste all other specific styles from your old file here ...*/
    :global(.plugin-item){border-top:2px solid #565869;padding-top:1.5rem}
    :global(.plugin-grid){display:grid;grid-template-columns:1fr 1fr;gap:1rem 1.5rem}
    :global(.action-btn){background-color: var(--primary-color); color: white; border: none; }
    :global(.action-btn:hover){background-color: var(--primary-hover); }
    :global(.action-btn-secondary){background-color: transparent; border: 1px solid var(--border-color); color: var(--text-color); }
    :global(.action-btn-secondary:hover){background-color: var(--border-color); }

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
    .status.success{background-color:var(--success-bg);color:var(--success-text)}.status.error{background-color:var(--error-bg);color:var(--error-text)}.status.info,.status.loading-special{background-color:var(--info-bg);color:var(--info-text)}
    .save-button {
      font-size: 1.1rem;
      padding: 0.8rem 2rem;
      background-color: var(--save-color);
      color: #fff;
    }
    .save-button:hover:not(:disabled) {
      background-color: var(--save-hover);
    }
    @media (max-width:1400px){
      :global(.page-container){flex-direction:column;align-items:stretch}
      :global(main){min-width:unset}
      :global(.log-viewer){width:auto;position:relative;top:0;height:70vh;margin-top:2rem}
    }
</style>
