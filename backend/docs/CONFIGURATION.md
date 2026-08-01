# Configuration Reference

> 本文档列出了 ELA-Bot 支持的所有环境变量及其说明。
> 更新日期：2026-07-27

---

## 快速索引

| 类别 | 变量 |
|------|------|
| **安全** | `ENCRYPTION_KEY` · `DISABLE_ENCRYPTION` |
| **限流** | `RATE_LIMIT_PER_MINUTE` |
| **存储** | `DATA_DIR` · `LOG_DIR` · `KNOWLEDGE_DB` · `USAGE_FILE` · `SCRIPTS_DIR` |
| **网络** | `REDIS_URL` · `REDIS_HOST` · `REDIS_PORT` · `CORS_ORIGINS` |
| **LLM** | `LLM_BASE_URL_<NAME>` |
| **运行时** | `BOT_INSTANCE_ID` |

---

## 完整清单

### 安全 / Security

| 变量 | 说明 | 默认值 | 敏感 |
|------|------|--------|:----:|
| `ENCRYPTION_KEY` | 凭据加密密钥。用于加密存储的 `discord_token`、`api_key` 等敏感配置字段。首次启动时自动生成，也可手动设置。**丢失后无法解密已有凭据**。 | 首次启动自动生成 | 🔴 |
| `DISABLE_ENCRYPTION` | 设为 `1` 启用只读迁移模式。在此模式下：<br>1. 新写入的凭据 **不加密**（明文存储）<br>2. 读取时仍会尝试解密已有加密凭据<br>3. 用于从加密向未加密存储的平滑迁移 | `0` | |

### 限流 / Rate Limiting

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `RATE_LIMIT_PER_MINUTE` | API 全局速率限制，每 IP 每分钟最大请求数。设为 `0` 可禁用限流。 | `60` |

### 存储路径 / Storage Paths

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATA_DIR` | 数据存储根目录，存放全局配置、Bot 配置、知识库等。 | `./data` |
| `LOG_DIR` | 应用日志输出目录。 | `{DATA_DIR}/logs` |
| `KNOWLEDGE_DB` | SQLite 知识库文件路径（记忆 + 世界书 + FTS5 索引）。 | `{DATA_DIR}/knowledge_base.sqlite` |
| `USAGE_FILE` | 用量统计数据 JSON 文件路径。 | `{DATA_DIR}/usage_data.json` |
| `SCRIPTS_DIR` | 自定义脚本目录。 | `./scripts` |

### 网络 / Networking

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `REDIS_URL` | Redis 连接字符串。若为空或 Redis 不可达，自动降级为进程内 mock（本地开发友好）。 | `""`（空 = 降级） |
| `REDIS_HOST` | Redis 主机地址（仅在 `REDIS_URL` 未设置时使用）。 | `localhost` |
| `REDIS_PORT` | Redis 端口（仅在 `REDIS_URL` 未设置时使用）。 | `6379` |
| `CORS_ORIGINS` | 允许的 CORS 来源，逗号分隔。用于限制 Web UI 的跨域访问来源。 | `http://localhost:8094,http://127.0.0.1:8094` |

### LLM 提供商 / LLM Providers

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_BASE_URL_<NAME>` | 覆盖指定 LLM 提供商的默认 Base URL。`<NAME>` 为大写的提供商标识，例如 `LLM_BASE_URL_OPENAI`、`LLM_BASE_URL_DEEPSEEK`。 | 各提供商内置默认值 |

**内置 Base URL 对照**：

| 标识 | 服务商 | 默认 Base URL |
|------|--------|--------------|
| `openai` | OpenAI | `https://api.openai.com/v1` |
| `google` | Google Gemini | —（Gemini SDK） |
| `anthropic` | Anthropic Claude | —（Anthropic SDK） |
| `grok` | xAI Grok | `https://api.x.ai` |
| `deepseek` | DeepSeek | `https://api.deepseek.com` |
| `siliconflow` | 硅基流动 | `https://api.siliconflow.cn/v1` |
| `volcengine` | 火山引擎 | `https://ark.cn-beijing.volces.com/api/v3` |
| `dashscope` | 阿里百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `moonshot` | Moonshot | `https://api.moonshot.cn/v1` |
| `zhipu` | 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` |
| `stepfun` | 阶跃星辰 | `https://api.stepfun.com/v1` |

