<!-- src/components/RoleConfigEditor.svelte (FINAL & CORRECT) -->
<script>
    import { t } from '../i18n.js';
    import { roleBasedConfigArray, config, updateConfigField } from '../lib/stores.js';
    import Card from './Card.svelte';

    // --- 数据更新函数 ---
    function updateRoleField(key, field, value) {
        const numberFields = ['message_limit', 'message_refresh_minutes', 'char_limit', 'char_refresh_minutes', 'char_output_budget'];
        if (numberFields.includes(field)) {
            value = value === '' ? 0 : Number(value);
        }
        updateConfigField(`role_based_config.${key}.${field}`, value);
    }
    
    function updateRoleId(oldKey, newId) {
        if (!newId || oldKey === newId) return;

        config.update(c => {
            const roles = c.role_based_config || {};
            if (roles[newId]) {
                alert($t('errors.duplicateId', { id: newId }));
                return c;
            }
            const roleData = roles[oldKey];
            delete roles[oldKey];
            roleData.id = newId;
            roles[newId] = roleData;
            return c;
        });
    }

    // --- 列表操作函数 ---
    function addRoleConfig() {
        config.update(c => {
            const newKey = `new-role-${Date.now()}`;
            if (!c.role_based_config) c.role_based_config = {};
            c.role_based_config[newKey] = {
                id: '', title: '', prompt: '', enable_message_limit: false, message_limit: 0, 
                message_refresh_minutes: 60, message_output_budget: 1, enable_char_limit: false, 
                char_limit: 0, char_refresh_minutes: 60, char_output_budget: 300, display_color: '#ffffff'
            };
            return c;
        });
    }

    function removeRoleConfig(key) {
        config.update(c => {
            delete c.role_based_config[key];
            return c;
        });
    }
</script>

<Card title={$t('roleConfig.title')}>
    <p class="info">{$t('roleConfig.info')}</p>
    <div class="list-container">
        {#each $roleBasedConfigArray as role (role._key)}
        <div class="list-item complex-item">
            <div class="list-item-main very-wide-grid">
                <input class="id-input" type="text" placeholder={$t('roleConfig.roleId')} value={role.id} on:blur={(e) => updateRoleId(role._key, e.target.value)}>
                <input class="nickname-input" type="text" placeholder={$t('roleConfig.roleTitle')} value={role.title} on:input={(e) => updateRoleField(role._key, 'title', e.target.value)}>
                <textarea class="prompt-input" rows="3" placeholder={$t('roleConfig.rolePrompt')} value={role.prompt} on:input={(e) => updateRoleField(role._key, 'prompt', e.target.value)}></textarea>
                
                <div class="limit-control-group">
                    <label class="toggle-switch"><input type="checkbox" checked={role.enable_message_limit} on:change={(e) => updateRoleField(role._key, 'enable_message_limit', e.target.checked)}><span class="slider"></span>{$t('roleConfig.enableMsgLimit')}</label>
                    <div class="limit-group" class:disabled={!role.enable_message_limit}>
                        <label>{$t('roleConfig.totalQuota')}:</label>
                        <input type="number" min="0" placeholder="0" disabled={!role.enable_message_limit} value={role.message_limit} on:input={(e) => updateRoleField(role._key, 'message_limit', e.target.value)}>
                        <span>/</span>
                        <input type="number" min="1" placeholder="60" disabled={!role.enable_message_limit} value={role.message_refresh_minutes} on:input={(e) => updateRoleField(role._key, 'message_refresh_minutes', e.target.value)}>
                        <span class="unit">{$t('roleConfig.minutes')}</span>
                    </div>
                </div>

                <div class="limit-control-group">
                    <label class="toggle-switch"><input type="checkbox" checked={role.enable_char_limit} on:change={(e) => updateRoleField(role._key, 'enable_char_limit', e.target.checked)}><span class="slider"></span>{$t('roleConfig.enableTokenLimit')}</label>
                    <div class="limit-group" class:disabled={!role.enable_char_limit}>
                        <label>{$t('roleConfig.totalQuota')}:</label>
                        <input type="number" min="0" placeholder="0" disabled={!role.enable_char_limit} value={role.char_limit} on:input={(e) => updateRoleField(role._key, 'char_limit', e.target.value)}>
                        <span>/</span>
                        <input type="number" min="1" placeholder="60" disabled={!role.enable_char_limit} value={role.char_refresh_minutes} on:input={(e) => updateRoleField(role._key, 'char_refresh_minutes', e.target.value)}>
                        <span class="unit">{$t('roleConfig.minutes')}</span>
                    </div>
                    <div class="limit-group budget-group" class:disabled={!role.enable_char_limit}>
                        <label>{$t('roleConfig.outputBudget')}:</label>
                        <input type="number" min="0" placeholder="300" disabled={!role.enable_char_limit} value={role.char_output_budget} on:input={(e) => updateRoleField(role._key, 'char_output_budget', e.target.value)}>
                    </div>
                </div>
                
                <div class="preview-section"><label>{$t('roleConfig.previewTitle')}</label><div class="quota-preview"><div class="preview-header" style="color: {role.display_color};">{$t('roleConfig.previewHeader')}</div><div class="preview-field"><span class="field-name">{$t('roleConfig.msgLimit')}</span><span class="field-value" style="color: {role.display_color};">{#if role.enable_message_limit}{role.message_limit - Math.floor(role.message_limit / 3)}/{role.message_limit > 0 ? role.message_limit : '∞'}{:else}{$t('roleConfig.disabled')}{/if}</span></div><div class="preview-field"><span class="field-name">{$t('roleConfig.tokenLimit')}</span><span class="field-value" style="color: {role.display_color};">{#if role.enable_char_limit}{role.char_limit - Math.floor(role.char_limit / 4)}/{role.char_limit > 0 ? role.char_limit : '∞'}{:else}{$t('roleConfig.disabled')}{/if}</span></div></div></div>
                <div class="color-picker-section"><label>{$t('roleConfig.displayColor')}</label><input type="color" value={role.display_color} on:input={(e) => updateRoleField(role._key, 'display_color', e.target.value)}></div>
            </div>
            <button class="remove-btn" on:click={() => removeRoleConfig(role._key)} title="Remove">×</button>
        </div>
        {/each}
    </div>
    <button class="add-btn" on:click={addRoleConfig}>{$t('roleConfig.add')}</button>
</Card>
