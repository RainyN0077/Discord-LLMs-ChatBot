<script>
  import { t } from '../i18n.js';
  import { coreConfig } from '../lib/stores.js';
  import { showStatus } from '../lib/commonStores.js';
  import { fetchAvailableModels, testModel } from '../lib/api.js';
  import { providerForPlaceholder } from '../lib/providerDefaults.js';
  import Card from './Card.svelte';

  /**
   * @prop {'ocr'|'embedding'|'rerank'} task - identifies which provider card to render
   */
  export let task;

  // Field prefix for store access: ocr_, embedding_, rerank_
  $: prefix = task;

  // Local state (each AdvancedProviderCard instance is independent)
  let availableModels = [];
  let isLoadingModels = false;
  let testResult = null;
  let isTesting = false;
  let useManualInput = false;
  let prevProvider = null;
  let prevKey = null;

  // Reset models when provider or API key changes
  $: if ($coreConfig[`${prefix}_provider`] !== prevProvider || $coreConfig[`${prefix}_api_key`] !== prevKey) {
    prevProvider = $coreConfig[`${prefix}_provider`];
    prevKey = $coreConfig[`${prefix}_api_key`];
    availableModels = [];
    testResult = null;
    useManualInput = false;
  }

  const advancedProviderOptions = [
    { value: 'openai', labelKey: 'modelProviders.openai' },
    { value: 'grok', labelKey: 'modelProviders.grok' },
    { value: 'openai_compatible', labelKey: 'modelProviders.openaiCompatible' },
    { value: 'gemini', labelKey: 'modelProviders.gemini' },
    { value: 'anthropic', labelKey: 'modelProviders.anthropic' },
    { value: 'anthropic_compatible', labelKey: 'modelProviders.anthropicCompatible' },
    { value: 'deepseek', labelKey: 'modelProviders.deepseek' },
    { value: 'siliconflow', labelKey: 'modelProviders.siliconflow' },
    { value: 'volcengine', labelKey: 'modelProviders.volcengine' },
    { value: 'dashscope', labelKey: 'modelProviders.dashscope' },
    { value: 'moonshot', labelKey: 'modelProviders.moonshot' },
    { value: 'zhipu', labelKey: 'modelProviders.zhipu' },
    { value: 'stepfun', labelKey: 'modelProviders.stepfun' }
  ];

  function buildEndpoint(baseUrl, port) {
    const cleanedBase = (baseUrl || '').trim();
    const cleanedPort = String(port || '').trim();
    if (!cleanedBase) return '';
    if (!cleanedPort) return cleanedBase;
    try {
      const parsed = new URL(cleanedBase);
      parsed.port = cleanedPort;
      return parsed.toString().replace(/\/$/, '');
    } catch (_) {
      const normalized = cleanedBase.replace(/\/$/, '');
      if (/:\d+$/.test(normalized)) return normalized;
      return `${normalized}:${cleanedPort}`;
    }
  }

  async function loadModels() {
    const apiKey = $coreConfig[`${prefix}_api_key`];
    if (!apiKey) {
      showStatus(t('llmProvider.noApiKey'), 'error');
      return;
    }
    isLoadingModels = true;
    try {
      const result = await fetchAvailableModels(
        $coreConfig[`${prefix}_provider`],
        apiKey,
        buildEndpoint($coreConfig[`${prefix}_base_url`], $coreConfig[`${prefix}_port`]),
        task
      );
      availableModels = result.models || [];
      useManualInput = false;
      showStatus(t('llmProvider.modelsLoaded'), 'success');
    } catch (e) {
      availableModels = [];
      useManualInput = true;
      showStatus(t('llmProvider.modelsLoadFailed') + e.message, 'error');
    } finally {
      isLoadingModels = false;
    }
  }

  async function handleTest() {
    const modelName = $coreConfig[`${prefix}_model_name`];
    if (!modelName) {
      showStatus(t('llmProvider.selectModelFirst'), 'error');
      return;
    }
    isTesting = true;
    testResult = null;
    try {
      const extra = task === 'ocr'
        ? {
            ocr_timeout_seconds: $coreConfig.ocr_timeout_seconds,
            ocr_timeout_disabled: !!$coreConfig.ocr_timeout_disabled
          }
        : {};
      const result = await testModel(
        $coreConfig[`${prefix}_provider`],
        $coreConfig[`${prefix}_api_key`],
        buildEndpoint($coreConfig[`${prefix}_base_url`], $coreConfig[`${prefix}_port`]),
        modelName,
        task,
        extra
      );
      testResult = result;
      if (result.success) {
        showStatus(t('llmProvider.testSuccess'), 'success');
      } else {
        showStatus(t('llmProvider.testFailed') + result.error, 'error');
      }
    } catch (e) {
      showStatus(t('llmProvider.testError') + e.message, 'error');
    } finally {
      isTesting = false;
    }
  }

  function setOcrTimeoutDisabled(disabled) {
    coreConfig.update((config) => ({
      ...config,
      ocr_timeout_disabled: disabled
    }));
  }
