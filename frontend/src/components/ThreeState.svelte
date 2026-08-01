<!-- src/components/ThreeState.svelte -->
<!--
  Three-state display component: loading / error / empty / default slot.

  Props:
    loading      {boolean}  show a centered loading spinner + text
    error        {string}   show error message and optional retry button
    empty        {boolean}  show empty-state placeholder message
    emptyMessage {string}   text for the empty state (default: '')
    onRetry      {function} optional callback for the retry button in error state
-->
<script>
  export let loading = false;
  export let error = '';
  export let empty = false;
  export let emptyMessage = '';
  export let onRetry = null;
</script>

{#if loading}
  <div class="three-state three-state-loading">
    <slot name="loading">
      <span class="spinner"></span>
      <p><slot name="loading-text">Loading...</slot></p>
    </slot>
  </div>
{:else if error}
  <div class="three-state three-state-error">
    <p>{error}</p>
    {#if onRetry}
      <button class="retry-btn" on:click={onRetry}>Retry</button>
    {/if}
  </div>
{:else if empty}
  <div class="three-state three-state-empty">
    {#if emptyMessage}
      <p>{emptyMessage}</p>
    {:else}
      <slot name="empty" />
    {/if}
  </div>
{:else}
  <slot />
{/if}

<style>
  .three-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-light);
    font-size: 1rem;
  }

  .three-state-error {
    color: var(--error-text);
  }

  .three-state-error p {
    margin-bottom: 1rem;
  }

  .retry-btn {
    padding: .5rem 1.2rem;
    background: linear-gradient(135deg, var(--primary-color), #1b73b0);
    color: #fff;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: .9rem;
    font-weight: 500;
    transition: transform .15s, box-shadow .15s;
  }

  .retry-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(31, 139, 214, .24);
  }

  .spinner {
    display: inline-block;
    width: 28px;
    height: 28px;
    border: 3px solid var(--border-color);
    border-top-color: var(--primary-color);
    border-radius: 50%;
    animation: three-state-spin .7s linear infinite;
    margin-bottom: .75rem;
  }

  @keyframes three-state-spin {
    to { transform: rotate(360deg); }
  }
</style>
