export default {
    title: "Discord LLM Bot Control Panel",
    globalConfig: { 
        title: "Global Configuration", 
        token: "Discord Bot Token", 
        tokenPlaceholder: "Enter your bot token",
        apiKey: "RESTful API Key",
        apiKeyUnavailable: "API Key will be generated after first save.",
        apiKeyInfo: "Use this key in the 'X-API-Key' header to trigger plugins via the RESTful API.",
        copy: "Copy"
    },
    llmProvider: { title: "LLM Provider Configuration", select: "Select Provider", providers: { openai: "OpenAI & Compatible", google: "Google Gemini", anthropic: "Anthropic Claude" }, apiKey: "API Key", apiKeyPlaceholder: "Enter API Key for the selected provider", baseUrl: "API Base URL (Optional)", baseUrlPlaceholder: "e.g., https://api.openai.com/v1", },
    contextControl: { title: "Conversation Context Control", contextMode: "Context Mode", modes: { none: "Disabled", channel: "Channel Mode", memory: "Memory Mode" }, noneModeInfo: "The bot will not read any past messages. It only responds to the current message.", channelModeInfo: "The bot reads all recent messages in the channel to understand context.", memoryModeInfo: "The bot only remembers direct conversations (mentions, replies, keywords) and their context.", historyLimit: "Message History Limit", messages: "messages", charLimit: "Character Limit for History", charLimitPlaceholder: "e.g., 4000", },
    userPortrait: { title: "User-Specific Portrait", info: "Assign a custom nickname and persona to specific users. This will override any role-based settings.", userId: "Discord User ID", customNicknamePlaceholder: "e.g., Master, Miss", personaPrompt: "Persona prompt for this user", add: "+ Add User Portrait", },
    roleConfig: { title: "Role-Based Configuration", info: "Set personas, titles, and usage limits. The system uses the official tokenizer for each model to calculate consumption. Users can check quota with `!myquota`. When triggered, the system pre-calculates consumption based on an output budget.", add: "+ Add Role Configuration", roleId: "Discord Role ID", roleTitle: "Custom Title (e.g., VIP Member)", rolePrompt: "Persona prompt for this role", enableMsgLimit: "Enable Message Limit", enableTokenLimit: "Enable Token Limit", msgLimit: "Messages", tokenLimit: "Tokens", minutes: "min", totalQuota: "Total Quota", outputBudget: "Output Budget", displayColor: "Quota Embed Color", previewTitle: "Quota Display Preview", previewHeader: "Quota Status for User", disabled: "Disabled" },
    defaultBehavior: { title: "Default Model & Behavior", modelName: "Model Name (Manual Input)", modelPlaceholders: { openai: "e.g., gpt-4o", google: "e.g., gemini-1.5-pro-latest", anthropic: "e.g., claude-3-opus-20240229" }, systemPrompt: "Default System Prompt", systemPromptPlaceholder: "Prompt for users without a specific persona.", triggerKeywords: "Trigger Keywords (comma-separated)", triggerKeywordsPlaceholder: "e.g., jarvis, aibot", responseMode: "Response Mode", modes: { stream: "Stream", nonStream: "Non-Stream" } },
    customParams: { title: "Custom LLM Parameters", add: "+ Add Parameter", paramName: "Parameter Name", paramValue: "Value", types: { text: "Text", number: "Number", boolean: "Boolean", json: "JSON" } },
    sessionManagement: { title: "Session Management", info: "To start a new conversation in a channel without old context, get the Channel ID from Discord and clear its memory here. This only affects the bot's current session.", channelIdPlaceholder: "Paste Channel ID here", clearButton: "Clear Channel Memory", clearing: "Clearing memory...", clearSuccess: "Memory cleared successfully for the specified channel!", clearFailed: "Failed to clear memory: ", errorNoId: "Please enter a Channel ID first." },
    pluginManager: {
        title: "Plugin Manager",
        info: "Create tools that the bot can use. Plugins trigger on specific commands or keywords to perform actions, like calling an external API. The API result can be directly displayed or summarized by the LLM.",
        add: "+ Add Plugin", name: "Plugin Name", enabled: "Enabled", triggerType: "Trigger Type",
        triggerTypes: { command: "Command", keyword: "Keyword" }, triggers: "Triggers (comma-separated)",
        triggersPlaceholder: "e.g., !weather, !stock", actionType: "Action Type",
        actionTypes: { http_request: "HTTP Request (Direct Output)", llm_augmented_tool: "LLM-Augmented Tool" },
        httpRequest: "HTTP Request Configuration", url: "URL", urlPlaceholder: "https://api.example.com/data?q={user_input}",
        method: "Method", headers: "Headers (JSON format)", body: "Body Template (JSON format, for POST/PUT)",
        llmPrompt: "LLM Prompt Template",
        templateInfo: "You can use placeholders: {user_input}, {author_name}, {channel_id}, etc. For LLM-Augmented tools, also use {api_result} to include the data fetched.",
    },
    logViewer: { title: "Backend Log Viewer", filterLevel: "Filter Level", autoscroll: "Auto-scroll" },
    buttons: { save: "Save Configuration & Restart Bot", saving: "Saving...", },
    status: { loading: "Loading configuration...", loadFailed: "Failed to load config: ", saving: "Saving configuration and restarting bot...", saveSuccess: "Configuration saved successfully!", saveFailed: "Save failed: ", }
};
