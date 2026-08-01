# AGENTS.md — AI 开发指南

> 本文档面向 AI 编码助手（Claude Code / Cursor / Copilot 等），提供项目开发的完整上下文、约定和最佳实践。

---

## 1. 项目概述

**Discord-LLMs-ChatBot** 是基于 NoneBot2 的多 Bot LLM 聊天机器人，支持 12 家 LLM 提供商，配备 Web 控制面板、知识引擎（SQLite FTS5 + embedding）、OCR 图片识别、插件系统和多 Bot 管理。

**核心能力**：
- 多提供商 LLM（OpenAI / Anthropic / Google / xAI / DeepSeek 等 12 家）
- 知识引擎（世界书关键词注入 + 自动记忆摄取 + FTS5 全文搜索 + 向量语义召回）
- 多 Bot 管理（单一面板管理多个 Bot，独立配置/人设/知识库/配额）
- Web 控制面板（Svelte 4 实时仪表盘）
- 插件系统（可扩展插件框架 + 工具调用）

---

## 1.1 子代理（Sub-Agent）使用要求

**强制规则**：所有非平凡任务（多文件修改、跨模块变更、复杂逻辑实现）**必须**通过 `Task()` 委托给专业子代理执行。禁止在主会话中直接编写复杂代码。

**可用子代理类型**：
- `requirement-triage` — 需求分类与复杂度评估
- `context-engineer` — 上下文工程（代码库探索、历史分析）
- `solutions-architect` — 方案设计与架构文档
- `implementer` — 代码实现（原子化切片）
- `integrator` — 跨文件集成验证
- `qa-reviewer` — 质量审查
- `security-reviewer` — 安全审查
- `fidelity-reviewer` — 精确性审查
- `performance-reviewer` — 性能审查
- `remediator` — 修复审查发现
- `delivery-manager` — 交付验证
- `repo-explorer` — 代码库快速探索

**流水线阶段**：每个复杂任务必须按顺序执行以下阶段，每个阶段委托给对应子代理：
1. Stage 0 — `requirement-triage`（分类复杂度）
2. Stage 1 — `context-engineer`（上下文简报）
3. Stage 2 — `solutions-architect`（设计文档）
4. Stage 3 — `implementer`（原子化实现）
5. Stage 4 — `integrator`（跨文件集成）
6. Stage 5 — `qa-reviewer` + 专项审查（质量/安全/性能）
7. Stage 6 — `remediator`（修复发现）
8. Stage 7 — `delivery-manager`（交付确认）

---

## 1.2 项目推荐子代理与技能

根据项目技术栈和架构，以下子代理和技能特别适用于本项目开发：

### 推荐子代理（按使用频率排序）

| 子代理 | 适用场景 |
|--------|----------|
| `python-development/python-pro` | Python 3.12+ 开发、async/await 优化、Pydantic/FastAPI 模式 |
| `api-scaffolding/fastapi-pro` | FastAPI 路由、依赖注入、中间件、WebSocket 开发 |
| `api-scaffolding/backend-architect` | 后端架构设计、微服务拆分、Port/Adapter 模式 |
| `backend-development/tdd-orchestrator` | TDD 红绿重构、测试策略、CI 集成 |
| `code-review-ai/architect-review` | 架构审查、设计模式评估、依赖方向检查 |
| `code-documentation/code-reviewer` | 代码质量审查、安全漏洞、性能热点 |
| `code-refactoring/legacy-modernizer` | 重构、技术债务清理、框架迁移 |
| `debugging-toolkit/debugger` | 错误诊断、测试失败分析、性能问题 |
| `database-design/database-architect__database-design` | PostgreSQL/SQLite  schema 设计、索引策略 |
| `database-design/sql-pro` | SQL 查询优化、FTS5 全文搜索、BM25 排序 |
| `async-python-patterns` | asyncio 并发模式、事件循环优化、异步生成器 |
| `architecture-patterns` | 六边形架构、Clean Architecture、DDD |
| `error-handling-patterns` | 异常传播、Result 类型、优雅降级 |
| `python-testing-patterns` | pytest 测试、fixture、mock、async 测试 |
| `security-reviewer` | 认证授权、输入验证、API 密钥管理 |
| `performance-reviewer` | 并发瓶颈、内存泄漏、缓存策略 |

