# Discord-LLMs-ChatBot

基于 NoneBot2 的多 Bot 聊天机器人，支持 **12 家 LLM 提供商**，配备 Web 控制面板、知识引擎、OCR 图片识别、插件系统和多 Bot 管理。

A multi-bot Discord / QQ chatbot powered by NoneBot2, supporting **12 LLM providers** with a web control panel, persistent knowledge, OCR, plugin automation, and multi-instance management.

---

## 核心特性 / Highlights

| 模块 | 说明 |
|------|------|
| **多提供商 LLM** | OpenAI · Google Gemini · Anthropic Claude · xAI Grok · DeepSeek · 硅基流动 · 火山引擎 · 阿里百炼 · Moonshot · 智谱 · 阶跃星辰 —— 全部支持 OpenAI 兼容协议 |
| **推理参数** | temperature · top_p · top_k · max_tokens · frequency_penalty · presence_penalty，独立模型设置页面统一管理 |
| **自定义 HTTP 头** | 为 OpenAI 兼容提供商注入自定义请求头，适配代理/网关鉴权 |
| **多 Bot 管理** | 单一面板管理多个 Bot，独立配置、人设、知识库、配额 |
| **Web 控制面板** | Svelte 4 实时仪表盘，模型设置 / 行为配置 / 自动化 / 高级工具四个页面，支持主题切换 |
| **分层人设系统** | 频道/服务器级别提示词 · 用户画像 · 角色行为规则 |
| **知识引擎** | 世界书关键词注入 · 自动记忆摄取（质量评分 + 候选提升）· FTS5 全文搜索 · 向量语义召回 |
| **插件系统** | 可扩展插件框架，HTTP 触发器、工具调用集成、外部 REST 接口 |
| **用量统计** | Token 统计 + 按模型定价，用户/频道/服务器维度拆分 |
| **OCR / 嵌入 / 重排** | 多模态 OCR（图片→文字）· 向量嵌入 · 重排序管道 |
| **跨平台启动器** | `run.py` 统管安装/启动/停止/重启/状态，兼容 Windows / Linux / macOS |
| **E2E 模拟测试** | `simulations/simulate.py` 文本 + 图片 OCR 验证，支持逐个 bot 批量测试 |

---

## 技术栈 / Tech Stack

| Layer | Technology |
|-------|------------|
| Bot Framework | NoneBot2 + Discord / QQ adapter |
| API Server | FastAPI (Python 3.11+) |
| Frontend | Svelte 4 + Vite |
| Cache / Lock | Redis（本地开发自动降级 mock） |
| LLM SDKs | `openai` · `google-genai` · `anthropic` · `xai-sdk` |
| Knowledge DB | SQLite FTS5 + embedding |
| Container | Docker Compose（backend + frontend + redis） |

---

## 快速开始 / Quick Start

```bash
git clone https://github.com/RainyN0077/Discord-LLMs-ChatBot.git
cd Discord-LLMs-ChatBot
docker compose up --build -d
```

打开 `http://localhost:8094`，在 Web UI 中：
1. 配置 Discord Bot Token
2. 选择 LLM 提供商，填入 API Key
3. 保存配置 → 启动 Bot

### 本地开发 / Local Dev

```bash
python run.py start                 # 后台启动
python run.py start --foreground    # 前台模式（Ctrl+C 停止）
python run.py stop                  # 停止所有
python run.py restart               # 重启
python run.py status                # 查看状态
python run.py install               # 安装依赖
```

`run.py` 自动处理：创建虚拟环境 → 安装 Python 依赖 → `npm install` → 启动 uvicorn（8093）+ Vite（8094）→ 管理 PID / 日志。

---

## 项目结构 / Structure

```
Discord-LLMs-ChatBot/
├── backend/
│   ├── app/                         # FastAPI + 业务逻辑
│   │   ├── llm_providers/           # LLM 提供商适配层
│   │   ├── routers/                 # REST API 路由
│   │   ├── core_logic/              # 上下文构建 / 人设管理 / 知识
│   │   └── handlers/                # 消息队列 / 图片处理 / 自动化
│   ├── nb_plugins/                  # NoneBot2 插件（核心 LLM Bot + 可配置工具）
│   ├── plugins/                     # 可扩展插件系统
│   └── tests/                       # pytest 单元/集成测试
├── frontend/
│   └── src/
│       ├── pages/                   # ConfigPanel / ModelSettings / Debugger / PromptStudio
│       ├── components/              # Card / Sidebar / LogPanel / KnowledgeEditor
│       ├── lib/                     # stores / api / providerDefaults / i18n
│       └── locales/                 # 中英文语言文件
├── simulations/                     # E2E 模拟测试
│   ├── simulate.py                  # 验证脚本（文本 + OCR + 多 Bot）
│   └── test_images/                 # OCR 测试图片
├── run.py                           # 跨平台启动器
├── docker-compose.yml
└── README.md
```

---

## 提供商对照 / Providers

| 标识 | 服务商 | 默认 Base URL | 协议 |
|------|--------|--------------|------|
| `openai` | OpenAI | `https://api.openai.com/v1` | OpenAI |
| `google` | Google Gemini | — | Gemini SDK |
| `anthropic` | Anthropic Claude | — | Anthropic SDK |
| `grok` | xAI Grok | `https://api.x.ai` | xAI SDK |
| `deepseek` | DeepSeek | `https://api.deepseek.com` | OpenAI 兼容 |
| `siliconflow` | 硅基流动 | `https://api.siliconflow.cn/v1` | OpenAI 兼容 |
| `volcengine` | 火山引擎 | `https://ark.cn-beijing.volces.com/api/v3` | OpenAI 兼容 |
| `dashscope` | 阿里百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | OpenAI 兼容 |
| `moonshot` | Moonshot | `https://api.moonshot.cn/v1` | OpenAI 兼容 |
| `zhipu` | 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` | OpenAI 兼容 |
| `stepfun` | 阶跃星辰 | `https://api.stepfun.com/v1` | OpenAI 兼容 |

