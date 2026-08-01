<script>
    import { t, lang } from '../i18n.js';
    import { STYLES, STYLE_ORDER, SCHEME_ORDER } from '../lib/themes.js';
    import { activeStyle, activeScheme, customCSS, animationsEnabled, setCustomCSSValue, resetToDefaults } from '../lib/themeStore.js';
    import Card from '../components/Card.svelte';

    let cssText = $customCSS;
    $: cssText = $customCSS;

    let showCyberpunkWarning = false;
    let pendingStyleId = null;

    function handleStyleSelect(styleId) {
        if (styleId === 'cyberpunk') {
            pendingStyleId = styleId;
            showCyberpunkWarning = true;
            return;
        }
        applyStyle(styleId);
    }

    function applyStyle(styleId) {
        activeStyle.set(styleId);
        const schemes = STYLES[styleId]?.schemes || {};
        const schemeIds = Object.keys(schemes);
        activeScheme.set(schemeIds.length > 0 ? schemeIds[0] : 'default');
    }

    function confirmCyberpunk() {
        showCyberpunkWarning = false;
        if (pendingStyleId) {
            applyStyle(pendingStyleId);
            pendingStyleId = null;
        }
    }

    function cancelCyberpunk() {
        showCyberpunkWarning = false;
        pendingStyleId = null;
    }

    function handleSchemeSelect(schemeId) {
        activeScheme.set(schemeId);
    }

    function applyCustomCSS() {
        setCustomCSSValue(cssText);
    }

    function resetCustomCSS() {
        cssText = '';
        setCustomCSSValue('');
    }

    function handleResetAll() {
        resetToDefaults();
        cssText = '';
    }

    function getStyleColor(styleId, schemeId) {
        const scheme = STYLES[styleId]?.schemes[schemeId];
        if (!scheme || !scheme.cssVars || !scheme.cssVars['--primary-color']) {
            const defaults = {
                light: '#1f8bd6',
                dark: '#45a3e6',
                neon: '#00e5ff',
                glass: '#7c8aff',
                minimal: '#1a1a1a',
                dawn: '#e67e22',
                midnight: '#7c8aff',
                nature: '#5a8a3c',
                cyberpunk: '#FFE600',
            };
            return defaults[styleId] || '#888';
        }
        return scheme.cssVars['--primary-color'];
    }

    function getStyleDisplayName(styleId) {
        const style = STYLES[styleId];
        if (!style) return styleId;
        return $lang === 'zh' ? style.name.zh : style.name.en;
    }

    function getSchemeDisplayName(schemeId) {
        for (const styleId of STYLE_ORDER) {
            const scheme = STYLES[styleId].schemes[schemeId];
            if (scheme) {
                return $lang === 'zh' ? scheme.name.zh : scheme.name.en;
            }
        }
        return schemeId;
    }

    $: currentSchemes = STYLES[$activeStyle]?.schemes || {};
    $: schemeIds = Object.keys(currentSchemes);
</script>

