# Discord-LLMs-ChatBot

A multi-bot Discord chatbot powered by NoneBot2, supporting multiple LLM providers with a web control panel, persistent knowledge features, and a plugin-based automation system.

---

## Highlights

- **Multi-Provider LLM**: OpenAI / Gemini / Claude / xAI (Grok) — swap models anytime via the Web UI
- **Multi-Bot Management**: Run multiple Discord bots from a single dashboard, each with independent config, persona, knowledge, and quota
- **Web Control Panel**: Real-time Svelte dashboard for config, debug captures, usage stats, and bot lifecycle (start/stop/restart)
- **Layered Persona System**: Scoped prompts per channel/guild, per-user portraits, and role-based behavior rules
- **Knowledge Engine**: World Book (keyword-triggered injection), auto-memory ingestion (quality-thresholded candidate promotion), FTS5 search, and embedding-based semantic recall
- **Plugin System**: Extensible plugin framework with configurable HTTP triggers, tool-calling integration, and external REST endpoint
- **Usage Dashboard**: Token statistics with per-model pricing, per-user/per-guild/per-channel breakdowns, and pricing overrides
- **Security Hardening**: API key lifecycle management, CORS allowlist, SSRF DNS rebinding protection, per-bot authentication
- **OCR / Embedding / Rerank**: Built-in multimodal OCR (image-to-text via LLM), vector embedding service, and rerank pipeline
- **Cross-Platform Launcher**: Unified `run.py` for install, start, stop, restart, and status — works on Windows, Linux, and macOS

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Bot Framework | NoneBot2 + discord.py adapter |
| API Server | FastAPI (Python 3.11+) |
| Frontend | Svelte 4 + Vite |
| Cache / Lock | Redis (with mock fallback for local dev) |
| LLM SDKs | `openai` · `google-genai` · `anthropic` · `openai` (xAI-compatible) |
| Knowledge DB | SQLite with FTS5 + embedding tables |
| Container | Docker Compose (3 services: backend, frontend, redis) |

---

## Ports and Runtime

### Docker (recommended)

```bash
docker compose up --build -d
```

| Service | URL |
|---------|-----|
| Frontend (Web UI) | `http://localhost:8094` |
| Backend API | `http://localhost:8093` |
| Redis | internal (`redis:6379`) |

### Local (cross-platform launcher)

```bash
python run.py start                  # start backend + frontend in background
python run.py start --foreground      # single terminal, Ctrl+C to stop
python run.py start --backend-only
python run.py start --frontend-only
python run.py stop                   # stop all processes
python run.py restart                # restart all
python run.py status                 # show process status
python run.py install                # install/sync dependencies only
```

What `run.py` handles automatically:
- Creates `backend/.venv` if missing
- Installs Python dependencies from `backend/requirements.txt`
- Runs `npm install` in `frontend/` if Node.js is available
- Starts backend on port `8093` (uvicorn with hot-reload) and frontend Vite dev server on `8094`
- Manages PID files and logs under `.local-run/`

---

## Quick Start

1. **Clone**
```bash
git clone https://github.com/RainyN0077/Discord-LLMs-ChatBot.git
cd Discord-LLMs-ChatBot
```

2. **Start**
```bash
docker compose up --build -d
```

3. **Open** `http://localhost:8094`

4. **Configure** in the Web UI:
   - Discord Bot Token
   - LLM provider, API key, and model name
   - Save config → Start Bot

---

## Configuration Reference

### Core Fields

| Field | Description |
|-------|-------------|
| `discord_token` | Discord bot token |
| `llm_provider` | `openai` / `google` / `anthropic` / `xai` |
| `api_key` | Provider API key |
| `model_name` | Model identifier (e.g. `gpt-4o`, `gemini-2.5-flash`, `claude-sonnet-4-20250514`) |
| `api_secret_key` | Internal API auth — send as `X-API-Key` header for protected endpoints |

### LLM Provider Notes

- **OpenAI** — also supports OpenAI-compatible APIs (set `openai_base_url`)
- **Google Gemini** — uses `google-genai` SDK
- **Anthropic Claude** — supports `anthropic_base_url` for custom endpoints
- **xAI (Grok)** — uses `grok_base_url`, defaults to `https://api.x.ai`

