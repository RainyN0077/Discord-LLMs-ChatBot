<!-- src/components/PluginEditor.svelte (FINAL & CORRECT) -->
<script>
    import { t } from '../i18n.js';
    import { pluginsArray, config, updateConfigField } from '../lib/stores.js';
    import Card from './Card.svelte';

    // --- 数据更新函数 ---
    function updatePluginField(key, field, value) {
        if (field === 'triggers' && typeof value === 'string') {
            value = value.split(',').map(s => s.trim()).filter(Boolean);
        }
        updateConfigField(`plugins.${key}.${field}`, value);
    }
    function updateHttpConfig(key, field, value) {
        updateConfigField(`plugins.${key}.http_request_config.${field}`, value);
    }

    // --- 列表操作函数 ---
    function addPlugin() {
        config.update(c => {
            const newKey = `new-plugin-${Date.now()}`;
            if (!c.plugins) c.plugins = {};
            c.plugins[newKey] = { 
                name: 'New Plugin', enabled: true, trigger_type: 'command', triggers: [], action_type: 'http_request', injection_mode: 'override', 
                http_request_config: { url: '', method: 'GET', headers: '{}', body_template: '{}' }, 
                llm_prompt_template: 'Based on the user query "{user_input}", summarize the following API data:\n\n{api_result}'
            };
            return c;
        });
    }
    function removePlugin(key) {
        config.update(c => {
            delete c.plugins[key];
            return c;
        });
    }
</script>

<Card title={$t('pluginManager.title')} theme="dark-theme">
    <p class="info">{$t('pluginManager.info')}</p>
    <div class="list-container">
        {#each $pluginsArray as plugin (plugin._key)}
        <div class="list-item complex-item plugin-item">
            <div class="list-item-main very-wide-grid plugin-grid">
                <div class="plugin-cell cell-name"><label>{$t('pluginManager.name')}</label><input type="text" value={plugin.name} on:input={e => updatePluginField(plugin._key, 'name', e.target.value)}></div>
                <div class="plugin-cell cell-toggle"><label class="toggle-switch"><input type="checkbox" checked={plugin.enabled} on:change={e => updatePluginField(plugin._key, 'enabled', e.target.checked)}><span class="slider"></span>{$t('pluginManager.enabled')}</label></div>
                <div class="plugin-cell cell-trigger-type"><label>{$t('pluginManager.triggerType')}</label><select value={plugin.trigger_type} on:change={e => updatePluginField(plugin._key, 'trigger_type', e.target.value)}><option value="command">{$t('pluginManager.triggerTypes.command')}</option><option value="keyword">{$t('pluginManager.triggerTypes.keyword')}</option></select></div>
                <div class="plugin-cell cell-triggers"><label>{$t('pluginManager.triggers')}</label><input type="text" placeholder={$t('pluginManager.triggersPlaceholder')} value={Array.isArray(plugin.triggers) ? plugin.triggers.join(', ') : ''} on:input={e => updatePluginField(plugin._key, 'triggers', e.target.value)}></div>
                <div class="plugin-cell cell-action-type"><label>{$t('pluginManager.actionType')}</label><select value={plugin.action_type} on:change={e => updatePluginField(plugin._key, 'action_type', e.target.value)}><option value="http_request">{$t('pluginManager.actionTypes.http_request')}</option><option value="llm_augmented_tool">{$t('pluginManager.actionTypes.llm_augmented_tool')}</option></select></div>
                {#if plugin.action_type === 'llm_augmented_tool'}
                <div class="plugin-cell cell-injection-mode">
                    <label>{$t('pluginManager.injectionMode')}</label>
                    <div class="radio-group small">
                        <label><input type="radio" name="injection-mode-{plugin._key}" value={'override'} checked={plugin.injection_mode === 'override'} on:change={e => updatePluginField(plugin._key, 'injection_mode', e.target.value)}> {$t('pluginManager.injectionModes.override')}</label>
                        <label><input type="radio" name="injection-mode-{plugin._key}" value={'append'} checked={plugin.injection_mode === 'append'} on:change={e => updatePluginField(plugin._key, 'injection_mode', e.target.value)}> {$t('pluginManager.injectionModes.append')}</label>
                    </div>
                </div>
                {/if}
                <div class="plugin-cell cell-http-config wide-cell">
                    <label>{$t('pluginManager.httpRequest')}</label>
                    <div class="http-grid">
                       <label>{$t('pluginManager.url')}</label><input type="text" placeholder={$t('pluginManager.urlPlaceholder')} value={plugin.http_request_config.url} on:input={e => updateHttpConfig(plugin._key, 'url', e.target.value)}>
                       <label>{$t('pluginManager.method')}</label><select value={plugin.http_request_config.method} on:change={e => updateHttpConfig(plugin._key, 'method', e.target.value)}><option>GET</option><option>POST</option><option>PUT</option><option>DELETE</option></select>
                       <label>{$t('pluginManager.headers')}</label><textarea rows=2 placeholder={'{ "Authorization": "Bearer YOUR_TOKEN" }'} value={plugin.http_request_config.headers} on:input={e => updateHttpConfig(plugin._key, 'headers', e.target.value)}></textarea>
                       <label>{$t('pluginManager.body')}</label><textarea rows=2 placeholder={'{ "query": "{user_input}" }'} value={plugin.http_request_config.body_template} on:input={e => updateHttpConfig(plugin._key, 'body_template', e.target.value)}></textarea>
                    </div>
                </div>
                {#if plugin.action_type === 'llm_augmented_tool'}
                <div class="plugin-cell cell-llm-prompt wide-cell">
                    <label>{$t('pluginManager.llmPrompt')}</label>
                    <textarea rows="4" value={plugin.llm_prompt_template} on:input={e => updatePluginField(plugin._key, 'llm_prompt_template', e.target.value)}></textarea>
                    <p class="info template-info">{$t('pluginManager.templateInfo')}<br><strong>{$t('pluginManager.injectionMode')}:</strong> {$t('pluginManager.injectionInfo')}</p>
                </div>
                {/if}
            </div>
            <button class="remove-btn" on:click={() => removePlugin(plugin._key)} title="Remove">×</button>
        </div>
        {/each}
    </div>
    <button class="add-btn" on:click={addPlugin}>{$t('pluginManager.add')}</button>
</Card>