### 推荐技能（按使用频率排序）

| 技能 | 适用场景 |
|------|----------|
| `fastapi-templates` | 创建 FastAPI 项目结构、路由模板 |
| `async-python-patterns` | asyncio 最佳实践、并发模式 |
| `architecture-patterns` | 六边形架构、Clean Architecture 实现 |
| `python-testing-patterns` | pytest 测试策略、覆盖率配置 |
| `error-handling-patterns` | 跨语言错误处理模式 |
| `database-migration` | 数据库迁移、schema 变更 |
| `sql-optimization-patterns` | SQL 索引、EXPLAIN 分析 |
| `debugging-strategies` | 系统化调试、根因分析 |
| `code-review-excellence` | 代码审查最佳实践 |
| `api-design-principles` | REST/GraphQL API 设计 |
| `rag-implementation` | 知识引擎、向量检索、embedding |
| `auth-implementation-patterns` | JWT、OAuth2、会话管理 |
| `secrets-management` | 密钥轮换、加密管理 |
| `dependency-upgrade` | 依赖版本升级、兼容性分析 |
| `uv-package-manager` | Python 包管理、虚拟环境 |

---

## 1.3 Feature Flag 系统

项目使用 Feature Flag 控制架构迁移步骤的开闭。所有 Flag 默认 `False`（旧代码路径），逐个 Wave 切换为 `True`。

**配置文件**：`backend/app/feature_flags.py`

**环境变量覆盖**：`FEATURE_<FLAG_NAME>=1`

| Flag | 默认值 | 说明 |
|------|--------|------|
| `USE_BOT_RUNTIME_ABSTRACTION` | False | BotRuntime 抽象层（Wave 1） |
| `USE_PLATFORM_MESSAGE_MODEL` | False | PlatformMessage 模型（Wave 1） |
| `USE_PLATFORM_ADAPTER` | False | PlatformAdapter 接口（Wave 1） |
| `USE_ENHANCED_PLUGIN_REGISTRY` | False | PluginRegistry 迁移（Wave 3） |
| `USE_NEW_PIPELINE_SEND` | False | 新消息发送路径（Wave 2） |
| `USE_NEW_CONTEXT_BUILDER` | False | 新上下文构建器（Wave 2） |
| `USE_MESSAGE_BUS` | False | MessageBus 事件路由（Wave 2） |
| `USE_PROVIDER_POOL` | False | ProviderPool 集成（Wave 3） |
| `USE_NEW_MAIN_PIPELINE` | False | Wave 4 总开关 |

**启动时捕获**：`capture_flags()` 在启动时捕获所有 Flag 值，防止运行时切换导致状态不一致。

---

## 2. 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| Bot 框架 | NoneBot2 + Discord/QQ adapter | 2.5.0 |
| API 服务器 | FastAPI + Uvicorn | 0.138.1 / 0.49.0 |
| 前端 | Svelte 4 + Vite | — |
| 数据库 | SQLite FTS5 | 3.x |
| 缓存/锁 | Redis | 5.3.1 |
| LLM SDK | openai / google-genai / anthropic / xai-sdk | — |
| 数据验证 | Pydantic | 2.13.4 |
| 加密 | cryptography (Fernet) | 49.0.0 |
| HTTP 客户端 | aiohttp | 3.14.1 |
| 验证 | Python | 3.11+ |

---

## 3. 目录结构

