<script>
  import { onMount } from 'svelte';
  import { derived } from 'svelte/store';
  import { t, get as t_get } from '../i18n.js';
  import Card from '../components/Card.svelte';
  import ScopedPromptEditor from '../components/ScopedPromptEditor.svelte';
  import PluginEditor from '../components/PluginEditor.svelte';
  import RoleConfigEditor from '../components/RoleConfigEditor.svelte';
  import { promptTemplates, behaviorConfig, saveConfig, fetchConfig, statusMessage, statusType, isLoading, roleConfigs } from '../lib/stores.js';
  import { fetchPromptPresets, fetchPresetDetails, savePromptPreset, deletePromptPreset, fetchPromptPreview } from '../lib/api.js';

  function debounce(fn, delay) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  let activeTab = 'global'; // global, scopes, plugins, roles

  // --- Preset Management ---
  let presets = [];
  let selectedPreset = '';
  let fileInput;
  const UNDELETABLE_PRESET_NAME = '(默认)开箱即用';

  async function loadPresets() {
    try {
      presets = await fetchPromptPresets();
      if (presets.length > 0 && !selectedPreset) {
        selectedPreset = presets[0];
      }
    } catch (error) {
      console.error("Failed to load presets:", error);
      statusMessage.set(`加载预设失败: ${error.message}`);
      statusType.set('error');
    }
  }

  onMount(loadPresets);

  async function handleLoadPreset() {
    if (!selectedPreset) return;
    isLoading.set(true);
    statusMessage.set(t_get('promptStudio.preset.loading', { name: selectedPreset }));
    statusType.set('loading-special');
    try {
      const presetData = await fetchPresetDetails(selectedPreset);
      promptTemplates.set(presetData);
      statusMessage.set(t_get('promptStudio.preset.loadSuccess', { name: selectedPreset }));
      statusType.set('success');
    } catch (error) {
      statusMessage.set(t_get('promptStudio.preset.loadFailed', { error: error.message }));
      statusType.set('error');
    } finally {
      isLoading.set(false);
    }
  }

  async function handleSavePreset() {
    const name = prompt(t_get('promptStudio.preset.savePrompt'), selectedPreset || "My Preset");
    if (!name) return;
    isLoading.set(true);
    statusMessage.set(t_get('promptStudio.preset.saving', { name: name }));
    statusType.set('loading-special');
    try {
      await savePromptPreset(name, $promptTemplates);
      statusMessage.set(t_get('promptStudio.preset.saveSuccess', { name: name }));
      statusType.set('success');
      await loadPresets();
      selectedPreset = name;
    } catch (error) {
      statusMessage.set(t_get('promptStudio.preset.saveFailed', { error: error.message }));
      statusType.set('error');
    } finally {
      isLoading.set(false);
    }
  }

  async function handleDeletePreset() {
    if (!selectedPreset) return;
    if (!confirm(t_get('promptStudio.preset.deleteConfirm', { name: selectedPreset }))) return;
    isLoading.set(true);
    statusMessage.set(t_get('promptStudio.preset.deleting', { name: selectedPreset }));
    statusType.set('loading-special');
    try {
      await deletePromptPreset(selectedPreset);
      statusMessage.set(t_get('promptStudio.preset.deleteSuccess', { name: selectedPreset }));
      statusType.set('success');
      selectedPreset = '';
      await loadPresets();
    } catch (error) {
      statusMessage.set(t_get('promptStudio.preset.deleteFailed', { error: error.message }));
      statusType.set('error');
    } finally {
      isLoading.set(false);
    }
  }

  function handleImportClick() {
    fileInput.click();
  }

  function handleFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const importedData = JSON.parse(e.target.result);
        
        const requiredKeys = [
          'message_format',
          'user_request_block',
          'system_prompt_foundation_header',
          'operational_instructions'
        ];

        const missingKeys = requiredKeys.filter(key => typeof importedData[key] === 'undefined');

        if (missingKeys.length > 0) {
          throw new Error(t_get('promptStudio.preset.invalidFormat', { keys: missingKeys.join(', ') }));
        }

        promptTemplates.set(importedData);
        statusMessage.set(t_get('promptStudio.preset.importSuccess', { name: file.name }));
        statusType.set('success');
      } catch (error) {
        statusMessage.set(t_get('promptStudio.preset.importFailed', { error: error.message }));
        statusType.set('error');
      }
    };
    reader.onerror = () => {
        statusMessage.set(`${reader.error}`);
        statusType.set('error');
    };
    reader.readAsText(file);
    event.target.value = '';
  }


  // --- Data structure for the new navigation ---
  $: templateSections = {
    [$t('promptStudio.nav.messageContext')]: {
      message_format: $t('promptStudio.nav.messageFormat'),
      image_note: $t('promptStudio.nav.imageNote'),
      reply_context: $t('promptStudio.nav.replyContext'),
      deleted_reply_context: $t('promptStudio.nav.deletedReplyContext'),
      user_request_block: $t('promptStudio.nav.userRequestBlock'),
    },
    [$t('promptStudio.nav.knowledgeInjection')]: {
      tool_context: $t('promptStudio.nav.toolContext'),
      memory_context: $t('promptStudio.nav.memoryContext'),
      worldbook_context: $t('promptStudio.nav.worldbookContext'),
    },
    [$t('promptStudio.nav.systemPromptStructure')]: {
      system_prompt_foundation_header: $t('promptStudio.nav.foundationHeader'),
      system_prompt_persona_header: $t('promptStudio.nav.personaHeader'),
      system_prompt_situation_header: $t('promptStudio.nav.situationHeader'),
      system_prompt_participants_header: $t('promptStudio.nav.participantsHeader'),
      system_prompt_security_header: $t('promptStudio.nav.securityHeader'),
    },
    [$t('promptStudio.nav.coreInstructions')]: {
      operational_instructions: $t('promptStudio.nav.operationalInstructions'),
    },
  };

  let selectedTemplateKey = 'message_format'; 

  const placeholders = {
    message_format: ['{author_id}', '{content}', '{image_note}'],
    image_note: ['{count}'],
    reply_context: ['{author_info}', '{replied_content}'],
    tool_context: ['{data}'],
    memory_context: ['{data}'],
    worldbook_context: ['{data}'],
    user_request_block: ['{parts}'],
  };

  function addInstruction() {
    $promptTemplates.operational_instructions = [...($promptTemplates.operational_instructions || []), ""];
  }

  function removeInstruction(index) {
    $promptTemplates.operational_instructions = $promptTemplates.operational_instructions.filter((_, i) => i !== index);
  }

  // --- Backend-Driven Live Preview ---
  let isPreviewLoading = false;
  let previewResult = {
    final_system_prompt: "在下方配置模拟场景并点击“生成预览”以查看结果...",
    final_user_request: "",
    construction_log: []
  };

  let scenario = {
    user_id: "123456789",
    user_roles: [],
    channel_id: "987654321",
    guild_id: "555555555",
    message_content: "你好，我想问一下关于 @张三 的信息，顺便搜索一下今天的天气。",
    is_reply: true,
    replied_message: {
        author_id: "111222333",
        content: "你有什么问题吗？"
    },
    image_count: 1,
    triggered_plugins: [
        {
            "name": "搜索",
            "simulated_output": "今天天气晴朗，气温25度。"
        }
    ]
  };

  const updatePreview = debounce(async () => {
    if (!$promptTemplates || Object.keys($promptTemplates).length === 0) return;
    isPreviewLoading = true;
    try {
      // Create a deep copy to avoid reactivity issues with the debounced function
      const templatesCopy = JSON.parse(JSON.stringify($promptTemplates));
      const scenarioCopy = JSON.parse(JSON.stringify(scenario));
      
      previewResult = await fetchPromptPreview(templatesCopy, scenarioCopy);
    } catch (error) {
      console.error("Failed to fetch prompt preview:", error);
      previewResult.final_system_prompt = t_get('promptStudio.simulator.previewFailed', { error: error.message });
      previewResult.final_user_request = "";
      previewResult.construction_log = [`错误详情: ${error.stack}`];
    } finally {
      isPreviewLoading = false;
    }
  }, 500); // 500ms debounce

  // Trigger preview update when templates or scenario change
  $: if ($promptTemplates) updatePreview();
  $: if (scenario) updatePreview();

  async function handleSave() {
    await saveConfig();
  }

  function resetChanges() {
    fetchConfig(); 
  }
