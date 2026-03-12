# Discord-LLMs-ChatBot

A highly customizable Discord chatbot with multi-provider LLM support, a web control panel, persistent knowledge features, and plugin-based automation.

---

## 1. Highlights

- Multi-provider LLM support:
  - OpenAI (and OpenAI-compatible APIs)
  - Google Gemini (`google-genai` SDK)
  - Anthropic Claude
- Real-time Web Control Panel for runtime settings
- Layered persona system:
  - Channel/Guild scoped prompts
  - User portraits
  - Role-based behavior
- Knowledge features:
  - World Book (keyword-triggered knowledge injection)
  - Long-term memory and candidate promotion workflow
- Usage dashboard with token stats and model pricing
- Secure plugin system with external trigger endpoint
- Quota management (`!myquota`)
- Docker deployment and Windows local dev scripts

---

## 2. Tech Stack

- Backend: FastAPI + discord.py
- Frontend: Svelte + Vite
- Cache/lock: Redis
- LLM SDKs:
  - `openai`
  - `google-genai`
  - `anthropic`

---

## 3. Ports and Runtime

### Docker (recommended)

```bash
docker compose up --build -d
```

Services:
- Frontend: `http://localhost:8094`
- Backend API: `http://localhost:8093`
- Redis: internal service in compose network

### Windows local (non-Docker)

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

CMD:

```bat
.\scripts\start-local.bat
```

Stop local processes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

or

```bat
.\scripts\stop-local.bat
```

What local scripts do:
- Create `backend/.venv` if missing
- Install backend dependencies from `backend/requirements.txt`
- Install frontend dependencies (`npm install`) if npm is available
- Start backend on `8093` and frontend dev server on `8094`

---

## 4. Quick Start

1. Clone repository

```bash
git clone https://github.com/RainyN0077/Discord-LLMs-ChatBot.git
cd Discord-LLMs-ChatBot
```

2. Start with Docker

```bash
docker compose up --build -d
```

3. Open Web UI

- `http://localhost:8094`

4. Configure in UI

- Discord bot token
- LLM provider + API key + model
- Save configuration and restart bot

---

## 5. Configuration Notes

### Core fields

- `discord_token`: your Discord bot token
- `llm_provider`: `openai` / `google` / `anthropic`
- `api_key`: selected provider API key
- `model_name`: selected model id
- `api_secret_key`: API auth key used by backend endpoints (`X-API-Key`)

### Data persistence

Runtime data is stored under `./data` (mounted to `/app/data` in Docker), including:
- `config.json`
- logs
- knowledge/memory related files

### Redis behavior

- Docker mode uses Redis service in compose
- Local scripts set `FAIL_ON_REDIS_ERROR=false`
  - If Redis is unavailable, app falls back to mock lock mode for local development

---

## 6. REST API (for integrations)

Main endpoint for external automation:

- `POST /api/plugins/trigger`
- Header: `X-API-Key: <api_secret_key>`

Example:

```bash
curl -X POST http://localhost:8093/api/plugins/trigger \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_SECRET_KEY" \
  -d '{
    "plugin_name": "Weather Check",
    "args": {
      "city": "Shanghai"
    }
  }'
```

Other commonly used backend endpoints:
- `GET /api/config`
- `POST /api/config`
- `POST /api/models/list`
- `POST /api/models/test`
- `GET /api/logs`
- `GET /api/usage/stats`
- `GET/POST /api/usage/pricing`
- `GET/POST/PUT/DELETE` memory/worldbook related endpoints

---

## 7. Google Provider Migration Notes

The project now uses `google-genai` as the Google SDK path.

- Requirements: `backend/requirements.txt` uses `google-genai`
- `backend/app/main.py` model list/test paths use `from google import genai`
- `backend/app/llm_providers/google_provider.py` migrated to `google-genai` implementation

If you previously installed only `google-generativeai`, refresh your venv:

```bash
# from backend folder
python -m pip install -r requirements.txt
```

---

## 8. Recent Updates (2026-03)

- Completed Google SDK migration to `google-genai` in provider path
- Updated model listing/testing logic for Google provider
- Cleaned backend requirements and removed duplicate dependency entries
- Improved Windows local startup scripts:
  - Added `scripts/run-backend-local.bat`
  - Refined `start-local.bat` process launch and command checks
  - Refactored `stop-local.bat` to call `stop-local.ps1`

---

## 9. Troubleshooting

### Web UI cannot access backend

- Check backend process is listening on `8093`
- Check frontend proxy target (`VITE_API_PROXY_TARGET`) in local mode
- In Docker mode, ensure both `backend` and `frontend` containers are healthy

### Plugin API returns 403

- Verify `X-API-Key` header value matches `api_secret_key` in current config

### Bot does not respond in Discord

- Verify token validity and bot permissions
- Check trigger conditions (mention/keyword/reply rules)
- Check backend logs via `/api/logs` or container logs

### Google provider errors after upgrade

- Reinstall dependencies from `backend/requirements.txt`
- Ensure runtime uses current venv and not stale global packages

---

## 10. License

MIT License. See [LICENSE](LICENSE).

---

## 11. Chinese Guide (中文版)

### 项目简介

这是一个支持多模型服务商的 Discord 机器人项目，提供 Web 控制面板、知识库（世界书 + 长期记忆）、插件系统、用量统计和配额控制。

### 主要功能

- 多服务商支持：OpenAI、Google Gemini（`google-genai`）、Anthropic
- 可视化控制面板：在线修改配置并重启机器人
- 分层人设：频道/服务器指令、用户画像、身份组配置
- 知识增强：世界书关键词注入、长期记忆候选提升
- 插件系统：支持外部接口触发 `POST /api/plugins/trigger`
- 用量统计与价格面板：追踪 token 和成本

### 快速启动（Docker）

```bash
docker compose up --build -d
```

启动后访问：

- 前端：`http://localhost:8094`
- 后端：`http://localhost:8093`

### Windows 本地开发（非 Docker）

PowerShell 启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

CMD 启动：

```bat
.\scripts\start-local.bat
```

停止本地进程：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

或：

```bat
.\scripts\stop-local.bat
```

### 关键配置项

- `discord_token`：Discord 机器人 Token
- `llm_provider`：`openai` / `google` / `anthropic`
- `api_key`：对应服务商 API Key
- `model_name`：模型名称
- `api_secret_key`：后端 API 鉴权密钥（请求头 `X-API-Key`）

### Google 迁移说明

当前 Google 路径已统一到 `google-genai`：

- `backend/requirements.txt` 使用 `google-genai`
- `backend/app/main.py` 使用 `from google import genai`
- `backend/app/llm_providers/google_provider.py` 已迁移到新 SDK 实现

如果你本地环境还停留在旧包，建议重新安装依赖：

```bash
# 在 backend 目录执行
python -m pip install -r requirements.txt
```
