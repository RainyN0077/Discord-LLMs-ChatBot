export default {
    title: "Discord LLM 机器人控制面板",
    globalConfig: {
        title: "全局配置",
        token: "Discord 机器人令牌",
        tokenPlaceholder: "输入你的机器人令牌",
    },
    llmProvider: {
        title: "LLM 服务商配置",
        select: "选择服务商",
        providers: {
            openai: "OpenAI 及兼容模型",
            google: "Google Gemini",
            anthropic: "Anthropic Claude",
        },
        apiKey: "API 密钥",
        apiKeyPlaceholder: "输入所选服务商的 API 密钥",
        baseUrl: "API Base URL (代理选填)",
        baseUrlPlaceholder: "例如: https://api.openai-proxy.com/v1",
    },
    contextControl: {
        title: "对话上下文控制",
        contextMode: "上下文模式",
        modes: {
            none: "禁用",
            channel: "频道模式",
            memory: "记忆模式"
        },
        noneModeInfo: "机器人将不读取任何历史消息，仅对当前消息做出回应。",
        channelModeInfo: "机器人会读取频道内所有近期消息来理解上下文，适合公共讨论。",
        memoryModeInfo: "机器人只记忆与它直接相关的对话（提及、回复、关键词）及其上下文，适合个人助理场景。",
        historyLimit: "历史消息数量限制",
        messages: "条消息",
        charLimit: "历史消息字数限制",
        charLimitPlaceholder: "例如: 4000",
    },
    userPortrait: {
        title: "用户肖像管理",
        info: "为特定用户分配自定义的称呼和人设。其他用户将使用下方设定的默认人设。",
        userId: "Discord 用户ID",
        customNickname: "自定义称呼",
        customNicknamePlaceholder: "例如：小姐, 阁下, 主人",
        personaPrompt: "描述该用户的专属人设提示词",
        add: "+ 添加用户肖像",
    },
    defaultBehavior: {
        title: "默认模型与行为",
        modelName: "模型名称 (手动输入)",
        modelPlaceholders: {
            openai: "例如: gpt-4o",
            google: "例如: gemini-1.5-pro-latest",
            anthropic: "例如: claude-3-opus-20240229",
        },
        systemPrompt: "默认系统提示词",
        systemPromptPlaceholder: "这是用于未设定专属肖像的用户的提示词。",
        triggerKeywords: "触发词 (英文逗号分隔)",
        triggerKeywordsPlaceholder: "例如: 贾维斯, aibot",
        responseMode: "回应模式",
        modes: {
            stream: "流式",
            nonStream: "非流式",
        }
    },
    customParams: {
        title: "自定义 LLM 参数",
        add: "+ 添加参数",
        paramName: "参数名称",
        paramValue: "值",
        types: {
            text: "文本",
            number: "数字",
            boolean: "布尔值",
            json: "JSON"
        }
    },
    sessionManagement: {
        title: "会话管理",
        info: "如需在某个频道开启一段全新的、不受旧上下文影响的对话，请在Discord中获取该频道的ID（开启开发者模式后，右键点击频道复制ID），然后在此处清除其记忆。此操作仅对机器人当前会话有效，机器人重启后将重置。",
        channelIdPlaceholder: "在此处粘贴频道ID",
        clearButton: "清除频道记忆",
        clearing: "正在清除记忆...",
        clearSuccess: "已成功为指定频道清除记忆！",
        clearFailed: "清除记忆失败：",
        errorNoId: "请先输入一个频道ID。"
    },
    buttons: {
        save: "保存配置并重启机器人",
        saving: "保存中...",
    },
    status: {
        loading: "正在加载配置...",
        loadFailed: "加载配置失败: ",
        saving: "正在保存配置并重启机器人...",
        saveSuccess: "配置已成功保存！",
        saveFailed: "保存失败: ",
    }
};