</script>

<style>
  /* --- Main container & Tabs --- */
  .studio-container { display: flex; flex-direction: column; gap: 1.5rem; }
  .tabs { display: flex; gap: 0.5rem; border-bottom: 2px solid var(--border-color); margin-bottom: 1.5rem; position: relative; }
  .tab { padding: 0.75rem 1.25rem; cursor: pointer; border: none; background: transparent; color: var(--text-light); font-size: 1rem; position: relative; transition: all 0.2s ease; }
  .tab::after { content: ''; position: absolute; bottom: -2px; left: 50%; transform: translateX(-50%) scaleX(0); width: 70%; height: 2px; background: var(--primary-color); border-radius: 2px; transition: transform 0.25s ease; }
  .tab.active { color: var(--primary-color); }
  .tab.active::after { transform: translateX(-50%) scaleX(1); }
  .tab:hover { color: var(--text-color); }
  
  /* --- Tab Content --- */
  .tab-content { display: none; }
  .tab-content.active { display: block; animation: fadeIn 0.3s ease-in-out; }
  
  @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  
  /* --- Global Template Tab (Three-column layout) --- */
  .global-template-grid {
    display: grid;
    grid-template-columns: 250px 1fr 1fr; /* Nav | Editor | Preview */
    gap: 2rem;
    height: calc(100vh - 280px); /* Adjust based on your header/footer height */
  }
  
  /* A common fix for flex/grid items overflowing their container */
  .global-template-grid > * {
    min-height: 0;
  }

  /* --- Left Nav --- */
  .template-nav { background-color: var(--card-bg); border-radius: var(--border-radius); padding: 1rem; overflow-y: auto; }
  .template-nav h4 { margin: 1rem 0 0.5rem; color: var(--text-color-secondary); font-size: 0.9rem; }
  .template-nav ul { list-style: none; padding: 0; margin: 0; }
  .template-nav li button { width: 100%; text-align: left; padding: 0.6rem 1rem; border: none; background: transparent; cursor: pointer; border-radius: 6px; color: var(--text-color); }
  .template-nav li button.active { background-color: var(--primary-color-translucent); color: var(--primary-color); font-weight: 500; }
  .template-nav li button:hover:not(.active) { background-color: var(--hover-bg); }

  /* --- Center Editor --- */
  .editor-panel {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .editor-panel textarea {
    width: 100%;
    flex-grow: 1; /* Let the textarea fill available space */
    resize: none; /* Disable manual resize as it's now adaptive */
  }
  .editor-panel label { font-weight: bold; display: block; }
  .instruction-item { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
  .instruction-item input { flex-grow: 1; }
  .placeholder-list { margin-top: 1rem; font-size: 0.9rem; color: var(--text-color-secondary); }
  .placeholder-list code { background: var(--hover-bg); padding: 2px 5px; border-radius: 4px; }

  /* --- Right Preview --- */
  .preview-panel .preview-content {
    height: 100%;
    margin: 0;
    overflow-y: auto;
    padding: 1rem;
    box-sizing: border-box;
    font-family: 'Fira Code', 'Courier New', monospace;
    font-size: 0.8rem;
    line-height: 1.6;
    color: #d4d4d4;
    white-space: pre-wrap;
    word-break: break-all;
    background-color: #1e1e1e;
    border-radius: 8px;
  }
  .preview-panel h3 { margin-top: 0; }

  .simulator-controls {
    background: var(--card-bg);
    padding: 1rem;
    border-radius: var(--border-radius);
    border: 1px solid var(--border-color);
  }
  .control-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin: 1rem 0;
  }
  .form-group { display: flex; flex-direction: column; gap: 0.5rem; }
  .form-group.checkbox-group { flex-direction: row; align-items: center; }
  .form-group label { font-weight: 500; font-size: 0.9rem; }
  
  .preview-content-container {
      background-color: #1e1e1e;
      border-radius: 8px;
      padding: 1rem;
      overflow-y: auto;
  }

  .preview-content h4 {
    color: var(--primary-color);
    margin: 1rem 0 0.5rem;
    padding-bottom: 0.25rem;
    border-bottom: 1px solid var(--border-color);
  }
  .construction-log {
    list-style-type: none;
    padding-left: 0;
    font-size: 0.8rem;
    color: #a0a0a0;
  }
  .construction-log li {
    padding: 0.2rem 0;
    white-space: pre-wrap;
  }
  .preview-content h4:first-child { margin-top: 0; }
  .preview-content i { color: var(--primary-color); }
  .preview-content pre {
    white-space: pre-wrap;
    word-break: break-all;
    margin: 0;
    padding: 0;
    font-family: inherit;
    font-size: inherit;
  }
  .preview-content hr {
    border: none;
    border-top: 1px solid var(--border-color);
    margin: 1.5rem 0;
  }

  /* --- General & Actions --- */
  .actions { display: flex; gap: 1rem; justify-content: flex-end; margin-top: 1rem; position: sticky; bottom: 1rem; background: var(--card-bg); padding: 1rem; border-radius: var(--border-radius); z-index: 10; }

  /* --- Preset Manager --- */
  .preset-manager {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    background-color: var(--card-bg);
    padding: 1rem;
    border-radius: var(--border-radius);
    margin-bottom: 1.5rem;
  }
  .preset-manager select {
    flex-grow: 1;
  }
  .preset-manager .danger {
      margin-left: auto; /* Pushes delete button to the right */
  }
</style>

<div class="studio-container">
  <h1>{$t('promptStudio.title')}</h1>
  <p>{$t('promptStudio.description')}</p>

  <div class="tabs">
    <button class="tab" class:active={activeTab === 'global'} on:click={() => activeTab = 'global'}>{$t('promptStudio.tabs.global')}</button>
    <button class="tab" class:active={activeTab === 'scopes'} on:click={() => activeTab = 'scopes'}>{$t('promptStudio.tabs.scopes')}</button>
    <button class="tab" class:active={activeTab === 'plugins'} on:click={() => activeTab = 'plugins'}>{$t('promptStudio.tabs.plugins')}</button>
    <button class="tab" class:active={activeTab === 'roles'} on:click={() => activeTab = 'roles'}>{$t('promptStudio.tabs.roles')}</button>
  </div>

  <div class="tab-content" class:active={activeTab === 'global'}>
    <div class="preset-manager">
      <select bind:value={selectedPreset} aria-label={$t('promptStudio.preset.selectPlaceholder')}>
        {#each presets as presetName}
          <option value={presetName}>{presetName}</option>
        {/each}
      </select>
      <button on:click={handleLoadPreset} disabled={!selectedPreset || $isLoading}>{$t('promptStudio.preset.load')}</button>
      <button on:click={handleSavePreset} disabled={$isLoading}>{$t('promptStudio.preset.saveAs')}</button>
      
      <button on:click={handleImportClick} disabled={$isLoading}>{$t('promptStudio.preset.import')}</button>
      <input type="file" bind:this={fileInput} on:change={handleFileSelected} accept=".json" style="display: none;" />

      <button class="danger" on:click={handleDeletePreset} disabled={!selectedPreset || selectedPreset === UNDELETABLE_PRESET_NAME || $isLoading}>{$t('promptStudio.preset.delete')}</button>
    </div>

    <div class="global-template-grid">
      <!-- Left Nav Panel -->
      <aside class="template-nav">
        {#each Object.entries(templateSections) as [sectionTitle, templates]}
          <h4>{sectionTitle}</h4>
          <ul>
            {#each Object.entries(templates) as [key, title]}
              <li>
                <button class:active={selectedTemplateKey === key} on:click={() => selectedTemplateKey = key}>
                  {title}
                </button>
              </li>
            {/each}
          </ul>
        {/each}
      </aside>

      <!-- Center Editor Panel -->
      <main class="editor-panel">
        {#if $promptTemplates}
          {#if selectedTemplateKey === 'operational_instructions'}
            <h3>{$t('promptStudio.editor.coreInstructions')}</h3>
            <p>{$t('promptStudio.editor.coreInstructionsDesc')}</p>
            {#if $promptTemplates.operational_instructions}
              {#each $promptTemplates.operational_instructions as instruction, i}
                <div class="instruction-item">
                  <input type="text" bind:value={$promptTemplates.operational_instructions[i]} placeholder={$t('promptStudio.editor.instructionPlaceholder')} />
                  <button class="danger" on:click={() => removeInstruction(i)}>{$t('promptStudio.editor.removeInstruction')}</button>
                </div>
              {/each}
            {/if}
            <button on:click={addInstruction}>{$t('promptStudio.editor.addInstruction')}</button>
          {:else}
            <label for="template-editor">{templateSections[Object.keys(templateSections).find(s => Object.keys(templateSections[s]).includes(selectedTemplateKey))]?.[selectedTemplateKey]}</label>
            <textarea id="template-editor" bind:value={$promptTemplates[selectedTemplateKey]}></textarea>
            {#if placeholders[selectedTemplateKey]}
              <div class="placeholder-list">
                <strong>{$t('promptStudio.editor.availablePlaceholders')}:</strong>
                {#each placeholders[selectedTemplateKey] as p}<code>{p}</code> {/each}
              </div>
            {/if}
          {/if}
        {/if}
      </main>

      <!-- Right Preview Panel -->
      <aside class="preview-panel" style="display: flex; flex-direction: column; gap: 1rem;">
        <div class="simulator-controls">
          <h3>{$t('promptStudio.simulator.title')}</h3>
          <div class="control-grid">
              <div class="form-group">
                  <label for="sim-message">{$t('promptStudio.simulator.userMessage')}</label>
                  <textarea id="sim-message" bind:value={scenario.message_content} rows="3"></textarea>
              </div>
              <div class="form-group">
                  <label for="sim-roles">{$t('promptStudio.simulator.userRoles')}</label>
                  <select id="sim-roles" bind:value={scenario.user_roles} multiple>
                      {#each Object.entries($roleConfigs) as [id, config]}
                          <option value={id}>{config.title}</option>
                      {/each}
                  </select>
              </div>
               <div class="form-group">
                  <label for="sim-images">{$t('promptStudio.simulator.imageCount')}</label>
                  <input id="sim-images" type="number" bind:value={scenario.image_count} min="0" />
              </div>
              <div class="form-group checkbox-group">
                  <input id="sim-is-reply" type="checkbox" bind:checked={scenario.is_reply} />
                  <label for="sim-is-reply">{$t('promptStudio.simulator.isReply')}</label>
              </div>
              {#if scenario.is_reply}
              <div class="form-group">
                  <label for="sim-reply-content">{$t('promptStudio.simulator.replyContent')}</label>
                  <input id="sim-reply-content" type="text" bind:value={scenario.replied_message.content} />
              </div>
              {/if}
          </div>
           <button on:click={updatePreview} disabled={isPreviewLoading}>
            {isPreviewLoading ? $t('promptStudio.simulator.generating') : $t('promptStudio.simulator.manualRefresh')}
          </button>
        </div>
        
        <div class="preview-content-container" style="flex-grow: 1; min-height: 0; display: flex; flex-direction: column;">
          <h3>{$t('promptStudio.simulator.backendPreview')} {isPreviewLoading ? $t('promptStudio.simulator.loading') : ''}</h3>
          <div class="preview-content" style="display: flex; flex-direction: column; gap: 1rem; flex-grow: 1;">
            <div class="prompt-section">
              <h4>{$t('promptStudio.simulator.systemPromptPreview')}</h4>
              <pre>{previewResult.final_system_prompt}</pre>
            </div>
            <hr/>
            <div class="prompt-section">
              <h4>{$t('promptStudio.simulator.userRequestPreview')}</h4>
              <pre>{previewResult.final_user_request}</pre>
            </div>
             <hr/>
            <div class="log-section">
              <h4>{$t('promptStudio.simulator.buildLog')}</h4>
              <ul class="construction-log">
                {#each previewResult.construction_log as log_entry}
                  <li>{log_entry}</li>
                {/each}
              </ul>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>

  <div class="tab-content" class:active={activeTab === 'scopes'}>
    <Card title={$t('promptStudio.scopeServerOverride')}>
      <ScopedPromptEditor type="guilds" />
    </Card>
    <Card title={$t('promptStudio.scopeChannelOverride')}>
      <ScopedPromptEditor type="channels" />
    </Card>
  </div>

  <div class="tab-content" class:active={activeTab === 'plugins'}>
    <PluginEditor />
  </div>

  <div class="tab-content" class:active={activeTab === 'roles'}>
    <RoleConfigEditor />
  </div>

  <div class="actions">
    {#if $statusMessage && $statusType !== 'loading-special'}
      <div class:success={$statusType === 'success'} class:error={$statusType === 'error'} style="margin-right: auto;">
        {$statusMessage}
      </div>
    {/if}
    <button on:click={resetChanges} disabled={$isLoading}>
      {$isLoading ? $t('promptStudio.loading') : $t('promptStudio.reset')}
    </button>
    <button class="primary" on:click={handleSave} disabled={$isLoading}>
      {$isLoading ? $t('promptStudio.saving') : $t('promptStudio.save')}
    </button>
  </div>
</div>