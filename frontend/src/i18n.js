// src/i18n.js
import { writable, derived } from 'svelte/store';

// --- Dynamic locale loaders (only the active language is loaded) ---
const localeLoaders = {
    en: () => import('./locales/en.js'),
    zh: () => import('./locales/zh.js'),
};
const _translations = {};

async function loadLocale(langCode) {
    if (_translations[langCode]) return;
    if (localeLoaders[langCode]) {
        try {
            const mod = await localeLoaders[langCode]();
            const raw = mod.default;
            _translations[langCode] = langCode === 'zh'
                ? mergeDeep(raw, zhOverrides)
                : raw;
        } catch (err) {
            console.error(`Failed to load locale "${langCode}":`, err);
        }
    }
}

function mergeDeep(base, extra) {
    if (typeof base !== 'object' || base === null) return extra;
    if (typeof extra !== 'object' || extra === null) return base;
    const out = { ...base };
    for (const [k, v] of Object.entries(extra)) {
        if (typeof v === 'object' && v !== null && typeof out[k] === 'object' && out[k] !== null) {
            out[k] = mergeDeep(out[k], v);
        } else {
            out[k] = v;
        }
    }
    return out;
}

const zhOverrides = {
    status: {
        waitingBackend: '后端启动中，正在等待连接...（{attempt}/{max}）',
    },
    promptStudio: {
        title: '机器人行为配置中心',
        description: '在这里，您可以统一管理机器人的各项行为配置，从全局指令到特定场景的响应。',
        tabs: {
            global: '全局模板',
            scopes: '范围覆盖',
            plugins: '插件集成',
            roles: '角色策略',
        },
        nav: {
            messageContext: '消息与上下文',
            knowledgeInjection: '知识与工具注入',
            systemPromptStructure: '系统提示词结构',
            coreInstructions: '核心操作指令',
            messageFormat: '用户消息格式',
            imageNote: '图片注释',
            replyContext: '回复上下文',
            deletedReplyContext: '已删除的回复上下文',
            userRequestBlock: '用户请求块',
            toolContext: '工具输出',
            memoryContext: '长期记忆',
            worldbookContext: '世界设定',
            foundationHeader: '基础规则标题',
            personaHeader: '当前人设标题',
            situationHeader: '情景上下文标题',
            participantsHeader: '参与者肖像标题',
            securityHeader: '安全与操作指令标题',
            operationalInstructions: '核心操作指令列表',
        },
        editor: {
            coreInstructions: '核心操作指令',
            coreInstructionsDesc: '这些是指导机器人行为的核心规则，将按顺序注入到系统提示词中。',
            addInstruction: '添加新指令',
            removeInstruction: '移除',
            availablePlaceholders: '可用占位符',
            instructionPlaceholder: '输入一条指令',
        },
        simulator: {
            title: '场景模拟器',
            userMessage: '用户消息',
            userRoles: '用户角色 (按住Ctrl多选)',
            imageCount: '图片数量',
            isReply: '是回复消息',
            replyContent: '回复的内容',
            manualRefresh: '手动更新预览',
            generating: '正在生成...',
            backendPreview: '后端实时预览',
            loading: '(加载中...)',
            systemPromptPreview: '系统提示词预览',
            userRequestPreview: '用户请求预览',
            buildLog: '构建日志',
            previewFailed: '预览生成失败: {error}',
        },
        preset: {
            selectPlaceholder: '选择预设',
            load: '加载',
            saveAs: '另存为...',
            import: '导入',
            delete: '删除',
            loadFailed: '加载预设失败: {error}',
            loading: '正在加载预设: {name}...',
            loadSuccess: '预设 "{name}" 加载成功。',
            savePrompt: '请输入新预设的名称：',
            saving: '正在保存预设: {name}...',
            saveSuccess: '预设 "{name}" 保存成功。',
            saveFailed: '保存预设失败: {error}',
            deleteConfirm: '您确定要删除预设 "{name}" 吗？此操作无法撤销。',
            deleting: '正在删除预设: {name}...',
            deleteSuccess: '预设 "{name}" 已删除。',
            deleteFailed: '删除预设失败: {error}',
            importFailed: '导入失败: {error}',
            importSuccess: '文件 "{name}" 已成功导入。您可以点击"另存为"来保存它。',
            invalidFormat: '无效的预设文件格式。缺少关键字段: {keys}',
        },
        save: '保存所有设置并重启',
        saving: '正在保存...',
        reset: '撤销本次修改',
        loading: '正在加载...',
        scopeServerOverride: '服务器 (Guild) 覆盖',
        scopeChannelOverride: '频道 (Channel) 覆盖',
    },
    contextControl: {
        unlimitedContextLength: '不限制上下文长度',
        unlimitedHistoryMessages: '不限制历史消息数量',
    },
    appNav: {
        modelSettings: '模型设置',
        controlPanel: '控制面板',
        themeDark: '切换到深色模式',
        themeLight: '切换到浅色模式',
        appearance: '外观',
    },
    modelProviders: {
        openai: 'OpenAI',
        grok: 'Grok (xAI)',
        openaiCompatible: 'OpenAI 兼容',
        gemini: 'Gemini',
        anthropic: 'Anthropic',
        anthropicCompatible: 'Anthropic 兼容',
        deepseek: 'DeepSeek (深度求索)',
        siliconflow: 'SiliconFlow (硅基流动)',
        volcengine: 'Volcano Ark (火山方舟)',
        dashscope: 'Alibaba Bailian (阿里百炼)',
        moonshot: 'Moonshot (月之暗面)',
        zhipu: 'Zhipu GLM (智谱)',
        stepfun: 'StepFun (阶跃星辰)',
    },
    llmProvider: {
        providers: {
            grok: 'Grok (xAI)',
            deepseek: 'DeepSeek (深度求索)',
            siliconflow: 'SiliconFlow (硅基流动)',
            volcengine: 'Volcano Ark (火山方舟)',
            dashscope: 'Alibaba Bailian (阿里百炼)',
            moonshot: 'Moonshot (月之暗面)',
            zhipu: 'Zhipu GLM (智谱)',
            stepfun: 'StepFun (阶跃星辰)',
        },
        multimodalLabel: '当前主模型支持多模态',
        multimodalInfo: '开启后，主模型会直接读取图片；关闭后，图片会先交给单独的 OCR 模型转成文本，再送给主模型。',
        ocrHiddenHint: '由于主模型会直接读取图片，OCR 设置已隐藏。',
    },
    defaultBehavior: {
        modelPlaceholders: {
            grok: '例如：grok-4、grok-3-mini',
            deepseek: '例如：deepseek-v4-pro、deepseek-v4-flash',
            siliconflow: '例如：deepseek-ai/DeepSeek-V3',
            volcengine: '例如：ep-20250101000000-xxxxx',
            dashscope: '例如：qwen-plus、qwen-max',
            moonshot: '例如：moonshot-v1-8k、moonshot-v1-32k',
            zhipu: '例如：glm-4-plus、glm-4-flash',
            stepfun: '例如：step-2-16k、step-1-8k',
        },
    },
    embeddingSettings: {
        title: 'Embedding 设置',
        provider: 'Embedding 提供方',
        apiKey: 'Embedding API Key',
        baseUrl: 'Embedding 接口地址',
        port: 'Embedding 端口',
        modelName: 'Embedding 模型',
        dimensions: '向量维度',
    },
    rerankSettings: {
        title: 'Rerank 设置',
        provider: 'Rerank 提供方',
        apiKey: 'Rerank API Key',
        baseUrl: 'Rerank 接口地址',
        port: 'Rerank 端口',
        modelName: 'Rerank 模型',
    },
    ocrSettings: {
        title: 'OCR 模型设置',
        info: '仅在主 LLM 不支持多模态时启用。图片会先被转写为 <ocr_output> 文本块，再交给文本主模型。',
        provider: 'OCR 提供方',
        apiKey: 'OCR API Key',
        baseUrl: 'OCR 接口地址',
        port: 'OCR 端口',
        modelName: 'OCR 模型',
        promptTemplate: 'OCR 提示词模板',
        promptTemplatePlaceholder: '控制 OCR 模型如何提取图片中的可见文字和关键视觉信息。',
        maxOutputChars: 'OCR 输出最大字符数',
        maxOutputCharsInfo: '限制注入主模型前的 OCR 文本长度，避免提示词膨胀。',
        timeoutSeconds: 'OCR 超时时长（秒）',
        timeoutMode: '超时设置',
        timeoutEnabledOption: '启用超时',
        timeoutDisabledOption: '不设置超时时长',
        timeoutInfo: '测试连接和实际 OCR 预处理共用这份超时设置；关闭后会一直等待直到 OCR 返回。',
    },
    personaHub: {
        title: '身份管理中心',
        sections: {
            users: '用户',
            channels: '频道',
            guilds: '服务器',
            roles: '身份组',
        },
        discoveredUsersTitle: '已读取用户',
        allChannels: '全部频道',
        channelFallback: '频道',
        searchPlaceholder: '按显示名、用户名或 ID 搜索',
        refresh: '刷新',
        refreshing: '刷新中...',
        syncPortraits: '从后端重新同步肖像',
        syncingPortraits: '同步中...',
        syncPortraitsSuccess: '已从后端重新同步用户肖像。',
        syncPortraitsFailed: '重新同步用户肖像失败：{error}',
        noDiscoveredUsers: '当前范围内暂无可管理用户。',
        addPortrait: '新增肖像',
        editPortrait: '编辑肖像',
        loadFailed: '加载已读取用户失败：{error}',
        helpLink: 'Help',
        helpTitle: '页面说明',
        helpBody: '身份管理中心用于集中维护身份相关配置。你可以快速筛选频道内已读取用户并编辑其用户肖像，也可以统一管理频道/服务器指令和身份组规则。',
        commonIssuesTitle: '常见问题',
        commonIssue1: '看不到已读取用户：当前范围内尚未产生可用 usage 元数据。',
        commonIssue2: '能看到用户但 @ 不正确：昵称应仅作称呼风格，不应替代真实 mention。',
        commonIssue3: '频道列表为空：最近可能没有被记录的交互数据。',
        commonIssue4: '改了肖像但效果不明显：可能尚未保存配置或后端未重载。',
        commonIssue5: '搜索不到目标用户：优先尝试直接输入完整用户 ID。',
        quickCheckTitle: '快速排查',
        quickCheck1: '点击本页刷新按钮，先拉取最新元数据。',
        quickCheck2: '将频道筛选切到“全部频道”，确认是否全局可见。',
        quickCheck3: '检查用户肖像中的 ID 是否正确且没有重复。',
        quickCheck4: '保存配置后确认后端已成功重启。',
        quickCheck5: '在 Discord 发一条测试消息，触发新一轮 usage 记录。',
        quickCheck6: '若仍异常，查看日志中 usage tracker 或 persona 解析错误。',
        helpClose: '关闭',
    },
    directChat: {
        title: 'LLM 直接对话',
        provider: '服务商',
        model: '模型',
        chatTab: '对话',
        captureTab: '截取',
        includeSystemPrompt: '附带当前系统提示词',
        debugMode: 'Debug 模式（模拟 Discord）',
        debugHint: 'Debug 模式会按 Discord 链路构造系统提示和输入修饰，并展示原始模型输出。',
        debugUserId: '用户 ID（数字）',
        debugChannelId: '频道 ID（数字）',
        debugGuildId: '服务器 ID（可选）',
        debugRoleId: '角色配置 ID（可选）',
        formattedInput: '发送给模型的输入修饰',
        captureRefresh: '刷新',
        captureLoading: '加载中...',
        captureChannelFilter: '按频道 ID 过滤（可选）',
        captureEmpty: '还没有截取到 Discord 触发对话。',
        captureSelectHint: '从左侧选择一条截取记录。',
        captureUseInput: '使用原始输入',
        captureRawInput: '触发原始输入（未修饰）',
        captureFormattedInput: '发送给模型的修饰输入',
        capturePluginOutputs: '插件注入上下文',
        captureIntermediateOutputs: '中间阶段模型输出',
        captureRawOutput: '模型原始输出（未修饰）',
        captureCleanedOutput: 'Bot 清洗后的输出',
        captureSystemPrompt: '本次系统提示词',
        captureLlmMessages: '完整 LLM 消息载荷',
        captureLoadFailed: '加载截取列表失败：',
        captureDetailFailed: '加载截取详情失败：',
        sanitizeTitle: 'DSML/思维链清洗测试',
        sanitizeInputPlaceholder: '粘贴模型原始输出文本...',
        sanitizeRun: '执行清洗',
        sanitizing: '清洗中...',
        sanitizeOutput: '清洗后输出',
        sanitizeFailed: '清洗失败：',
        attachments: '附件',
        attachFiles: '添加文件',
        selectedFiles: '已选择 {count} 个文件',
        removeFile: '移除',
        debugOcrOutput: '发送给模型的 OCR 输出',
        debugAttachmentContext: '发送给模型的附件文本上下文',
        debugMultimodalImages: '图片处理方式',
        debugMultimodalImagesUsed: '图片已直接传给多模态模型。',
        clear: '清空对话',
        empty: '现在可以不借助 Discord，直接和当前配置的 LLM 对话。',
        you: '你',
        assistant: '助手',
        inputPlaceholder: '输入消息...（Enter 发送，Shift+Enter 换行）',
        send: '发送',
        sending: '发送中...',
        sendFailed: '发送失败：',
        usage: 'Token 用量',
    },
    usage: {
        periodLabel: '周期',
    },
    searchSettings: {
        getApiKey: '获取 Tavily API Key',
        maxResults: '最大搜索结果数',
        requireMainTrigger: '需要同时命中 Bot 触发',
        rewriteQueryWithLlm: '搜索前先用 LLM 整理查询词',
        usageGuide: {
            link: '触发说明',
            title: '搜索触发使用说明',
            intro: '搜索功能支持命令触发和关键词触发。请二选一配置并明确规则。',
            commandTitle: '命令触发',
            command1: '将触发模式设为命令，然后设置命令词，如 !search。',
            command2: '使用示例：!search 今天的 AI 新闻',
            command3: '命令必须出现在消息开头。',
            keywordTitle: '关键词触发',
            keyword1: '将触发模式设为关键词，并填写逗号分隔的关键词列表。',
            keyword2: '消息中出现任意关键词就会触发搜索。',
            keyword3: '关键词模式下会把整条消息作为搜索查询。',
            troubleshootTitle: '快速排查',
            troubleshoot1: '确认“启用搜索”已开启。',
            troubleshoot2: '检查 Tavily API Key 和 API URL 是否正确。',
            troubleshoot3: '触发模式只能选一种，不要混用。',
            troubleshoot4: '修改后请保存配置并等待 Bot 重启完成。',
            close: '关闭',
        },
    },
    knowledge: {
        tabs: {
            candidates: '记忆候选',
        },
        worldBook: {
            searchPlaceholder: '按关键词搜索...',
            noResults: '未找到匹配的世界书条目。',
        },
        confirmDeleteMemoryCandidate: '确定要删除这条记忆候选吗？',
        error: {
            loadMemoryCandidates: '加载记忆候选失败',
            promoteMemoryCandidate: '提升记忆候选失败',
            deleteMemoryCandidate: '删除记忆候选失败',
        },
        candidates: {
            title: '记忆候选',
            showPromoted: '显示已提升候选',
            refresh: '刷新',
            noResults: '暂无候选记录。',
            seenCount: '出现次数',
            distinctUsers: '用户数',
            lastSeen: '最后出现',
            status: '状态',
            promoted: '已提升',
            staged: '待提升',
            promote: '提升',
            delete: '删除',
        },
    },
    logPanel: {
        logs: '日志',
        auto: '自动',
        lines: '行',
        showLast: '显示最近 {limit} 行',
        hiddenCount: '已隐藏 {hidden} 行',
    },
    modelSettings: {
        backToConfig: '返回配置面板',
        saveAndRestart: '保存并重启 Bot',
        goToModelSettings: 'LLM 模型配置已移至独立的"模型设置"页面。',
        openSettings: '打开模型设置'
    },
    inferenceParams: {
        title: '推理参数（可选）',
        hint: '留空使用模型默认值。',
        temperature: '温度 (Temperature)',
        maxTokens: '最大令牌数 (Max Tokens)',
        maxTokensHint: '留空使用模型默认值',
        topP: 'Top P',
        topK: 'Top K',
        frequencyPenalty: '频率惩罚 (Frequency Penalty)',
        presencePenalty: '存在惩罚 (Presence Penalty)',
        placeholders: {
            default: '留空使用默认值',
            openai: '留空使用默认值',
            grok: '推荐：0.7',
            google: '推荐：0.9',
            anthropic: '推荐：0.7',
            deepseek: '推荐：0.7',
            siliconflow: '推荐：0.7',
            volcengine: '推荐：0.7',
            dashscope: '推荐：0.7',
            moonshot: '推荐：0.7',
            zhipu: '推荐：0.8',
            stepfun: '推荐：0.7',
            topP: '0.7 - 1.0',
            topK: '1 - 100',
            frequencyPenalty: '-2.0 - 2.0',
            presencePenalty: '-2.0 - 2.0'
        }
    },
    customHeaders: {
        title: '自定义 HTTP 请求头',
        namePlaceholder: '请求头名称',
        valuePlaceholder: '请求头值',
        add: '添加请求头',
        remove: '删除'
    },
    actionBtn: {
        start: '启动',
        stop: '停止',
        restart: '重启',
        delete: '删除',
    },
    appearance: {
        title: '外观设置',
        uiStyle: 'UI 风格',
        colorScheme: '配色方案',
        animationSettings: '动画设置',
        enablePageTransitions: '启用页面过渡动画',
        customCSS: '自定义 CSS',
        applyCSS: '应用 CSS',
        resetCSS: '重置为默认',
        resetAll: '恢复全部默认',
        cssPlaceholder: '/* 在此输入自定义 CSS */\n/* 变量参考: --primary-color, --bg-color, --card-bg, --text-color 等 */\n/* 查看 README.md 获取完整 CSS 变量列表 */',
    },
};

