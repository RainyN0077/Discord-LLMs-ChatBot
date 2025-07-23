// src/locales/en.js
export default {
  title: 'Discord LLM Bot Control Panel',
  tabs: {
    core: 'Core Settings',
    directives: 'Identity Directives',
    advanced: 'Advanced Tools'
  },
  buttons: {
    save: 'Save Configuration & Restart Bot',
    saving: 'Saving...'
  },
  status: {
    loading: 'Loading configuration...',
    saving: 'Saving...',
    saveSuccess: 'Configuration saved and bot restarted!',
    saveFailed: 'Save failed: {error}',
    loadFailed: 'Failed to load configuration: {error}'
  },
  errors: {
    duplicateId: 'ID "{id}" already exists, please use another ID'
  },
  globalConfig: {
    title: 'Global Configuration',
    token: 'Discord Bot Token',
    tokenPlaceholder: 'Enter your Discord Bot Token',
    apiKey: 'RESTful API Key',
    apiKeyUnavailable: 'API key unavailable',
    copy: 'Copy',
    apiKeyInfo: 'This is your unique API key for external services to call plugin endpoints. Keep it safe and do not share with others.'
  },
  llmProvider: {
    title: 'LLM Provider',
    select: 'Select Provider',
    providers: {
      openai: 'OpenAI',
      google: 'Google Gemini',
      anthropic: 'Anthropic Claude'
    },
    apiKey: 'API Key',
    apiKeyPlaceholder: 'Enter your API Key',
    baseUrl: 'Base URL (Optional)',
    baseUrlPlaceholder: 'Leave empty for official API, or enter custom endpoint',
    fetchModels: 'Fetch Models',
    loading: 'Loading...',
    testConnection: 'Test Connection',
    testing: 'Testing...',
    selectModel: 'Select Model',
    noApiKey: 'Please enter API key first',
    modelsLoaded: 'Model list loaded successfully',
    modelsLoadFailed: 'Failed to load model list: ',
    selectModelFirst: 'Please select a model first',
    testSuccess: 'Connection test successful!',
    testFailed: 'Connection test failed: ',
    testError: 'Test error: ',
    testResult: 'Test Result',
    modelResponded: 'Model responded',
    toggleInputMode: 'Toggle input mode',
    fetchModelsTooltip: 'Fetch or refresh available model list',
    modelListInfo: 'Loaded {count} available models, click ✏️ to switch to manual input'
  },
  defaultBehavior: {
    title: 'Default Behavior',
    modelName: 'Model Name',
    modelPlaceholders: {
      openai: 'e.g., gpt-4o, gpt-3.5-turbo',
      google: 'e.g., gemini-1.5-flash, gemini-1.5-pro',
      anthropic: 'e.g., claude-3-opus-20240229'
    },
    botNickname: 'Bot Nickname',
    botNicknamePlaceholder: 'e.g., Endless',
    systemPrompt: 'System Prompt',
    systemPromptPlaceholder: 'Define the bot\'s base persona and behavior guidelines...',
    blockedResponse: 'Blocked Response Template',
    blockedResponseInfo: 'Message sent when content is blocked by filter. Use {reason} to insert the block reason.',
    triggerKeywords: 'Trigger Keywords',
    triggerKeywordsPlaceholder: 'Enter keywords, separated by commas',
    responseMode: 'Response Mode',
    modes: {
      stream: 'Stream Response (show typing)',
      nonStream: 'Complete Response (send at once)'
    }
  },
  contextControl: {
    title: 'Context Control',
    contextMode: 'Context Mode',
    modes: {
      none: 'No Context',
      channel: 'Channel-based',
      memory: 'Memory-based'
    },
    channelModeInfo: 'Bot will read recent chat history from the channel as context.',
    memoryModeInfo: 'Bot only remembers conversations related to it (mentions, replies, keywords).',
    noneModeInfo: 'Bot will not read any message history, each conversation is independent.',
    historyLimit: 'History Limit',
    messages: 'messages',
    charLimit: 'Token Limit',
    charLimitPlaceholder: 'Enter max token count'
  },
  scopedPrompts: {
    enabled: 'Enabled',
    mode: {
      title: 'Mode',
      override: 'Override',
      append: 'Append'
    },
    remove: 'Remove',
    channels: {
      title: 'Channel-Specific Directives',
      info: 'Set bot identity or context for specific channels. Override mode completely replaces the persona, append mode adds contextual information.',
      id: 'Channel ID',
      idPlaceholder: 'Enter channel ID',
      prompt: 'Directive Content',
      overridePlaceholder: 'In this channel, the bot will completely act as...',
      appendPlaceholder: 'Describe the scene or atmosphere of this channel...',
      add: 'Add Channel Directive'
    },
    guilds: {
      title: 'Server-Specific Directives',
      info: 'Set bot identity or context for entire servers. Lower priority than channel directives.',
      id: 'Server ID',
      idPlaceholder: 'Enter server ID',
      prompt: 'Directive Content',
      overridePlaceholder: 'In this server, the bot\'s default identity is...',
      appendPlaceholder: 'Background setting or special rules for this server...',
      add: 'Add Server Directive'
    }
  },
  roleConfig: {
    title: 'Role-Based Configuration',
    info: 'Set exclusive bot personas and usage limits for users with different roles.',
    roleId: 'Role ID',
    roleTitle: 'Display Name',
    rolePrompt: 'Exclusive Persona Prompt',
    enableMsgLimit: 'Enable Message Limit',
    enableTokenLimit: 'Enable Token Limit',
    totalQuota: 'Total Quota',
    minutes: 'minutes',
    outputBudget: 'Output Budget',
    previewTitle: 'Quota Display Preview',
    previewHeader: 'Quota Status',
    msgLimit: 'Message Quota',
    tokenLimit: 'Token Quota',
    disabled: 'Disabled',
    displayColor: 'Display Color',
    add: 'Add Role Config',
    remove: 'Remove'
  },
  userPortrait: {
    title: 'User Portraits',
    info: 'Define how specific users appear to the bot. This is the highest priority context that will always be considered.',
    userId: 'User ID',
    customNicknamePlaceholder: 'Custom nickname (optional)',
    personaPrompt: 'Describe this user\'s identity, characteristics, or relationship with the bot',
    add: 'Add User Portrait'
  },
  pluginManager: {
    title: 'Plugin Manager',
    info: 'Create custom tools triggered by commands or keywords. Supports calling external APIs with optional LLM processing.',
    name: 'Plugin Name',
    enabled: 'Enabled',
    triggerType: 'Trigger Type',
    triggerTypes: {
      command: 'Command Trigger',
      keyword: 'Keyword Trigger'
    },
    triggers: 'Triggers',
    triggersPlaceholder: 'Separate multiple triggers with commas',
    actionType: 'Action Type',
    actionTypes: {
      http_request: 'HTTP Request (Direct Output)',
      llm_augmented_tool: 'LLM-Augmented Tool'
    },
    injectionMode: 'Injection Mode',
    injectionModes: {
      override: 'Override Response',
      append: 'Append to Context'
    },
    injectionInfo: 'Override mode sends LLM response directly; Append mode provides API result as additional context to bot\'s main logic.',
    httpRequest: 'HTTP Request Config',
    url: 'URL',
    urlPlaceholder: 'https://api.example.com/endpoint',
    method: 'Request Method',
    headers: 'Headers (JSON)',
    body: 'Body Template (JSON)',
    llmPrompt: 'LLM Prompt Template',
    templateInfo: 'Available variables: {user_input} = user input, {api_result} = API response',
    allowInternalRequests: 'Allow Internal Network Requests',
    allowInternalWarning: 'Warning: Enabling this may cause security risks (SSRF). Only enable for trusted APIs.',
    add: 'Add Plugin'
  },
  customParams: {
    title: 'Custom Parameters',
    paramName: 'Parameter Name',
    paramValue: 'Parameter Value',
    types: {
      text: 'Text',
      number: 'Number',
      boolean: 'Boolean',
      json: 'JSON'
    },
    add: 'Add Parameter',
    remove: 'Remove'
  },
  sessionManagement: {
    title: 'Session Management',
    info: 'Clear conversation memory for specific channels. The bot will forget all conversations before this point.',
    channelIdPlaceholder: 'Enter channel ID',
    clearButton: 'Clear Memory',
    clearing: 'Clearing...',
    clearSuccess: 'Memory cleared successfully',
    clearFailed: 'Clear failed: ',
    errorNoId: 'Please enter channel ID'
  },
  uiSettings: {
    title: 'UI Settings',
    font: {
      loadButton: 'Load Custom Font',
      resetButton: 'Reset to Default',
      currentFont: 'Current font: {fontName}',
      defaultFont: 'Using system default font',
      loadError: 'Failed to load font file',
      localStorageError: 'Cannot save font to local storage',
      resetSuccess: 'Font reset to default',
      loadSuccess: 'Font loaded successfully',
      fileTooLarge: 'Font file too large ({size}MB), max supported is {maxSize}MB',
      storageError: 'Storage error',
      localStorageUnavailable: 'localStorage is unavailable, please check browser settings',
      quotaExceeded: 'localStorage quota exceeded, please clear browser data'
    },
    timezone: {
      title: 'Timezone'
    }
  },
  logViewer: {
    title: 'Live Logs',
    filterLevel: 'Filter Level',
    autoscroll: 'Auto-scroll'
  },
  debugger: {
    title: 'Debugger',
    info: 'Simulate the bot\'s response generation process for testing and debugging.',
    userId: 'User ID',
    userIdPlaceholder: 'Simulated user ID',
    roleId: 'Role ID',
    channelId: 'Channel ID',
    channelIdPlaceholder: 'Simulated channel ID',
    guildId: 'Server ID',
    guildIdPlaceholder: 'Simulated server ID (optional)',
    message: 'Message Content',
    messagePlaceholder: 'Enter test message...',
    button: 'Simulate',
    simulating: 'Simulating...',
    error: 'Error: ',
    generatedPrompt: 'Generated System Prompt',
    llmResponse: 'LLM Response',
    errorIncomplete: 'Please fill in all required fields'
  },
  usage: {
    title: 'Usage Statistics',
    periods: {
        today: 'Today',
        week: 'This Week',
        month: 'This Month',
        all: 'All Time'
    },
    views: {
        user: 'User',
        role: 'Role',
        channel: 'Channel',
        guild: 'Server'
    },
    loading: 'Loading...',
    totalRequests: 'Total Requests',
    totalTokens: 'Total Tokens',
    estimatedCost: 'Estimated Cost',
    breakdown: 'Breakdown',
    userInfo: 'User Info',
    roleInfo: 'Role Info',
    channelInfo: 'Channel Info',
    guildInfo: 'Server Info',
    totalUsage: 'Total Usage',
    totalCost: 'Total Cost',
    requestsShort: 'reqs',
    refresh: 'Refresh',
    configurePricing: 'Configure Pricing',
    pricingConfig: 'Pricing Configuration',
    pricingInfo: 'Configure pricing for each model (per million tokens)',
    provider: 'Provider',
    modelName: 'Model Name',
    modelPlaceholder: 'e.g., gpt-4o',
    inputPrice: 'Input Price',
    outputPrice: 'Output Price',
    addModel: 'Add Model',
    save: 'Save',
    cancel: 'Cancel'
},
"searchSettings": {
    "title": "Search Settings",
    "enable": "Enable Search",
    "apiKey": "API Key",
    "apiUrl": "API URL",
    "triggerMode": {
        "title": "Trigger Mode",
        "command": "Command",
        "keyword": "Keyword"
    },
    "commandLabel": "Command",
    "commandInfo": "The command to trigger the search (e.g., !search).",
    "keywordsLabel": "Keywords",
    "keywordsInfo": "Comma-separated keywords that trigger the search.",
    "includeDate": "Include Date in Search",
    "maxResults": "Max Search Results",
    "compression": "Compression Method",
    "compressionNone": "None",
    "compressionTruncate": "Truncate",
    "compressionRAG": "RAG",
    "config": {
        "title": "Configuration"
    },
    "blacklist": {
        "title": "Blacklist",
        "add": "Add Subscription",
        "addPlaceholder": "Enter a domain to block, e.g., example.com",
        "name": "Name",
        "empty": "No data",
        "updateNow": "Update Now",
        "deleteSource": "Delete Source"
    }
 },
 knowledge: {
   title: 'Knowledge Base',
   tabs: {
     worldBook: 'World Book',
     memory: 'Memory'
   },
   confirmDeleteMemory: 'Are you sure you want to delete this memory item?',
   confirmDeleteWorldBook: 'Are you sure you want to delete this entry?',
   error: {
     loadMemory: 'Failed to load memory',
     addMemory: 'Failed to add memory item',
     deleteMemory: 'Failed to delete memory item',
     updateMemory: 'Failed to update memory item',
     loadWorldBook: 'Failed to load World Book',
     emptyFields: 'Keywords and content cannot be empty',
     saveWorldBook: 'Failed to save World Book entry',
     deleteWorldBook: 'Failed to delete World Book entry'
   },
   memory: {
     title: 'Memory',
     addPlaceholder: 'Add a new memory item...',
     add: 'Add Memory',
     edit: 'Edit',
     save: 'Save',
     cancel: 'Cancel',
     delete: 'Delete',
     by: 'By',
     at: 'At',
     source: 'Source',
     contentLabel: 'Content'
   },
   worldBook: {
     title: 'World Book',
     keywordsLabel: 'Keywords',
     keywordsHint: 'separated by commas',
     keywordsPlaceholder: 'e.g., worldview, main characters...',
     contentLabel: 'Content',
     contentPlaceholder: 'Describe this setting in detail...',
     addTitle: 'Add New Entry',
     editTitle: 'Edit Entry',
     add: 'Add Entry',
     save: 'Save Changes',
     edit: 'Edit',
     delete: 'Delete',
     cancelEdit: 'Cancel Edit'
   }
 }
};
