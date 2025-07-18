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