<div class="appearance-page">
    <Card title={$t('appearance.uiStyle')}>
        <div class="style-grid">
            {#each STYLE_ORDER as styleId}
                {@const style = STYLES[styleId]}
                <button
                    class="style-card"
                    class:active={$activeStyle === styleId}
                    on:click={() => handleStyleSelect(styleId)}
                >
                    <div class="style-preview">
                        <div class="preview-bar" style="background: {getStyleColor(styleId, 'default')};" />
                        <div class="preview-blocks">
                            <div class="preview-block" />
                            <div class="preview-block short" />
                        </div>
                        <div class="preview-dot" style="background: {getStyleColor(styleId, 'default')};" />
                    </div>
                    <span class="style-name">{getStyleDisplayName(styleId)}</span>
                </button>
            {/each}
        </div>
    </Card>

    <Card title={$t('appearance.colorScheme')}>
        <div class="scheme-list">
            {#each schemeIds as schemeId}
                <button
                    class="scheme-chip"
                    class:active={$activeScheme === schemeId}
                    on:click={() => handleSchemeSelect(schemeId)}
                >
                    <span
                        class="scheme-dot"
                        style="background: {getStyleColor($activeStyle, schemeId)};"
                    />
                    <span class="scheme-label">{getSchemeDisplayName(schemeId)}</span>
                </button>
            {/each}
        </div>
    </Card>

    <Card title={$t('appearance.animationSettings')}>
        <div class="toggle-group">
            <label class="toggle-switch switch-spring">
                <input type="checkbox" bind:checked={$animationsEnabled} />
                <span class="slider" />
                {$t('appearance.enablePageTransitions')}
            </label>
        </div>
    </Card>

    <Card title={$t('appearance.customCSS')}>
        <textarea
            class="css-editor"
            bind:value={cssText}
            placeholder={$t('appearance.cssPlaceholder')}
            rows="10"
            spellcheck="false"
        />
        <div class="css-actions">
            <button class="btn-primary" on:click={applyCustomCSS}>
                {$t('appearance.applyCSS')}
            </button>
            <button class="btn-secondary" on:click={resetCustomCSS}>
                {$t('appearance.resetCSS')}
            </button>
        </div>
    </Card>

    <div class="reset-section">
        <button class="btn-reset-all" on:click={handleResetAll}>
            {$t('appearance.resetAll')}
        </button>
    </div>
</div>

{#if showCyberpunkWarning}
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
    <div class="cyberpunk-warning-overlay" role="dialog" aria-modal="true" on:click={cancelCyberpunk} on:keydown={(e) => e.key === 'Escape' && cancelCyberpunk()}>
        <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
        <div class="cyberpunk-warning-dialog" on:click|stopPropagation on:keydown|stopPropagation>
            <h3 class="cyberpunk-warning-title">{$t('appearance.cyberpunkWipTitle')}</h3>
            <p class="cyberpunk-warning-body">{$t('appearance.cyberpunkWipBody')}</p>
            <div class="cyberpunk-warning-actions">
                <button class="btn-confirm" on:click={confirmCyberpunk}>
                    {$t('appearance.cyberpunkWipConfirm')}
                </button>
                <button class="btn-cancel" on:click={cancelCyberpunk}>
                    {$t('appearance.cyberpunkWipCancel')}
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
    .appearance-page {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        padding: 1rem 1.25rem;
        max-width: 800px;
        width: 100%;
        box-sizing: border-box;
    }

    .style-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: .75rem;
    }

    .style-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: .5rem;
        padding: .75rem .5rem;
        border: 2px solid var(--border-color);
        border-radius: var(--radius-md);
        background: var(--panel-soft-bg-2);
        cursor: pointer;
        transition: all .2s ease;
        box-shadow: none;
        font-weight: 500;
        font-size: .85rem;
        color: var(--text-color);
    }

    .style-card:hover {
        transform: translateY(-2px) scale(1.02);
        border-color: var(--primary-color);
        box-shadow: 0 6px 16px rgba(0, 0, 0, .1);
    }

    .style-card.active {
        border-color: var(--primary-color);
        background: var(--panel-muted-bg);
        box-shadow: 0 0 0 3px rgba(31, 139, 214, .15);
    }

    .style-preview {
        display: flex;
        flex-direction: column;
        gap: .3rem;
        width: 100%;
        padding: .4rem;
        background: var(--card-bg);
        border-radius: 4px;
        border: 1px solid var(--border-color);
    }

    .preview-bar {
        height: 6px;
        border-radius: 3px;
        width: 80%;
    }

    .preview-blocks {
        display: flex;
        flex-direction: column;
        gap: .2rem;
    }

    .preview-block {
        height: 5px;
        background: var(--text-muted);
        border-radius: 2px;
        width: 100%;
        opacity: .4;
    }

    .preview-block.short {
        width: 60%;
    }

    .preview-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        align-self: flex-end;
    }

    .style-name {
        font-size: .8rem;
        line-height: 1.2;
    }

    .scheme-list {
        display: flex;
        flex-wrap: wrap;
        gap: .5rem;
    }

    .scheme-chip {
        display: flex;
        align-items: center;
        gap: .4rem;
        padding: .4rem .7rem;
        border: 1.5px solid var(--border-color);
        border-radius: 20px;
        background: var(--panel-soft-bg-2);
        cursor: pointer;
        transition: all .2s ease;
        box-shadow: none;
        font-size: .82rem;
        color: var(--text-color);
    }

    .scheme-chip:hover {
        border-color: var(--primary-color);
    }

    .scheme-chip.active {
        border-color: var(--primary-color);
        background: var(--panel-muted-bg);
        box-shadow: 0 0 0 3px rgba(31, 139, 214, .12);
    }

    .scheme-dot {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        flex-shrink: 0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, .2);
        transition: transform .2s ease;
    }

    .scheme-chip.active .scheme-dot {
        transform: scale(1.2);
        box-shadow: 0 0 8px currentColor;
    }

    .scheme-label {
        font-size: .8rem;
    }

    .toggle-group {
        display: flex;
        flex-direction: column;
        gap: .75rem;
    }

    .css-editor {
        width: 100%;
        font-family: 'Fira Code', 'Courier New', monospace;
        font-size: .82rem;
        line-height: 1.5;
        background: var(--log-shell-bg);
        color: var(--log-text-color);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: .75rem;
        resize: vertical;
        min-height: 160px;
        tab-size: 2;
    }

    .css-editor::placeholder {
        color: var(--log-time-color);
    }

    .css-actions {
        display: flex;
        gap: .5rem;
        margin-top: .5rem;
    }

    .btn-primary {
        background: var(--primary-color);
        color: #fff;
        padding: .5rem 1.2rem;
        border-radius: var(--radius-md);
        font-size: .85rem;
        font-weight: 600;
        cursor: pointer;
        border: none;
        box-shadow: var(--shadow-soft);
        transition: all .2s ease;
    }

    .btn-primary:hover {
        background: var(--primary-hover);
    }

    .btn-secondary {
        background: var(--panel-muted-bg);
        color: var(--text-color);
        border: 1px solid var(--border-color);
        padding: .5rem 1.2rem;
        border-radius: var(--radius-md);
        font-size: .85rem;
        cursor: pointer;
        box-shadow: none;
        transition: all .2s ease;
    }

    .btn-secondary:hover {
        background: var(--panel-hover-bg);
    }

    .reset-section {
        display: flex;
        justify-content: flex-end;
        padding-top: .5rem;
    }

    .btn-reset-all {
        background: transparent;
        color: var(--error-text);
        border: 1px solid var(--error-text);
        padding: .4rem 1rem;
        border-radius: var(--radius-md);
        font-size: .8rem;
        cursor: pointer;
        box-shadow: none;
        transition: all .2s ease;
    }

    .btn-reset-all:hover {
        background: var(--error-bg);
    }

    @media (max-width: 768px) {
        .appearance-page {
            padding: .75rem;
            gap: .75rem;
        }

        .style-grid {
            grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
            gap: .5rem;
        }

        .style-card {
            padding: .5rem .35rem;
        }
    }

    .cyberpunk-warning-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, .6);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        animation: overlay-in .18s ease-out both;
    }

    .cyberpunk-warning-dialog {
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow), 0 0 40px rgba(255, 230, 0, .08);
        padding: 1.5rem 2rem;
        max-width: 460px;
        width: 90%;
        animation: dialog-in .2s cubic-bezier(.34, 1.56, .64, 1) both;
    }

    .cyberpunk-warning-title {
        margin: 0 0 .75rem 0;
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text-color);
    }

    .cyberpunk-warning-body {
        margin: 0 0 1.25rem 0;
        font-size: .88rem;
        line-height: 1.6;
        color: var(--text-light);
    }

    .cyberpunk-warning-actions {
        display: flex;
        gap: .5rem;
        justify-content: flex-end;
    }

    .btn-confirm {
        background: var(--primary-color);
        color: #0D0D0D;
        border: none;
        padding: .5rem 1.2rem;
        border-radius: var(--radius-md);
        font-size: .85rem;
        font-weight: 600;
        cursor: pointer;
        box-shadow: var(--shadow-soft);
        transition: all .2s ease;
    }

    .btn-confirm:hover {
        background: var(--primary-hover);
    }

    .btn-cancel {
        background: var(--panel-muted-bg);
        color: var(--text-color);
        border: 1px solid var(--border-color);
        padding: .5rem 1.2rem;
        border-radius: var(--radius-md);
        font-size: .85rem;
        cursor: pointer;
        box-shadow: none;
        transition: all .2s ease;
    }

    .btn-cancel:hover {
        background: var(--panel-hover-bg);
    }

    @keyframes overlay-in {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    @keyframes dialog-in {
        from { opacity: 0; transform: scale(.92) translateY(12px); }
        to { opacity: 1; transform: scale(1) translateY(0); }
    }
</style>
