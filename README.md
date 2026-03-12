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

## 11. Chinese Guide (涓枃鐗?

### 椤圭洰绠€浠?
杩欐槸涓€涓敮鎸佸妯″瀷鏈嶅姟鍟嗙殑 Discord 鏈哄櫒浜洪」鐩紝鎻愪緵 Web 鎺у埗闈㈡澘銆佺煡璇嗗簱锛堜笘鐣屼功 + 闀挎湡璁板繂锛夈€佹彃浠剁郴缁熴€佺敤閲忕粺璁″拰閰嶉鎺у埗銆?
### 涓昏鍔熻兘

- 澶氭湇鍔″晢鏀寔锛歄penAI銆丟oogle Gemini锛坄google-genai`锛夈€丄nthropic
- 鍙鍖栨帶鍒堕潰鏉匡細鍦ㄧ嚎淇敼閰嶇疆骞堕噸鍚満鍣ㄤ汉
- 鍒嗗眰浜鸿锛氶閬?鏈嶅姟鍣ㄦ寚浠ゃ€佺敤鎴风敾鍍忋€佽韩浠界粍閰嶇疆
- 鐭ヨ瘑澧炲己锛氫笘鐣屼功鍏抽敭璇嶆敞鍏ャ€侀暱鏈熻蹇嗗€欓€夋彁鍗?- 鎻掍欢绯荤粺锛氭敮鎸佸閮ㄦ帴鍙ｈЕ鍙?`POST /api/plugins/trigger`
- 鐢ㄩ噺缁熻涓庝环鏍奸潰鏉匡細杩借釜 token 鍜屾垚鏈?
### 蹇€熷惎鍔紙Docker锛?
```bash
docker compose up --build -d
```

鍚姩鍚庤闂細

- 鍓嶇锛歚http://localhost:8094`
- 鍚庣锛歚http://localhost:8093`

### Windows 鏈湴寮€鍙戯紙闈?Docker锛?
PowerShell 鍚姩锛?
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start-local.ps1
```

CMD 鍚姩锛?
```bat
.\scripts\windows\start-local.bat
```

鍋滄鏈湴杩涚▼锛?
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop-local.ps1
```

鎴栵細

```bat
.\scripts\windows\stop-local.bat
```

### 鍏抽敭閰嶇疆椤?
- `discord_token`锛欴iscord 鏈哄櫒浜?Token
- `llm_provider`锛歚openai` / `google` / `anthropic`
- `api_key`锛氬搴旀湇鍔″晢 API Key
- `model_name`锛氭ā鍨嬪悕绉?- `api_secret_key`锛氬悗绔?API 閴存潈瀵嗛挜锛堣姹傚ご `X-API-Key`锛?
### Google 杩佺Щ璇存槑

褰撳墠 Google 璺緞宸茬粺涓€鍒?`google-genai`锛?
- `backend/requirements.txt` 浣跨敤 `google-genai`
- `backend/app/main.py` 浣跨敤 `from google import genai`
- `backend/app/llm_providers/google_provider.py` 宸茶縼绉诲埌鏂?SDK 瀹炵幇

濡傛灉浣犳湰鍦扮幆澧冭繕鍋滅暀鍦ㄦ棫鍖咃紝寤鸿閲嶆柊瀹夎渚濊禆锛?
```bash
# 鍦?backend 鐩綍鎵ц
python -m pip install -r requirements.txt
```

