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

---

## CSS 自定义指南 / CSS Customization Guide

### CSS 变量系统

BOT Manager 使用 CSS 自定义属性（CSS Variables）来管理整个 UI 的主题样式。所有颜色、阴影、圆角、间距等视觉属性都定义在 `:root` 下的 CSS 变量中。通过**外观设置**页面，你可以无需修改任何代码即可切换 UI 风格和配色方案，或注入自定义 CSS。

### 完整 CSS 变量列表

#### 背景 / 表面

| 变量 | 说明 | 浅色默认值 |
|------|------|-----------|
| `--bg-color` | 主背景色 | `#eef2f7` |
| `--card-bg` | 卡片背景色 | `#fff` |
| `--surface-tint` | 输入框/控件背景 | `#f8fbff` |
| `--panel-soft-bg` | 次级面板背景 | `#f8f9fa` |
| `--panel-soft-bg-2` | 三级面板背景 | `#fafbfc` |
| `--panel-muted-bg` | 弱化面板背景 | `rgba(15, 23, 42, .04)` |
| `--panel-hover-bg` | 面板 hover 背景 | `#f6f8fb` |
| `--control-bg` | 按钮控件背景 | `rgba(15, 23, 42, .06)` |
| `--control-hover-bg` | 按钮 hover 背景 | `rgba(15, 23, 42, .1)` |

#### 文字颜色

| 变量 | 说明 | 浅色默认值 |
|------|------|-----------|
| `--text-color` | 主文字颜色 | `#1f2a37` |
| `--text-light` | 次级文字颜色 | `#66768a` |
| `--text-muted` | 弱化文字颜色 | `#9ca3af` |

#### 主色 / 强调色

| 变量 | 说明 | 浅色默认值 |
|------|------|-----------|
| `--primary-color` | 主色 | `#1f8bd6` |
| `--primary-hover` | 主色悬停态 | `#1c75b5` |
| `--success-bg` | 成功背景 | `#e0f2f1` |
| `--success-text` | 成功文字 | `#00796b` |
| `--error-bg` | 错误背景 | `#fce4ec` |
| `--error-text` | 错误文字 | `#c2185b` |
| `--info-bg` | 信息背景 | `#e1f5fe` |
| `--info-text` | 信息文字 | `#0277bd` |
| `--save-color` | 保存按钮颜色 | `#1ea864` |
| `--save-hover` | 保存按钮悬停 | `#188a51` |

#### 边框 / 分隔线

| 变量 | 说明 | 浅色默认值 |
|------|------|-----------|
| `--border-color` | 边框颜色 | `#dde5ee` |
| `--floating-border` | 浮动面板边框 | `rgba(15, 23, 42, .08)` |
| `--panel-muted-border` | 弱化面板边框 | `rgba(15, 23, 42, .08)` |

#### 阴影 / 圆角 / 间距

| 变量 | 说明 | 浅色默认值 |
|------|------|-----------|
| `--shadow` | 主阴影 | `0 18px 36px rgba(15, 23, 42, .08)` |
| `--shadow-soft` | 柔和阴影 | `0 6px 14px rgba(15, 23, 42, .07)` |
| `--radius-md` | 小圆角 | `10px` |
| `--radius-lg` | 大圆角 | `16px` |
| `--gap-sm` | 小间距 | `0.5rem` |
| `--gap-md` | 中间距 | `1rem` |
| `--gap-lg` | 大间距 | `1.5rem` |
| `--padding-sm` | 小内边距 | `0.5rem` |
| `--padding-md` | 中内边距 | `0.75rem` |
| `--padding-lg` | 大内边距 | `1.25rem` |

#### 侧边栏

| 变量 | 说明 |
|------|------|
| `--sidebar-bg` | 侧边栏背景 |
| `--sidebar-border` | 侧边栏边框 |
| `--sidebar-active-indicator` | 侧边栏当前指示色 |

#### 日志面板

| 变量 | 说明 |
|------|------|
| `--log-shell-bg` | 日志面板背景 |
| `--log-text-color` | 日志文字颜色 |
| `--log-time-color` | 日志时间戳颜色 |

#### 标签页 / 导航

| 变量 | 说明 |
|------|------|
| `--tab-bg` | 标签背景 |
| `--tab-hover-bg` | 标签 hover 背景 |
| `--tab-text` | 标签文字 |
| `--tab-active-bg` | 活动标签背景 |
| `--tab-active-text` | 活动标签文字 |

#### 浮动面板 / 底部栏

| 变量 | 说明 |
|------|------|
| `--floating-bg` | 浮动面板背景 |
| `--footer-bg` | 底部栏背景 |
| `--footer-border` | 底部栏边框 |

### 自定义 CSS 示例

#### 更换主色调

```css
:root {
  --primary-color: #e91e63;
  --primary-hover: #c2185b;
}
```

#### 调整字体大小

```css
body {
  font-size: 15px;
}

h2 {
  font-size: 1.2rem;
}
```

#### 自定义侧边栏宽度

```css
.sidebar {
  width: 280px !important;
}
```

#### 修改卡片圆角

```css
:root {
  --radius-md: 6px;
  --radius-lg: 12px;
}
```

#### 自定义代码块/日志字体

```css
.css-editor,
.log-panel {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
```

### 动画控制

动画通过 `<html>` 标签上的 `data-animations` 属性控制：

- `data-animations="on"` — 正常播放所有动画（默认）
- `data-animations="off"` — 禁用所有 CSS 动画和过渡

在外观设置页面中切换「启用页面过渡动画」开关即可控制此属性。你也可以在自定义 CSS 中用此选择器编写条件样式：

```css
[data-animations="off"] .my-element {
  /* 仅在动画关闭时生效 */
}
```

### 主题开发指南

1. 打开 **外观设置** 页面
2. 选择一种 **UI 风格**（浅色/深色/霓虹/毛玻璃/极简）
3. 为当前风格选择一种 **配色方案**（默认/初音绿/天依蓝/樱粉/紫苑/黄昏/深林）
4. 在 **自定义 CSS** 编辑器中输入额外样式，点击「应用」
5. 所有设置自动保存到浏览器本地存储，刷新页面后自动恢复

### CSS 书写规范

- **优先使用 `var(--xxx)` 引用已有变量**——代码库中的变量保持语义化，方便统一管理和主题切换
- **避免使用 `!important`**——除非确有必要覆盖内联样式，否则应依赖选择器特异性
- **选择器特异性建议**——使用类选择器（`.card`）而非标签选择器，避免与组件内部样式冲突
- **不建议在自定义 CSS 中覆盖 `:root` 变量**——外观设置页面的配色方案已经提供了完整的变量管理。请使用 UI 风格 + 配色方案矩阵来修改主题色，仅在需要细粒度调整时使用自定义 CSS