```
Discord-LLMs-ChatBot/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口 + lifespan
│   │   ├── app_context.py           # 应用上下文（单例）
│   │   ├── state.py                 # 全局状态代理
│   │   ├── bot_manager.py           # Bot 管理器
│   │   ├── bot_instance.py          # 单个 Bot 实例（状态机）
│   │   ├── config_cache.py          # 配置缓存 + 默认配置
│   │   ├── config_bridge.py         # NoneBot .env 文件生成
│   │   ├── discord_patch.py         # Discord ComponentEmoji 修复
│   │   ├── models.py                # Pydantic 请求/响应模型
│   │   ├── usage_tracker.py         # 用量追踪器
│   │   ├── feature_flags.py         # Feature Flag 配置（迁移开关）
│   │   ├── utils.py                 # 通用工具函数
│   │   ├── paths.py                 # 数据路径配置
│   │   ├── core_logic/              # 核心业务逻辑
│   │   │   ├── knowledge_manager.py     # 知识库管理（recall/ingest）
│   │   │   ├── context_builder.py       # 上下文构建器
│   │   │   ├── interaction_recorder.py  # 交互记录器
│   │   │   ├── persona_manager.py       # 人设管理器
│   │   │   ├── usage_manager.py         # 用量管理器（配额检查）
│   │   │   ├── user_options_manager.py  # 用户选项管理器（黑白名单）
│   │   │   ├── user_validator.py        # 用户验证器
│   │   │   ├── embedding_service.py     # Embedding 服务
│   │   │   ├── rerank_service.py        # 重排序服务
│   │   │   ├── preview_builder.py       # Prompt 预览构建器
│   │   │   └── sqlite_pool.py           # SQLite 连接池
│   │   ├── ports/                   # 六边形架构 - 端口接口（抽象）
│   │   │   ├── bot_runtime.py          # BotRuntime/BotIdentity/MessageSender ABC
│   │   │   ├── platform_message.py     # PlatformMessage/AuthorInfo/ChannelInfo
│   │   │   ├── platform_adapter.py     # PlatformAdapter ABC
│   │   │   ├── message_bus.py          # MessageBus 抽象接口
│   │   │   ├── plugin_base.py          # 统一 PluginBase ABC
│   │   │   ├── plugin_registry.py      # PluginRegistry 注册中心
│   │   │   ├── llm_provider.py         # LLMProvider 接口（ProviderHealth/QuotaInfo）
│   │   │   └── guild_member_resolver.py # GuildMemberResolver 接口
│   │   ├── adapters/                # 六边形架构 - 适配器实现
│   │   │   ├── nonebot_runtime.py     # NoneBotRuntime 适配器
│   │   │   ├── mock_bot_runtime.py    # MockBotRuntime 测试桩
│   │   │   ├── discord_platform_adapter.py # Discord → PlatformMessage 转换
│   │   │   ├── mock_platform_adapter.py    # MockPlatformAdapter 测试桩
│   │   │   ├── plugin_context_adapter.py   # 插件上下文适配器
│   │   │   ├── factory.py             # create_bot_runtime() 工厂
│   │   │   └── message_bus_impl.py    # DefaultMessageBus 实现
│   │   ├── llm_providers/           # LLM 提供商
│   │   │   ├── base.py                  # LLMProvider 抽象基类
│   │   │   ├── factory.py               # LLM 工厂（缓存 + 创建）
│   │   │   ├── openai_provider.py       # OpenAI 提供商
│   │   │   ├── anthropic_provider.py    # Anthropic 提供商
│   │   │   ├── google_provider.py       # Google Gemini 提供商
│   │   │   └── xai_provider.py          # xAI Grok 提供商
│   │   ├── routers/                 # FastAPI 路由
│   │   │   ├── config.py                # 配置 CRUD
│   │   │   ├── bots.py                  # Bot 管理
│   │   │   ├── chat.py                  # WebUI 直接对话
│   │   │   ├── memory.py                # 知识库管理
│   │   │   ├── usage.py                 # 用量统计查询
│   │   │   ├── plugins.py               # 插件管理
│   │   │   ├── logs.py                  # 日志查看
│   │   │   ├── debug.py                 # 调试数据
│   │   │   ├── health.py                # 健康检查
│   │   │   ├── interactions.py          # 交互记录查询
│   │   │   ├── internal.py              # 内部 API（Star 插件通信）
│   │   │   ├── models_test.py           # 模型连通性测试
│   │   │   ├── state.py                 # 状态查询
│   │   │   └── user_options.py          # 用户选项管理
│   │   ├── security/                # 安全
│   │   │   ├── secrets_manager.py       # Fernet 加密管理
│   │   │   ├── input_sanitizer.py       # 输入消毒
│   │   │   ├── output_encoder.py        # 输出 HTML 编码
│   │   │   └── log_sanitizer.py         # 日志脱敏
│   │   ├── middleware/               # 中间件
│   │   │   ├── rate_limit.py            # 速率限制
│   │   │   ├── metrics.py               # 指标收集
│   │   │   └── request_id.py            # Request ID 注入
│   │   └── handlers/                # 处理器
│   │       ├── context_assembler.py     # 上下文组装
│   │       ├── automation.py            # 自动插话/复读鹦鹉
│   │       ├── image_processor.py       # 图片处理
│   │       └── message_queue.py         # 消息队列
│   ├── nb_plugins/                  # NoneBot2 插件
│   │   └── core_llm_bot/                # 核心 LLM Bot 插件
│   │       ├── __init__.py              # 插件入口
│   │       ├── matchers.py              # 消息触发器
│   │       ├── pipeline.py              # 消息处理流水线
│   │       ├── context.py               # 上下文构建
│   │       ├── rendering.py             # 响应渲染
│   │       ├── automation.py            # 自动化逻辑
│   │       ├── image_processor.py       # 图片处理
│   │       ├── config.py                # 插件配置
│   │       └── _compat.py               # 向后兼容层（Phase 2 后移除）
│   ├── tests/                       # 测试
│   ├── data/                        # 数据目录
│   │   ├── bots/                        # 每 Bot 独立配置
│   │   │   └── main/                    # Bot ID = main
│   │   │       ├── config.json          # Bot 配置
│   │   │       └── knowledge.sqlite     # 知识库
│   │   ├── knowledge_base.sqlite        # 全局知识库
│   │   └── logs/                        # 日志
│   ├── requirements.txt             # Python 依赖
│   └── .env                         # 环境变量
├── frontend/                        # Svelte 前端
│   ├── src/
│   │   ├── components/                  # 共享组件
│   │   ├── pages/                       # 页面
│   │   ├── lib/                         # 工具库
│   │   ├── locales/                     # i18n
│   │   └── styles/                      # 样式
│   └── package.json
├── run.py                           # 统一启动器
├── docker-compose.yml               # Docker 编排
└── README.md                        # 项目说明
```

