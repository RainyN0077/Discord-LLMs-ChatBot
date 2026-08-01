<script>
  import { t } from '../i18n.js';
  import { behaviorConfig } from '../lib/stores.js';
  import Card from './Card.svelte';
</script>

<Card title={$t('automation.title')}>
  <p class="info">{$t('automation.description')}</p>

  <div class="automation-section">
    <h3>{$t('automation.autoInterjectTitle')}</h3>
    <p class="info">{$t('automation.autoInterjectInfo')}</p>
    <label>
      <input type="checkbox" bind:checked={$behaviorConfig.auto_interject_enabled}>
      {$t('automation.autoInterjectEnabled')}
    </label>
    <label for="auto-interject-interval">{$t('automation.autoInterjectInterval')}</label>
    <input id="auto-interject-interval" type="number" min="1" step="1" bind:value={$behaviorConfig.auto_interject_interval}>
    <label for="auto-interject-min-length">{$t('automation.autoInterjectMinLength')}</label>
    <div class="inline-input">
      <input id="auto-interject-min-length" type="number" min="0" step="1" bind:value={$behaviorConfig.auto_interject_min_length}>
      <span>{$t('automation.autoInterjectMinLengthHint')}</span>
    </div>
  </div>

  <div class="automation-section">
    <h3>{$t('automation.repeatParrotTitle')}</h3>
    <p class="info">{$t('automation.repeatParrotInfo')}</p>
    <label>
      <input type="checkbox" bind:checked={$behaviorConfig.repeat_parrot_enabled}>
      {$t('automation.repeatParrotEnabled')}
    </label>
    <label for="repeat-parrot-threshold">{$t('automation.repeatParrotThreshold')}</label>
    <input id="repeat-parrot-threshold" type="number" min="2" step="1" bind:value={$behaviorConfig.repeat_parrot_threshold}>
    <label for="repeat-parrot-min-length">{$t('automation.repeatParrotMinLength')}</label>
    <input id="repeat-parrot-min-length" type="number" min="0" step="1" bind:value={$behaviorConfig.repeat_parrot_min_length}>
    <label>
      <input type="checkbox" bind:checked={$behaviorConfig.repeat_parrot_case_sensitive}>
      {$t('automation.repeatParrotCaseSensitive')}
    </label>
    <label>
      <input type="checkbox" bind:checked={$behaviorConfig.repeat_parrot_trim_whitespace}>
      {$t('automation.repeatParrotTrimWhitespace')}
    </label>
    <label>
      <input type="checkbox" bind:checked={$behaviorConfig.repeat_parrot_require_multiple_users}>
      {$t('automation.repeatParrotRequireMultipleUsers')}
    </label>
  </div>
</Card>

<style>
  .automation-section {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    gap: .75rem;
  }

  .automation-section:first-of-type {
    margin-top: .5rem;
  }

  .automation-section h3 {
    margin: 0;
  }

  .inline-input {
    display: flex;
    align-items: center;
    gap: .75rem;
    flex-wrap: wrap;
  }

  .inline-input input[type="number"] {
    max-width: 180px;
  }

  @media (max-width: 600px) {
    .inline-input {
      flex-direction: column;
      align-items: flex-start;
    }

    .inline-input input[type="number"] {
      max-width: 100%;
    }

    .automation-section {
      gap: .5rem;
    }
  }
</style>