### 运行时 / Runtime

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BOT_INSTANCE_ID` | 显式指定 Bot 实例 ID。未设置时自动由 `hostname-pid-uuid` 生成。用于在多实例部署中区分不同进程。 | 自动生成 |

---

## Bot 配置字段

以下字段存在于 `data/config.json`（全局）或 `data/bots/<id>/config.json`（Bot 独立）中。

### 核心字段

| 字段 | 类型 | 说明 | 必需 | 敏感 |
|------|------|------|:----:|:----:|
| `bot_id` | `string` | Bot 唯一标识符（小写字母、数字、连字符、下划线） | ✅ | |
| `bot_name` | `string` | Bot 显示名称 | | |
| `discord_token` | `string` | Discord Bot Token | ✅ | 🔴 |
| `llm_provider` | `string` | LLM 提供商标识（见上表） | ✅ | |
| `api_key` | `string` | LLM 提供商 API Key | ✅ | 🔴 |
| `model_name` | `string` | 模型标识符 | ✅ | |
| `openai_base_url` | `string` | OpenAI 兼容端点 URL | | |
| `api_secret_key` | `string` | API 鉴权密钥（`X-API-Key` 请求头） | ✅ | 🔴 |
| `enabled` | `boolean` | 是否自动启动 Bot | `true` | |

### 推理参数 / Inference Parameters

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `temperature` | `number` | 采样温度 0–2 | 提供商默认 |
| `top_p` | `number` | 核采样 0–1 | 提供商默认 |
| `top_k` | `integer` | Top-K 采样 | 提供商默认 |
| `max_tokens` | `integer` | 最大输出 Token 数 | 提供商默认 |
| `frequency_penalty` | `number` | 频率惩罚 -2–2 | 提供商默认 |
| `presence_penalty` | `number` | 存在惩罚 -2–2 | 提供商默认 |
| `stream_response` | `boolean` | 是否启用流式响应 | `true` |

### 行为配置 / Behaviour

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `system_prompt` | `string` | 系统提示词 / 人设 | `""` |
| `context_mode` | `string` | 上下文模式：`channel` / `global` | `channel` |
| `trigger_keywords` | `string[]` | 触发关键词列表 | `[]` |
| `trigger_match_mode` | `string` | 关键词匹配模式：`contains` / `exact` / `regex` | `contains` |
| `llm_is_multimodal` | `boolean` | LLM 是否支持多模态（图片直接输入） | `true` |

### 数据路径 / Data Files

| 路径 | 内容 |
|------|------|
| `data/config.json` | 全局配置 |
| `data/bots/<id>/config.json` | Bot 独立配置 |
| `data/bots/<id>/knowledge.sqlite` | Bot 知识库（记忆 + 世界书 + FTS5 索引） |
| `data/bots/<id>/usage_data.json` | Bot 用量统计 |
| `data/logs/` | 应用日志 |
| `data/pricing_config.json` | 模型定价配置 |

---

## 敏感字段管理

1. **环境变量中的敏感字段**（`ENCRYPTION_KEY`）：
   - 建议通过 `.env` 文件或容器 secret 注入
   - `.env` 文件已在 `.gitignore` 中排除
   - 不应提交到版本控制

2. **配置文件中的敏感字段**（`discord_token`、`api_key`、`api_secret_key`）：
   - 默认使用 `ENCRYPTION_KEY` 加密存储在 `config.json` 中
   - 可通过 `DISABLE_ENCRYPTION=1` 切换到明文存储（仅用于迁移）
   - 前端不持久化 API Key 到浏览器本地存储

3. **日志安全**：
   - 日志系统会过滤敏感字段值，避免明文写入日志文件
   - 生产环境建议限制日志文件的访问权限

---

## 默认值加载优先级

```
环境变量 > 内置默认值
```

对于 Bot 配置字段：
```
Bot 独立配置 (data/bots/<id>/config.json) > 全局配置 (data/config.json) > 代码默认值
```