---

## 4. 代码约定

### 4.1 通用规则
- **类型注解**：所有 public 方法必须有完整 type hint（`def foo(x: int) -> str:`）
- **异步优先**：所有 IO 操作必须使用 `async/await`，禁止同步阻塞
- **错误处理**：使用 `logger.exception("context")` 捕获异常，禁止 bare `except:`
- **Import 顺序**：stdlib → 第三方 → 本地（`app.` 开头），各组间空一行
- **Docstring**：所有 public 方法必须有 docstring（Google style 或 reST）

### 4.2 命名约定
- 模块/包：`snake_case`（`knowledge_manager.py`）
- 类：`PascalCase`（`KnowledgeManager`）
- 函数/方法：`snake_case`（`get_relevant_memories`）
- 常量：`UPPER_SNAKE_CASE`（`MAX_RECONNECT_ATTEMPTS`）
- 私有方法：前缀 `_`（`_resolve_role_config`）

### 4.3 文件头
```python
"""模块简要描述.

详细描述（可选）.
"""
```

### 4.4 日志
```python
import logging
logger = logging.getLogger(__name__)

# 正确
logger.info("Bot '%s' started", bot_id)
logger.exception("Failed to process message")  # 自动包含堆栈

# 错误
logger.info(f"Bot '{bot_id}' started")  # 避免 f-string（性能）
except Exception:
    pass  # 禁止吞掉异常
```

---

## 5. 数据库 Schema

> **未来方向**：计划支持 SQLite / MySQL / PgSQL 多数据库后端，通过连接池模式切换。当前实现以 SQLite 为基准，迁移时需保持 Schema 兼容。

### 5.1 知识库（`knowledge.sqlite`）

#### `memory` — 记忆表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 ID |
| `content` | TEXT | 原始内容 |
| `normalized_content` | TEXT | 规范化内容（用于去重） |
| `timestamp` | TEXT | ISO 8601 时间戳 |
| `user_id` | TEXT | 用户 ID |
| `user_name` | TEXT | 用户名 |
| `source` | TEXT | 来源（discord / web / api） |
| `embedding` | BLOB | 向量嵌入（float32 序列化） |

#### `world_book` — 世界书表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 ID |
| `keywords` | TEXT | 触发关键词（逗号分隔） |
| `content` | TEXT | 注入内容 |
| `enabled` | INTEGER | 是否启用（0/1） |
| `linked_user_id` | TEXT | 关联用户 ID |
| `source` | TEXT | 来源 |