### Data Persistence

All runtime data under `./data` (mounted as `/app/data` in Docker):

| Path | Content |
|------|---------|
| `data/config.json` | Global configuration |
| `data/bots/<id>/config.json` | Per-bot configuration |
| `data/bots/<id>/knowledge.sqlite` | Bot-specific knowledge DB |
| `data/bots/<id>/usage_data.json` | Bot-specific usage stats |
| `data/logs/` | Application logs |

### Redis Behavior

- Docker Compose: Redis is always available
- Local development: `FAIL_ON_REDIS_ERROR=false` (default) — falls back to in-memory mock lock if Redis is unavailable

---

## Multi-Bot Management

The Web UI supports creating and managing multiple Discord bot instances:

- **Independent Configs**: Each bot has its own LLM provider, persona, knowledge base, and usage quotas
- **Per-Bot API Key**: Each bot generates a unique `api_secret_key` on first load
- **Lifecycle Control**: Start / stop / restart individual bots from the dashboard
- **Knowledge Migration**: Legacy global `data/knowledge.sqlite` is automatically migrated to the first bot's directory on startup

---

## REST API

### Core Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/api/config` | Get global configuration | Optional |
| `POST` | `/api/config` | Update global configuration | Required |
| `GET` | `/api/bots` | List all bot instances | Required |
| `POST` | `/api/bots` | Create a new bot instance | Required |
| `GET` | `/api/bots/{id}/config` | Get bot-specific config | Required |
| `POST` | `/api/bots/{id}/config` | Update bot-specific config | Required |
| `POST` | `/api/bots/{id}/start` | Start a bot instance | Required |
| `POST` | `/api/bots/{id}/stop` | Stop a bot instance | Required |
| `POST` | `/api/bots/{id}/restart` | Restart a bot instance | Required |
| `DELETE` | `/api/bots/{id}` | Delete a bot instance | Required |
| `POST` | `/api/chat/direct` | Direct LLM chat (debug) | Required |
| `GET` | `/api/logs` | Fetch application logs | Required |
| `GET` | `/api/usage/stats` | Usage statistics | Required |
| `GET/POST` | `/api/usage/pricing` | Model pricing config | Required |

### Memory / World Book Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/memory` | List all memories |
| `POST` | `/api/memory` | Add a new memory |
| `PUT` | `/api/memory/{id}` | Update a memory |
| `DELETE` | `/api/memory/{id}` | Delete a memory |
| `POST` | `/api/memory/clear` | Clear channel memory |
| `GET` | `/api/memory/candidates` | List candidate memories |
| `GET` | `/api/worldbook` | List world book entries |
| `POST` | `/api/worldbook` | Add world book entry |
| `PUT` | `/api/worldbook/{id}` | Update world book entry |
| `DELETE` | `/api/worldbook/{id}` | Delete world book entry |

### Plugin Trigger Endpoint

```bash
curl -X POST http://localhost:8093/api/plugins/trigger \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_SECRET_KEY" \
  -d '{
    "plugin_name": "Weather Check",
    "args": {"city": "Shanghai"}
  }'
```

---

## Plugin System

Plugins extend the bot with custom tools and automations:

- **Built-in Plugins**: Auto-memory ingestion (quality scoring + candidate promotion), repeat-parrot detection, auto-interject, world book injection
- **Configurable Plugins**: HTTP-triggered external services with templated headers/body, response parsing, and context injection
- **Search Plugin**: RAG (Retrieval-Augmented Generation) plugin with external search integration and content compression
- **Tool Integration**: Plugins expose tool definitions compatible with LLM function calling

---

## Security

- **API Authentication**: All mutating endpoints require `X-API-Key` header matching the configured `api_secret_key`
- **Per-Bot Keys**: Each bot instance generates its own independent API key, no cross-bot leakage
- **CORS Control**: Backend only allows `Content-Type`, `X-API-Key`, and `X-Timezone` headers from configured origins
- **SSRF Protection**: Plugin HTTP requests are validated against internal IP ranges (RFC 1918, loopback, link-local) with DNS rebinding defense
- **No Client-Side Secrets**: API keys are never persisted in browser storage

