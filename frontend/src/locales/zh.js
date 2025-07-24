// src/locales/zh.js
export default {
  title: 'Discord LLM 机器人控制面板',
  tabs: {
    core: '核心设置',
    directives: '身份指令',
    advanced: '高级工具'
  },
  buttons: {
    save: '保存配置并重启机器人',
    saving: '保存中...'
  },
  status: {
    loading: '加载配置中...',
    saving: '正在保存...',
    saveSuccess: '配置已保存，机器人重启成功！',
    saveFailed: '保存失败：{error}',
    loadFailed: '加载配置失败：{error}'
  },
  errors: {
    duplicateId: 'ID "{id}" 已存在，请使用其他ID'
  },
  globalConfig: {
    title: '全局配置',
    token: 'Discord 机器人令牌',
    tokenPlaceholder: '输入你的 Discord Bot Token',
    apiKey: 'RESTful API 密钥',
    apiKeyUnavailable: 'API密钥不可用',
    copy: '复制',
    apiKeyInfo: '这是你的专属API密钥，用于外部服务调用插件接口。请妥善保管，不要分享给他人。'
  },
  llmProvider: {
    title: '大模型服务商',
    select: '选择服务商',
    providers: {
      openai: 'OpenAI',
      google: 'Google Gemini',
      anthropic: 'Anthropic Claude'
    },
    apiKey: 'API 密钥',
    apiKeyPlaceholder: '输入你的 API Key',
    baseUrl: '基础URL (可选)',
    baseUrlPlaceholder: '留空使用官方API，或输入自定义端点',
    fetchModels: '获取模型列表',
    loading: '加载中...',
    testConnection: '测试连接',
    testing: '测试中...',
    selectModel: '选择模型',
    noApiKey: '请先输入API密钥',
    modelsLoaded: '模型列表加载成功',
    modelsLoadFailed: '加载模型列表失败：',
    selectModelFirst: '请先选择一个模型',
    testSuccess: '连接测试成功！',
    testFailed: '连接测试失败：',
    testError: '测试出错：',
    testResult: '测试结果',
    modelResponded: '模型响应',
    toggleInputMode: '切换输入模式',
    fetchModelsTooltip: '获取或刷新可用模型列表',
    modelListInfo: '已加载 {count} 个可用模型，点击 ✏️ 可切换到手动输入'
  },
  defaultBehavior: {
    title: '默认行为',
    modelName: '模型名称',
    modelPlaceholders: {
      openai: '例如: gpt-4o, gpt-3.5-turbo',
      google: '例如: gemini-1.5-flash, gemini-1.5-pro',
      anthropic: '例如: claude-3-opus-20240229'
    },
    botNickname: 'Bot 昵称',
    botNicknamePlaceholder: '例如: Endless',
    systemPrompt: '系统提示词',
    systemPromptPlaceholder: '定义机器人的基础人设和行为准则...',
    blockedResponse: '屏蔽响应模板',
    blockedResponseInfo: '当内容被过滤器拦截时发送的消息。使用 {reason} 插入拦截原因。',
    triggerKeywords: '触发关键词',
    triggerKeywordsPlaceholder: '输入关键词，用逗号分隔',
    responseMode: '响应模式',
    modes: {
      stream: '流式响应 (逐字显示)',
      nonStream: '完整响应 (一次性发送)'
    }
  },
  knowledge: {
    title: '知识库',
    confirmDeleteMemory: '确定要删除这条记忆吗？',
    confirmDeleteWorldBook: '确定要删除这个世界书条目吗？',
    tabs: {
      worldBook: '世界书',
      memory: '记忆库',
      settings: '查重设置'
    },
    settings: {
      title: '查重设置',
      memoryDedupThreshold: '记忆库查重阈值',
      worldBookDedupThreshold: '世界书查重阈值',
      dedupDescription: '设置查重阈值。0%将会导致完全不记录任何信息，100%则只阻止完全相同的信息。推荐值为80-90%。',
      save: '保存查重设置'
    },
    error: {
      loadMemory: '加载记忆库失败',
      addMemory: '添加记忆失败',
      deleteMemory: '删除记忆失败',
      updateMemory: '更新记忆失败',
      loadWorldBook: '加载世界书失败',
      saveWorldBook: '保存世界书条目失败',
      deleteWorldBook: '删除世界书条目失败',
      emptyFields: '关键词和内容不能为空'
    },
    memory: {
      title: '记忆库',
      add: '添加记忆',
      edit: '编辑',
      save: '保存',
      cancel: '取消',
      delete: '删除',
      addPlaceholder: '添加一条新的记忆...',
      by: '记录者',
      at: '时间',
      source: '来源',
      contentLabel: '内容',
      userIdLabel: '用户 ID',
      timestampLabel: '时间戳 (可选, 你的本地时间)',
      byPlaceholder: '例如 WebUI 或用户名',
      userIdPlaceholder: '例如 1234567890 (可选)',
      searchPlaceholder: '按记录者搜索...',
      noResults: '没有找到匹配的记录。'
    },
    worldBook: {
      title: '世界书',
      edit: '编辑',
      delete: '删除',
      add: '添加条目',
      save: '保存更改',
      cancelEdit: '取消编辑',
      addTitle: '添加新条目',
      editTitle: '编辑条目',
      keywordsLabel: '关键词',
      keywordsHint: '用逗号分隔',
      keywordsPlaceholder: '例如：地点, 设定, 角色A',
      contentLabel: '内容',
      contentPlaceholder: '当关键词被提及时，这段内容将被注入到上下文中。',
      searchPlaceholder: '按关键词搜索...',
      noResults: '没有找到匹配的条目。',
      linkedUserLabel: '关联用户',
      noLinkedUser: '无'
    },
    dynamic: {
      linkedUserLabel: "关联用户 ID (动态模式)",
      userIdPlaceholder: "在此处手动输入用户ID",
      aliasesLabel: "别名/昵称",
      aliasesPlaceholder: "用户的其他称呼，用逗号分隔",
      triggersLabel: "专用触发词",
      triggersPlaceholder: "提及这些词也会关联到此用户，用逗号分隔"
    }
  },
  contextControl: {
    title: '上下文控制',
    contextMode: '上下文模式',
    modes: {
      none: '无上下文',
      channel: '基于频道',
      memory: '基于记忆'
    },
    channelModeInfo: '机器人会读取频道内最近的聊天记录作为上下文。',
    memoryModeInfo: '机器人只会记住与它相关的对话（被@、回复、包含关键词）。',
    noneModeInfo: '机器人不会读取任何历史消息，每次对话都是独立的。',
    historyLimit: '历史消息数量',
    messages: '条消息',
    charLimit: 'Token 限制',
    charLimitPlaceholder: '输入最大 token 数'
  },
  scopedPrompts: {
    enabled: '启用',
    mode: {
      title: '模式',
      override: '覆盖',
      append: '追加'
    },
    remove: '删除',
    channels: {
      title: '频道特定指令',
      info: '为特定频道设置机器人的身份或场景。覆盖模式会完全替换机器人的人设，追加模式会在原有基础上添加情境信息。',
      id: '频道 ID',
      idPlaceholder: '输入频道 ID',
      prompt: '指令内容',
      overridePlaceholder: '在这个频道中，机器人将完全扮演这个角色...',
      appendPlaceholder: '描述这个频道的场景或氛围...',
      add: '添加频道指令'
    },
    guilds: {
      title: '服务器特定指令',
      info: '为整个服务器设置机器人的身份或场景。优先级低于频道指令。',
      id: '服务器 ID',
      idPlaceholder: '输入服务器 ID',
      prompt: '指令内容',
      overridePlaceholder: '在这个服务器中，机器人的默认身份是...',
      appendPlaceholder: '这个服务器的背景设定或特殊规则...',
      add: '添加服务器指令'
    }
  },
  roleConfig: {
    title: '基于身份组的配置',
    info: '为不同身份组的用户设置专属的机器人人设和使用限制。',
    roleId: '身份组 ID',
    roleTitle: '显示名称',
    rolePrompt: '专属人设提示词',
    enableMsgLimit: '启用消息限制',
    enableTokenLimit: '启用 Token 限制',
    totalQuota: '总额度',
    minutes: '分钟',
    outputBudget: '输出预算',
    previewTitle: '额度查询预览',
    previewHeader: '额度状态',
    msgLimit: '消息额度',
    tokenLimit: 'Token 额度',
    disabled: '未启用',
    displayColor: '显示颜色',
    add: '添加身份组配置',
    remove: '删除'
  },
  userPortrait: {
    title: '用户肖像',
    info: '定义特定用户在机器人眼中的身份。这是最高优先级的上下文，会始终被机器人考虑。',
    userId: '用户 ID',
    customNicknamePlaceholder: '自定义昵称（可选）',
    personaPrompt: '描述这个用户的身份、特征或与机器人的关系',
    add: '添加用户肖像',
    triggerKeywordsPlaceholder: '触发关键词 (用英文逗号 , 分隔)'
  },
  knowledgeSource: {
    title: "知识源模式",
    modeSelection: "模式选择",
    modes: {
        static: {
            title: "静态肖像模式",
            description: "AI将结合使用您手动配置的“用户肖像”和它自己学习的“世界书”。此模式稳定可控，适合需要固定核心人设的场景。"
        },
        dynamic: {
            title: "动态学习模式",
            description: "警告：AI将完全忽略“用户肖像”配置，并获得世界书的完整管理权限（增、删、改）。它将从对话中自主学习一切。此模式高度自动化，但有AI犯错的风险。"
        }
    },
    migration: {
      toDynamicButton: "迁移用户肖像到世界书",
      toDynamicInfo: "点击此按钮，会将您在下方“用户肖像”中配置的所有数据，转换为“世界书”中的结构化条目。此操作不会删除原有的用户肖像。",
      confirmToDynamic: "您确定要将所有用户肖像迁移到世界书吗？这不会删除您现有的用户肖像配置。",
      toStaticButton: "压平世界书画像以兼容静态模式",
      toStaticInfo: "点击此按钮，会将世界书中所有结构化的画像条目“压平”为纯文本格式，以便在静态模式下使用。此操作不可逆。",
      confirmToStatic: "您确定要将所有结构化画像“压平”为纯文本格式吗？此操作不可轻易撤销。",
      migrating: "迁移中...",
      error: "迁移失败"
    }
  },
  pluginManager: {
    title: '插件管理器',
    info: '创建可通过命令或关键词触发的自定义工具。支持调用外部API并可选择性地通过LLM处理结果。',
    name: '插件名称',
    enabled: '启用',
    triggerType: '触发类型',
    triggerTypes: {
      command: '命令触发',
      keyword: '关键词触发'
    },
    triggers: '触发词',
    triggersPlaceholder: '用逗号分隔多个触发词',
    actionType: '动作类型',
    actionTypes: {
      http_request: 'HTTP请求 (直接输出)',
      llm_augmented_tool: 'LLM增强工具'
    },
    injectionMode: '注入模式',
    injectionModes: {
      override: '覆盖响应',
      append: '追加到上下文'
    },
    injectionInfo: '覆盖模式会直接发送LLM的响应；追加模式会将API结果作为额外信息提供给机器人的主逻辑。',
    httpRequest: 'HTTP 请求配置',
    url: 'URL',
    urlPlaceholder: 'https://api.example.com/endpoint',
    method: '请求方法',
    headers: '请求头 (JSON)',
    body: '请求体模板 (JSON)',
    llmPrompt: 'LLM 提示词模板',
    templateInfo: '可用变量: {user_input} = 用户输入, {api_result} = API返回结果',
    allowInternalRequests: '允许访问内网',
    allowInternalWarning: '警告：启用此项可能导致安全风险(SSRF)，仅用于信任的API。',
    add: '添加插件'
  },
  customParams: {
    title: '自定义参数',
    paramName: '参数名称',
    paramValue: '参数值',
    types: {
      text: '文本',
      number: '数字',
      boolean: '布尔值',
      json: 'JSON'
    },
    add: '添加参数',
    remove: '删除'
  },
  sessionManagement: {
    title: '会话管理',
    info: '清除特定频道的对话记忆。机器人将忘记该频道在此时间点之前的所有对话。',
    channelIdPlaceholder: '输入频道 ID',
    clearButton: '清除记忆',
    clearing: '正在清除...',
    clearSuccess: '记忆清除成功',
    clearFailed: '清除失败：',
    errorNoId: '请输入频道 ID'
  },
  uiSettings: {
    title: '界面设置',
    font: {
      loadButton: '加载自定义字体',
      resetButton: '重置为默认字体',
      currentFont: '当前字体: {fontName}',
      defaultFont: '使用系统默认字体',
      loadError: '字体文件加载失败',
      localStorageError: '无法保存字体到本地存储',
      resetSuccess: '字体已重置为默认',
      loadSuccess: '字体加载成功',
      fileTooLarge: '字体文件太大（{size}MB），最大支持 {maxSize}MB',
      storageError: '存储错误',
      localStorageUnavailable: 'localStorage 不可用，请检查浏览器设置',
      quotaExceeded: 'localStorage 空间不足，请清理浏览器数据'
    },
    timezone: {
      title: '时区'
    }
  },
  logViewer: {
    title: '实时日志',
    filterLevel: '过滤级别',
    autoscroll: '自动滚动'
  },
  debugger: {
    title: '调试器',
    info: '模拟机器人的响应生成过程，用于测试和调试配置。',
    userId: '用户 ID',
    userIdPlaceholder: '模拟的用户 ID',
    roleId: '身份组 ID',
    channelId: '频道 ID',
    channelIdPlaceholder: '模拟的频道 ID',
    guildId: '服务器 ID',
    guildIdPlaceholder: '模拟的服务器 ID（可选）',
    message: '消息内容',
    messagePlaceholder: '输入要测试的消息...',
    button: '模拟生成',
    simulating: '模拟中...',
    error: '错误：',
    generatedPrompt: '生成的系统提示词',
    llmResponse: 'LLM 响应',
    errorIncomplete: '请填写所有必填字段'
  },
  usage: {
    title: '使用量统计',
    periods: {
        today: '今日',
        week: '本周',
        month: '本月',
        all: '全部'
    },
    views: {
        user: '用户',
        role: '身份组',
        channel: '频道',
        guild: '服务器'
    },
    loading: '加载中...',
    totalRequests: '总请求数',
    totalTokens: '总Token数',
    estimatedCost: '预估费用',
    breakdown: '详细分析',
    userInfo: '用户信息',
    roleInfo: '身份组信息',
    channelInfo: '频道信息',
    guildInfo: '服务器信息',
    totalUsage: '总使用量',
    totalCost: '总费用',
    requestsShort: '次',
    refresh: '刷新',
    configurePricing: '配置价格',
    pricingConfig: '价格配置',
    pricingInfo: '配置各模型的价格（每百万Token）',
    provider: '供应商',
    modelName: '模型名称',
    modelPlaceholder: '例如: gpt-4o',
    inputPrice: '输入价格',
    outputPrice: '输出价格',
    addModel: '添加模型',
    save: '保存',
    cancel: '取消'
},
"searchSettings": {
    "title": "搜索设置",
    "enable": "启用搜索",
    "apiKey": "API 密钥",
    "apiUrl": "API 地址",
    "triggerMode": {
        "title": "触发模式",
        "command": "指令模式",
        "keyword": "关键词模式"
    },
    "commandLabel": "指令",
    "commandInfo": "用于触发搜索的指令（例如 !search）。",
    "keywordsLabel": "关键词",
    "keywordsInfo": "用于触发搜索的关键词，用逗号分隔。",
    "includeDate": "搜索包含日期",
    "maxResults": "搜索结果个数",
    "compression": "压缩方法",
    "compressionNone": "不压缩",
    "compressionTruncate": "截断",
    "compressionRAG": "RAG",
    "config": {
        "title": "常规设置"
    },
    "blacklist": {
        "title": "黑名单",
        "add": "添加订阅",
        "addPlaceholder": "输入要屏蔽的域名，例如 example.com",
        "name": "名称",
        "empty": "暂无数据",
        "updateNow": "立即更新",
        "deleteSource": "删除订阅源"
    }
 }
};