#### `memory_candidates` — 记忆候选表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 ID |
| `normalized_content` | TEXT | 规范化内容 |
| `content_sample` | TEXT | 内容样本 |
| `first_seen` | TEXT | 首次出现时间 |
| `last_seen` | TEXT | 最后出现时间 |
| `seen_count` | INTEGER | 出现次数 |
| `distinct_user_count` | INTEGER | 独立用户数 |
| `last_user_id` | TEXT | 最后发言用户 |
| `last_user_name` | TEXT | 最后发言用户名 |
| `user_ids_json` | TEXT | 用户 ID 列表（JSON） |
| `channel_ids_json` | TEXT | 频道 ID 列表（JSON） |
| `source_types_json` | TEXT | 来源类型列表（JSON） |
| `promoted` | INTEGER | 是否已提升为正式记忆 |
| `promoted_memory_id` | INTEGER | 提升后的 memory ID |
| `promoted_at` | TEXT | 提升时间 |
| `last_reason` | TEXT | 最后拒绝原因 |

#### `memory_stats` — 记忆统计表
| 字段 | 类型 | 说明 |
|------|------|------|
| `memory_id` | INTEGER FK → memory.id | 记忆 ID |
| `recall_count` | INTEGER | 召回次数 |
| `last_recalled_at` | TEXT | 最后召回时间 |
| `last_recall_score` | REAL | 最后召回分数 |

#### FTS5 全文索引
```sql
-- 记忆 FTS5 虚拟表
CREATE VIRTUAL TABLE memory_fts USING fts5(content, content='memory', content_rowid='id');

-- 世界书 FTS5 虚拟表
CREATE VIRTUAL TABLE world_book_fts USING fts5(keywords, content, content='world_book', content_rowid='id');
```

### 5.2 配置存储（`config.json`）
```json
{
  "bot_id": "main",
  "bot_name": "My Bot",
  "platform": "discord",
  "enabled": true,
  "discord_token": "...",
  "discord_intents": {"guilds": true, "guild_messages": true, "direct_messages": true, "message_content": true, "members": true},
  "llm_provider": "openai",
  "api_key": "...",
  "base_url": null,
  "model_name": "gpt-4o",
  "system_prompt": "...",
  "trigger_keywords": [],
  "trigger_match_mode": "contains",
  "context_mode": "channel",
  "channel_context_settings": {"message_limit": 10, "char_limit": 4000},
  "memory_context_settings": {"message_limit": 15, "char_limit": 6000},
  "auto_memory_recall_top_k": 12,
  "auto_memory_recall_char_limit": 2200,
  "auto_memory_recall_max_age_days": 365,
  "user_personas": {},
  "role_based_config": {},
  "scoped_prompts": {"guilds": {}, "channels": {}},
  "user_options": {"enabled": false, "rules": {}},
  "plugins": {},
  "api_secret_key": "..."
}
```

---

## 6. API 约定

### 6.1 REST 风格
- 前缀：`/api/`
- 资源名词复数：`/api/bots/`, `/api/config/`
- 嵌套资源：`/api/bots/{bot_id}/config`

### 6.2 认证
- Header: `X-API-Key: <api_secret_key>`
- 内部 API: `X-Internal-Token: <derived_token>`

### 6.3 错误格式
```json
{"error": "Error message"}
```

### 6.4 HTTP 状态码
| 状态码 | 场景 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 认证失败 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 429 | 速率限制 |
| 500 | 服务器内部错误 |

### 6.5 核心端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/config` | 获取全局配置 |
| PUT | `/api/config` | 更新全局配置 |
| GET | `/api/bots` | 列出所有 Bot |
| POST | `/api/bots` | 创建 Bot |
| GET | `/api/bots/{id}` | 获取 Bot 详情 |
| GET | `/api/bots/{id}/config` | 获取 Bot 配置 |
| PUT | `/api/bots/{id}/config` | 更新 Bot 配置 |
| DELETE | `/api/bots/{id}/config` | 删除 Bot |
| POST | `/api/bots/{id}/start` | 启动 Bot |
| POST | `/api/bots/{id}/stop` | 停止 Bot |
| POST | `/api/chat` | WebUI 直接对话 |
| GET | `/api/memory` | 查询知识库 |
| POST | `/api/memory/ingest` | 注入知识 |
| GET | `/api/usage` | 用量统计 |
| GET | `/api/interactions` | 交互记录 |
| GET | `/api/logs` | 日志查看 |
| GET | `/api/debug/captures` | 调试数据 |

