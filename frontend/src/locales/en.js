export default {
    title: "Discord LLM Bot Control Panel",
    globalConfig: {
        title: "Global Configuration",
        token: "Discord Bot Token",
        tokenPlaceholder: "Enter your bot token",
    },
    llmProvider: {
        title: "LLM Provider Configuration",
        select: "Select Provider",
        providers: { openai: "OpenAI & Compatible", google: "Google Gemini", anthropic: "Anthropic Claude" },
        apiKey: "API Key",
        apiKeyPlaceholder: "Enter API Key for the selected provider",
        baseUrl: "API Base URL (Optional)",
        baseUrlPlaceholder: "e.g., https://api.openai.com/v1",
    },
    contextControl: {
        title: "Conversation Context Control",
        contextMode: "Context Mode",
        modes: { none: "Disabled", channel: "Channel Mode", memory: "Memory Mode" },
        noneModeInfo: "The bot will not read any past messages. It only responds to the current message.",
        channelModeInfo: "The bot reads all recent messages in the channel to understand context.",
        memoryModeInfo: "The bot only remembers direct conversations (mentions, replies, keywords) and their context.",
        historyLimit: "Message History Limit",
        messages: "messages",
        charLimit: "Character Limit for History",
        charLimitPlaceholder: "e.g., 4000",
    },
    userPortrait: {
        title: "User-Specific Portrait",
        info: "Assign a custom nickname and persona to specific users. This will override any role-based settings.",
        userId: "Discord User ID",
        customNicknamePlaceholder: "e.g., Master, Miss",
        personaPrompt: "Persona prompt describing this user",
        add: "+ Add User Portrait",
    },
    roleConfig: {
        title: "Role-Based Configuration",
        info: "Set personas, custom titles, and usage limits for Discord roles. The user's highest role takes precedence. User-specific settings will override these. Users can check their quota with the `!myquota` command.",
        add: "+ Add Role Configuration",
        roleId: "Discord Role ID",
        roleTitle: "Custom Title (e.g., VIP Member)",
        rolePrompt: "Persona prompt for members of this role",
        enableMsgLimit: "Enable Message Limit",
        enableCharLimit: "Enable Character Limit",
        msgLimit: "Messages",
        charLimit: "Characters",
        minutes: "min",
        displayColor: "Quota Embed Color",
        previewTitle: "Quota Display Preview",
        previewHeader: "Quota Status for User",
        disabled: "Disabled"
    },
    defaultBehavior: {
        title: "Default Model & Behavior",
        modelName: "Model Name (Manual Input)",
        modelPlaceholders: { openai: "e.g., gpt-4o", google: "e.g., gemini-1.5-pro-latest", anthropic: "e.g., claude-3-opus-20240229" },
        systemPrompt: "Default System Prompt",
        systemPromptPlaceholder: "This is the prompt for users without a specific persona.",
        triggerKeywords: "Trigger Keywords (comma-separated)",
        triggerKeywordsPlaceholder: "e.g., jarvis, aibot",
        responseMode: "Response Mode",
        modes: { stream: "Stream", nonStream: "Non-Stream" }
    },
    customParams: {
        title: "Custom LLM Parameters",
        add: "+ Add Parameter",
        paramName: "Parameter Name",
        paramValue: "Value",
        types: { text: "Text", number: "Number", boolean: "Boolean", json: "JSON" }
    },
    sessionManagement: {
        title: "Session Management",
        info: "To start a new conversation in a channel without old context, get the Channel ID from Discord and clear its memory here. This only affects the bot's current session.",
        channelIdPlaceholder: "Paste Channel ID here",
        clearButton: "Clear Channel Memory",
        clearing: "Clearing memory...",
        clearSuccess: "Memory cleared successfully for the specified channel!",
        clearFailed: "Failed to clear memory: ",
        errorNoId: "Please enter a Channel ID first."
    },
    logViewer: {
        title: "Backend Log Viewer",
        filterLevel: "Filter Level",
        autoscroll: "Auto-scroll"
    },
    buttons: {
        save: "Save Configuration & Restart Bot",
        saving: "Saving...",
    },
    status: {
        loading: "Loading configuration...",
        loadFailed: "Failed to load config: ",
        saving: "Saving configuration and restarting bot...",
        saveSuccess: "Configuration saved successfully!",
        saveFailed: "Save failed: ",
    }
};
