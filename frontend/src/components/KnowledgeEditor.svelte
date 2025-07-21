<!-- frontend/src/components/KnowledgeEditor.svelte -->
<script>
  import { onMount } from 'svelte';
  import { t } from '../i18n.js';
  import {
    fetchMemoryItems, addMemoryItem, deleteMemoryItem,
    fetchWorldBookItems, addWorldBookItem, updateWorldBookItem, deleteWorldBookItem
  } from '../lib/api.js';
  import Card from './Card.svelte';

  let activeTab = 'worldbook';
  let memoryItems = [];
  let worldBookItems = [];
  let newMemoryContent = '';
  
  let newWorldBookItem = { keywords: '', content: '', enabled: true };
  let editingWorldBookItem = null;

  onMount(async () => {
    loadMemoryItems();
    loadWorldBookItems();
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
      await addMemoryItem(newMemoryContent.trim());
      newMemoryContent = '';
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
    background-color: #2a2a2a;
  }
  .item-content {
    flex-grow: 1;
    margin-right: 1rem;
    white-space: pre-wrap;
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
  label {
      display: block;
      margin-bottom: 0.5rem;
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
            <span class="item-content">{item.content}</span>
            <div class="actions">
              <button on:click={() => handleDeleteMemory(item.id)}>{$t('knowledge.memory.delete')}</button>
            </div>
          </div>
        {/each}
      </div>
      <textarea bind:value={newMemoryContent} placeholder={$t('knowledge.memory.addPlaceholder')}></textarea>
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
              <div>{item.content}</div>
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