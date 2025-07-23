<!-- frontend/src/components/KnowledgeEditor.svelte -->
<script>
  import { onMount, onDestroy } from 'svelte';
  import { t } from '../i18n.js';
  import {
    fetchMemoryItems, addMemoryItem, deleteMemoryItem, updateMemoryItem,
    fetchWorldBookItems, addWorldBookItem, updateWorldBookItem, deleteWorldBookItem
  } from '../lib/api.js';
  import Card from './Card.svelte';

  let activeTab = 'worldbook';
  let memoryItems = [];
  let worldBookItems = [];
  let newMemoryContent = '';
  let newMemoryUserName = 'WebUI';
  let newMemoryUserId = '';
  let newMemoryTimestamp = '';
  
  let newWorldBookItem = { keywords: '', content: '', enabled: true };
  let editingWorldBookItem = null;
  let editingMemoryId = null;
  let editingMemoryContent = '';
  let intervalId = null;

  onMount(async () => {
    loadMemoryItems();
    loadWorldBookItems();
    intervalId = setInterval(loadMemoryItems, 5000); // Poll for new memories
  });

  onDestroy(() => {
    if (intervalId) {
      clearInterval(intervalId);
    }
  });

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
        // Only include timestamp if it's been set by the user
        timestamp: newMemoryTimestamp || null,
        timezone: newMemoryTimestamp ? timezone : null,
        source: '手动添加'
      };
      
      await addMemoryItem(itemData);

      // Reset form
      newMemoryContent = '';
      newMemoryUserId = '';
      newMemoryTimestamp = '';
      // Do not reset username, to allow multiple entries from same person
      
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
      loadMemoryItems(); // Refresh the list
    } catch (e) {
      alert(`${$t('knowledge.error.updateMemory')}: ${e.message}`);
    }
  }
  
  async function loadWorldBookItems() {
    try {
      worldBookItems = await fetchWorldBookItems();
    } catch (e) {
      alert(`${$t('knowledge.error.loadWorldBook')}: ${e.message}`);
    }
  }

  async function handleSaveWorldBookItem() {
    const itemToSave = editingWorldBookItem || newWorldBookItem;
    if (!itemToSave.keywords.trim() || !itemToSave.content.trim()) {
        alert($t('knowledge.error.emptyFields'));
        return;
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
    editingWorldBookItem = { ...item };
  }

  function resetWorldBookForm() {
    newWorldBookItem = { keywords: '', content: '', enabled: true };
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

  function formatMemoryContent(rawContent) {
    if (!rawContent) return '';
    // Use replace with a regex to remove the tag and any leading space
    return rawContent.replace(/\[memory\s+.*?\]\s*/, '');
  }
 
</script>
 
 <style>
  .tabs {
    display: flex;
    border-bottom: 2px solid #333;
    margin-bottom: 1rem;
  }
  .tab {
    padding: 0.5rem 1rem;
    cursor: pointer;
    border: none;
    background: none;
    color: #ccc;
    font-size: 1rem;
  }
  .tab.active {
    background-color: #333;
    color: #fff;
    border-radius: 5px 5px 0 0;
  }
  .item-list {
    max-height: 400px;
    overflow-y: auto;
    margin-bottom: 1rem;
  }
  .item {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 0.5rem;
    border: 1px solid #444;
    border-radius: 4px;
    margin-bottom: 0.5rem;
    background-color: #333740; /* A lighter, more distinct dark color for better contrast */
  }
  .item-content {
    flex-grow: 1;
    margin-right: 1rem;
    white-space: pre-wrap;
  }
  .item-content > span {
      display: block;
      margin-bottom: 0.5rem;
      color: #81c784; /* Set text color to INFO green for readability */
   }
   .item-content > .wb-content {
        color: #81c784; /* INFO green for world book content */
   }
   .meta {
       font-size: 0.8em;
      color: #ddd; /* Increased font color contrast for better readability */
      display: flex;
      gap: 1rem;
  }
  .keywords {
    font-style: italic;
    color: #aaa;
    margin-bottom: 0.5em;
  }
  .actions button {
    margin-left: 0.5rem;
  }
  textarea, input[type="text"] {
    width: 100%;
    margin-bottom: 0.5rem;
  }
  .edit-textarea {
      width: 100%;
      box-sizing: border-box;
  }
  label {
      display: block;
      margin-bottom: 0.5rem;
 }
 .form-grid {
   display: grid;
   grid-template-columns: 1fr 2fr;
   gap: 1rem;
   align-items: end;
 }
 .form-group.full-width {
   grid-column: 1 / -1;
 }
</style>

<Card>
  <h2>{$t('knowledge.title')}</h2>

  <div class="tabs">
    <button class="tab" class:active={activeTab === 'worldbook'} on:click={() => activeTab = 'worldbook'}>
      {$t('knowledge.tabs.worldBook')}
    </button>
    <button class="tab" class:active={activeTab === 'memory'} on:click={() => activeTab = 'memory'}>
      {$t('knowledge.tabs.memory')}
    </button>
  </div>

  {#if activeTab === 'memory'}
    <div class="memory-section">
      <h3>{$t('knowledge.memory.title')}</h3>
      <div class="item-list">
        {#each memoryItems as item (item.id)}
          <div class="item">
            <div class="item-content">
              {#if editingMemoryId === item.id}
                <textarea bind:value={editingMemoryContent} rows="3" class="edit-textarea"></textarea>
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
                <button on:click={handleUpdateMemory}>{$t('knowledge.memory.save')}</button>
                <button on:click={cancelEditMemory}>{$t('knowledge.memory.cancel')}</button>
              {:else}
                <button on:click={() => startEditMemory(item)}>{$t('knowledge.memory.edit')}</button>
                <button on:click={() => handleDeleteMemory(item.id)}>{$t('knowledge.memory.delete')}</button>
              {/if}
            </div>
          </div>
        {/each}
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
      <div class="item-list">
        {#each worldBookItems as item (item.id)}
          <div class="item">
            <div class="item-content">
              <div class="keywords">{$t('knowledge.worldBook.keywordsLabel')}: {item.keywords}</div>
              <div class="wb-content">{item.content}</div>
            </div>
            <div class="actions">
              <button on:click={() => editWorldBookItem(item)}>{$t('knowledge.worldBook.edit')}</button>
              <button on:click={() => handleDeleteWorldBookItem(item.id)}>{$t('knowledge.worldBook.delete')}</button>
            </div>
          </div>
        {/each}
      </div>
      
      <Card extraClass="form-card">
        <h4>{editingWorldBookItem ? $t('knowledge.worldBook.editTitle') : $t('knowledge.worldBook.addTitle')}</h4>
        {#if editingWorldBookItem}
          <label>
            {$t('knowledge.worldBook.keywordsLabel')} ({$t('knowledge.worldBook.keywordsHint')}):
            <input type="text" bind:value={editingWorldBookItem.keywords} placeholder={$t('knowledge.worldBook.keywordsPlaceholder')}>
          </label>
          <label>
            {$t('knowledge.worldBook.contentLabel')}:
            <textarea rows="4" bind:value={editingWorldBookItem.content} placeholder={$t('knowledge.worldBook.contentPlaceholder')}></textarea>
          </label>
        {:else}
          <label>
            {$t('knowledge.worldBook.keywordsLabel')} ({$t('knowledge.worldBook.keywordsHint')}):
            <input type="text" bind:value={newWorldBookItem.keywords} placeholder={$t('knowledge.worldBook.keywordsPlaceholder')}>
          </label>
          <label>
            {$t('knowledge.worldBook.contentLabel')}:
            <textarea rows="4" bind:value={newWorldBookItem.content} placeholder={$t('knowledge.worldBook.contentPlaceholder')}></textarea>
          </label>
        {/if}
        <button on:click={handleSaveWorldBookItem}>{editingWorldBookItem ? $t('knowledge.worldBook.save') : $t('knowledge.worldBook.add')}</button>
        {#if editingWorldBookItem}
          <button on:click={resetWorldBookForm}>{$t('knowledge.worldBook.cancelEdit')}</button>
        {/if}
      </Card>
    </div>
  {/if}
</Card>