---

## 7. Commit 风格

遵循 **Conventional Commits** 格式：

```
<type>(<scope>): <subject>

<body>

Signed-off-by: RainyN0077 <gotiyu0407@gmail.com>
```

### 7.1 Type
| Type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `refactor` | 代码重构（用 `!` 表示破坏性：`refactor!:`） |
| `test` | 测试添加/修改 |
| `chore` | 构建/工具/配置 |
| `docs` | 文档 |
| `perf` | 性能优化 |
| `security` | 安全修复 |

### 7.2 Scope
- 模块名：`knowledge` / `pipeline` / `memory` / `config` / `security` / `frontend`
- 用 `!` 标记破坏性变更：`refactor(migrations)!:`

### 7.3 Subject
- 中文或英文，简洁描述
- 可引用 Issue ID：`(task 10.8)` / `(7.6)`

### 7.4 Body
- 空行分隔
- 分类描述（`##` 或 `-` 列表）
- 包含验证证据

### 7.5 示例
```
fix(SQLite): 修复路径穿越/PRAGMA 注入/null 字节注入及 .bak 向后兼容

集中式路径验证 (C-1 + C-2)
- 新增 SQLite.ValidateAndCanonicalizeDatabasePath 作为单一审计点
- Path.GetFullPath 规范化 + 边界检查

验证
- dotnet build VRCX-Cef.csproj: 0 警告 0 错误
- npm test -- src/stores/__tests__/vrcx: 15/15 通过

Signed-off-by: RainyN0077 <gotiyu0407@gmail.com>
```

---

## 8. 测试

### 8.1 框架
- pytest + pytest-asyncio
- 覆盖率：`pytest --cov=backend`

### 8.2 运行方式
```bash
# 全部测试
pytest backend/tests/

# 特定模块
pytest backend/tests/test_knowledge_manager.py

# 带覆盖率
pytest --cov=backend --cov-report=html backend/tests/
```

### 8.3 覆盖率要求
- 核心模块（`core_logic/` / `llm_providers/`）：≥80%
- 路由层（`routers/`）：≥70%
- 整体：≥75%

### 8.4 测试命名
- 文件：`test_{module}.py`
- 类：`Test{ModuleName}`（可选）
- 方法：`test_{场景}_{预期行为}`

### 8.5 Mock 规范
- 外部 API（Discord / LLM）：必须 Mock
- 数据库：使用临时 SQLite（`:memory:` 或 tempfile）
- Redis：使用 `fakeredis` 或 mock

---

## 9. 设计模式

### 9.1 BotInstance 状态机
```
STARTING → RUNNING → STOPPED
   ↓           ↓
   └───────────┘ (重连循环)
```

- `start()` → `_start_nonebot()` → 启动后台重连循环
- `stop()` → `_stop_nonebot()` → 取消任务 + 清理资源
- 重连：指数退避（1s → 2s → 4s → ... → 60s），最大 10 次

### 9.2 LLM 调用链
```
Discord 消息
  → NoneBot on_message (matchers.py)
    → _record_interaction()  # 记录用户消息
    → track_auto_interject() / track_repeat_parrot()
    → pipeline.py.process_message()
      → build_full_context()  # 构建 system_prompt + history
      → knowledge_manager.get_relevant_memories()  # 知识库 recall
      → llm_provider.get_response_stream()  # LLM 调用
      → render_streaming_response()  # 流式渲染
      → _process_knowledge_tags()  # 知识库 ingest
      → usage_tracker.record_usage()  # 用量记录
      → _record_bot_interaction()  # 记录 bot 回复
```

### 9.3 知识库流程
```
用户消息 → 提取 <memory> 标签 → 解析内容 → 质量评分
  ↓
质量合格 → 直接写入 memory 表
质量存疑 → 写入 memory_candidates 表 → 达到阈值后提升
  ↓
Recall: FTS5 全文搜索 + embedding 向量检索 → rerank → 注入 system_prompt
```

