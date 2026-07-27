# AstrBot 迁移规划书

> 版本: 1.1
> 日期: 2026-07-27
> 状态: **已评审 — 审查发现已修复**
> 作者: RainyN0077

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [迁移目标与范围](#2-迁移目标与范围)
3. [AstrBot 框架技术概览](#3-astrbot-框架技术概览)
4. [当前项目架构与迁移现状](#4-当前项目架构与迁移现状)
5. [迁移可行性矩阵](#5-迁移可行性矩阵)
6. [目标架构设计](#6-目标架构设计)
7. [分阶段迁移计划](#7-分阶段迁移计划)
8. [Star 插件补全清单](#8-star-插件补全清单)
9. [Legacy 代码删除清单](#9-legacy-代码删除清单)
10. [管理服务器适配](#10-管理服务器适配)
11. [数据迁移方案](#11-数据迁移方案)
12. [部署架构变更](#12-部署架构变更)
13. [协议变更（MIT → AGPL-3.0）](#13-协议变更mit--agpl-30)
14. [风险评估与回滚方案](#14-风险评估与回滚方案)
15. [验收标准](#15-验收标准)
16. [附录](#16-附录)

---

## 1. 执行摘要

### 1.1 背景

Discord-LLMs-ChatBot 当前是一个基于 NoneBot2 的多 Bot 聊天机器人，支持 12 家 LLM 提供商，配备 Svelte Web 控制面板、知识引擎（SQLite FTS5）、OCR、插件系统和多 Bot 管理。

项目已启动向 AstrBot 框架的迁移，采用**双模式架构**（`provider_mode`: `nonebot` / `astrbot`），AstrBot 侧以子进程方式运行，通过 `/internal` HTTP API 与管理服务器通信。目前 AstrBot 侧的基础设施（子进程管理器、配置生成器、IPC 端点、15 个 Star 插件骨架、前端切换 UI）已搭建，但 Star 插件功能不完整，NoneBot legacy 路径仍在主代码路径中。

### 1.2 迁移目标

**彻底将 Bot 迁移至 AstrBot 框架，删除 NoneBot legacy 路径，使 AstrBot 成为唯一的 Bot 运行时。**

具体目标：
- 删除 NoneBot2 及其 Discord/OneBot 适配器依赖
- 删除 `nb_plugins/` 目录及所有 NoneBot 插件代码
- 补全 15 个 Star 插件至功能完整，使其完全替代 legacy pipeline 的全部能力
- 保留管理服务器（FastAPI + Svelte 前端）作为配置/知识库/用量/交互记录的中心化管理层
- 移除 `provider_mode` 双模式分支，AstrBot 成为唯一路径
- 项目协议从 MIT 变更为 AGPL-3.0（AstrBot 依赖要求）

### 1.3 迁移策略

采用**渐进式迁移 + 最终切换**策略，分 4 个阶段：
1. **阶段一**：补全 Star 插件功能（不破坏 legacy 路径）
2. **阶段二**：集成测试与验证（双模式并存，AstrBot 模式全功能验证）
3. **阶段三**：删除 Legacy 代码（NoneBot 路径、依赖、双模式分支）
4. **阶段四**：协议变更与部署切换

---

## 2. 迁移目标与范围

### 2.1 范围内（In Scope）

| 模块 | 迁移动作 |
|------|----------|
| Bot 运行时 | NoneBot2 → AstrBot 子进程（唯一路径） |
| Discord 连接 | nonebot-adapter-discord → AstrBot 内置 Discord 适配器（py-cord） |
| LLM 调用 | 管理服务器 `llm_providers/` → AstrBot 内置 provider（Discord 消息流）；管理服务器保留 `llm_providers/` 仅供 `/chat` WebUI 端点 |
| 消息处理 pipeline | `nb_plugins/core_llm_bot/` → `astrbot_stars/` 15 个 Star 插件 |
| 触发器 | `matchers.py` trigger 逻辑 → `trigger` Star |
| 上下文构建 | `context.py` + `handlers/context_assembler.py` → `context_assembler` Star |
| 知识库 recall/ingest | 直接调用 `KnowledgeManager` → 通过 `/internal` IPC 调用 |
| 交互记录 | 直接调用 `InteractionRecorder` → 通过 `/internal` IPC 调用 |
| 用量统计 | 直接调用 `UsageTracker` → 通过 `/internal` IPC 调用 |
| Persona | 直接读 config → 通过 `/internal` IPC 调用 |
| OCR | `image_processor.py` → `ocr_image` Star |
| 自动插话/复读鹦鹉 | `automation.py` → `auto_interject` / `repeat_parrot` Star |
| 插件系统 | `plugins/manager.py` → `plugin_bridge` Star |
| 配置管理 | 保留管理服务器 `config_cache.py` + FastAPI 路由 |
| WebUI | 保留 Svelte 前端 + FastAPI 后端 |
| 部署 | docker-compose 调整：backend + frontend + redis + astrbot 镜像依赖 |

### 2.2 范围外（Out of Scope）

- 不替换管理服务器的 FastAPI 后端和 Svelte 前端（AstrBot 内置 WebUI 不面向最终用户）
- 不迁移知识库存储到 AstrBot 内置知识库（保留 SQLite FTS5 在管理服务器侧）
- 不引入 AstrBot 的 MCP / Agent Sandbox / Skills 能力（可作为后续增强）
- 不迁移到 AstrBot 内置的 faiss 向量知识库（保留现有 embedding + FTS5 混合检索）
- 不变更前端 WebUI 的页面结构和 API 契约

---

## 3. AstrBot 框架技术概览

### 3.1 基本信息

| 属性 | 值 |
|------|-----|
| 仓库 | https://github.com/AstrBotDevs/AstrBot |
| 版本 | 4.26.7（截至 2026-07） |
| 协议 | **AGPL-3.0-or-later** |
| Python | >=3.12 |
| Stars | 38.1k |
| 部署 | Docker / uv / 桌面客户端 / 启动器 |
| Docker 镜像 | `soulter/astrbot:latest` |
| WebUI 端口 | 6185 |
| 数据目录 | `/AstrBot/data` |

### 3.2 核心架构

AstrBot 是一个事件驱动的多平台 ChatBot 框架，核心分层：

```
┌─────────────────────────────────────────────┐
│              平台适配器层                    │
│  Discord · QQ · Telegram · 飞书 · 钉钉 ...  │
│  (py-cord · aiocqhttp · python-telegram-bot)│
└──────────────────┬──────────────────────────┘
                   │ MessageEvent
                   ▼
┌─────────────────────────────────────────────┐
│              事件总线 / 调度器               │
│         (Star 插件链 · 优先级排序)           │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │ Star 1 │ │ Star 2 │ │ Star N │  ← 插件层
   │trigger │ │context│ │respond │
   └────────┘ └────────┘ └────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           LLM 调度层 / Agent 执行器          │
│  OpenAI · Anthropic · Gemini · DeepSeek ... │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│        知识库 · MCP · Agent Sandbox          │
│   (faiss · rank-bm25 · jieba · MCP server)  │
└─────────────────────────────────────────────┘
```

### 3.3 Star 插件系统

Star 是 AstrBot 的插件抽象，基于装饰器的事件钩子模型：

```python
from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

class MyPlugin(star.Star):
    name = "my_plugin"          # 插件唯一标识
    author = "author"           # 作者

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        # context.get_config()          — 获取 AstrBot 配置
        # context.conversation_manager  — 会话历史管理器
        # context.get_provider()        — 获取 LLM provider

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        # 事件钩子：每条消息触发
        event.get_sender_id()       # 发送者 ID
        event.get_group_id()        # 群组/服务器 ID
        event.get_session_id()      # 会话 ID
        event.get_message_str()     # 消息文本
        event.is_at_or_wake_command # 是否 @本bot
        event.set_extra(key, val)   # 附加上下文数据
        event.get_result()          # 获取/设置响应结果
        event.unified_msg_origin    # 统一消息来源标识
```

**关键 API**：
- `star.Star` — 插件基类
- `star.Context` — 插件上下文（配置、会话管理、provider 访问）
- `filter.event_message_type(EventMessageType.ALL)` — 消息事件过滤器
- `AstrMessageEvent` — 消息事件对象

**插件目录结构**（AstrBot 约定）：
```
data/plugins/{plugin_name}/
    main.py            # Star 类定义
    metadata.yaml      # 插件元数据
    _conf_schema.json  # 插件配置 schema（WebUI 可视化配置）
    requirements.txt   # 插件依赖
```

### 3.4 配置体系

AstrBot 主配置文件为 `data/cmd_config.json`（WebUI 管理），平台/LLM/插件配置均通过 WebUI 可视化操作。本项目通过 `astrbot_config_gen.py` 生成 `config.yml` 供子进程使用。

### 3.5 内置能力 vs 本项目需求

| AstrBot 内置能力 | 本项目是否采用 | 说明 |
|------------------|----------------|------|
| Discord 适配器 | ✅ 采用 | 替代 nonebot-adapter-discord |
| LLM provider（OpenAI/Anthropic/Gemini 等） | ✅ 采用 | Discord 消息流由 AstrBot 调用 LLM |
| 会话历史管理 | ✅ 采用 | `context.conversation_manager` |
| 知识库（faiss + bm25） | ❌ 不采用 | 保留管理服务器 SQLite FTS5 |
| WebUI（Vue dashboard） | ❌ 不暴露 | 保留本项目 Svelte 前端 |
| MCP | ❌ 不采用 | 范围外 |
| Agent Sandbox | ❌ 不采用 | 范围外 |
| 自动上下文压缩 | ⚠️ 评估 | 可作为增强，当前由 context_assembler Star 控制 |
| 插件市场 | ❌ 不采用 | 使用自研 plugin_bridge Star |

---

## 4. 当前项目架构与迁移现状

### 4.1 当前架构（双模式）

```
┌──────────────────────────────────────────────────────────────┐
│                    Web UI (Svelte 4)  :8094                   │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST API (X-API-Key)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              管理服务器 (FastAPI)  :8093                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  routers/: config·bots·chat·memory·usage·plugins·logs   │ │
│  │           debug·health(+/metrics)·interactions·internal    │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  core_logic/: knowledge_manager·interaction_recorder    │ │
│  │              persona_manager·context_builder·sqlite_pool │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  llm_providers/: factory·openai·anthropic·google·xai    │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  security/: input_sanitizer·output_encoder·secrets_mgr   │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  middleware/: rate_limit·request_id·metrics              │ │
│  └─────────────────────────────────────────────────────────┘ │
│                               │                              │
│         ┌─────────────────────┼─────────────────────┐        │
│         ▼ NoneBot 模式         ▼ AstrBot 模式        │        │
│  ┌──────────────┐    ┌──────────────────────────┐   │        │
│  │  NoneBot2     │    │  AstrBot 子进程管理器     │   │        │
│  │  Driver       │    │  (astrbot_manager.py)    │   │        │
│  │  + Discord    │    │  spawn·health·reconnect  │   │        │
│  │  Adapter      │    └───────────┬──────────────┘   │        │
│  │               │                │ /internal IPC     │        │
│  │  nb_plugins/  │                ▼                    │        │
│  │  core_llm_bot │    ┌──────────────────────────┐   │        │
│  │  (pipeline)   │    │  AstrBot 子进程           │   │        │
│  │               │    │  python -m astrbot run   │   │        │
│  └──────────────┘    │  --config config.yml     │   │        │
│                      │                          │   │        │
│                      │  astrbot_stars/ (15个)    │   │        │
│                      │  context_assembler       │   │        │
│                      │  knowledge_bridge        │   │        │
│                      │  trigger · persona ...   │   │        │
│                      └───────────┬──────────────┘   │        │
│                                  │                  │        │
│                      ┌───────────▼──────────────┐   │        │
│                      │  Discord (py-cord)       │   │        │
│                      │  LLM Provider            │   │        │
│                      └──────────────────────────┘   │        │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 迁移现状评估

#### 已完成 ✅

| 组件 | 文件 | 完成度 | 说明 |
|------|------|--------|------|
| 子进程管理器 | `astrbot_manager.py` | 100% | spawn/health/reconnect/stop/shutdown 完整 |
| 配置生成器 | `astrbot_config_gen.py` | 100% | platform/provider/knowledge/conversation/stars/persona/trigger/internal_api |
| IPC 端点 | `routers/internal.py` | 100% | knowledge recall/ingest, usage track, interaction record, config, persona |
| 双模式切换 | `bot_instance.py` | 100% | `provider_mode` 分支，`_start_astrbot`/`_stop_astrbot` |
| 前端切换 UI | `AstrBotMigration.svelte` | 100% | 倒计时确认弹窗，Beta 警告 |

#### 部分完成 ⚠️（Star 插件骨架）

| Star 插件 | 完成度 | 缺失功能 |
|-----------|--------|----------|
| `context_assembler` | 40% | 缺 memory 注入、role-based 完整逻辑、history 构建不完整 |
| `knowledge_bridge` | 30% | 只 recall 不 ingest，recall 结果未注入 context |
| `trigger` | 60% | user_options block 检查是 stub（`return False`） |
| `streaming_respond` | 70% | 清理/分片已实现，未确认是否正确接入响应流程 |
| `persona` | 30% | 只 `set_extra`，未注入 system prompt |
| `post_process` | 20% | `<memory>`/`<user_info>` 标签 ingest 是 TODO |
| `usage_tracker` | 5% | 完全是 `pass`（未实现） |
| `ocr_image` | 未确认 | 需检查 |
| `auto_interject` | 未确认 | 需检查 |
| `repeat_parrot` | 未确认 | 需检查 |
| `plugin_bridge` | 未确认 | 需检查 |
| `memory_tools` | 未确认 | 需检查 |
| `interaction_recorder` | 未确认 | 需检查 |
| `debug_capture` | 未确认 | 需检查 |
| `message_queue` | 未确认 | 需检查 |

#### 未完成 ❌

- NoneBot legacy 路径仍在主代码路径（`main.py` 的 `nonebot.init()`）
- `provider_mode` 双模式分支未移除
- NoneBot 依赖未从 `requirements.txt` 移除
- 协议未变更（仍为 MIT）

### 4.3 NoneBot Legacy 路径（待删除）

| 文件/目录 | 职责 | 删除策略 |
|-----------|------|----------|
| `main.py` 中 nonebot 初始化 | `nonebot.init()` / `register_adapter` / `load_plugins` | 移除 NoneBot 初始化代码 |
| `nb_plugins/` 整个目录 | NoneBot 插件（core_llm_bot, search_plugin, configurable_tools, memory_tools） | 整目录删除 |
| `bot_instance.py` NoneBot 路径 | `_start_nonebot` / `_nonebot_reconnect_loop` / `_stop_nonebot` / `_reconnect_nonebot` | 删除方法，移除 `provider_mode` 分支 |
| `routers/bots.py` `get_adapter_status` | 依赖 `nonebot_driver` | 删除或改为查询 AstrBot 子进程状态 |
| `discord_patch.py` | NoneBot Discord 适配器 emoji 修复 | 删除 |
| `config_bridge.py` / `generate_env_file` | 生成 NoneBot `.env` 文件 | 删除 |
| `requirements.txt` | `nonebot2` / `nonebot-adapter-discord` / `nonebot-adapter-onebot` / `discord.py` | 移除依赖 |

---

## 5. 迁移可行性矩阵

### 5.1 功能模块映射

| # | 当前功能 | Legacy 实现 | AstrBot 对应 | 迁移策略 | 复杂度 |
|---|----------|-------------|-------------|----------|--------|
| F1 | Discord 连接 | nonebot-adapter-discord | AstrBot Discord 适配器（py-cord） | **内置替代** — 配置生成器已映射 | 低 |
| F2 | LLM 调用（消息流） | `llm_providers/factory.py` + pipeline | AstrBot 内置 provider | **内置替代** — config.yml 直接配 api_key | 低 |
| F3 | LLM 调用（WebUI /chat） | `llm_providers/factory.py` | 保留管理服务器 `llm_providers/` | **保留** — 仅 WebUI 端点使用 | 无 |
| F4 | 触发器（@mention/reply/keyword） | `matchers.py` | `trigger` Star | **插件补全** — 骨架已存在 | 中 |
| F5 | 上下文构建 | `context.py` + `handlers/context_assembler.py` | `context_assembler` Star | **插件补全** — 需移植 memory 注入、role-based | 高 |
| F6 | 知识库 recall | `KnowledgeManager.get_relevant_memories()` | `knowledge_bridge` Star → `/internal/knowledge/recall` | **插件补全** — IPC 桥接 | 中 |
| F7 | 知识库 ingest（`<memory>` 标签） | `pipeline.py` `_process_knowledge_tags` | `post_process` Star → `/internal/knowledge/ingest` | **插件补全** — 当前是 TODO | 中 |
| F8 | 世界书 ingest（`<user_info>` 标签） | `pipeline.py` `_process_knowledge_tags` | `post_process` Star → `/internal/knowledge/ingest` | **插件补全** — 当前是 TODO | 中 |
| F9 | 交互记录 | `InteractionRecorder.record_message()` | `interaction_recorder` Star → `/internal/interaction/record` | **插件补全** | 中 |
| F10 | 用量统计 | `UsageTracker.record_usage()` | `usage_tracker` Star → `/internal/usage/track` | **插件补全** — 当前是 pass | 中 |
| F11 | Persona 注入 | 直接读 `config.user_personas` | `persona` Star → `/internal/persona/{user_id}` | **插件补全** — 需注入 system prompt | 中 |
| F12 | Role-based config | `pipeline.py` `_resolve_role_config` | `context_assembler` Star | **插件补全** — 需移植 | 中 |
| F13 | Scoped prompts（guild/channel） | `context_assembler.py` | `context_assembler` Star | **插件补全** — 骨架已实现 | 低 |
| F14 | OCR 图片处理 | `image_processor.py` + `ocr_service.py` | `ocr_image` Star | **插件补全** | 高 |
| F15 | 自动插话 | `automation.py` `track_auto_interject` | `auto_interject` Star | **插件补全** | 中 |
| F16 | 复读鹦鹉 | `automation.py` `track_repeat_parrot` | `repeat_parrot` Star | **插件补全** | 中 |
| F17 | 插件系统 | `plugins/manager.py` | `plugin_bridge` Star | **插件补全** | 高 |
| F18 | 消息队列（频道串行化） | `matchers.py` `MessageQueue` | `message_queue` Star | **插件补全** | 中 |
| F19 | 流式响应渲染 | `rendering.py` `render_streaming_response` | `streaming_respond` Star | **插件补全** — 需确认接入 | 中 |
| F20 | 消息分片（2000 字限制） | `utils.py` `split_message` | `streaming_respond` Star | **插件补全** — 已实现 | 低 |
| F21 | DSML 工具块清理 | `core_shared.py` `strip_dsml_tool_blocks` | `streaming_respond` Star | **插件补全** — 已实现 | 低 |
| F22 | thinking 段清理 | `core_shared.py` `strip_thinking_sections` | `streaming_respond` Star | **插件补全** — 已实现 | 低 |
| F23 | 工具调用（function calling） | `plugin_manager.get_all_tools()` + `plugins/memory_plugin.py` + `plugins/search.py` | AstrBot 内置 function calling 或 `plugin_bridge` Star | **评估后决策** — 见下方 F23 评估方案 | 高 |
| F24 | User options（用户屏蔽） | `user_options_manager.py` | `trigger` Star | **插件补全** — 当前是 stub | 中 |
| F25 | Debug capture | `debug_capture_store.py` | `debug_capture` Star → `/internal` 或本地存储 | **插件补全** | 中 |
| F26 | Redis 消息锁 | `pipeline.py` `get_redis().set(lock_key)` | `message_queue` Star | **插件补全** — 频道串行化替代 | 中 |
| F27 | 配置管理 | `config_cache.py` + FastAPI 路由 | 保留管理服务器 | **保留** | 无 |
| F28 | WebUI | Svelte 前端 + FastAPI | 保留 | **保留** | 无 |
| F29 | 凭据加密 | `secrets_manager.py` Fernet | 保留管理服务器 | **保留** | 无 |
| F30 | 速率限制 | `middleware/rate_limit.py` | 保留管理服务器 | **保留** | 无 |
| F31 | 模型连通性测试 | `routers/models_test.py`（直接 import openai/anthropic/google/xai_sdk） | 保留管理服务器 | **保留** — WebUI 模型测试端点，与 AstrBot 子进程无关 | 无 |
| F32 | 用户选项管理（屏蔽规则） | `routers/user_options.py`（依赖 `nonebot_driver` 第 131 行） | 保留管理服务器，移除 nonebot_driver 依赖 | **保留 + 适配** — 用户屏蔽规则存储在管理服务器，trigger Star 通过 IPC 查询 | 中 |
| F33 | 适配器/驱动状态查询 | `routers/state.py`（依赖 `nonebot_driver` 第 16 行） | 改为查询 `astrbot_process_manager` | **适配** — 移除 nonebot_driver，改为 AstrBot 子进程状态 | 中 |
| F34 | Prompt 预览构建 | `core_logic/preview_builder.py`（间接依赖 `discord` via persona_manager） | 保留管理服务器，移除 discord 依赖 | **保留 + 适配** — WebUI prompt 预览，需移除 `import discord` | 中 |
| F35 | 知识库嵌入服务 | `core_logic/embedding_service.py` | 保留管理服务器 | **保留** — 被 `knowledge_manager` 调用，IPC recall 链路内使用 | 无 |
| F36 | 知识库重排服务 | `core_logic/rerank_service.py` | 保留管理服务器 | **保留** — 同 F35 | 无 |
| F37 | 用量配额管理 | `core_logic/usage_manager.py`（`import discord` 第 10 行） | 保留管理服务器，移除 discord 依赖 | **保留 + 适配** — role-based 配额检查，需移除 `import discord` | 中 |
| F38 | 用户验证 | `core_logic/user_validator.py`（`import discord` 第 4 行） | 保留管理服务器，移除 discord 依赖 | **保留 + 适配** — 需移除 `import discord`，改为平台无关验证 | 中 |
| F39 | 插件系统（基类/加载器/可配置插件） | `plugins/base.py` + `plugins/manager.py` + `plugins/configurable_plugin.py` | `plugin_bridge` Star 加载 | **插件补全** — plugin_bridge Star 需加载继承 `base.py` 的插件 | 高 |
| F40 | Tavily 搜索插件（function calling tool） | `plugins/search.py` | `plugin_bridge` Star 或 AstrBot 内置 web search | **评估** — AstrBot 内置网页搜索能力，可能替代 | 中 |
| F41 | 内存操作插件（function calling tools） | `plugins/memory_plugin.py`（`add_to_memory`/`search_memory`/`add_to_world_book`） | `memory_tools` Star → `/internal/knowledge/ingest` | **插件补全** — 提供 LLM 可调用的 memory tools | 高 |
| F42 | 消息队列（频道串行化） | `handlers/message_queue.py` + `matchers.py` `MessageQueue` | `message_queue` Star | **插件补全** — 频道级串行化 | 中 |

#### F23 评估方案（function calling 迁移决策）

**评估目标**：确定 AstrBot 模式下 function calling 的实现路径。

**现有工具清单**（`plugins/` 提供的 function calling tools）：
- `memory_plugin.py`：`add_to_memory`、`search_memory`、`add_to_world_book` — 知识库操作工具
- `search.py`：Tavily web search — 网页搜索工具
- `configurable_plugin.py`：用户自定义可配置工具

**评估维度**：
1. AstrBot 内置 function calling 是否支持自定义 tool 注册？（查 AstrBot 文档 `/dev/star/guides/ai.html`）
2. AstrBot 内置 function calling 的 tool schema 格式与自研 `plugin_manager` 是否兼容？
3. AstrBot 内置网页搜索（`/use/websearch.html`）能否替代 Tavily？
4. `memory_plugin` 的 tools 是否可通过 `memory_tools` Star + IPC 实现？

**决策路径**：
- **路径 A**（优先）：AstrBot 内置 function calling 支持自定义 tool → `plugin_bridge` Star 注册现有 tools → 验证行为一致
- **路径 B**（备选）：AstrBot 内置不支持自定义 tool → `plugin_bridge` Star 自行实现 tool 调用循环 → 保留 `plugins/manager.py` 逻辑
- **路径 C**（降级）：function calling 行为差异无法弥合 → 阶段二发现后回退到 NoneBot 模式评估

**评估截止**：阶段一 Star 补全前完成，输出决策记录。

### 5.2 复杂度汇总

| 复杂度 | 数量 | 说明 |
|--------|------|------|
| 低 | 8 | 内置替代或已实现 |
| 中 | 14 | 需补全插件逻辑 |
| 高 | 5 | 需深度移植（context_assembler, ocr_image, plugin_bridge, function calling, message_queue） |
| 无 | 4 | 保留不变 |

---

## 6. 目标架构设计

### 6.1 目标架构（迁移后）

```
┌──────────────────────────────────────────────────────────────┐
│                    Web UI (Svelte 4)  :8094                   │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST API (X-API-Key)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              管理服务器 (FastAPI)  :8093                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  routers/: config·bots·chat·memory·usage·plugins·logs   │ │
│  │           debug·health(+/metrics)·interactions·internal    │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  core_logic/: knowledge_manager·interaction_recorder    │ │
│  │              persona_manager·context_builder·sqlite_pool │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  llm_providers/: (仅 /chat WebUI 端点使用)              │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  security/: input_sanitizer·output_encoder·secrets_mgr   │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  middleware/: rate_limit·request_id·metrics              │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  astrbot_manager.py: 子进程生命周期管理                   │ │
│  │  astrbot_config_gen.py: 配置生成                          │ │
│  └─────────────────────────┬───────────────────────────────┘ │
│                            │ /internal IPC                    │
│                            ▼                                  │
│            ┌──────────────────────────────────┐               │
│            │  AstrBot 子进程 (每 bot 一个)     │               │
│            │  python -m astrbot run           │               │
│            │  --config config.yml            │               │
│            │                                  │               │
│            │  ┌────────────────────────────┐ │               │
│            │  │  astrbot_stars/ (15个)      │ │               │
│            │  │  trigger → context_assembler│ │               │
│            │  │  → knowledge_bridge → persona│ │               │
│            │  │  → ocr_image → LLM 调用      │ │               │
│            │  │  → streaming_respond        │ │               │
│            │  │  → post_process → usage_track│ │               │
│            │  │  → interaction_record        │ │               │
│            │  └────────────────────────────┘ │               │
│            │                                  │               │
│            │  Discord (py-cord) · LLM Provider│               │
│            └──────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 关键设计决策

#### D1: LLM 调用归属

**决策**：Discord 消息流的 LLM 调用由 AstrBot 子进程内的内置 provider 执行；管理服务器的 `llm_providers/` 仅保留供 WebUI `/chat` 端点使用。

**理由**：
- AstrBot 内置 provider 已支持 OpenAI/Anthropic/Gemini 等，配置直接写入 `config.yml`
- 避免跨进程 LLM 调用的延迟和复杂性
- `/chat` WebUI 端点需要直接调用 LLM（不经过 Discord），保留 `llm_providers/` 合理

**影响**：
- `astrbot_config_gen.py` 已将 provider 配置（api_key, model, base_url）写入 `config.yml` ✅
- 管理服务器 `llm_providers/factory.py` 保留，但仅被 `routers/chat.py` 调用
- 需确认 AstrBot provider 是否支持本项目所有 provider（OpenAI 兼容协议的 11 家 + Anthropic + Google + xAI）

#### D2: 知识库存储归属

**决策**：知识库 SQLite（FTS5 + embedding）保留在管理服务器侧，AstrBot 子进程通过 `/internal/knowledge/recall` 和 `/internal/knowledge/ingest` IPC 访问。

**理由**：
- 避免多子进程并发写入 SQLite 的冲突
- 保留现有 FTS5 + embedding 混合检索逻辑（不迁移到 AstrBot faiss）
- 知识库数据与 bot 配置同目录管理，便于备份

**影响**：
- `knowledge_bridge` Star 需补全 recall 结果注入 context + ingest 调用
- `post_process` Star 需补全 `<memory>`/`<user_info>` 标签的 ingest IPC 调用

#### D3: 上下文构建归属

**决策**：上下文构建由 `context_assembler` Star 在 AstrBot 子进程内完成，通过 `/internal/config` IPC 获取完整 bot 配置（trigger_keywords, role_based_config, scoped_prompts, user_options 等）。

**理由**：
- 上下文构建需要会话历史（AstrBot `conversation_manager` 提供）
- system prompt 解析需要 role-based config 和 scoped prompts（来自管理服务器 config）
- memory 注入需要 knowledge recall（来自 `/internal` IPC）

**影响**：
- `context_assembler` Star 需补全：memory 注入、role-based config、完整 history 构建
- 需通过 `/internal/config` 获取完整配置（当前 Star 用 `self.context.get_config()` 只拿到 AstrBot config.yml）

#### D4: WebUI 定位

**决策**：保留现有 Svelte 前端 + FastAPI 后端作为面向用户的唯一 WebUI。AstrBot 内置 WebUI（端口 6185）不暴露给最终用户。

**理由**：
- 现有 WebUI 已提供配置管理、日志查看、调试、用量统计等完整功能
- AstrBot 内置 WebUI 主要用于 AstrBot 自身配置，本项目通过 `config.yml` 生成器控制
- 避免双 WebUI 的用户困惑

**影响**：
- `docker-compose.yml` 中 AstrBot 子进程的 6185 端口不映射到宿主机
- 前端 `AstrBotMigration.svelte` 切换 UI 移除（不再需要双模式切换）

#### D5: 消息处理流程

**决策**：AstrBot Star 插件链按优先级顺序处理消息，替代 NoneBot 的 `on_message` matcher + `MessageQueue`。

**目标流程**：
```
Discord 消息 → AstrBot 事件总线
  → trigger Star:        判断是否唤醒（@mention/reply/keyword/user_options）
  → context_assembler:   构建 system_prompt + history
  → knowledge_bridge:    recall memories → 注入 system_prompt
  → persona:             获取 user persona → 注入 system_prompt
  → ocr_image:           图片 OCR（如多模态禁用）
  → [AstrBot LLM 调用]   AstrBot 内置 provider
  → streaming_respond:   清理 thinking/DSML + 分片
  → post_process:        <memory>/<user_info> 标签 ingest
  → usage_tracker:       记录 token 用量 → /internal/usage/track
  → interaction_recorder: 记录交互 → /internal/interaction/record
  → debug_capture:       捕获调试数据
  → Discord 发送响应
```

**并行/串行**：
- `auto_interject` 和 `repeat_parrot` 是独立触发路径，不经过主 LLM 流程
- `message_queue` Star 负责频道级串行化（替代 Redis 消息锁）

#### D6: provider_mode 移除

**决策**：移除 `provider_mode` 双模式分支，AstrBot 成为唯一路径。

**影响**：
- `bot_instance.py`：删除 `_start_nonebot`/`_stop_nonebot`/`_nonebot_reconnect_loop`/`_reconnect_nonebot`，`start()` 直接调用 `_start_astrbot()`
- `config_cache.py` `DEFAULT_CONFIG`：移除 `provider_mode` 字段
- 前端 `AstrBotMigration.svelte`：删除
- `astrbot_config_gen.py`：保留（生成 config.yml）
- `to_status_dict()`：移除 `provider_mode` 字段

---

## 7. 分阶段迁移计划

### 阶段一：Star 插件补全（不破坏 legacy）

**目标**：将 15 个 Star 插件从骨架补全至功能完整，使其能完全替代 legacy pipeline。

**原则**：本阶段不修改 legacy 代码，不删除任何文件。所有工作在 `astrbot_stars/` 目录内进行。

**任务清单**：见 [第 8 节](#8-star-插件补全清单)

**验证**：以 `provider_mode=astrbot` 启动 bot，全功能测试（触发、上下文、知识库、OCR、自动化、用量、交互记录）。

### 阶段二：集成测试与验证

**目标**：在双模式并存下，验证 AstrBot 模式全功能正确性。

**任务**：
1. 编写 AstrBot 模式集成测试（模拟 Discord 消息 → AstrBot 子进程 → IPC 回调 → 验证管理服务器状态）
2. E2E 模拟测试适配（`simulations/simulate.py` 支持 AstrBot 模式）
3. 逐 bot 批量功能验证
4. 性能基准对比（AstrBot 模式 vs NoneBot 模式的延迟、吞吐）

**验证标准**：AstrBot 模式下所有 F1-F30 功能项行为与 NoneBot 模式一致。

### 阶段三：删除 Legacy 代码

**目标**：移除 NoneBot legacy 路径、依赖、双模式分支。

**任务清单**：见 [第 9 节](#9-legacy-代码删除清单)

**验证**：
- `pip install` 无 nonebot 依赖
- 代码中无 `nonebot` / `nb_plugins` 引用
- `provider_mode` 字段完全移除
- 所有测试通过

### 阶段四：协议变更与部署切换

**目标**：项目协议从 MIT 变更为 AGPL-3.0，部署架构调整。

**任务**：
1. LICENSE 文件变更为 AGPL-3.0
2. README 更新协议声明
3. `docker-compose.yml` 调整（见 [第 12 节](#12-部署架构变更)）
4. `requirements.txt` 移除 nonebot/discord.py 依赖，添加 `astrbot` 依赖
5. 文档更新（README 架构图、技术栈表）

---

## 8. Star 插件补全清单

### 8.0 AstrBot 扩展模块（非 Star）

`backend/astrbot_stars/` 目录下除 15 个 Star 插件外，还存在一个 `providers/xai_provider.py` 模块。该模块**不是 Star 插件**，而是为 AstrBot 扩展 xAI（Grok）provider 支持的自定义 provider 适配器。

**分析**：
- AstrBot 内置 provider 列表（pyproject.toml 依赖）包含 `openai`、`anthropic`、`google-genai`、`dashscope` 等，但**未明确列出 xAI/Grok SDK**
- 本项目支持 xAI Grok（`llm_providers/xai_provider.py` 使用 `xai-sdk`）
- `astrbot_stars/providers/xai_provider.py` 的存在暗示 AstrBot 内置 provider 可能不完整支持 xAI，需要自定义扩展

**迁移影响**：
- 如果 AstrBot 4.26.7 内置支持 xAI（通过 OpenAI 兼容协议或原生 SDK），该文件可删除
- 如果不支持，该文件需保留并确保被 AstrBot 正确加载为自定义 provider
- **阶段二验证项**：测试 xAI provider 在 AstrBot 模式下是否可用，决定该文件保留或删除
- **风险 R2 关联**：该文件的存在使 R2（xAI provider 支持）的概率从"低"调整为"中"

### 8.1 优先级分组

| 优先级 | Star 插件 | 依赖关系 |
|--------|-----------|----------|
| P0（核心链路） | trigger, context_assembler, knowledge_bridge, streaming_respond | trigger → context_assembler → knowledge_bridge → LLM → streaming_respond |
| P1（数据记录） | usage_tracker, interaction_recorder, post_process | 依赖 LLM 响应完成 |
| P2（增强功能） | persona, ocr_image, auto_interject, repeat_parrot | 独立功能模块 |
| P3（基础设施） | message_queue, plugin_bridge, memory_tools, debug_capture | 辅助/兼容 |

### 8.2 详细补全规格

#### 8.2.1 trigger Star（P0）

**现状**：60% — mention/reply/keyword 检测已实现，user_options block 是 stub。

**补全项**：
- [ ] 实现 user_options block 检查：通过 `/internal/config` 获取 `user_options` 配置，调用 `is_user_blocked_from_response` 逻辑（需移植到 Star 或通过 IPC）
- [ ] 确认 `event.is_at_or_wake_command` 在 AstrBot Discord 适配器中的行为与 NoneBot `to_me` 一致
- [ ] 确认 reply-to-bot 检测：`event.message_obj.raw_message.reference` 在 py-cord 中的字段路径
- [ ] 设置 `event.set_extra("trigger_source", trigger_source)` 供后续 Star 使用
- [ ] 未触发时停止后续 Star 执行（`event.stop_event()` 或等效 API）

**参考实现**：`nb_plugins/core_llm_bot/matchers.py` 第 124-194 行

#### 8.2.2 context_assembler Star（P0）

**现状**：40% — system prompt 解析 + history 获取骨架已实现，缺 memory 注入、role-based 完整逻辑。

**补全项**：
- [ ] 通过 `/internal/config` IPC 获取完整 bot 配置（当前 `self.context.get_config()` 只拿到 AstrBot config.yml，需获取 trigger_keywords, role_based_config, scoped_prompts, user_options, channel_context_settings, memory_context_settings）
- [ ] 实现 role-based config 解析：根据用户角色匹配 `role_based_config`（需通过 Discord API 获取用户角色，或通过 event 附件传递）
- [ ] 实现 scoped prompts（guild/channel 级别 system prompt 覆盖）— 骨架已实现，需确认 `event.get_group_id()` / `event.get_session_id()` 返回值与 guild_id/channel_id 映射
- [ ] 实现 memory 注入：调用 `knowledge_bridge` 的 recall 结果，注入到 system_prompt（`<knowledge><long_term_memory>...</long_term_memory></knowledge>` 格式）
- [ ] 实现 history 构建：使用 `self.context.conversation_manager.get_history()`，按 `context_mode`（channel/memory）和 `message_limit`/`char_limit` 配置截断
- [ ] 实现 `injected_data`（plugin_append_blocks）注入到 user message

**参考实现**：
- `nb_plugins/core_llm_bot/context.py` + `app/handlers/context_assembler.py` `build_full_context()`
- `nb_plugins/core_llm_bot/pipeline.py` 第 62-91 行（memory 注入逻辑）

#### 8.2.3 knowledge_bridge Star（P0）

**现状**：30% — 只 recall，recall 结果未注入 context，无 ingest。

**补全项**：
- [ ] recall 结果注入：将 `memories` 通过 `event.set_extra("memories", memories)` 传递给 `context_assembler`
- [ ] recall 参数配置：从 `/internal/config` 获取 `auto_memory_recall_top_k`, `auto_memory_recall_char_limit`, `auto_memory_recall_max_age_days`
- [ ] recall 查询文本：使用 `event.get_message_str()` 作为 query
- [ ] 错误降级：IPC 失败时返回空列表，不阻断主流程
- [ ] 连接池复用：`aiohttp.ClientSession` 应复用而非每次创建（性能优化）

**参考实现**：`nb_plugins/core_llm_bot/pipeline.py` 第 69-91 行

#### 8.2.4 streaming_respond Star（P0）

**现状**：70% — 清理/分片已实现，需确认接入响应流程。

**补全项**：
- [ ] 确认 `event.get_result().message` 在 AstrBot 响应流程中的时机（LLM 响应完成后、发送前）
- [ ] 确认消息分片后多 chunk 发送：AstrBot 是否自动处理 2000 字限制，还是需要 Star 手动分片发送
- [ ] 确认流式响应：AstrBot 内置 provider 的流式响应是否需要 Star 介入，还是 AstrBot 自动处理
- [ ] 确认 `reply_message` 行为：AstrBot Discord 适配器是否自动回复引用

**参考实现**：`nb_plugins/core_llm_bot/rendering.py` + `pipeline.py` 第 189-201 行

#### 8.2.5 post_process Star（P1）

**现状**：20% — `<memory>`/`<user_info>` 标签解析已实现，ingest 是 TODO。

**补全项**：
- [ ] 实现 `<memory>` 标签 ingest：POST `/internal/knowledge/ingest`（type=memory）
- [ ] 实现 `<user_info>` 标签 ingest：POST `/internal/knowledge/ingest`（type=world_book）
- [ ] ingest 参数：content, timestamp, user_id, user_name, source, channel_id
- [ ] 清理标签后的文本写回 `result.message`
- [ ] 确认执行时机：LLM 响应清理后、发送前

**参考实现**：`nb_plugins/core_llm_bot/pipeline.py` 第 264-343 行 `process_knowledge_tags_from_context`

#### 8.2.6 usage_tracker Star（P1）

**现状**：5% — 完全是 `pass`。

**补全项**：
- [ ] 获取 LLM usage 数据：从 AstrBot LLM 响应中提取 input_tokens/output_tokens（AstrBot provider 返回的 usage 信息）
- [ ] 无 usage 数据时降级估算：使用 token_calculator（需移植或通过 IPC）
- [ ] POST `/internal/usage/track`：provider, model, input_tokens, output_tokens, user_id, user_name, user_display_name, role_id, role_name, channel_id, channel_name, guild_id, guild_name
- [ ] role-based 配额检查：通过 `/internal/config` 获取 `role_based_config`，调用 usage_manager 逻辑（需移植或 IPC）
- [ ] 确认执行时机：LLM 响应完成后

**参考实现**：`nb_plugins/core_llm_bot/pipeline.py` 第 209-234 行

#### 8.2.7 interaction_recorder Star（P1）

**现状**：未确认 — 需检查 `astrbot_stars/interaction_recorder/star.py`

**补全项**：
- [ ] 记录用户消息：POST `/internal/interaction/record`（is_bot_reply=False）
- [ ] 记录 bot 回复：POST `/internal/interaction/record`（is_bot_reply=True）
- [ ] 记录图片：如有图片附件，调用 `/internal/interaction/record` 的图片记录功能
- [ ] 参数：bot_id, guild_id, channel_id, member_id, member_name, role_id, content, message_id, attachments, is_bot_reply, trigger_source
- [ ] 确认执行时机：用户消息接收时 + bot 回复发送后

**参考实现**：`nb_plugins/core_llm_bot/matchers.py` 第 87-122 行 + `pipeline.py` 第 346-409 行

#### 8.2.8 persona Star（P2）

**现状**：30% — 获取 persona 但只 `set_extra`，未注入 system prompt。

**补全项**：
- [ ] 将 persona 数据注入 system_prompt（或通过 `event.set_extra` 传递给 `context_assembler` 处理）
- [ ] 确认 persona 注入格式：当前 legacy 是直接读 `config.user_personas`，IPC 端点已提供 `/internal/persona/{user_id}`
- [ ] 确认与 `context_assembler` 的协作：persona 应在 context_assembler 之前执行，或 context_assembler 内部调用 persona 获取

**参考实现**：`app/handlers/context_assembler.py` 中 persona 注入逻辑

#### 8.2.9 ocr_image Star（P2）

**现状**：未确认 — 需检查 `astrbot_stars/ocr_image/star.py`

**补全项**：
- [ ] 检测图片附件：从 `event.message_obj` 提取图片附件
- [ ] 下载图片：使用 aiohttp 下载 Discord 附件
- [ ] 多模态判断：如果 `llm_is_multimodal=True`，图片直接传给 LLM；否则 OCR
- [ ] OCR 调用：通过管理服务器 `/internal` 或直接调用 OCR provider（需确认架构）
- [ ] OCR 结果注入：将识别文本注入到 user message

**参考实现**：`nb_plugins/core_llm_bot/pipeline.py` 第 59-68 行 + `app/handlers/image_processor.py`

#### 8.2.10 auto_interject Star（P2）

**现状**：未确认 — 需检查 `astrbot_stars/auto_interject/star.py`

**补全项**：
- [ ] 频道消息计数：按 channel_id 维护消息计数
- [ ] 触发条件：消息数达到 `auto_interject_interval` 且内容长度 >= `auto_interject_min_length`
- [ ] 触发后执行 LLM pipeline（主动发言）
- [ ] 状态重置：触发后或异常后重置计数

**参考实现**：`nb_plugins/core_llm_bot/automation.py` `track_auto_interject`

#### 8.2.11 repeat_parrot Star（P2）

**现状**：未确认 — 需检查 `astrbot_stars/repeat_parrot/star.py`

**补全项**：
- [ ] 重复消息检测：按 channel_id 维护重复连续计数
- [ ] 触发条件：同一消息连续出现 `repeat_parrot_threshold` 次
- [ ] 选项：case_sensitive, trim_whitespace, min_length, require_multiple_users
- [ ] 触发后发送重复内容（不经过 LLM）
- [ ] 状态重置

**参考实现**：`nb_plugins/core_llm_bot/automation.py` `track_repeat_parrot`

#### 8.2.12 message_queue Star（P3）

**现状**：未确认 — 需检查 `astrbot_stars/message_queue/star.py`

**补全项**：
- [ ] 频道级串行化：同一 channel_id 的消息按顺序处理，避免并发 LLM 调用
- [ ] 替代 Redis 消息锁：`pipeline.py` 中的 `get_redis().set(lock_key)` 逻辑
- [ ] 队列满时返回 "Bot is busy" 提示

**参考实现**：`nb_plugins/core_llm_bot/matchers.py` `MessageQueue` + `_ensure_channel_processor`

#### 8.2.13 plugin_bridge Star（P3）

**现状**：未确认 — 需检查 `astrbot_stars/plugin_bridge/star.py`

**补全项**：
- [ ] 加载用户自定义插件（`config.plugins`）
- [ ] 插件消息处理：`process_message` → 返回 consumed / append / none
- [ ] 插件工具调用：`get_all_tools()` / `get_all_tool_functions()` 供 LLM function calling
- [ ] 插件配置转发：从 `/internal/config` 获取 `plugins` 配置

**参考实现**：`plugins/manager.py` + `nb_plugins/core_llm_bot/pipeline.py` 第 118-119 行

#### 8.2.14 memory_tools Star（P3）

**现状**：未确认 — 需检查 `astrbot_stars/memory_tools/star.py`

**职责定义**（明确边界）：
`memory_tools` Star 提供 **LLM 主动调用的 function calling tools**，对应 `plugins/memory_plugin.py` 的工具集。与 `knowledge_bridge`（被动 recall）和 `post_process`（被动 ingest）的职责区分：

| Star | 触发方式 | 职责 | 对应 Legacy |
|------|----------|------|-------------|
| `knowledge_bridge` | 被动（每条消息自动） | recall 相关记忆注入 context | `pipeline.py` memory recall |
| `post_process` | 被动（LLM 响应后自动） | 提取 `<memory>`/`<user_info>` 标签 ingest | `pipeline.py` `_process_knowledge_tags` |
| `memory_tools` | **主动（LLM function calling）** | 提供 `add_to_memory`/`search_memory`/`add_to_world_book` 工具供 LLM 调用 | `plugins/memory_plugin.py` |

**补全项**：
- [ ] 注册 function calling tools：`add_to_memory`、`search_memory`、`add_to_world_book`（对应 `plugins/memory_plugin.py` 的 tool 定义）
- [ ] tool 实现通过 IPC 调用管理服务器：`add_to_memory` → `POST /internal/knowledge/ingest`（type=memory）；`search_memory` → `GET /internal/knowledge/recall`；`add_to_world_book` → `POST /internal/knowledge/ingest`（type=world_book）
- [ ] tool schema 定义：参数名、类型、描述与 `plugins/memory_plugin.py` 保持一致
- [ ] 确认 AstrBot function calling 注册机制（见 F23 评估方案）

**参考实现**：`plugins/memory_plugin.py`（tool 定义）+ `nb_plugins/memory_tools/__init__.py`（NoneBot 版本）

#### 8.2.15 debug_capture Star（P3）

**现状**：未确认 — 需检查 `astrbot_stars/debug_capture/star.py`

**补全项**：
- [ ] 捕获调试数据：trigger_message_id, channel_id, guild_id, user_id, system_prompt, history, llm_messages, raw_response, cleaned_response, usage
- [ ] 存储方式：通过 `/internal` IPC 或本地存储（需确认）
- [ ] 供 WebUI Debugger 页面查询

**参考实现**：`nb_plugins/core_llm_bot/pipeline.py` 第 167-187 行 `add_capture`

---

## 9. Legacy 代码删除清单

### 9.1 文件/目录删除

| 路径 | 类型 | 说明 |
|------|------|------|
| `backend/nb_plugins/` | 目录 | 整个 NoneBot 插件目录（core_llm_bot, search_plugin, configurable_tools, memory_tools） |
| `backend/app/discord_patch.py` | 文件 | NoneBot Discord 适配器 emoji 修复 |
| `backend/app/config_bridge.py` | 文件 | NoneBot `.env` 文件生成 |
| `frontend/src/components/AstrBotMigration.svelte` | 文件 | 双模式切换 UI（迁移完成后不需要） |

### 9.2 代码修改

| 文件 | 修改内容 |
|------|----------|
| `backend/app/main.py` | 移除 `nonebot.init()` / `driver.register_adapter(DiscordAdapter)` / `nonebot.load_plugins("nb_plugins")` / `discord_patch` 导入 / `config_bridge.generate_env_file()`；保留 FastAPI lifespan 但初始化 `AstrBotProcessManager` |
| `backend/app/bot_instance.py` | 删除 `_start_nonebot` / `_stop_nonebot` / `_nonebot_reconnect_loop` / `_reconnect_nonebot`；`start()` 直接调用 `_start_astrbot()`；移除 `provider_mode` property（第 41-43 行）和 `to_status_dict()` 中的 `provider_mode` 字段。**注意：`DEFAULT_CONFIG` 不含 `provider_mode`，该字段是运行时从 per-bot config 读取的 `@property`，删除目标在 `bot_instance.py` 而非 `config_cache.py`** |
| `backend/app/routers/bots.py` | `get_adapter_status`（第 123 行 `state.nonebot_driver`）改为查询 `astrbot_process_manager.get_status()`，移除 `nonebot_driver` 依赖 |
| `backend/app/routers/state.py` | 第 16 行 `driver = state.nonebot_driver` — 移除 NoneBot driver 依赖，改为查询 AstrBot 子进程状态 |
| `backend/app/routers/user_options.py` | 第 131 行 `driver = getattr(state, "nonebot_driver", None)` — 移除 NoneBot driver 依赖，用户屏蔽检查改为通过 IPC 或管理服务器本地逻辑 |
| `backend/app/state.py` | 移除 `nonebot_driver` 代理，添加 `astrbot_process_manager` 单例 |
| `backend/app/app_context.py` | 移除 `nonebot_driver` 字段，添加 `astrbot_process_manager` 字段 |
| `backend/app/core_logic/context_builder.py` | 第 8 行 `import discord` — 移除 discord.py 依赖，改为通过 IPC 传递 Discord 上下文数据（guild/channel/user ID），或抽象为平台无关的上下文对象 |
| `backend/app/core_logic/persona_manager.py` | 第 6 行 `import discord` — 同上，移除 discord.py 依赖 |
| `backend/app/core_logic/usage_manager.py` | 第 10 行 `import discord` — 同上，移除 discord.py 依赖 |
| `backend/app/core_logic/user_validator.py` | 第 4 行 `import discord` — 同上，移除 discord.py 依赖 |
| `backend/requirements.txt` | 移除 `nonebot2` / `nonebot-adapter-discord` / `nonebot-adapter-onebot` / `discord.py`；添加 `astrbot`（或通过子进程方式不需要安装到管理服务器） |
| `frontend/src/locales/zh.js` + `en.js` | 移除 `astrBotMigration.*` i18n key |
| `frontend/src/pages/ConfigPanel.svelte` | 移除 `AstrBotMigration` 组件导入和使用 |
| `README.md` | 更新架构图、技术栈表（NoneBot2 → AstrBot） |

### 9.3 依赖变更

**移除**：
```
nonebot2==2.5.0
nonebot-adapter-discord==1.1.9
nonebot-adapter-onebot==2.4.6
discord.py==2.7.1
```

**新增**（如管理服务器需要直接 import astrbot 模块）：
```
astrbot>=4.26.7
```

**注意**：如果 AstrBot 仅作为子进程运行（`python -m astrbot run`），管理服务器不需要安装 astrbot 包，只需在运行环境中安装。需确认 `astrbot_manager.py` 的 `sys.executable, "-m", "astrbot"` 是否要求管理服务器环境内安装 astrbot。

**建议**：在 Docker 镜像中安装 astrbot 到管理服务器环境，使子进程能复用同一 Python 环境。

---

## 10. 管理服务器适配

### 10.1 保留不变

| 模块 | 说明 |
|------|------|
| `routers/config.py` | Bot 配置 CRUD |
| `routers/chat.py` | WebUI 直接对话（使用 `llm_providers/`） |
| `routers/memory.py` | 知识库管理 |
| `routers/usage.py` | 用量统计查询 |
| `routers/plugins.py` | 插件管理 |
| `routers/logs.py` | 日志查看 |
| `routers/debug.py` | 调试数据 |
| `routers/interactions.py` | 交互记录查询 |
| `routers/health.py` | 健康检查 |
| `routers/internal.py` | IPC 端点（AstrBot 子进程调用） |
| `core_logic/*` | 知识库、交互记录、persona、上下文构建、SQLite 池 |
| `llm_providers/*` | 仅 `/chat` 端点使用 |
| `security/*` | 输入消毒、输出编码、日志脱敏、凭据加密 |
| `middleware/*` | 速率限制、RequestID、Metrics |

### 10.2 需修改

| 模块 | 修改 |
|------|------|
| `main.py` | 移除 NoneBot 初始化，改为初始化 `AstrBotProcessManager` |
| `bot_instance.py` | 移除 NoneBot 路径和 `provider_mode` |
| `routers/bots.py` | `get_adapter_status` 改为查询 AstrBot 子进程状态 |
| `state.py` / `app_context.py` | 移除 `nonebot_driver`，添加 `astrbot_process_manager` |

### 10.3 IPC 端点扩展评估

当前 `/internal` 端点：
- ✅ `GET /{bot_id}/knowledge/recall`
- ✅ `POST /{bot_id}/knowledge/ingest`
- ✅ `POST /{bot_id}/usage/track`
- ✅ `POST /{bot_id}/interaction/record`
- ✅ `GET /{bot_id}/config`
- ✅ `GET /{bot_id}/persona/{user_id}`

**可能需新增**：
- `POST /{bot_id}/interaction/record_images` — 图片记录（当前 `interaction_record` 不含图片）
- `GET /{bot_id}/user_options/check` — 用户屏蔽检查（当前 trigger Star 是 stub）
- `POST /{bot_id}/debug/capture` — 调试数据上报（当前 debug_capture Star 未确认）

---

## 11. 数据迁移方案

### 11.1 无需迁移的数据

| 数据 | 位置 | 说明 |
|------|------|------|
| Bot 配置 | `data/bots/{bot_id}/config.json` | 管理服务器管理，AstrBot 通过 IPC 读取 |
| 知识库 | `data/bots/{bot_id}/knowledge.sqlite` | 管理服务器管理，AstrBot 通过 IPC 访问 |
| 用量数据 | `data/bots/{bot_id}/usage_data.json` | 管理服务器管理 |
| 交互记录 | `data/interactions/` | 管理服务器管理 |

**理由**：管理服务器保留所有数据存储，AstrBot 子进程无状态，通过 IPC 访问。无需数据迁移。

### 11.2 需生成的数据

| 数据 | 位置 | 生成方式 |
|------|------|----------|
| AstrBot 配置 | `data/bots/{bot_id}/astrbot/config.yml` | `astrbot_config_gen.py` 自动生成 |
| AstrBot 日志 | `data/bots/{bot_id}/astrbot/logs/astrbot.log` | 子进程运行时生成 |

### 11.3 会话历史

**风险**：NoneBot 模式的会话历史存储在管理服务器侧（`context_builder.py`），AstrBot 模式的会话历史由 `conversation_manager` 管理（AstrBot 内部存储）。

**决策**：迁移时**不保留** NoneBot 模式的会话历史。AstrBot 模式从空历史开始。如需保留，需编写迁移脚本将 NoneBot 历史转换为 AstrBot `conversation_manager` 格式（**评估为低优先级，不推荐**）。

---

## 12. 部署架构变更

### 12.1 当前 docker-compose.yml

```yaml
services:
  redis: ...
  backend: ...  # FastAPI + NoneBot2 同进程
  frontend: ... # Svelte
```

### 12.2 目标 docker-compose.yml

```yaml
services:
  redis:
    image: "redis:alpine"
    restart: always
    volumes:
      - ./redis_data:/data

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    restart: always
    volumes:
      - ./data:/app/data
    ports:
      - "8093:8000"
    depends_on:
      - redis
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - FAIL_ON_REDIS_ERROR=true
      - HTTP_PROXY=${HTTP_PROXY:-}
      - HTTPS_PROXY=${HTTPS_PROXY:-}
      - NO_PROXY=${NO_PROXY:-localhost,127.0.0.1,backend,frontend,redis}

  frontend:
    build: ./frontend
    restart: always
    ports:
      - "8094:8080"
    depends_on:
      - backend
```

**变更说明**：
- backend 容器内安装 `astrbot` 包，子进程通过 `python -m astrbot run` 启动
- AstrBot WebUI 端口 6185 **不映射**到宿主机（仅容器内部使用）
- 数据卷 `./data` 已包含 `data/bots/{bot_id}/astrbot/` 子目录
- 无需独立的 AstrBot 容器（子进程方式，与管理服务器同容器）

### 12.3 Dockerfile 变更

`backend/Dockerfile` 需：
1. 安装 `astrbot` 包（`pip install astrbot==4.26.7` 或 `uv tool install astrbot --python 3.12`），**锁定版本**以避免 Star API 破坏性变更（见风险 R8）
2. 确保 `python -m astrbot run` 可执行
3. Python 版本升级到 3.12+（AstrBot 要求 `requires-python = ">=3.12"`）

**注意**：当前项目 Python 3.11+，AstrBot 要求 3.12+。需升级基础镜像。

### 12.4 环境变量

无新增环境变量。AstrBot 配置通过 `astrbot_config_gen.py` 从 bot config.json 生成。

---

## 13. 协议变更（MIT → AGPL-3.0）

### 13.1 原因

AstrBot 采用 **AGPL-3.0-or-later** 协议。AGPL-3.0 是强 copyleft 协议：
- 任何分发或网络服务提供（SaaS）基于 AstrBot 的衍生作品，必须以 AGPL-3.0 开源全部代码
- 与 MIT 协议不兼容（MIT 代码可以并入 AGPL 项目，但 AGPL 代码不能并入 MIT 项目）

本项目通过子进程方式调用 AstrBot，且 `astrbot_stars/` 导入了 `astrbot.api` 模块，构成衍生作品关系。因此本项目必须从 MIT 变更为 AGPL-3.0。

### 13.2 变更内容

| 文件 | 变更 |
|------|------|
| `LICENSE` | 替换为 AGPL-3.0 全文（https://www.gnu.org/licenses/agpl-3.0.txt） |
| `README.md` | 协议声明从 "MIT License" 改为 "GNU Affero General Public License v3.0 or later" |
| 代码文件头 | 推荐添加 SPDX 协议标识（`SPDX-License-Identifier: AGPL-3.0-or-later`），确保所有贡献者知情 |

### 13.3 影响评估

| 影响项 | 说明 |
|--------|------|
| 商业使用 | AGPL-3.0 允许商业使用，但网络服务提供需开源衍生代码 |
| 二次分发 | 任何分发必须开源全部代码并保持 AGPL-3.0 |
| SaaS 部署 | 通过网络提供服务（如部署给他人使用）需开源 |
| 个人自用 | 无影响 |
| 贡献者 | 贡献的代码自动以 AGPL-3.0 授权 |

### 13.4 版权声明

```
Copyright (C) 2025 RainyN0077 <gotiyu0407@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.
```

---

## 14. 风险评估与回滚方案

### 14.1 风险矩阵

| # | 风险 | 严重度 | 概率 | 缓解措施 |
|---|------|--------|------|----------|
| R1 | AstrBot Discord 适配器行为与 NoneBot 不一致（@mention/reply 检测） | 高 | 中 | 阶段二集成测试覆盖所有触发场景 |
| R2 | AstrBot LLM provider 不支持本项目所有 provider（如 xAI） | 高 | 中 | 阶段二验证 12 家 provider；`astrbot_stars/providers/xai_provider.py` 的存在暗示 xAI 可能需自定义扩展；AstrBot 支持 "自定义 OpenAI 兼容" 可作为降级方案 |
| R3 | Star 插件事件顺序不可控，导致上下文构建错误 | 高 | 中 | 确认 AstrBot Star 优先级机制；用 `event.set_extra` 传递数据 |
| R4 | IPC 延迟导致响应变慢（每条消息多次 HTTP 调用） | 中 | 中 | 连接池复用；批量 IPC；异步非阻塞 |
| R5 | AstrBot 子进程崩溃后自动重连丢失会话状态 | 中 | 中 | `astrbot_manager.py` 已有重连机制；会话历史由 conversation_manager 持久化 |
| R6 | Python 3.12 升级导致依赖不兼容 | 中 | 低 | 阶段二在 3.12 环境全量测试 |
| R7 | AGPL-3.0 协议变更影响项目接受度 | 中 | 高 | 在 README 明确声明；评估是否可接受 |
| R8 | AstrBot 版本升级导致 Star API 破坏性变更 | 中 | 中 | 锁定 AstrBot 版本；Star 代码标注兼容版本 |
| R9 | function calling 行为差异（AstrBot 内置 vs 自研 plugin_manager） | 高 | 中 | 阶段二验证工具调用场景；可能保留 plugin_bridge Star |
| R10 | OCR 功能在 AstrBot 子进程内无法访问管理服务器 OCR 服务 | 中 | 中 | OCR 通过 IPC 或直接调用 OCR provider |

### 14.2 回滚方案

**阶段一/二回滚**（Star 补全/集成测试阶段）：
- Legacy 路径完整保留，`provider_mode=nonebot` 可随时切回
- 无破坏性变更，回滚零成本

**阶段三回滚**（删除 Legacy 阶段）：
- 在独立分支执行删除操作
- 如需回滚，revert 该分支的提交
- 保留删除前的 git tag

**阶段四回滚**（协议/部署切换）：
- LICENSE 变更可 revert
- docker-compose 变更可 revert
- requirements.txt 变更可 revert

**建议**：阶段三和阶段四在独立分支 `astrbot-cutover` 上执行，经完整验证后再合并到主分支。

---

## 15. 验收标准

### 15.1 阶段一验收（Star 插件补全）

| 验收项 | 标准 |
|--------|------|
| 15 个 Star 插件功能完整 | 每个 Star 的补全项全部完成 |
| Star 单元测试 | 每个 Star 有对应单元测试，覆盖率 >=80% |
| IPC 端点测试 | `/internal` 端点测试通过 |
| AstrBot 模式启动 | `provider_mode=astrbot` 能成功启动 bot |

### 15.2 阶段二验收（集成测试）

| 验收项 | 标准 |
|--------|------|
| 功能对等 | F1-F30 所有功能项在 AstrBot 模式下行为与 NoneBot 模式一致 |
| E2E 测试 | `simulations/simulate.py` AstrBot 模式全通过 |
| 性能基准 | AstrBot 模式响应延迟与 NoneBot 模式差距 <20% |
| 12 家 provider | 全部 provider 在 AstrBot 模式下可调用 |
| 多 bot 实例 | 多 bot 并发运行无冲突 |

### 15.3 阶段三验收（Legacy 删除）

| 验收项 | 标准 |
|--------|------|
| 代码无 nonebot 引用 | `grep -ri nonebot backend/` 无结果 |
| 代码无 nb_plugins 引用 | `grep -ri nb_plugins backend/` 无结果 |
| provider_mode 移除 | `grep -ri provider_mode backend/ frontend/` 无结果 |
| 依赖移除 | `requirements.txt` 无 nonebot/discord.py |
| 测试通过 | 全部测试通过，0 失败 |
| 启动成功 | 无 NoneBot 依赖下管理服务器正常启动 |

### 15.4 阶段四验收（协议与部署）

| 验收项 | 标准 |
|--------|------|
| LICENSE | 文件为 AGPL-3.0 全文 |
| README | 协议声明更新 |
| docker-compose | AstrBot 子进程正常启动 |
| Docker 构建 | `docker-compose build` 成功 |
| Python 3.12 | 基础镜像升级到 3.12+ |

---

## 16. 附录

### 16.1 AstrBot Star API 速查

```python
from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

class MyPlugin(star.Star):
    name = "my_plugin"
    author = "author"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        # context.get_config()          — AstrBot 配置
        # context.conversation_manager   — 会话历史管理
        # context.get_provider()        — LLM provider

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        event.get_sender_id()          # 发送者 ID
        event.get_group_id()           # 群组/服务器 ID
        event.get_session_id()         # 会话 ID
        event.get_message_str()        # 消息文本
        event.is_at_or_wake_command     # 是否 @本bot
        event.set_extra(key, val)       # 附加上下文数据
        event.get_result()             # 获取/设置响应结果
        event.unified_msg_origin       # 统一消息来源标识
        event.message_obj              # 原始消息对象
        event.get_self_id()            # bot 自身 ID
```

### 16.2 AstrBot 官方文档索引

| 文档 | URL |
|------|-----|
| 主页 | https://astrbot.app/ |
| 插件开发入门 | https://docs.astrbot.app/dev/star/plugin-new.html |
| 最小实例 | https://docs.astrbot.app/dev/star/guides/simple.html |
| 接收消息事件 | https://docs.astrbot.app/dev/star/guides/listen-message-event.html |
| 发送消息 | https://docs.astrbot.app/dev/star/guides/send-message.html |
| 插件配置 | https://docs.astrbot.app/dev/star/guides/plugin-config.html |
| 调用 AI | https://docs.astrbot.app/dev/star/guides/ai.html |
| 存储 | https://docs.astrbot.app/dev/star/guides/storage.html |
| 会话控制器 | https://docs.astrbot.app/dev/star/guides/session-control.html |
| Discord 平台接入 | https://docs.astrbot.app/platform/discord.html |
| 配置文件 | https://docs.astrbot.app/dev/astrbot-config.html |
| HTTP API | https://docs.astrbot.app/scalar.html |
| 知识库 | https://docs.astrbot.app/use/knowledge-base.html |
| 上下文压缩 | https://docs.astrbot.app/use/context-compress.html |
| Docker 部署 | https://docs.astrbot.app/deploy/astrbot/docker.html |

### 16.3 当前项目文件清单（迁移相关）

**AstrBot 侧（保留/补全）**：
```
backend/app/astrbot_manager.py          # 子进程管理器 ✅
backend/app/astrbot_config_gen.py       # 配置生成器 ✅
backend/app/routers/internal.py        # IPC 端点 ✅
backend/astrbot_stars/                  # 15 个 Star 插件 ⚠️ 需补全
  context_assembler/star.py
  knowledge_bridge/star.py
  trigger/star.py
  streaming_respond/star.py
  persona/star.py
  post_process/star.py
  usage_tracker/star.py
  interaction_recorder/star.py
  ocr_image/star.py
  auto_interject/star.py
  repeat_parrot/star.py
  message_queue/star.py
  plugin_bridge/star.py
  memory_tools/star.py
  debug_capture/star.py
backend/astrbot_stars/providers/        # 非 Star 扩展模块 ⚠️ 需评估
  xai_provider.py                       # xAI provider 适配器（阶段二验证保留或删除）
```

**Legacy 侧（删除）**：
```
backend/nb_plugins/                     # 整目录删除（core_llm_bot, search_plugin, configurable_tools, memory_tools）
backend/app/discord_patch.py            # 删除
backend/app/config_bridge.py             # 删除
frontend/src/components/AstrBotMigration.svelte  # 删除
```

**管理服务器（保留/适配）**：
```
backend/app/main.py                     # 修改（移除 NoneBot 初始化，改为初始化 AstrBotProcessManager）
backend/app/bot_instance.py             # 修改（移除 NoneBot 路径 + provider_mode property）
backend/app/bot_manager.py              # 保留
backend/app/config_cache.py             # 保留（DEFAULT_CONFIG 不含 provider_mode，无需修改）
backend/app/state.py                    # 修改（移除 nonebot_driver，添加 astrbot_process_manager）
backend/app/app_context.py              # 修改（移除 nonebot_driver 字段，添加 astrbot_process_manager）
backend/app/routers/bots.py             # 修改（get_adapter_status 移除 nonebot_driver）
backend/app/routers/state.py            # 修改（第 16 行 nonebot_driver 依赖移除）
backend/app/routers/user_options.py     # 修改（第 131 行 nonebot_driver 依赖移除）
backend/app/routers/models_test.py      # 保留（WebUI 模型连通性测试）
backend/app/routers/*.py               # 其余路由保留
backend/app/core_logic/context_builder.py    # 适配（移除 import discord）
backend/app/core_logic/persona_manager.py   # 适配（移除 import discord）
backend/app/core_logic/usage_manager.py     # 适配（移除 import discord）
backend/app/core_logic/user_validator.py     # 适配（移除 import discord）
backend/app/core_logic/*.py             # 其余保留（knowledge_manager, interaction_recorder, preview_builder, sqlite_pool, embedding_service, rerank_service, user_options_manager）
backend/app/llm_providers/*.py          # 保留（仅 /chat 端点 + models_test 使用）
backend/app/security/*.py               # 保留
backend/app/middleware/*.py              # 保留
backend/plugins/*.py                    # 保留（base, manager, configurable_plugin, memory_plugin, search — 供 plugin_bridge Star 加载）
backend/app/handlers/message_queue.py   # 保留（管理服务器侧消息队列逻辑参考）
```

**测试/模拟（适配）**：
```
simulations/simulate.py                 # 适配（阶段二支持 AstrBot 模式 E2E 测试）
backend/tests/                          # 适配（移除 NoneBot 相关测试，新增 AstrBot 模式测试）
```

### 16.4 迁移阶段与提交规划

| 阶段 | 预计提交数 | 提交前缀 |
|------|-----------|----------|
| 阶段一：Star 补全 | 15-20 | `feat(astrbot-stars): ...` |
| 阶段二：集成测试 | 8-12 | `test(astrbot): ...` |
| 阶段三：Legacy 删除 | 6-10 | `refactor!(astrbot): ...` |
| 阶段四：协议/部署 | 3-5 | `chore(license): ...` / `chore(deploy): ...` |

### 16.5 术语表

| 术语 | 说明 |
|------|------|
| Star | AstrBot 的插件抽象，基于 `star.Star` 基类 |
| Legacy | 当前基于 NoneBot2 的 Bot 运行时路径 |
| 管理服务器 | 本项目的 FastAPI 后端，负责配置/知识库/用量/交互记录的中心化管理 |
| IPC | 进程间通信，本项目通过 `/internal` HTTP API 实现 |
| 子进程模式 | AstrBot 作为独立 Python 子进程运行，由管理服务器管理生命周期 |
| provider_mode | 当前双模式切换字段（`nonebot` / `astrbot`），迁移完成后移除 |

---

> **本文档为设计阶段产出，需经评审后进入实施。实施过程中如发现 AstrBot API 与文档描述不符，应以 AstrBot 官方文档和源码为准并更新本文档。**