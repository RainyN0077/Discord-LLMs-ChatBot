<script>
  import { onMount } from 'svelte';
  import { derived } from 'svelte/store';
  import Card from '../components/Card.svelte';
  import ScopedPromptEditor from '../components/ScopedPromptEditor.svelte';
  import PluginEditor from '../components/PluginEditor.svelte';
  import RoleConfigEditor from '../components/RoleConfigEditor.svelte';
  import { promptTemplates, behaviorConfig, saveConfig, fetchConfig, statusMessage, statusType, isLoading, roleConfigs } from '../lib/stores.js';
  import { fetchPromptPresets, fetchPresetDetails, savePromptPreset, deletePromptPreset, fetchPromptPreview } from '../lib/api.js';
  import { debounce } from 'lodash-es';

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
    statusMessage.set(`正在加载预设: ${selectedPreset}...`);
    statusType.set('loading-special');
    try {
      const presetData = await fetchPresetDetails(selectedPreset);
      promptTemplates.set(presetData);
      statusMessage.set(`预设 "${selectedPreset}" 加载成功。`);
      statusType.set('success');
    } catch (error) {
      statusMessage.set(`加载预设失败: ${error.message}`);
      statusType.set('error');
    } finally {
      isLoading.set(false);
    }
  }

  async function handleSavePreset() {
    const name = prompt("请输入新预设的名称：", selectedPreset || "我的预设");
    if (!name) return;
    isLoading.set(true);
    statusMessage.set(`正在保存预设: ${name}...`);
    statusType.set('loading-special');
    try {
      await savePromptPreset(name, $promptTemplates);
      statusMessage.set(`预设 "${name}" 保存成功。`);
      statusType.set('success');
      await loadPresets(); // Refresh the list
      selectedPreset = name; // Select the new preset
    } catch (error) {
      statusMessage.set(`保存预设失败: ${error.message}`);
      statusType.set('error');
    } finally {
      isLoading.set(false);
    }
  }

  async function handleDeletePreset() {
    if (!selectedPreset) return;
    if (!confirm(`您确定要删除预设 "${selectedPreset}" 吗？此操作无法撤销。`)) return;
    isLoading.set(true);
    statusMessage.set(`正在删除预设: ${selectedPreset}...`);
    statusType.set('loading-special');
    try {
      await deletePromptPreset(selectedPreset);
      statusMessage.set(`预设 "${selectedPreset}" 已删除。`);
      statusType.set('success');
      selectedPreset = '';
      await loadPresets();
    } catch (error) {
      statusMessage.set(`删除预设失败: ${error.message}`);
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
        
        // Enhanced validation: check for a set of essential keys
        const requiredKeys = [
          'message_format',
          'user_request_block',
          'system_prompt_foundation_header',
          'operational_instructions'
        ];

        const missingKeys = requiredKeys.filter(key => typeof importedData[key] === 'undefined');

        if (missingKeys.length > 0) {
          throw new Error(`无效的预设文件格式。缺少关键字段: ${missingKeys.join(', ')}`);
        }

        promptTemplates.set(importedData);
        statusMessage.set(`文件 "${file.name}" 已成功导入。您可以点击“另存为”来保存它。`);
        statusType.set('success');
      } catch (error) {
        statusMessage.set(`导入失败: ${error.message}`);
        statusType.set('error');
      }
    };
    reader.onerror = () => {
        statusMessage.set(`读取文件时出错: ${reader.error}`);
        statusType.set('error');
    };
    reader.readAsText(file);
    event.target.value = ''; // Reset file input
  }


  // --- Data structure for the new navigation ---
  const templateSections = {
    '消息与上下文': {
      message_format: '用户消息格式',
      image_note: '图片注释',
      reply_context: '回复上下文',
      deleted_reply_context: '已删除的回复上下文',
      user_request_block: '用户请求块',
    },
    '知识与工具注入': {
      tool_context: '工具输出',
      memory_context: '长期记忆',
      worldbook_context: '世界设定',
    },
    '系统提示词结构': {
      system_prompt_foundation_header: '基础规则标题',
      system_prompt_persona_header: '当前人设标题',
      system_prompt_situation_header: '情景上下文标题',
      system_prompt_participants_header: '参与者肖像标题',
      system_prompt_security_header: '安全与操作指令标题',
    },
    '核心操作指令': {
      operational_instructions: '核心操作指令列表',
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
      previewResult.final_system_prompt = `预览生成失败: ${error.message}`;
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
  .tabs { display: flex; gap: 0.5rem; border-bottom: 2px solid var(--border-color); margin-bottom: 1.5rem; }
  .tab { padding: 0.75rem 1.25rem; cursor: pointer; border: none; background: transparent; color: var(--text-color-secondary); font-size: 1rem; border-bottom: 2px solid transparent; transform: translateY(2px); }
  .tab.active { color: var(--primary-color); border-bottom-color: var(--primary-color); }
  
  /* --- Tab Content --- */
  .tab-content { display: none; }
  .tab-content.active { display: block; animation: fadeIn 0.3s ease-in-out; }
  
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
  .actions { display: flex; gap: 1rem; justify-content: flex-end; margin-top: 1rem; position: sticky; bottom: 1rem; background: var(--background-color); padding: 1rem; border-radius: var(--border-radius); z-index: 10; }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

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
  <h1>机器人行为配置中心</h1>
  <p>在这里，您可以统一管理机器人的各项行为配置，从全局指令到特定场景的响应。</p>

  <div class="tabs">
    <button class="tab" class:active={activeTab === 'global'} on:click={() => activeTab = 'global'}>全局模板</button>
    <button class="tab" class:active={activeTab === 'scopes'} on:click={() => activeTab = 'scopes'}>范围覆盖</button>
    <button class="tab" class:active={activeTab === 'plugins'} on:click={() => activeTab = 'plugins'}>插件集成</button>
    <button class="tab" class:active={activeTab === 'roles'} on:click={() => activeTab = 'roles'}>角色策略</button>
  </div>

  <div class="tab-content" class:active={activeTab === 'global'}>
    <div class="preset-manager">
      <select bind:value={selectedPreset} aria-label="选择预设">
        {#each presets as presetName}
          <option value={presetName}>{presetName}</option>
        {/each}
      </select>
      <button on:click={handleLoadPreset} disabled={!selectedPreset || $isLoading}>加载</button>
      <button on:click={handleSavePreset} disabled={$isLoading}>另存为...</button>
      
      <button on:click={handleImportClick} disabled={$isLoading}>导入</button>
      <input type="file" bind:this={fileInput} on:change={handleFileSelected} accept=".json" style="display: none;" />

      <button class="danger" on:click={handleDeletePreset} disabled={!selectedPreset || selectedPreset === UNDELETABLE_PRESET_NAME || $isLoading}>删除</button>
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
            <h3>核心操作指令</h3>
            <p>这些是指导机器人行为的核心规则，将按顺序注入到系统提示词中。</p>
            {#if $promptTemplates.operational_instructions}
              {#each $promptTemplates.operational_instructions as instruction, i}
                <div class="instruction-item">
                  <input type="text" bind:value={$promptTemplates.operational_instructions[i]} placeholder="输入一条指令" />
                  <button class="danger" on:click={() => removeInstruction(i)}>移除</button>
                </div>
              {/each}
            {/if}
            <button on:click={addInstruction}>添加新指令</button>
          {:else}
            <label for="template-editor">{templateSections[Object.keys(templateSections).find(s => Object.keys(templateSections[s]).includes(selectedTemplateKey))]?.[selectedTemplateKey]}</label>
            <textarea id="template-editor" bind:value={$promptTemplates[selectedTemplateKey]}></textarea>
            {#if placeholders[selectedTemplateKey]}
              <div class="placeholder-list">
                <strong>可用占位符:</strong>
                {#each placeholders[selectedTemplateKey] as p}<code>{p}</code> {/each}
              </div>
            {/if}
          {/if}
        {/if}
      </main>

      <!-- Right Preview Panel -->
      <aside class="preview-panel" style="display: flex; flex-direction: column; gap: 1rem;">
        <div class="simulator-controls">
          <h3>场景模拟器</h3>
          <div class="control-grid">
              <div class="form-group">
                  <label for="sim-message">用户消息</label>
                  <textarea id="sim-message" bind:value={scenario.message_content} rows="3"></textarea>
              </div>
              <div class="form-group">
                  <label for="sim-roles">用户角色 (按住Ctrl多选)</label>
                  <select id="sim-roles" bind:value={scenario.user_roles} multiple>
                      {#each Object.entries($roleConfigs) as [id, config]}
                          <option value={id}>{config.title}</option>
                      {/each}
                  </select>
              </div>
               <div class="form-group">
                  <label for="sim-images">图片数量</label>
                  <input id="sim-images" type="number" bind:value={scenario.image_count} min="0" />
              </div>
              <div class="form-group checkbox-group">
                  <input id="sim-is-reply" type="checkbox" bind:checked={scenario.is_reply} />
                  <label for="sim-is-reply">是回复消息</label>
              </div>
              {#if scenario.is_reply}
              <div class="form-group">
                  <label for="sim-reply-content">回复的内容</label>
                  <input id="sim-reply-content" type="text" bind:value={scenario.replied_message.content} />
              </div>
              {/if}
          </div>
           <button on:click={updatePreview} disabled={isPreviewLoading}>
            {isPreviewLoading ? '正在生成...' : '手动更新预览'}
          </button>
        </div>
        
        <div class="preview-content-container" style="flex-grow: 1; min-height: 0; display: flex; flex-direction: column;">
          <h3>后端实时预览 {isPreviewLoading ? '(加载中...)' : ''}</h3>
          <div class="preview-content" style="display: flex; flex-direction: column; gap: 1rem; flex-grow: 1;">
            <div class="prompt-section">
              <h4>系统提示词预览</h4>
              <pre>{previewResult.final_system_prompt}</pre>
            </div>
            <hr/>
            <div class="prompt-section">
              <h4>用户请求预览</h4>
              <pre>{previewResult.final_user_request}</pre>
            </div>
             <hr/>
            <div class="log-section">
              <h4>构建日志</h4>
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
    <Card title="服务器 (Guild) 覆盖">
      <ScopedPromptEditor type="guilds" />
    </Card>
    <Card title="频道 (Channel) 覆盖">
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
      {$isLoading ? '正在加载...' : '撤销本次修改'}
    </button>
    <button class="primary" on:click={handleSave} disabled={$isLoading}>
      {$isLoading ? '正在保存...' : '保存所有设置并重启'}
    </button>
  </div>
</div>