### 9.4 插件注册
```python
# plugins/ 下的 BasePlugin 体系
class BasePlugin:
    async def handle_message(message, config) -> bool | tuple | None
    def get_tools() -> list[dict]
    def get_tool_functions() -> dict[str, callable]

# PluginManager
plugins = PluginManager(config)
result = await plugins.process_message(message, config)
tools = plugins.get_all_tools()
```

### 9.5 安全管道
```
用户输入 → input_sanitizer.sanitize() → Prompt Injection 检测
  ↓
LLM 调用 → output_encoder.encode() → HTML 实体编码
  ↓
日志输出 → log_sanitizer.sanitize() → 敏感信息脱敏
```

---

## 10. 禁止事项

### 10.1 代码
- ❌ 不在 pipeline 中执行同步 IO（如 `requests.get()`）
- ❌ 不在 handler 中直接操作数据库（通过 `core_logic/`）
- ❌ 不硬编码 API Key / Token
- ❌ 不跳过认证中间件
- ❌ 不使用 `except: pass` 吞掉异常
- ❌ 不在循环中 `await` 串行调用（改用 `asyncio.gather`）

### 10.2 数据库
- ❌ 不直接拼接 SQL（参数化查询）
- ❌ 不在事务中执行外部 API 调用
- ❌ 不忽略 FTS5 索引同步

### 10.3 安全
- ❌ 不记录明文 API Key / Token
- ❌ 不返回内部错误详情给客户端
- ❌ 不跳过输入消毒

---

## 11. 架构图

### 11.1 系统架构
```
┌──────────────────────────────────────────────────────────┐
│                     Web UI (Svelte 4)                     │
│              http://localhost:8094                        │
└────────────────────┬─────────────────────────────────────┘
                     │ REST API (X-API-Key auth)
                     ▼
┌──────────────────────────────────────────────────────────┐
│               FastAPI 路由层 (routers/)                    │
│  config · bots · chat · memory · usage · plugins · logs   │
│  debug · health · metrics · interactions · internal       │
└────────┬──────────┬──────────┬──────────┬────────────────┘
         │          │          │          │
         ▼          ▼          ▼          ▼
┌───────────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐
│ 配置缓存   │ │ Bot 管理器│ │ 中间件  │ │  NoneBot2     │
│ config_   │ │bot_      │ │ 限速    │ │  Driver +     │
│ cache.py  │ │manager.py│ │ 指标    │ │  Discord      │
│           │ │          │ │ 请求ID  │ │  Adapter      │
└───────────┘ └────┬─────┘ └────────┘ └──────┬───────┘
                   │                         │
                   ▼                         ▼
            ┌──────────────┐          ┌───────────┐
            │ BotInstance   │          │  Discord   │
            │ (per-bot)     │          │  Gateway   │
            │ 启动/重连/停止 │          └───────────┘
            └──────────────┘
```

### 11.2 消息处理流程
```
Discord 消息
    │
    ▼
NoneBot2 Driver → on_message event
    │
    ▼
matchers.py (priority=10, block=False)
    │
    ├─→ Bot 自过滤 (author.id == self_id → return)
    ├─→ _record_interaction(is_bot_reply=False)
    ├─→ track_auto_interject()
    ├─→ track_repeat_parrot()
    │
    ▼
pipeline.py.process_message()
    │
    ├─→ Redis 消息锁 (防并发)
    ├─→ 图片收集 + 多模态判断
    ├─→ build_full_context()
    │     ├─→ persona_manager.get_persona()
    │     ├─→ context_builder.build_full_context()
    │     └─→ knowledge_manager.get_relevant_memories()
    │
    ├─→ llm_provider.get_response_stream()
    │     ├─→ OpenAI / Anthropic / Google / xAI / DeepSeek ...
    │     └─→ 工具调用 (function calling)
    │
    ├─→ render_streaming_response()
    │     ├─→ strip_thinking_sections()
    │     ├─→ strip_dsml_tool_blocks()
    │     └─→ split_message() (2000 字限制)
    │
    ├─→ _process_knowledge_tags()
    │     ├─→ <memory> → ingest_memory_candidate()
    │     └─→ <user_info> → add_world_book_entry()
    │
    ├─→ usage_tracker.record_usage()
    └─→ _record_bot_interaction(is_bot_reply=True)
    │
    ▼
Discord 发送响应
```

