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
- Docker deployment and Windows/Linux local dev scripts

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
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start-local.ps1
```

CMD:

```bat
.\scripts\windows\start-local.bat
```

Stop local processes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop-local.ps1
```

or

```bat
.\scripts\windows\stop-local.bat
```

What local scripts do:
- Create `backend/.venv` if missing
- Install backend dependencies from `backend/requirements.txt`
- Install frontend dependencies (`npm install`) if npm is available
- Start backend on `8093` and frontend dev server on `8094`

### Linux local (non-Docker)

Foreground mode (easy debugging):

```bash
bash ./scripts/linux/start-local-foreground.sh
```

Background mode (`nohup`, with logs/PID files):

```bash
bash ./scripts/linux/start-local-nohup.sh
```

`tmux` mode (separate windows for backend/frontend):

```bash
bash ./scripts/linux/start-local-tmux.sh
```

Stop local processes:

```bash
bash ./scripts/linux/stop-local.sh
```

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
  - Added `scripts/windows/run-backend-local.bat`
  - Refined `scripts/windows/start-local.bat` process launch and command checks
  - Refactored `scripts/windows/stop-local.bat` to call `scripts/windows/stop-local.ps1`
- Added Linux local startup scripts:
  - `scripts/linux/start-local-foreground.sh`
  - `scripts/linux/start-local-nohup.sh`
  - `scripts/linux/start-local-tmux.sh`
  - `scripts/linux/stop-local.sh`

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

这是一个高度可定制的 Discord 聊天机器人项目，支持多家 LLM 服务商、Web 控制面板、知识增强、长期记忆、插件自动化和用量统计。

### 主要功能

- 多服务商 LLM 支持：
  - OpenAI（以及 OpenAI 兼容接口）
  - Google Gemini（`google-genai` SDK）
  - Anthropic Claude
- Web 控制面板，可在运行时调整配置
- 分层人设系统：
  - 频道 / 服务器级提示词
  - 用户画像
  - 身份组行为设定
- 知识增强能力：
  - 世界书关键词注入
  - 长期记忆与候选提升流程
- 用量统计面板，可查看 token 与模型价格
- 安全插件系统，支持外部接口触发
- 配额管理（`!myquota`）
- 支持 Docker 部署，以及 Windows / Linux 本地开发脚本

### 端口与运行方式

#### Docker（推荐）

```bash
docker compose up --build -d
```

服务端口：

- 前端：`http://localhost:8094`
- 后端 API：`http://localhost:8093`
- Redis：运行在 compose 网络内部

#### Windows 本地开发（非 Docker）

PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start-local.ps1
```

CMD：

```bat
.\scripts\windows\start-local.bat
```

停止本地进程：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop-local.ps1
```

或：

```bat
.\scripts\windows\stop-local.bat
```

本地脚本会自动：

- 在缺失时创建 `backend/.venv`
- 安装 `backend/requirements.txt` 中的后端依赖
- 如果检测到 npm，则安装前端依赖
- 在 `8093` 启动后端、在 `8094` 启动前端开发服务器

#### Linux 本地开发（非 Docker）

前台调试模式：

```bash
bash ./scripts/linux/start-local-foreground.sh
```

后台模式（`nohup`，带日志和 PID 文件）：

```bash
bash ./scripts/linux/start-local-nohup.sh
```

`tmux` 模式（前后端分窗口）：

```bash
bash ./scripts/linux/start-local-tmux.sh
```

停止本地进程：

```bash
bash ./scripts/linux/stop-local.sh
```

### 快速开始

1. 克隆仓库

```bash
git clone https://github.com/RainyN0077/Discord-LLMs-ChatBot.git
cd Discord-LLMs-ChatBot
```

2. 使用 Docker 启动

```bash
docker compose up --build -d
```

3. 打开 Web 控制台

- `http://localhost:8094`

4. 在 UI 中完成配置

- Discord Bot Token
- LLM 服务商、API Key 和模型名
- 保存配置并重启机器人

### 关键配置项

- `discord_token`：Discord 机器人 Token
- `llm_provider`：`openai` / `google` / `anthropic`
- `api_key`：所选服务商的 API Key
- `model_name`：所选模型 ID
- `api_secret_key`：后端接口鉴权密钥，请通过请求头 `X-API-Key` 传入

### 数据持久化

运行数据保存在 `./data` 目录（Docker 中挂载到 `/app/data`），包括：

- `config.json`
- 日志
- 世界书 / 记忆等相关数据文件

### Redis 行为说明

- Docker 模式默认使用 compose 中的 Redis 服务
- 本地脚本会设置 `FAIL_ON_REDIS_ERROR=false`
  - 如果 Redis 不可用，程序会退回到 mock lock 模式，便于本地开发

### 对外 REST API

主要的外部自动化接口：

- `POST /api/plugins/trigger`
- 请求头：`X-API-Key: <api_secret_key>`

示例：

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

常用后端接口还包括：

- `GET /api/config`
- `POST /api/config`
- `POST /api/models/list`
- `POST /api/models/test`
- `GET /api/logs`
- `GET /api/usage/stats`
- `GET/POST /api/usage/pricing`
- 记忆 / 世界书相关的 `GET/POST/PUT/DELETE` 接口

### Google Provider 迁移说明

当前项目已统一使用 `google-genai` 作为 Google SDK 路径。

- `backend/requirements.txt` 使用 `google-genai`
- `backend/app/main.py` 的模型列出 / 测试逻辑使用 `from google import genai`
- `backend/app/llm_providers/google_provider.py` 已迁移到 `google-genai` 实现

如果你本地环境还停留在旧版 `google-generativeai`，建议刷新虚拟环境依赖：

```bash
# 在 backend 目录执行
python -m pip install -r requirements.txt
```