</script>

<Card title={$t(`${prefix}Settings.title`)}>
  {#if task === 'ocr'}
    <p class="info">{$t('ocrSettings.info')}</p>
  {/if}

  <div class="provider-top-grid">
    <div>
      <label for="{prefix}-provider">{$t(`${prefix}Settings.provider`)}</label>
      <select id="{prefix}-provider" bind:value={$coreConfig[`${prefix}_provider`]}>
        {#each advancedProviderOptions as option}
          <option value={option.value}>{$t(option.labelKey)}</option>
        {/each}
      </select>
    </div>
    <div>
      <label for="{prefix}-api-key">{$t(`${prefix}Settings.apiKey`)}</label>
      <input id="{prefix}-api-key" type="password" placeholder={$t('llmProvider.apiKeyPlaceholder')} bind:value={$coreConfig[`${prefix}_api_key`]}>
    </div>
  </div>

  <div class="provider-top-grid advanced-endpoint-grid">
    <div>
      <label for="{prefix}-base-url">{$t(`${prefix}Settings.baseUrl`)}</label>
      <input id="{prefix}-base-url" type="text" placeholder={$t('llmProvider.baseUrlPlaceholder')} bind:value={$coreConfig[`${prefix}_base_url`]}>
    </div>
    <div>
      <label for="{prefix}-port">{$t(`${prefix}Settings.port`)}</label>
      <input id="{prefix}-port" type="text" placeholder="443" bind:value={$coreConfig[`${prefix}_port`]}>
    </div>
  </div>

  <div class="model-selector-group">
    <label for="{prefix}-model-name">{$t(`${prefix}Settings.modelName`)}</label>
    <div class="model-controls">
      {#if !useManualInput && availableModels.length > 0}
        <select id="{prefix}-model-name" bind:value={$coreConfig[`${prefix}_model_name`]}>
          <option value="">-- {$t('llmProvider.selectModel')} --</option>
          {#each availableModels as model}
            <option value={model}>{model}</option>
          {/each}
        </select>
      {:else}
        <input
          id="{prefix}-model-name"
          type="text"
          placeholder={$t(`defaultBehavior.modelPlaceholders.${providerForPlaceholder($coreConfig[`${prefix}_provider`])}`)}
          bind:value={$coreConfig[`${prefix}_model_name`]}
        >
      {/if}
      <div class="model-buttons">
        <button class="action-btn-secondary" on:click={loadModels} disabled={isLoadingModels}>
          {isLoadingModels ? $t('llmProvider.loading') : $t('llmProvider.fetchModels')}
        </button>
        {#if availableModels.length > 0}
          <button class="action-btn-secondary" on:click={() => useManualInput = !useManualInput} title={$t('llmProvider.toggleInputMode')}>
            {useManualInput ? 'SEL' : 'TXT'}
          </button>
        {/if}
        <button class="action-btn" on:click={handleTest} disabled={isTesting || !$coreConfig[`${prefix}_model_name`]}>
          {isTesting ? $t('llmProvider.testing') : $t('llmProvider.testConnection')}
        </button>
      </div>
    </div>
  </div>

  {#if task === 'embedding'}
    <label for="embedding-dimensions">{$t('embeddingSettings.dimensions')}</label>
    <input id="embedding-dimensions" type="number" min="1" step="1" bind:value={$coreConfig.embedding_dimensions}>
  {/if}

  {#if task === 'ocr'}
    <label for="ocr-prompt-template">{$t('ocrSettings.promptTemplate')}</label>
    <textarea
      id="ocr-prompt-template"
      rows="5"
      placeholder={$t('ocrSettings.promptTemplatePlaceholder')}
      bind:value={$coreConfig.ocr_prompt_template}
    ></textarea>
    <label for="ocr-max-output-chars">{$t('ocrSettings.maxOutputChars')}</label>
    <input id="ocr-max-output-chars" type="number" min="200" max="20000" step="100" bind:value={$coreConfig.ocr_max_output_chars}>
    <p class="info">{$t('ocrSettings.maxOutputCharsInfo')}</p>
    <div class="provider-top-grid advanced-endpoint-grid">
      <div>
        <label for="ocr-timeout-seconds">{$t('ocrSettings.timeoutSeconds')}</label>
        <input
          id="ocr-timeout-seconds"
          type="number"
          min="1"
          max="86400"
          step="1"
          bind:value={$coreConfig.ocr_timeout_seconds}
          disabled={$coreConfig.ocr_timeout_disabled}
        >
      </div>
      <div>
        <label for="ocr-timeout-mode">{$t('ocrSettings.timeoutMode')}</label>
        <select
          id="ocr-timeout-mode"
          value={$coreConfig.ocr_timeout_disabled ? 'disabled' : 'enabled'}
          on:change={(event) => setOcrTimeoutDisabled(event.currentTarget.value === 'disabled')}
        >
          <option value="enabled">{$t('ocrSettings.timeoutEnabledOption')}</option>
          <option value="disabled">{$t('ocrSettings.timeoutDisabledOption')}</option>
        </select>
      </div>
    </div>
    <p class="info">{$t('ocrSettings.timeoutInfo')}</p>
  {/if}

  {#if testResult}
    <div class="test-result {testResult.success ? 'success' : 'error'}">
      <strong>{$t('llmProvider.testResult')}:</strong>
      <p>{testResult.success ? testResult.response : testResult.error}</p>
    </div>
  {/if}
</Card>

<style>
  .provider-top-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: .9rem;
  }

  .advanced-endpoint-grid {
    margin-top: .8rem;
  }

  .model-controls {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .model-controls > * {
    width: 100%;
  }

  .model-buttons {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .model-buttons button:first-child {
    flex: 1;
  }

  .test-result {
    margin-top: 1rem;
    padding: 1rem;
    border-radius: 8px;
    font-size: 0.9rem;
    border: 1px solid rgba(15, 23, 42, .08);
  }

  .test-result.success {
    background-color: var(--success-bg);
    color: var(--success-text);
  }

  .test-result.error {
    background-color: var(--error-bg);
    color: var(--error-text);
  }

  @media (min-width: 768px) {
    .model-controls {
      flex-direction: row;
      align-items: center;
    }

    .model-controls select,
    .model-controls input {
      flex: 1;
      width: auto;
    }

    .model-buttons {
      flex-shrink: 0;
      width: auto;
    }
  }

  @media (max-width: 900px) {
    .provider-top-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 600px) {
    .model-controls {
      flex-direction: column;
    }

    .model-controls select,
    .model-controls input {
      width: 100%;
    }
  }
</style>