### 11.3 数据流（知识库）
```
┌─────────────────────────────────────────────────────────┐
│                     知识库系统                            │
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Recall     │    │   Ingest    │    │   Search    │  │
│  │             │    │             │    │             │  │
│  │ FTS5 全文   │    │ 质量评分    │    │ 向量语义    │  │
│  │ + BM25      │    │ + 候选提升  │    │ + Rerank    │  │
│  └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                  │                  │          │
│         └──────────────────┼──────────────────┘          │
│                            ▼                            │
│                   ┌─────────────────┐                    │
│                   │  knowledge.sqlite │                   │
│                   │  memory          │                   │
│                   │  world_book      │                   │
│                   │  memory_candidates│                  │
│                   │  memory_stats    │                   │
│                   └─────────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

---

## 12. AI 开发指南

### 12.1 常见陷阱
1. **NoneBot2 事件循环**：Windows 上必须使用 `ProactorEventLoop`（已在 `main.py` 设置）
2. **SQLite 并发**：写操作必须加锁（`asyncio.Lock` 或 Redis 锁）
3. **流式响应**：Discord 2000 字限制，必须分片发送
4. **内存泄漏**：`aiohttp.ClientSession` 必须复用，不能每次请求创建
5. **配置热更新**：修改配置后需调用 `config_cache.invalidate()` 刷新缓存

### 12.2 推荐工作流
1. **新增功能**：先写接口定义 → 写测试 → 实现 → 验证
2. **修复 Bug**：先写复现测试 → 定位根因 → 修复 → 验证
3. **重构**：先建抽象接口 → 迁移调用方 → 删除旧代码
4. **数据库变更**：先写迁移脚本 → 测试回滚 → 执行迁移

### 12.3 模块依赖关系
```
main.py → bot_manager.py → bot_instance.py → nonebot_driver
                ↓
         config_cache.py ← paths.py
                ↓
         routers/ → core_logic/ → sqlite_pool.py
                ↓
         llm_providers/factory.py → base.py
                ↓
         security/ ← utils.py

六边形架构（Wave 1-3）:
  ports/ (接口) ← adapters/ (实现)
    bot_runtime.py ← nonebot_runtime.py
    platform_message.py ← discord_platform_adapter.py
    message_bus.py ← message_bus_impl.py
    plugin_base.py ← plugin_context_adapter.py
    llm_provider.py ← llm_providers/base.py
```

### 12.4 调试技巧
- **日志级别**：`LOGURU_LEVEL=DEBUG` 开启详细日志
- **Debugger 页面**：WebUI `/Debugger` 可查看 LLM 请求/响应详情
- **健康检查**：`GET /api/health` 返回各模块状态
- **数据库查询**：`sqlite3 backend/data/bots/main/knowledge.sqlite`

### 12.5 性能热点
- **知识库 recall**：FTS5 + embedding 计算，考虑缓存
- **LLM 调用**：网络延迟主导，考虑连接池复用
- **流式渲染**：Discord API 编辑频率限制（每分钟 5 次）
- **配置读取**：已缓存，但频繁 invalidate 会影响性能

---

## 13. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BACKEND_PORT` | 8093 | FastAPI 端口 |
| `FRONTEND_PORT` | 8094 | Vite 端口 |
| `REDIS_HOST` | localhost | Redis 主机 |
| `REDIS_PORT` | 6379 | Redis 端口 |
| `FAIL_ON_REDIS_ERROR` | false | Redis 失败时是否终止 |
| `LOGURU_LEVEL` | WARNING | 日志级别 |
| `ENCRYPTION_KEY` | (required) | Fernet 加密密钥 |
| `DISABLE_ENCRYPTION` | 0 | 禁用加密（仅迁移模式） |
| `HTTP_PROXY` | (optional) | HTTP 代理 |
| `HTTPS_PROXY` | (optional) | HTTPS 代理 |

---

*本文档持续更新。如有变更，请同步更新本文档。*
