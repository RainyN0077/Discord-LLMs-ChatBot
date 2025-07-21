<script>
  export let title;
  export let theme = 'light'; // light 或 dark-theme
</script>

<div class="card {theme}">
  {#if title}
    <h2>{title}</h2>
  {/if}
  <slot />
</div>

<style>
    .card {
        background: var(--card-bg);
        border-radius: 12px;
        padding: 1.5rem 2rem;
        box-shadow: var(--shadow);
        display: flex;
        flex-direction: column;
        gap: 1.2rem;
    }

    /* Since h2 is used as the card title, its style belongs here. */
    h2 {
        color: var(--text-color);
        font-weight: 600;
        border-bottom: 1px solid var(--border-color);
        padding-bottom: .5rem;
        margin-top: 0;
    }
</style>
