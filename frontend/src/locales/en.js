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
        providers: {
            openai: "OpenAI & Compatible",
            google: "Google Gemini",
            anthropic: "Anthropic Claude",
        },
        apiKey: "API Key",
        apiKeyPlaceholder: "Enter API Key for the selected provider",
        baseUrl: "API Base URL (Optional)",
        baseUrlPlaceholder: "e.g., https://api.openai.com/v1",
    },
    contextControl: {
        title: "Conversation Context Control",
        info: "Allow the bot to read previous messages for context. Set messages to 0 to disable. The bot will stop reading when either limit is reached.",
        historyLimit: "Message History Limit",
        messages: "messages",
        charLimit: "Character Limit for History",
        charLimitPlaceholder: "e.g., 4000",
    },
    userPortrait: {
        title: "User Portrait Management",
        info: "Assign a custom nickname and persona prompt to specific users.",
        userId: "Discord User ID",
        customNickname: "Custom Nickname",
        customNicknamePlaceholder: "e.g., Master, Miss",
        personaPrompt: "Persona prompt describing this user",
        add: "+ Add User Portrait",
    },
    defaultBehavior: {
        title: "Default Model & Behavior",
        modelName: "Model Name (Manual Input)",
        modelPlaceholders: {
            openai: "e.g., gpt-4o",
            google: "e.g., gemini-1.5-pro-latest",
            anthropic: "e.g., claude-3-opus-20240229",
        },
        systemPrompt: "Default System Prompt",
        systemPromptPlaceholder: "This is the prompt for users without a specific persona.",
        triggerKeywords: "Trigger Keywords (comma-separated)",
        triggerKeywordsPlaceholder: "e.g., jarvis, aibot",
        responseMode: "Response Mode",
        modes: {
            stream: "Stream",
            nonStream: "Non-Stream",
        }
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
