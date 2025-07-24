<!-- frontend/src/components/KnowledgeEditor.svelte -->
<script>
  import { onMount, onDestroy } from 'svelte';
  import { t } from '../i18n.js';
  import {
    fetchMemoryItems, addMemoryItem, deleteMemoryItem, updateMemoryItem,
    fetchWorldBookItems, addWorldBookItem, updateWorldBookItem, deleteWorldBookItem
  } from '../lib/api.js';
  import { userPersonasArray, behaviorConfig, saveConfig } from '../lib/stores.js';
  import Card from './Card.svelte';

  let activeTab = 'worldbook';
  let memoryItems = [];
  let worldBookItems = [];
  let newMemoryContent = '';
  let newMemoryUserName = 'WebUI';
  let newMemoryUserId = '';
  let newMemoryTimestamp = '';
  
  let searchQuery = '';
  
  let newWorldBookItem = { keywords: '', content: '', enabled: true, linked_user_id: '', aliases: '', triggers: '' };
  let editingWorldBookItem = null;
  let worldBookSearchQuery = '';
  let editingMemoryId = null;
  let editingMemoryContent = '';
  let memoryPollInterval = null;

  onMount(async () => {
    loadMemoryItems();
    loadWorldBookItems();
    memoryPollInterval = setInterval(loadMemoryItems, 5000);
  });

  onDestroy(() => {
    if (memoryPollInterval) clearInterval(memoryPollInterval);
  });

  // --- Memory Functions ---
  async function loadMemoryItems() {
    try {
      memoryItems = await fetchMemoryItems();
    } catch (e) {
      alert(`${$t('knowledge.error.loadMemory')}: ${e.message}`);
    }
  }

  async function handleAddMemory() {
    if (!newMemoryContent.trim()) return;
    try {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const itemData = {
        content: newMemoryContent.trim(),
        user_name: newMemoryUserName.trim() || 'WebUI',
        user_id: newMemoryUserId.trim() || null,
        timestamp: newMemoryTimestamp || null,
        timezone: newMemoryTimestamp ? timezone : null,
        source: '手动添加'
      };
      await addMemoryItem(itemData);
      newMemoryContent = '';
      newMemoryUserId = '';
      newMemoryTimestamp = '';
      loadMemoryItems();
    } catch (e) {
      alert(`${$t('knowledge.error.addMemory')}: ${e.message}`);
    }
  }

  async function handleDeleteMemory(id) {
    if (confirm($t('knowledge.confirmDeleteMemory'))) {
      try {
        await deleteMemoryItem(id);
        loadMemoryItems();
      } catch (e) {
        alert(`${$t('knowledge.error.deleteMemory')}: ${e.message}`);
      }
    }
  }

  function startEditMemory(item) {
    editingMemoryId = item.id;
    editingMemoryContent = formatMemoryContent(item.content);
  }

  function cancelEditMemory() {
    editingMemoryId = null;
    editingMemoryContent = '';
  }

  async function handleUpdateMemory() {
    if (!editingMemoryContent.trim()) return;
    try {
      await updateMemoryItem(editingMemoryId, editingMemoryContent.trim());
      cancelEditMemory();
      loadMemoryItems();
    } catch (e) {
      alert(`${$t('knowledge.error.updateMemory')}: ${e.message}`);
    }
  }
  
  // --- World Book Functions ---
  async function loadWorldBookItems() {
    try {
      worldBookItems = await fetchWorldBookItems();
    } catch (e) {
      alert(`${$t('knowledge.error.loadWorldBook')}: ${e.message}`);
    }
  }

  async function handleSaveWorldBookItem() {
    let itemToSave = editingWorldBookItem || newWorldBookItem;
    
    if ($behaviorConfig.knowledge_source_mode === 'dynamic_learning') {
        const aliases = (itemToSave.aliases || '').split(',').map(k => k.trim()).filter(Boolean);
        const triggers = (itemToSave.triggers || '').split(',').map(k => k.trim()).filter(Boolean);
        const baseKeywords = (itemToSave.keywords || '').split(',').map(k => k.trim()).filter(Boolean);
        
        const allKeywords = [...new Set([...baseKeywords, ...aliases, ...triggers])];
        itemToSave.keywords = allKeywords.join(', ');

        const structuredContent = {
            schema_version: 1,
            aliases: aliases,
            triggers: triggers,
            core_content: itemToSave.content.trim()
        };
        itemToSave.content = JSON.stringify(structuredContent, null, 2);
    }

    if (!itemToSave.keywords.trim() || !itemToSave.content.trim()) {
        alert($t('knowledge.error.emptyFields'));
        return;
    }
    
    if (itemToSave.linked_user_id !== null && itemToSave.linked_user_id !== undefined) {
        itemToSave.linked_user_id = String(itemToSave.linked_user_id).trim();
        if (itemToSave.linked_user_id === '') {
            itemToSave.linked_user_id = null;
        }
    }

    try {
      if (editingWorldBookItem) {
        await updateWorldBookItem(editingWorldBookItem.id, itemToSave);
      } else {
        await addWorldBookItem(itemToSave);
      }
      resetWorldBookForm();
      loadWorldBookItems();
    } catch (e) {
      alert(`${$t('knowledge.error.saveWorldBook')}: ${e.message}`);
    }
  }

  function editWorldBookItem(item) {
    let content = item.content;
    let aliases = '';
    let triggers = '';

    if ($behaviorConfig.knowledge_source_mode === 'dynamic_learning') {
        try {
            const data = JSON.parse(item.content);
            if (data && typeof data === 'object' && data.schema_version === 1) {
                content = data.core_content || '';
                aliases = (data.aliases || []).join(', ');
                triggers = (data.triggers || []).join(', ');
            }
        } catch (e) {
            // It's a plain text entry, leave it as is.
        }
    }
    editingWorldBookItem = { ...item, content, aliases, triggers };
  }

  function resetWorldBookForm() {
    newWorldBookItem = { keywords: '', content: '', enabled: true, linked_user_id: '', aliases: '', triggers: '' };
    editingWorldBookItem = null;
  }
  
  async function handleDeleteWorldBookItem(id) {
    if (confirm($t('knowledge.confirmDeleteWorldBook'))) {
      try {
        await deleteWorldBookItem(id);
        loadWorldBookItems();
      } catch (e) {
        alert(`${$t('knowledge.error.deleteWorldBook')}: ${e.message}`);
      }
    }
  }

  // --- Utility Functions ---
  function formatMemoryContent(rawContent) {
    if (!rawContent) return '';
    return rawContent.replace(/\[memory\s+.*?\]\s*/, '');
  }

  function formatWorldBookContent(rawContent) {
      if (!rawContent || !rawContent.includes('schema_version')) {
          return rawContent;
      }
      try {
          const data = JSON.parse(rawContent);
          if (data && typeof data === 'object' && data.schema_version === 1) {
              return data.core_content || '';
          }
      } catch (e) {
          // Not a valid JSON, return as is
      }
      return rawContent;
  }

  function getPersonaName(userId) {
    if (!userId) return `ID: ${userId}`;
    if ($userPersonasArray) {
        const persona = $userPersonasArray.find(p => p.id === userId);
        if (persona) return persona.nickname || `ID: ${userId}`;
    }
    return `ID: ${userId}`;
  }
 
  $: filteredMemoryItems = memoryItems.filter(item =>
    item.user_name && item.user_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  $: filteredWorldBookItems = worldBookItems.filter(item =>
    (item.keywords || '').toLowerCase().includes(worldBookSearchQuery.toLowerCase())
  );

</script>
 
 <style>
   .search-bar { margin-bottom: 1rem; }
   .search-bar input { width: 100%; padding: 0.5rem; box-sizing: border-box; }
   .tabs { display: flex; border-bottom: 2px solid #333; margin-bottom: 1rem; }
   .tab { padding: 0.5rem 1rem; cursor: pointer; border: none; background: none; color: #ccc; font-size: 1rem; }
   .tab.active { background-color: #333; color: #fff; border-radius: 5px 5px 0 0; }
   .item-list { max-height: 400px; overflow-y: auto; margin-bottom: 1rem; }
   .item { display: flex; justify-content: space-between; align-items: flex-start; padding: 0.5rem; border: 1px solid #444; border-radius: 4px; margin-bottom: 0.5rem; background-color: #ffffff; }
   .item-content { flex-grow: 1; margin-right: 1rem; white-space: pre-wrap; }
   .item-content > span { display: inline-block; color: #00ad09; }
   .meta { font-size: 0.8em; color: #000000; display: flex; gap: 1rem; }
   .keywords { font-style: italic; color: #7e7e7e; margin-bottom: 0.5em; }
   .actions { display: flex; justify-content: flex-end; align-items: center; gap: 0.2rem; }
   .actions button { margin-left: 0.5rem; }
   .actions .small-btn { font-size: 12px; padding: 4px 8px; border-radius: 4px; min-width: 50px; text-align: center; white-space: nowrap; }
   textarea, input[type="text"] { width: 100%; margin-bottom: 0.5rem; }
   .edit-textarea { width: 100%; box-sizing: border-box; }
   label { display: block; margin-bottom: 0.5rem; }
   .form-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 1rem; align-items: end; }
   .form-group.full-width { grid-column: 1 / -1; }
    .settings-section { display: flex; flex-direction: column; gap: 1.5rem; }
    .setting-item { display: flex; flex-direction: column; gap: 0.5rem; }
    .setting-item label { font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
    .threshold-value { font-weight: normal; background-color: #444; padding: 2px 8px; border-radius: 12px; font-size: 0.9em; }
    .setting-description { font-size: 0.9em; color: #aaa; margin: 0; }
  </style>

<Card>
  <h2>{$t('knowledge.title')}</h2>

  <div class="tabs">
    <button class="tab" class:active={activeTab === 'settings'} on:click={() => activeTab = 'settings'}>
      {$t('knowledge.tabs.settings')}
    </button>
    <button class="tab" class:active={activeTab === 'worldbook'} on:click={() => activeTab = 'worldbook'}>
      {$t('knowledge.tabs.worldBook')}
    </button>
    <button class="tab" class:active={activeTab === 'memory'} on:click={() => activeTab = 'memory'}>
      {$t('knowledge.tabs.memory')}
    </button>
  </div>

  {#if activeTab === 'settings'}
    <div class="settings-section">
      <h3>{$t('knowledge.settings.title')}</h3>
      
      <div class="setting-item">
        <label for="memory-dedup-threshold">
          {$t('knowledge.settings.memoryDedupThreshold')}
          <span class="threshold-value">{Math.round(($behaviorConfig.memory_dedup_threshold || 0) * 100)}%</span>
        </label>
        <input
          type="range"
          id="memory-dedup-threshold"
          min="0"
          max="1"
          step="0.01"
          bind:value={$behaviorConfig.memory_dedup_threshold}
        />
        <p class="setting-description">{$t('knowledge.settings.dedupDescription')}</p>
      </div>

      <div class="setting-item">
        <label for="world-book-dedup-threshold">
          {$t('knowledge.settings.worldBookDedupThreshold')}
          <span class="threshold-value">{Math.round(($behaviorConfig.world_book_dedup_threshold || 0) * 100)}%</span>
        </label>
        <input
          type="range"
          id="world-book-dedup-threshold"
          min="0"
          max="1"
          step="0.01"
          bind:value={$behaviorConfig.world_book_dedup_threshold}
        />
        <p class="setting-description">{$t('knowledge.settings.dedupDescription')}</p>
      </div>

      <button on:click={saveConfig}>{$t('knowledge.settings.save')}</button>
    </div>
  {/if}

  {#if activeTab === 'memory'}
    <div class="memory-section">
      <h3>{$t('knowledge.memory.title')}</h3>
      <div class="search-bar">
        <input type="text" bind:value={searchQuery} placeholder={$t('knowledge.memory.searchPlaceholder')}>
      </div>
      <div class="item-list">
        {#if filteredMemoryItems.length === 0}
          <p>{$t('knowledge.memory.noResults')}</p>
        {:else}
          {#each filteredMemoryItems as item (item.id)}
            <div class="item">
              <div class="item-content">
                {#if editingMemoryId === item.id}
                <textarea bind:value={editingMemoryContent} rows="2" class="edit-textarea"></textarea>
              {:else}
                <span>{formatMemoryContent(item.content)}</span>
              {/if}
              <div class="meta">
                {#if item.user_name}
                  <span>{$t('knowledge.memory.by')}: {item.user_name}</span>
                {/if}
                {#if item.timestamp}
                  <span>{$t('knowledge.memory.at')}: {new Date(item.timestamp).toLocaleString()}</span>
                {/if}
                {#if item.source}
                  <span>{$t('knowledge.memory.source')}: {item.source}</span>
                {/if}
              </div>
            </div>
            <div class="actions">
              {#if editingMemoryId === item.id}
                <button class="small-btn" on:click={handleUpdateMemory}>{$t('knowledge.memory.save')}</button>
                <button class="small-btn" on:click={cancelEditMemory}>{$t('knowledge.memory.cancel')}</button>
              {:else}
                <button class="small-btn" on:click={() => startEditMemory(item)}>{$t('knowledge.memory.edit')}</button>
                <button class="small-btn" on:click={() => handleDeleteMemory(item.id)}>{$t('knowledge.memory.delete')}</button>
              {/if}
            </div>
          </div>
          {/each}
        {/if}
      </div>
      <div class="form-grid" style="grid-template-columns: 1fr 1fr 2fr; gap: 0.5rem 1rem;">
        <div class="form-group">
            <label for="memory-user-name">{$t('knowledge.memory.by')}</label>
            <input id="memory-user-name" type="text" bind:value={newMemoryUserName} placeholder={$t('knowledge.memory.byPlaceholder')}>
        </div>
        <div class="form-group">
            <label for="memory-user-id">{$t('knowledge.memory.userIdLabel')}</label>
            <input id="memory-user-id" type="text" bind:value={newMemoryUserId} placeholder={$t('knowledge.memory.userIdPlaceholder')}>
        </div>
        <div class="form-group">
            <label for="memory-timestamp">{$t('knowledge.memory.timestampLabel')}</label>
            <input id="memory-timestamp" type="datetime-local" bind:value={newMemoryTimestamp}>
        </div>
        <div class="form-group full-width">
            <label for="memory-content">{$t('knowledge.memory.contentLabel')}</label>
            <textarea id="memory-content" bind:value={newMemoryContent} placeholder={$t('knowledge.memory.addPlaceholder')} rows="3"></textarea>
        </div>
      </div>
      <button on:click={handleAddMemory}>{$t('knowledge.memory.add')}</button>
    </div>
  {/if}

  {#if activeTab === 'worldbook'}
    <div class="worldbook-section">
      <h3>{$t('knowledge.worldBook.title')}</h3>
      <div class="search-bar">
        <input type="text" bind:value={worldBookSearchQuery} placeholder={$t('knowledge.worldBook.searchPlaceholder')}>
      </div>
      <div class="item-list">
        {#if filteredWorldBookItems.length === 0}
          <p>{$t('knowledge.worldBook.noResults')}</p>
        {:else}
          {#each filteredWorldBookItems as item (item.id)}
            <div class="item">
              <div class="item-content">
                <div class="keywords">{$t('knowledge.worldBook.keywordsLabel')}: {item.keywords}</div>
                <div style="white-space: pre-wrap;">{formatWorldBookContent(item.content)}</div>
                {#if item.linked_user_id}
                  <div class="meta" style="margin-top: 0.5em;">
                    <span>{$t('knowledge.worldBook.linkedUserLabel')}: {getPersonaName(item.linked_user_id)}</span>
                  </div>
                {/if}
              </div>
              <div class="actions">
                <button class="small-btn" on:click={() => editWorldBookItem(item)}>{$t('knowledge.worldBook.edit')}</button>
              <button class="small-btn" on:click={() => handleDeleteWorldBookItem(item.id)}>{$t('knowledge.worldBook.delete')}</button>
            </div>
          </div>
          {/each}
        {/if}
      </div>
      
      <Card extraClass="form-card">
        <h4>{editingWorldBookItem ? $t('knowledge.worldBook.editTitle') : $t('knowledge.worldBook.addTitle')}</h4>
        
        <!-- Corrected Logic: Top-level check for mode, then inner check for edit/add -->
        {#if $behaviorConfig.knowledge_source_mode === 'dynamic_learning'}
            <!-- DYNAMIC MODE FORMS -->
            {#if editingWorldBookItem}
                <!-- Dynamic Editing -->
                <label>{$t('knowledge.dynamic.linkedUserLabel')}<input type="text" bind:value={editingWorldBookItem.linked_user_id} placeholder={$t('knowledge.dynamic.userIdPlaceholder')}></label>
                <label>{$t('knowledge.dynamic.aliasesLabel')} ({$t('knowledge.worldBook.keywordsHint')})<input type="text" bind:value={editingWorldBookItem.aliases} placeholder={$t('knowledge.dynamic.aliasesPlaceholder')}></label>
                <label>{$t('knowledge.dynamic.triggersLabel')} ({$t('knowledge.worldBook.keywordsHint')})<input type="text" bind:value={editingWorldBookItem.triggers} placeholder={$t('knowledge.dynamic.triggersPlaceholder')}></label>
                <label>{$t('knowledge.worldBook.keywordsLabel')} ({$t('knowledge.worldBook.keywordsHint')})<input type="text" bind:value={editingWorldBookItem.keywords} placeholder={$t('knowledge.worldBook.keywordsPlaceholder')}></label>
                <label>{$t('knowledge.worldBook.contentLabel')}<textarea rows="4" bind:value={editingWorldBookItem.content} placeholder={$t('knowledge.worldBook.contentPlaceholder')}></textarea></label>
            {:else}
                <!-- Dynamic Adding -->
                <label>{$t('knowledge.dynamic.linkedUserLabel')}<input type="text" bind:value={newWorldBookItem.linked_user_id} placeholder={$t('knowledge.dynamic.userIdPlaceholder')}></label>
                <label>{$t('knowledge.dynamic.aliasesLabel')} ({$t('knowledge.worldBook.keywordsHint')})<input type="text" bind:value={newWorldBookItem.aliases} placeholder={$t('knowledge.dynamic.aliasesPlaceholder')}></label>
                <label>{$t('knowledge.dynamic.triggersLabel')} ({$t('knowledge.worldBook.keywordsHint')})<input type="text" bind:value={newWorldBookItem.triggers} placeholder={$t('knowledge.dynamic.triggersPlaceholder')}></label>
                <label>{$t('knowledge.worldBook.keywordsLabel')} ({$t('knowledge.worldBook.keywordsHint')})<input type="text" bind:value={newWorldBookItem.keywords} placeholder={$t('knowledge.worldBook.keywordsPlaceholder')}></label>
                <label>{$t('knowledge.worldBook.contentLabel')}<textarea rows="4" bind:value={newWorldBookItem.content} placeholder={$t('knowledge.worldBook.contentPlaceholder')}></textarea></label>
            {/if}
        {:else}
            <!-- STATIC MODE FORMS -->
            {#if editingWorldBookItem}
                <!-- Static Editing -->
                <label>{$t('knowledge.worldBook.keywordsLabel')} ({$t('knowledge.worldBook.keywordsHint')})<input type="text" bind:value={editingWorldBookItem.keywords} placeholder={$t('knowledge.worldBook.keywordsPlaceholder')}></label>
                <label>{$t('knowledge.worldBook.contentLabel')}<textarea rows="4" bind:value={editingWorldBookItem.content} placeholder={$t('knowledge.worldBook.contentPlaceholder')}></textarea></label>
                <label>{$t('knowledge.worldBook.linkedUserLabel')}
                    <select bind:value={editingWorldBookItem.linked_user_id}>
                        <option value={null}>{$t('knowledge.worldBook.noLinkedUser')}</option>
                        {#each $userPersonasArray as persona}<option value={persona.id}>{persona.nickname || `ID: ${persona.id}`}</option>{/each}
                    </select>
                </label>
            {:else}
                <!-- Static Adding -->
                <label>{$t('knowledge.worldBook.keywordsLabel')} ({$t('knowledge.worldBook.keywordsHint')})<input type="text" bind:value={newWorldBookItem.keywords} placeholder={$t('knowledge.worldBook.keywordsPlaceholder')}></label>
                <label>{$t('knowledge.worldBook.contentLabel')}<textarea rows="4" bind:value={newWorldBookItem.content} placeholder={$t('knowledge.worldBook.contentPlaceholder')}></textarea></label>
                <label>{$t('knowledge.worldBook.linkedUserLabel')}
                    <select bind:value={newWorldBookItem.linked_user_id}>
                        <option value={null}>{$t('knowledge.worldBook.noLinkedUser')}</option>
                        {#each $userPersonasArray as persona}<option value={persona.id}>{persona.nickname || `ID: ${persona.id}`}</option>{/each}
                    </select>
                </label>
            {/if}
        {/if}

        <button on:click={handleSaveWorldBookItem}>{editingWorldBookItem ? $t('knowledge.worldBook.save') : $t('knowledge.worldBook.add')}</button>
        {#if editingWorldBookItem}
          <button on:click={resetWorldBookForm}>{$t('knowledge.worldBook.cancelEdit')}</button>
        {/if}
      </Card>
    </div>
  {/if}
</Card>