<!-- src/components/ScopedPromptEditor.svelte (FIXED) -->
<script>
    import { scopedPromptsObject, config, updateConfigField } from '../lib/stores.js';
    import { t, get as t_get } from '../i18n.js';

    export let type; // 'guilds' or 'channels'
    
    // --- 数据更新函数 ---
    function updateItem(key, field, value) {
        updateConfigField(`scoped_prompts.${type}.${key}.${field}`, value);
    }

    function updateItemId(oldKey, newId) {
        if (!newId || oldKey === newId) return;
        
        config.update(c => {
            const typeItems = c.scoped_prompts[type] || {};
            if (typeItems[newId]) {
                // 在 <script> 块中使用 t_get 是正确的，因为它不是响应式的
                alert(t_get('errors.duplicateId', { id: newId }));
                return c;
            }
            const itemData = typeItems[oldKey];
            delete typeItems[oldKey];
            itemData.id = newId;
            typeItems[newId] = itemData;
            return c;
        });
    }

    // --- 列表操作函数 ---
    function addItem() {
        config.update(c => {
            const newKey = `new-${type}-${Date.now()}`;
            if (!c.scoped_prompts[type]) c.scoped_prompts[type] = {};
            c.scoped_prompts[type][newKey] = { id: '', enabled: true, mode: 'append', prompt: '' };
            return c;
        });
    }

    function removeItem(key) {
        config.update(c => {
            delete c.scoped_prompts[type][key];
            return c;
        });
    }
</script>

<!-- 在 HTML 模板中，所有对 t 的调用都需要加上 $ 前缀 -->
<p class="info">{$t(`scopedPrompts.${type}.info`)}</p>
<div class="list-container">
    {#if $scopedPromptsObject && $scopedPromptsObject[type]}
        {#each $scopedPromptsObject[type] as item (item._key)}
        <div class="list-item complex-item">
            <div class="list-item-main scoped-prompt-grid">
                <div class="cell-id">
                    <label>{$t(`scopedPrompts.${type}.id`)}</label>
                    <input type="text" placeholder={$t(`scopedPrompts.${type}.idPlaceholder`)} 
                           value={item.id} on:blur={(e) => updateItemId(item._key, e.target.value)}>
                </div>
                <div class="cell-toggle">
                    <label class="toggle-switch">
                        <input type="checkbox" checked={item.enabled} on:change={(e) => updateItem(item._key, 'enabled', e.target.checked)}>
                        <span class="slider"></span>{$t('scopedPrompts.enabled')}
                    </label>
                </div>
                <div class="cell-mode">
                    <label>{$t('scopedPrompts.mode.title')}</label>
                    <div class="radio-group small">
                        <label>
                            <input type="radio" name="mode-{type}-{item._key}" value='override' checked={item.mode === 'override'}
                                   on:change={(e) => updateItem(item._key, 'mode', e.target.value)}> {$t('scopedPrompts.mode.override')}
                        </label>
                        <label>
                             <input type="radio" name="mode-{type}-{item._key}" value='append' checked={item.mode === 'append'}
                                   on:change={(e) => updateItem(item._key, 'mode', e.target.value)}> {$t('scopedPrompts.mode.append')}
                        </label>
                    </div>
                </div>
                <div class="cell-prompt">
                    <label>{$t(`scopedPrompts.${type}.prompt`)}</label>
                    <textarea rows="3" 
                        placeholder={item.mode === 'override' ? $t(`scopedPrompts.${type}.overridePlaceholder`) : $t(`scopedPrompts.${type}.appendPlaceholder`)} 
                        value={item.prompt} on:input={(e) => updateItem(item._key, 'prompt', e.target.value)}
                    ></textarea>
                </div>
            </div>
            <button class="remove-btn" on:click={() => removeItem(item._key)} title={$t('scopedPrompts.remove')}>×</button>
        </div>
        {/each}
    {/if}
</div>
<button class="add-btn" on:click={addItem}>{$t(`scopedPrompts.${type}.add`)}</button>

