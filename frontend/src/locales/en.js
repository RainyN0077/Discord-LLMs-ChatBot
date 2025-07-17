export default {
    title: "Discord LLM Bot Control Panel",
    uiSettings: {
        title: "UI Settings",
        font: {
            loadButton: "Load Font File",
            resetButton: "Reset to Default Font",
            currentFont: "Current font: {fontName}",
            defaultFont: "Using default system font.",
            loadSuccess: "Font '{fontName}' loaded successfully!",
            loadError: "Error reading font file.",
            resetSuccess: "Font reset to default.",
            localStorageError: "Failed to save font. Local storage might be full or disabled.",
        }
    },
    globalConfig: { 
        title: "Global Configuration", 
        token: "Discord Bot Token", 
        tokenPlaceholder: "Enter your bot token",
        apiKey: "RESTful API Key",
        apiKeyUnavailable: "API Key will be generated after first save.",
        apiKeyInfo: "Use this key in the 'X-API-Key' header to trigger plugins via the RESTful API.",
        copy: "Copy"
    },
    llmProvider: { 
        title: "LLM Provider Configuration", 
        select: "Select Provider", 
        providers: { 
            openai: "OpenAI & Compatible", 
            google: "Google Gemini", 
            anthropic: "Anthropic Claude" 
        }, 
        apiKey: "API Key", 
        apiKeyPlaceholder: "Enter API Key for the selected provider", 
        baseUrl: "API Base URL (Optional)", 
        baseUrlPlaceholder: "e.g., https://api.openai.com/v1"
    },
    scopedPrompts: {
        enabled: "Enabled",
        mode: {
            title: "Mode",
            override: "Override Bot's Identity",
            append: "Append as Scene Context"
        },
        channel: {
            title: "Channel-Specific Directive (Highest Priority for Bot's Identity)",
            info: "Define the bot's core identity (Override) or the scene's context (Append) for a specific channel. A channel's 'Override' directive is the highest priority rule for determining the bot's persona.",
            add: "+ Add Channel Directive",
            id: "Channel ID",
            idPlaceholder: "Enter Discord Channel ID",
            prompt: "Directive Prompt",
            overridePlaceholder: "The bot will adopt this persona in THIS channel ONLY...",
            appendPlaceholder: "Describe this channel's purpose or current topic..."
        },
        guild: {
            title: "Server-Specific Directive (Mid Priority for Bot's Identity)",
            info: "Define the bot's identity (Override) or scene context (Append) for an entire server. This is applied only if there is NO channel-specific 'Override' directive active.",
            add: "+ Add Server Directive",
            id: "Server ID",
            idPlaceholder: "Enter Discord Server ID",
            prompt: "Directive Prompt",
            overridePlaceholder: "The bot will adopt this persona for the whole server...",
            appendPlaceholder: "Describe this server's theme or context..."
        }
    },
    userPortrait: { 
        title: "User Portrait (Highest Priority for User Context)", 
        info: "Define a specific user's identity IN THE EYES OF THE BOT. This is NOT for setting the bot's persona, but to inform the bot about the user. This information is always included as critical context.", 
        userId: "Discord User ID", 
        customNicknamePlaceholder: "Custom Nickname for this user", 
        personaPrompt: "Describe THIS USER (e.g., 'The captain of the ship', 'My creator and master')", 
        add: "+ Add User Portrait"
    },
    roleConfig: { 
        title: "Role-Based Configuration (Low Priority for Bot's Identity)", 
        info: "Define the BOT's persona when interacting with users of a certain role. This is applied only if no Channel or Server 'Override' directives are active. You can also set usage limits.", 
        add: "+ Add Role Configuration", 
        roleId: "Discord Role ID", 
        roleTitle: "Custom Title (e.g., VIP Member)", 
        rolePrompt: "Bot's persona FOR THIS ROLE (e.g., 'A respectful butler')", 
        enableMsgLimit: "Enable Message Limit", 
        enableTokenLimit: "Enable Token Limit", 
        msgLimit: "Messages", 
        tokenLimit: "Tokens", 
        minutes: "min", 
        totalQuota: "Total Quota", 
        outputBudget: "Output Budget", 
        displayColor: "Quota Embed Color", 
        previewTitle: "Quota Display Preview", 
        previewHeader: "Quota Status for User", 
        disabled: "Disabled" 
    },
    defaultBehavior: { 
        title: "Default Model & Behavior (Lowest Priority)", 
        modelName: "Model Name (Manual Input)", 
        modelPlaceholders: { 
            openai: "e.g., gpt-4o", 
            google: "e.g., gemini-1.5-pro-latest", 
            anthropic: "e.g., claude-3-opus-20240229" 
        }, 
        systemPrompt: "Default System Prompt (Foundation)", 
        systemPromptPlaceholder: "The bot's foundational, fallback persona.", 
        blockedResponse: "Blocked Response Template",
        blockedResponseInfo: "Sorry, a communication issue occurred. This is an automated reply: [{reason}] (Use {reason} as a placeholder for the block code.)",
        triggerKeywords: "Trigger Keywords (comma-separated)", 
        triggerKeywordsPlaceholder: "e.g., jarvis, aibot", 
        responseMode: "Response Mode", 
        modes: { 
            stream: "Stream", 
            nonStream: "Non-Stream" 
        } 
    },
    customParams: { 
        title: "Custom LLM Parameters", 
        add: "+ Add Parameter", 
        paramName: "Parameter Name", 
        paramValue: "Value", 
        types: { 
            text: "Text", 
            number: "Number", 
            boolean: "Boolean", 
            json: "JSON" 
        } 
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
    pluginManager: {
        title: "Plugin Manager",
        info: "Create tools that the bot can use. Plugins trigger on specific commands or keywords to perform actions, like calling an external API. The API result can be directly displayed or summarized by the LLM.",
        add: "+ Add Plugin", 
        name: "Plugin Name", 
        enabled: "Enabled", 
        triggerType: "Trigger Type",
        triggerTypes: { 
            command: "Command", 
            keyword: "Keyword" 
        }, 
        triggers: "Triggers (comma-separated)",
        triggersPlaceholder: "e.g., !weather, !stock", 
        actionType: "Action Type",
        actionTypes: { 
            http_request: "HTTP Request (Direct Output)", 
            llm_augmented_tool: "LLM-Augmented Tool" 
        },
        injectionMode: "Injection Mode",
        injectionModes: {
            override: "Override (Standalone Response)",
            append: "Append (Inject into Context)"
        },
        injectionInfo: "'Override' creates a separate, one-off response. 'Append' injects the tool's result into the current conversation for the bot to react to with its persona.",
        httpRequest: "HTTP Request Configuration", 
        url: "URL", 
        urlPlaceholder: "https://api.example.com/data?q={user_input}",
        method: "Method", 
        headers: "Headers (JSON format)", 
        body: "Body Template (JSON format, for POST/PUT)",
        llmPrompt: "LLM Prompt Template",
        templateInfo: "You can use placeholders: {user_input}, {author_name}, {channel_id}, etc. For LLM-Augmented tools, also use {api_result} to include the data fetched.",
    },
    contextControl: { 
        title: "Conversation Context Control", 
        contextMode: "Context Mode", 
        modes: { 
            none: "Disabled", 
            channel: "Channel Mode", 
            memory: "Memory Mode" 
        }, 
        noneModeInfo: "The bot will not read any past messages. It only responds to the current message.", 
        channelModeInfo: "The bot reads all recent messages in the channel to understand context.", 
        memoryModeInfo: "The bot only remembers direct conversations (mentions, replies, keywords) and their context.", 
        historyLimit: "Message History Limit", 
        messages: "messages", 
        charLimit: "Character Limit for History", 
        charLimitPlaceholder: "e.g., 4000"
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