const getInitialLang = () => {
    if (typeof window === 'undefined') return 'zh';
    const browserLang = navigator.language.split('-')[0];
    return localeLoaders[browserLang] ? browserLang : 'zh';
};

const storedLang = typeof window !== 'undefined' ? localStorage.getItem('lang') : null;
export const lang = writable(storedLang || getInitialLang());

// Preload the default locale immediately so translations are ready ASAP
const initialLang = storedLang || getInitialLang();
if (localeLoaders[initialLang]) {
    loadLocale(initialLang).then(() => {
        // Re-trigger reactivity once translations are loaded
        lang.update(v => v);
    });
}

lang.subscribe((value) => {
    if (typeof window !== 'undefined') {
        localStorage.setItem('lang', value);
    }
});

let _pendingLang = null;

export function setLang(newLang) {
    if (!localeLoaders[newLang]) return;
    _pendingLang = newLang;
    loadLocale(newLang).then(() => {
        if (_pendingLang === newLang) {
            lang.set(newLang);
        }
    });
}

function translate(currentLang, key, vars = {}) {
    if (!currentLang || !key) {
        return '';
    }

    const readKey = (langCode) => {
        let value = _translations[langCode];
        const keys = key.split('.');
        for (const k of keys) {
            if (value && typeof value === 'object' && k in value) {
                value = value[k];
            } else {
                return null;
            }
        }
        return value;
    };

    let text = readKey(currentLang);
    if (text == null && currentLang !== 'en') {
        text = readKey('en');
    }
    if (text == null) {
        return key;
    }

    if (typeof text !== 'string') {
        return key;
    }

    return text.replace(/\{(\w+)\}/g, (match, placeholder) => {
        return vars[placeholder] !== undefined ? vars[placeholder] : match;
    });
}

export const t = derived(lang, ($lang) => (key, vars) => translate($lang, key, vars));

export const get = (key, vars) => {
    let currentLang;
    lang.subscribe((value) => {
        currentLang = value;
    })();
    return translate(currentLang, key, vars);
};

export { get as t_get };
