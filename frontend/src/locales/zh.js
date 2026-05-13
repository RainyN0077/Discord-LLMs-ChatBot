// src/locales/zh.js
export default {
  title: 'Discord LLM Bot 控制面板',
  tabs: {
    core: '核心设置',
    directives: '身份指令',
    automation: '自动互动',
    advanced: '高级工具'
  },
  buttons: {
    save: '保存配置并重启 Bot',
    saving: '保存中...'
  },
  status: {
    loading: '正在加载配置...',
    saving: '正在保存...',
    saveSuccess: '配置已保存，Bot 已重启',
    saveFailed: '保存失败：{error}',
    loadFailed: '加载配置失败：{error}'
  },
  errors: {
    duplicateId: 'ID "{id}" 已存在，请使用其他 ID'
  },
  globalConfig: {
    title: '全局配置',
    token: 'Discord Bot Token',
    tokenPlaceholder: '输入你的 Discord Bot Token',
    apiKey: 'RESTful API Key',
    apiKeyUnavailable: 'API Key 不可用',
    copy: '复制',
    apiKeyInfo: '这是给外部服务调用插件接口使用的唯一 API Key。请妥善保管，不要泄露。'
  },
  llmProvider: {
    title: 'LLM 提供商',
    select: '选择提供商',
    providers: {
      openai: 'OpenAI',
      google: 'Google Gemini',
      anthropic: 'Anthropic Claude'
    },
    apiKey: 'API Key',
    apiKeyPlaceholder: '输入你的 API Key',
    baseUrl: '基础 URL（可选）',
    baseUrlPlaceholder: '留空使用官方 API，或填写自定义接口地址',
    fetchModels: '获取模型列表',
    loading: '加载中...',
    testConnection: '测试连接',
    testing: '测试中...',
    selectModel: '选择模型',
    noApiKey: '请先输入 API Key',
    modelsLoaded: '模型列表加载成功',
    modelsLoadFailed: '模型列表加载失败：',
    selectModelFirst: '请先选择一个模型',
    testSuccess: '连接测试成功',
    testFailed: '连接测试失败：',
    testError: '测试错误：',
    testResult: '测试结果',
    modelResponded: '模型返回',
    toggleInputMode: '切换输入模式',
    fetchModelsTooltip: '获取或刷新可用模型列表',
    modelListInfo: '已加载 {count} 个可用模型，可切换为手动输入'
  },
  defaultBehavior: {
    title: '默认行为',
    modelName: '模型名称',
    modelPlaceholders: {
      openai: '例如：gpt-4o、gpt-3.5-turbo',
      google: '例如：gemini-1.5-flash、gemini-1.5-pro',
      anthropic: '例如：claude-3-opus-20240229'
    },
    botNickname: 'Bot 昵称',
    botNicknamePlaceholder: '例如：Endless',
    systemPrompt: '系统提示词',
    systemPromptPlaceholder: '定义 Bot 的基础人设和行为规范...',
    blockedResponse: '拦截回复模板',
    blockedResponseInfo: '当内容被过滤时发送的消息。可使用 {reason} 插入拦截原因。',
    triggerKeywords: '触发词',
    triggerKeywordsPlaceholder: '输入关键词，用逗号分隔',
    triggerMatchMode: '触发词匹配模式',
    triggerMatchModes: {
      contains: '包含',
      startsWith: '开头匹配',
      exact: '完全匹配',
      regex: '正则表达式'
    },
    triggerCaseSensitive: '区分大小写',
    responseMode: '响应模式',
    modes: {
      stream: '流式响应（边生成边显示）',
      nonStream: '完整响应（一次性发送）'
    }
  },
  automation: {
    title: '自动互动',
    description: '配置不依赖提及或触发词的被动发言行为。',
    autoInterjectTitle: '定时插话',
    autoInterjectInfo: '频道内每累计 N 条用户消息后，Bot 会读取当前上下文并主动发言一次。',
    autoInterjectEnabled: '启用定时插话',
    autoInterjectInterval: '每 N 条消息发言一次',
    autoInterjectMinLength: '忽略短于以下长度的消息',
    autoInterjectMinLengthHint: '个字符',
    repeatParrotTitle: '复读跟读',
    repeatParrotInfo: '当频道进入复读机状态时，Bot 可以本地直接跟读一次，不调用 LLM API。',
    repeatParrotEnabled: '启用复读跟读',
    repeatParrotThreshold: '连续相同消息达到 N 条后跟读',
    repeatParrotMinLength: '参与复读检测的最短消息长度',
    repeatParrotCaseSensitive: '复读检测区分大小写',
    repeatParrotTrimWhitespace: '比较前去掉首尾空白字符',
    repeatParrotRequireMultipleUsers: '要求连续复读中至少包含两个不同用户'
  },
  contextControl: {
    title: '上下文控制',
    contextMode: '上下文模式',
    modes: {
      none: '无上下文',
      channel: '基于频道',
      memory: '基于记忆'
    },
    channelModeInfo: 'Bot 会读取当前频道最近的聊天记录作为上下文。',
    memoryModeInfo: 'Bot 只会记住与自己相关的对话（被提及、被回复、包含触发词）。',
    noneModeInfo: 'Bot 不会读取任何历史消息，每次对话都是独立的。',
    historyLimit: '历史消息数量',
    messages: '条消息',
    charLimit: 'Token 上限',
    charLimitPlaceholder: '输入最大 Token 数'
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
      title: '频道级指令',
      info: '为特定频道设置 Bot 身份或场景。覆盖模式会完全替换 Bot 人设，追加模式会补充上下文信息。',
      id: '频道 ID',
      idPlaceholder: '输入频道 ID',
      prompt: '指令内容',
      overridePlaceholder: '在这个频道中，Bot 将完全扮演...',
      appendPlaceholder: '描述这个频道的场景、氛围或规则...',
      add: '添加频道指令'
    },
    guilds: {
      title: '服务器级指令',
      info: '为整个服务器设置 Bot 身份或场景，优先级低于频道指令。',
      id: '服务器 ID',
      idPlaceholder: '输入服务器 ID',
      prompt: '指令内容',
      overridePlaceholder: '在这个服务器中，Bot 的默认身份是...',
      appendPlaceholder: '这个服务器的背景设定或特殊规则...',
      add: '添加服务器指令'
    }
  },
  roleConfig: {
    title: '身份组配置',
    info: '为不同身份组的用户设置专属 Bot 人设和使用额度。',
    roleId: '身份组 ID',
    roleTitle: '显示名称',
    rolePrompt: '专属人设提示词',
    enableMsgLimit: '启用消息限制',
    enableTokenLimit: '启用 Token 限制',
    totalQuota: '总额度',
    minutes: '分钟',
    outputBudget: '输出预算',
    previewTitle: '额度显示预览',
    previewHeader: '额度状态',
    msgLimit: '消息额度',
    tokenLimit: 'Token 额度',
    disabled: '未启用',
    displayColor: '显示颜色',
    add: '添加身份组配置',
    remove: '删除'
  },
  userPortrait: {
    title: '用户画像',
    info: '定义特定用户在 Bot 视角中的身份。这是最高优先级上下文，会始终被考虑。',
    userId: '用户 ID',
    customNicknamePlaceholder: '自定义昵称（可选）',
    personaPrompt: '描述这个用户的身份、特点或与 Bot 的关系',
    add: '添加用户画像',
    triggerKeywordsPlaceholder: '触发关键词（逗号分隔）'
  },
  pluginManager: {
    title: '插件管理器',
    info: '创建由命令或关键词触发的自定义工具，支持调用外部 API，并可选通过 LLM 处理结果。',
    name: '插件名称',
    enabled: '启用',
    triggerType: '触发类型',
    triggerTypes: {
      command: '命令触发',
      keyword: '关键词触发'
    },
    triggers: '触发词',
    triggersPlaceholder: '多个触发词请用逗号分隔',
    actionType: '动作类型',
    actionTypes: {
      http_request: 'HTTP 请求（直接输出）',
      llm_augmented_tool: 'LLM 增强工具'
    },
    injectionMode: '注入模式',
    injectionModes: {
      override: '覆盖响应',
      append: '追加到上下文'
    },
    injectionInfo: '覆盖模式会直接返回工具输出；追加模式会把结果作为额外上下文交给 Bot 主逻辑。',
    httpRequest: 'HTTP 请求配置',
    url: 'URL',
    urlPlaceholder: 'https://api.example.com/endpoint',
    method: '请求方法',
    headers: '请求头（JSON）',
    body: '请求体模板（JSON）',
    llmPrompt: 'LLM 提示模板',
    templateInfo: '可用变量：{user_input} = 用户输入，{api_result} = API 返回结果',
    allowInternalRequests: '允许访问内网',
    allowInternalWarning: '警告：启用后可能带来 SSRF 风险，仅建议对可信 API 使用。',
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
    info: '清除指定频道的会话记忆。Bot 将忽略该时间点之前的所有对话。',
    channelIdPlaceholder: '输入频道 ID',
    clearButton: '清除记忆',
    clearing: '清除中...',
    clearSuccess: '记忆清除成功',
    clearFailed: '清除失败：',
    errorNoId: '请输入频道 ID'
  },
  uiSettings: {
    title: '界面设置',
    font: {
      loadButton: '加载自定义字体',
      resetButton: '恢复默认字体',
      currentFont: '当前字体：{fontName}',
      defaultFont: '使用系统默认字体',
      loadError: '字体文件加载失败',
      localStorageError: '无法将字体保存到本地存储',
      resetSuccess: '字体已恢复默认',
      loadSuccess: '字体加载成功',
      fileTooLarge: '字体文件过大（{size}MB），最大支持 {maxSize}MB',
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
    autoscroll: '自动滚动',
    maxLines: '最大行数',
    limitNotice: '当前仅显示最近 {limit} 行，已隐藏更早的 {hidden} 行。'
  },
  debugger: {
    title: '调试器',
    info: '模拟 Bot 的响应生成流程，用于测试和调试配置。',
    userId: '用户 ID',
    userIdPlaceholder: '模拟用户 ID',
    roleId: '身份组 ID',
    channelId: '频道 ID',
    channelIdPlaceholder: '模拟频道 ID',
    guildId: '服务器 ID',
    guildIdPlaceholder: '模拟服务器 ID（可选）',
    message: '消息内容',
    messagePlaceholder: '输入测试消息...',
    button: '开始模拟',
    simulating: '模拟中...',
    error: '错误：',
    generatedPrompt: '生成的系统提示词',
    llmResponse: 'LLM 响应',
    errorIncomplete: '请填写所有必填项'
  },
  usage: {
    title: '使用统计',
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
    totalTokens: '总 Token 数',
    estimatedCost: '预估费用',
    breakdown: '明细',
    userInfo: '用户信息',
    roleInfo: '身份组信息',
    channelInfo: '频道信息',
    guildInfo: '服务器信息',
    totalUsage: '总用量',
    totalCost: '总费用',
    requestsShort: '次',
    refresh: '刷新',
    configurePricing: '配置价格',
    pricingConfig: '价格配置',
    pricingInfo: '配置各模型价格（按每百万 Token）',
    provider: '提供商',
    modelName: '模型名称',
    modelPlaceholder: '例如：gpt-4o',
    inputPrice: '输入价格',
    outputPrice: '输出价格',
    addModel: '添加模型',
    save: '保存',
    cancel: '取消'
  },
  searchSettings: {
    title: '搜索设置',
    enable: '启用搜索',
    apiKey: 'API Key',
    apiUrl: 'API 地址',
    triggerMode: {
      title: '触发模式',
      command: '命令',
      keyword: '关键词'
    },
    commandLabel: '命令',
    commandInfo: '用于触发搜索的命令，例如 `!search`。',
    keywordsLabel: '关键词',
    keywordsInfo: '用于触发搜索的关键词，使用逗号分隔。',
    includeDate: '搜索结果包含日期',
    maxResults: '最大搜索结果数',
    compression: '压缩方式',
    compressionNone: '不压缩',
    compressionTruncate: '截断',
    compressionRAG: 'RAG',
    config: {
      title: '基础配置'
    },
    blacklist: {
      title: '黑名单',
      add: '添加订阅',
      addPlaceholder: '输入要屏蔽的域名，例如 example.com',
      name: '名称',
      empty: '暂无数据',
      updateNow: '立即更新',
      deleteSource: '删除来源'
    }
  },
  knowledge: {
    title: '知识库',
    tabs: {
      worldBook: '世界书',
      memory: '记忆库',
      settings: '查重设置'
    },
    settings: {
      title: '查重设置',
      memoryDedupThreshold: '记忆库查重阈值',
      worldBookDedupThreshold: '世界书查重阈值',
      dedupDescription: '设置查重阈值。0% 表示关闭查重，100% 只阻止完全相同的内容。推荐值为 80-90%。',
      save: '保存查重设置'
    },
    confirmDeleteMemory: '确定要删除这条记忆吗？',
    confirmDeleteWorldBook: '确定要删除这个世界书条目吗？',
    error: {
      loadMemory: '加载记忆库失败',
      addMemory: '添加记忆失败',
      deleteMemory: '删除记忆失败',
      updateMemory: '更新记忆失败',
      loadWorldBook: '加载世界书失败',
      emptyFields: '关键词和内容不能为空',
      saveWorldBook: '保存世界书条目失败',
      deleteWorldBook: '删除世界书条目失败'
    },
    memory: {
      title: '记忆库',
      addPlaceholder: '添加一条新的记忆...',
      add: '添加记忆',
      edit: '编辑',
      save: '保存',
      cancel: '取消',
      delete: '删除',
      by: '记录者',
      at: '时间',
      source: '来源',
      contentLabel: '内容',
      userIdLabel: '用户 ID',
      timestampLabel: '时间戳（可选，按你的本地时间）',
      byPlaceholder: '例如：WebUI 或用户名',
      userIdPlaceholder: '例如：1234567890（可选）',
      searchPlaceholder: '按记录者搜索...',
      noResults: '没有找到匹配的记录。'
    },
    worldBook: {
      title: '世界书',
      keywordsLabel: '关键词',
      keywordsHint: '使用逗号分隔',
      keywordsPlaceholder: '例如：世界观、主角、地点...',
      contentLabel: '内容',
      contentPlaceholder: '详细描述这条设定内容...',
      addTitle: '添加新条目',
      editTitle: '编辑条目',
      add: '添加条目',
      save: '保存修改',
      edit: '编辑',
      delete: '删除',
      cancelEdit: '取消编辑',
      linkedUserLabel: '关联用户',
      noLinkedUser: '无'
    },
    searchPlaceholder: '按关键词搜索...',
    noResults: '没有找到匹配的条目。'
  }
};