> **提示**：选择任一提供商后，前端自动填入默认 Base URL 和内置模型列表。如需自定义代理端点，选择 `openai` 并手动填入 URL。

---

## 模型设置 / Model Settings

独立的 **模型设置** 页面，统一管理 LLM 提供商和推理参数：

```
提供商选择  →  自动填入默认 Base URL  +  内置模型列表
API Key     →  Fetch Models 拉取可用模型  |  切换手动输入  |  Test Connection
推理参数    →  temperature / max_tokens / top_p / top_k / frequency_penalty / presence_penalty（全部可选，留空用默认）
自定义头    →  动态添加/删除 HTTP 请求头（适配代理鉴权）
多模态      →  OCR 图片识别开关 + 流式响应模式切换
自定义参数  →  键值对参数编辑器（text / number / boolean / json 类型）
```

---

## 配置参考 / Configuration

### 核心字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `discord_token` | Discord Bot Token | `MTA...` |
| `llm_provider` | LLM 提供商 | `deepseek` |
| `api_key` | 提供商 API Key | `sk-...` |
| `model_name` | 模型标识符 | `deepseek-v4-pro` |
| `openai_base_url` | OpenAI 兼容端点 | 自动填入 |
| `temperature` | 推理温度 0–2 | `0.7`（留空=默认） |
| `max_tokens` | 最大输出 token 数 | `4096`（留空=默认） |
| `api_secret_key` | 内部 API 鉴权密钥 | 自动生成 |

### 数据持久化 / Data

| 路径 | 内容 |
|------|------|
| `data/config.json` | 全局配置 |
| `data/bots/<id>/config.json` | Bot 独立配置 |
| `data/bots/<id>/knowledge.sqlite` | Bot 知识库 |
| `data/bots/<id>/usage_data.json` | Bot 用量统计 |
| `data/logs/` | 应用日志（`/api/logs` 可查） |

---

## REST API

### Bot 管理

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/bots` | 列表 |
| `POST` | `/api/bots` | 创建 |
| `DELETE` | `/api/bots/{id}` | 删除 |
| `POST` | `/api/bots/{id}/rename` | 重命名 |
| `GET/POST` | `/api/bots/{id}/config` | 获取/更新配置 |
| `POST` | `/api/bots/{id}/start` | 启动 |
| `POST` | `/api/bots/{id}/stop` | 停止 |
| `POST` | `/api/bots/{id}/restart` | 重启 |
| `GET/POST` | `/api/bots/{id}/export` · `/import` | 导出/导入配置 |

### LLM 调试

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat/direct` | 直接发消息（带 attachments 支持图片） |
| `POST` | `/api/models/list` | 拉取可用模型列表 |
| `POST` | `/api/models/test` | 测试模型连接 |

### 记忆 / 知识 / 插件 / 用量

| Method | Path | Description |
|--------|------|-------------|
| `GET/POST` | `/api/memory` | 记忆 CRUD |
| `POST` | `/api/memory/clear` | 清除频道记忆 |
| `GET` | `/api/memory/candidates` | 候选记忆 |
| `GET/POST` | `/api/worldbook` | 世界书条目 |
| `POST` | `/api/plugins/trigger` | 触发插件 |
| `GET` | `/api/usage/stats` | 用量统计 |
| `GET/POST` | `/api/usage/pricing` | 定价配置 |
| `GET` | `/api/logs` | 应用日志 |

> 所有变更接口需 `X-API-Key` 请求头（值 = `api_secret_key`）。

---

## E2E 模拟测试 / Simulation

```bash
# 单个 bot，含图片 OCR
python simulations/simulate.py

# 测试所有 bot
python simulations/simulate.py --all

# 最多测 2 个，跳过图片
python simulations/simulate.py --all --max-bots 2 --no-image

# 指定 bot + 自定义后端地址
python simulations/simulate.py --bot-id my-bot --api-url http://192.168.1.100:8093
```

测试步骤：问候 → 问答 → 图片识别（英文 / 中英 / 纯中文）→ 多轮上下文 → 角色扮演验证。每一步打印响应时间、Token 用量、Bot 回复、后端日志截取。

---

## 安全 / Security

- 所有变更接口需 `X-API-Key` 鉴权，每 Bot 独立密钥
- CORS 白名单限制来源和请求头
- 插件 HTTP 请求 SSRF 防护（RFC 1918 / loopback / link-local + DNS rebinding）
- API Key 不持久化到浏览器存储
- `data/` 目录已在 `.gitignore` 中排除

---

## 故障排查 / Troubleshooting

| 现象 | 检查 |
|------|------|
| 前端连不上后端 | 后端 `8093` 端口 · Vite 代理配置 · Docker 容器状态 |
| API 401 / 403 | `api_secret_key` 是否配置 · `X-API-Key` 值是否匹配 |
| Bot Discord 不响应 | Token 权限 · 触发条件（@提及 / 关键词）· `/api/logs` 日志 |
| 模型列表拉不到 | API Key 是否正确 · Base URL 是否可访问 · 提供商是否在 `models_test.py` 中注册 |
| OCR 不工作 | `llm_is_multimodal` 是否开启 · OCR 提供商配置 |

---

## License

MIT — see [LICENSE](LICENSE).
