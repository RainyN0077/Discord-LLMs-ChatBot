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
        border-radius: 16px;
        padding: 1.25rem clamp(1rem, 1.8vw, 1.75rem);
        box-shadow: var(--shadow);
        border: 1px solid rgba(15, 23, 42, .06);
        display: flex;
        flex-direction: column;
        gap: 1rem;
        position: relative;
        overflow: hidden;
        animation: card-enter .28s ease-out both;
    }

    .card::before {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(130deg, rgba(31, 139, 214, .04), transparent 40%);
        pointer-events: none;
    }

    .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 20px 40px rgba(15, 23, 42, .12);
    }

    /* Since h2 is used as the card title, its style belongs here. */
    h2 {
        color: var(--text-color);
        font-weight: 700;
        font-size: 1.05rem;
        border-bottom: 1px solid var(--border-color);
        padding-bottom: .5rem;
        margin-top: 0;
        margin-bottom: .3rem;
    }

    @keyframes card-enter {
        from {
            opacity: 0;
            transform: translateY(8px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
</style>