---

## Troubleshooting

### Web UI cannot reach backend
- Verify backend is listening on port `8093`
- Check `VITE_API_PROXY_TARGET` for local dev mode
- In Docker: ensure both `backend` and `frontend` containers are healthy

### Plugin API returns 403 / 401
- `401`: API key is not configured — set `api_secret_key` in the Web UI
- `403`: Verify the `X-API-Key` header matches the configured `api_secret_key`

### Bot does not respond in Discord
- Verify token validity and bot permissions (Send Messages, Read Message History, etc.)
- Check trigger conditions: mention, keyword match, reply rules
- Review backend logs via `/api/logs` or `docker compose logs backend`

### Google Gemini errors
```bash
# In backend directory
python -m pip install -r requirements.txt
```

---

## License

MIT License. See [LICENSE](LICENSE).

---

## 中文说明

### 项目简介

基于 NoneBot2 的多 Bot Discord 聊天机器人，支持多家 LLM 服务商，配备 Web 控制面板、知识增强、长期记忆和插件自动化系统。

### 核心特性

- **多服务商 LLM**：OpenAI / Gemini / Claude / xAI (Grok)，通过 Web UI 随时切换
- **多 Bot 管理**：单个面板同时管理多个 Discord Bot，每个 Bot 独立配置、独立人设、独立知识库和配额
- **Web 控制面板**：实时配置编辑、调试抓取、用量统计、Bot 生命周期控制（启动/停止/重启）
- **分层人设系统**：按频道/服务器配置提示词、用户画像、身份组行为规则
- **知识引擎**：世界书关键词注入、自动记忆摄取（质量评分 + 候选提升）、FTS5 全文搜索、向量语义召回
- **插件系统**：可扩展的插件框架，支持 HTTP 触发、工具调用集成、外部 REST 接口
- **用量统计**：Token 统计 + 按模型定价，可按用户/频道/服务器维度拆分
- **安全加固**：API 密钥生命周期管理、CORS 白名单、SSRF DNS rebinding 防护、每 Bot 独立鉴权
- **OCR/嵌入/重排**：内置多模态 OCR（图片转文字）、向量嵌入服务、重排序管道
- **跨平台启动器**：`run.py` 统一管理安装、启动、停止、重启、状态查询

### 运行方式

#### Docker（推荐）

```bash
docker compose up --build -d
```

服务端口：前端 `http://localhost:8094`，后端 API `http://localhost:8093`，Redis 运行在 compose 网络内部。

#### 本地开发

```bash
python run.py start              # 后台启动
python run.py start --foreground  # 前台模式
python run.py stop               # 停止
python run.py restart            # 重启
python run.py status             # 状态
python run.py install            # 安装依赖
```

### 快速开始

1. 克隆仓库 → 2. Docker 启动 → 3. 打开 `http://localhost:8094` → 4. 在 UI 中配置 Discord Token、LLM 服务商和模型，保存后启动 Bot

### 关键配置

- `discord_token`：Discord 机器人 Token
- `llm_provider`：`openai` / `google` / `anthropic` / `xai`
- `api_key`：所选服务商的 API Key
- `model_name`：模型标识符
- `api_secret_key`：后端接口鉴权密钥（`X-API-Key` 请求头）

### 多 Bot 管理

Web UI 支持创建并管理多个 Discord Bot 实例：每个 Bot 拥有独立的 LLM 配置、人设、知识库和用量统计。旧版全局知识库 `data/knowledge.sqlite` 在首次启动时会自动迁移到第一个 Bot 的目录下。

### REST API

主要端点包括 `/api/config`、`/api/bots`（Bot CRUD + 生命周期）、`/api/chat/direct`（LLM 调试）、`/api/memory`（记忆管理）、`/api/worldbook`（世界书管理）、`/api/usage/stats`（用量统计）、`/api/plugins/trigger`（插件触发）。所有变更接口需要 `X-API-Key` 请求头。

### 故障排查

- 前端无法连接后端：检查 `8093` 端口、Vite 代理配置、Docker 容器健康状态
- 插件接口 401：`api_secret_key` 未配置；403：密钥不匹配
- Bot 不响应：检查 Token 权限、触发条件、日志
