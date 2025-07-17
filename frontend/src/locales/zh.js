export default {
    title: "Discord LLM 机器人控制面板",
    globalConfig: { 
        title: "全局配置", 
        token: "Discord 机器人令牌", 
        tokenPlaceholder: "输入你的机器人令牌",
        apiKey: "RESTful API 密钥",
        apiKeyUnavailable: "首次保存后将自动生成API密钥。",
        apiKeyInfo: "通过 RESTful API 触发插件时，请在 'X-API-Key' 请求头中使用此密钥。",
        copy: "复制"
    },
    llmProvider: { 
        title: "LLM 服务商配置", 
        select: "选择服务商", 
        providers: { 
            openai: "OpenAI 及兼容模型", 
            google: "Google Gemini", 
            anthropic: "Anthropic Claude" 
        }, 
        apiKey: "API 密钥", 
        apiKeyPlaceholder: "输入所选服务商的 API 密钥", 
        baseUrl: "API Base URL (代理选填)", 
        baseUrlPlaceholder: "例如: https://api.openai-proxy.com/v1"
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
        charLimitPlaceholder: "例如: 4000"
    },
    userPortrait: { 
        title: "特定用户肖像", 
        info: "为特定用户分配自定义的称呼和人设。此设置将覆盖任何基于身份组的设置。", 
        userId: "Discord 用户ID", 
        customNicknamePlaceholder: "例如：小姐, 阁下, 主人", 
        personaPrompt: "描述该用户的专属人设提示词", 
        add: "+ 添加用户肖像"
    },
    roleConfig: { 
        title: "基于身份组的配置", 
        info: "为不同身份组设置专属人设、头衔和使用频率限制。系统会根据所选模型，使用官方方式精确计算Token消耗。触发时，系统会根据“输出预算”来预估并检查本次消耗。用户可使用 `!myquota` 查询额度。", 
        add: "+ 添加身份组配置", 
        roleId: "Discord 身份组ID", 
        roleTitle: "自定义头衔 (例如：尊贵的会员)", 
        rolePrompt: "此身份组成员专属的人设提示词", 
        enableMsgLimit: "启用消息数限制器", 
        enableTokenLimit: "启用Token限制器", 
        msgLimit: "消息数", 
        tokenLimit: "Token数", 
        minutes: "分钟", 
        totalQuota: "总额度", 
        outputBudget: "输出预算", 
        displayColor: "额度查询框颜色", 
        previewTitle: "额度显示预览", 
        previewHeader: "用户的额度状态", 
        disabled: "未启用" 
    },
    defaultBehavior: { 
        title: "默认模型与行为", 
        modelName: "模型名称 (手动输入)", 
        modelPlaceholders: { 
            openai: "例如: gpt-4o", 
            google: "例如: gemini-1.5-pro-latest", 
            anthropic: "例如: claude-3-opus-20240229" 
        }, 
        systemPrompt: "默认系统提示词", 
        systemPromptPlaceholder: "这是用于未设定专属肖像的用户的提示词。", 
        triggerKeywords: "触发词 (英文逗号分隔)", 
        triggerKeywordsPlaceholder: "例如: 贾维斯, aibot", 
        responseMode: "回应模式", 
        modes: { 
            stream: "流式", 
            nonStream: "非流式" 
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
        info: "如需在某个频道开启一段全新的对话，请在此处清除其记忆。此操作仅对机器人当前会话有效。", 
        channelIdPlaceholder: "在此处粘贴频道ID", 
        clearButton: "清除频道记忆", 
        clearing: "正在清除记忆...", 
        clearSuccess: "已成功为指定频道清除记忆！", 
        clearFailed: "清除记忆失败：", 
        errorNoId: "请先输入一个频道ID。" 
    },
    pluginManager: {
        title: "插件管理器",
        info: "创建可供机器人使用的工具。插件通过特定命令或关键词触发，以执行调用外部API等操作。API返回的结果可以直接显示，也可以交由LLM进行智能总结。",
        add: "+ 添加插件", 
        name: "插件名称", 
        enabled: "启用", 
        triggerType: "触发方式",
        triggerTypes: { 
            command: "命令", 
            keyword: "关键词" 
        }, 
        triggers: "触发词 (英文逗号分隔)",
        triggersPlaceholder: "例如: !天气, !股票", 
        actionType: "动作类型",
        actionTypes: { 
            http_request: "HTTP请求 (直接输出)", 
            llm_augmented_tool: "LLM增强工具" 
        },
        injectionMode: "注入模式",
        injectionModes: {
            override: "覆盖 (独立回应)",
            append: "追加 (注入上下文)"
        },
        injectionInfo: "“覆盖”模式会生成一次独立、全新的回应。“追加”模式会将工具获取的结果注入到当前对话中，让机器人以其自身人设对此信息做出反应。",
        httpRequest: "HTTP 请求配置", 
        url: "URL", 
        urlPlaceholder: "https://api.example.com/data?q={user_input}",
        method: "请求方法", 
        headers: "请求头 (JSON格式)", 
        body: "请求体模板 (JSON格式, 用于POST/PUT)",
        llmPrompt: "LLM 提示词模板",
        templateInfo: "可使用占位符: {user_input}, {author_name}, {channel_id} 等。对于LLM增强工具，额外使用 {api_result} 来引用获取到的数据。",
    },
    logViewer: { 
        title: "后端日志查看器", 
        filterLevel: "筛选等级", 
        autoscroll: "自动滚动" 
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
