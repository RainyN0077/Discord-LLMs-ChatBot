# ELA-Bot — frontend-vue

新一代 Web 控制面板：**Vue 3.5 + Vite 8 + TypeScript + naive-ui**，覆盖 Bot 管理、提供商切换、模型设置、提示词工坊、调试器等全部功能模块。

与旧版 Svelte 控制面板（仓库根 `frontend/`）**并存、隔离、互不影响**——两者共享同一套后端 REST API，但拥有独立的端口（`8095`）、构建产物与依赖。迁移进度见仓库 Issue 跟踪。

## 技术栈 / Tech Stack

| 层 | 技术 |
|----|------|
| 框架 | Vue 3.5（`<script setup>`） |
| 构建 | Vite 8 + `@vitejs/plugin-vue` |
| UI 组件库 | naive-ui 2.x（真实组件，非二次封装） |
| 状态管理 | Pinia（setup store 风格） |
| 路由 | vue-router |
| 国际化 | vue-i18n（zh / en 双语 + 6 语言复用英文） |
| 测试 | Vitest 4 + @vue/test-utils + jsdom |

## 目录结构 / Structure

```
frontend-vue/
├── src/
│   ├── api/              # 后端 API 客户端（fetchWithAuth：X-API-Key 注入 + 401 自动重试）
│   │   ├── client.ts     #   统一错误规范化 + auth 引导
│   │   ├── bots.ts       #   Bot CRUD / 状态 / 成员搜索
│   │   ├── providers.ts  #   提供商列表 / 切换
│   │   ├── prompts.ts    #   提示词工坊预设 / 预览
│   │   └── ...           #   config / logs / memory / usage / debug
│   ├── stores/           # Pinia stores（bots / logs / providers / theme / configs / auth）
│   ├── components/       # 共享组件（BotCard / LogPanel / common/* / config/*）
│   ├── layouts/          # 主布局（侧栏 + 顶栏 + 内容区，断点 768 折叠）
│   ├── pages/            # 页面（Providers / ModelSettings / PromptStudio / Debugger / UserOptions / ...）
│   ├── locales/          # i18n 目录（zh.ts / en.ts / languages.ts）
│   ├── styles/           # 全局样式（global.css / theme.ts）
│   ├── themes/           # 设计 token（themes.ts / naiveMapping.ts）
│   ├── router/           # 路由表
│   ├── utils/            # 工具（feedback / fontStore）
│   └── test/setup.ts     # Vitest 全局 setup
├── vite.config.ts        # dev 端口 8095 + /api 代理 + vitest 配置
└── tsconfig*.json
```

## 开发命令 / Commands

```bash
npm install          # 安装依赖
npm run dev          # 开发服务器 → http://localhost:8095（strictPort）
npm run build        # 类型检查（vue-tsc --noEmit）+ 生产构建到 dist/
npm run typecheck    # 仅类型检查（0 错误标准）
npm test             # 运行全部单元测试（vitest run）
npm run test:watch   # 监听模式
npm run preview      # 预览生产构建
```

### 开发代理 / Dev Proxy

`vite.config.ts` 将 `/api` 前缀请求代理到后端（`changeOrigin: true`）：

```ts
proxy: {
  '/api': {
    target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8093',
    changeOrigin: true,
  },
}
```

默认后端地址 `http://localhost:8093`；可通过环境变量覆盖：

```bash
VITE_API_PROXY_TARGET=http://192.168.1.100:8093 npm run dev
```

## 设计约定 / Design Conventions

### Token 体系（themes.ts，48 键）

`src/themes/themes.ts` 是主题数据的单一事实来源，完整变量集见 `CSS_VAR_KEYS`（48 键 = 20 基础色 + 24 样式级默认 + 4 配色方案专属）：

| 分组 | 键数 | 说明 |
|------|------|------|
| base（`--bg-color` / `--text-color` / `--primary-color` 等） | 20 | 每种 style 的基调配色 |
| defaults（`--shadow` / `--radius-md` / `--tab-*` / `--text-muted` 等） | 24 | 样式级兜底默认值 |
| scheme-only（`--sidebar-active-*` 等） | 4 | 仅配色方案覆盖 |

结构：9 种 style（light / dark / neon / glass / minimal / dawn / midnight / nature / cyberpunk）× 13 种配色方案，浅色/深色各一套变量集，合并规则与旧版 `themeStore.js` 逐项对齐。组件内禁止硬编码颜色，一律使用 CSS 变量（`var(--xxx)`）或 naive-ui 主题映射（`themes/naiveMapping.ts`）。

### 响应式断点（768px）

统一断点 `768px`：`layouts/MainLayout.vue` 的 `n-layout-sider :breakpoint="768"` 控制侧栏自动折叠，页面内移动端适配使用 `@media (max-width: 768px)`。

### 三态规范

需要区分"未发生 / 进行中 / 结果确定"的状态一律采用三态展示，不省略中间态：

- **提供商健康徽章**（ProvidersPage）：未配置 → `default` 灰态；已配置但健康未知（`healthy === null`）→ `warning` 中态；已确定 → `success` / `error`
- **模型连接测试**（LLMProviderCard）：未测试 / 测试中 / 通过·失败三态呈现
- **成员搜索**（BlocklistTab）：HTTP 200 也可能携带 `error` 字段（Discord 侧限速/超时），必须作为独立分支处理，而非默认视为成功

## 测试 / Testing

```bash
npm test              # 全部测试（vitest run）
npx vitest run src/components/BotCard.test.ts   # 单文件
npx vitest --watch    # 监听模式
```

- 运行环境：`jsdom`（`vite.config.ts` → `test.environment`），`globals: false`，测试文件匹配 `src/**/*.test.ts`，前置加载 `src/test/setup.ts`
- 全局 setup（`src/test/setup.ts`）提供：`ResizeObserver` / `matchMedia` shim（naive-ui 依赖）、内存版 `localStorage` / `sessionStorage`（避免 Node webstorage 告警），并在每个用例后清理存储与 `vi.unstubAllGlobals()`
- 组件测试模式：**挂载真实 naive-ui 组件**（`NDialogProvider` / `NMessageProvider` 等按需包裹）+ 真实 Pinia store + `vi.mock()` 拦截 API 模块（如 `@/api/bots`），与旧测试互不干扰

## 与后端 API 的关系 / Backend API

- 所有请求经 `src/api/client.ts` 的 `fetchWithAuth` 发出，携带 **`X-API-Key`** 请求头（值 = 后端 `api_secret_key`）
- **token 存储**：API Key 以 btoa 编码保存在 `sessionStorage`（键 `_ak`），会话级生命周期，不持久化到 localStorage
- **自动引导**：无 key 时前端调用 `GET /api/auth/status`（仅 localhost 放行）获取密钥并暂存
- **401/403 自愈**：收到鉴权失败后清空旧 key → 重新引导 → 原请求自动重试一次；仍失败则抛出 `AuthError`
- 错误统一规范化为 `{ status, message }`，调用方可按 `status`（如 429 限速）分派逻辑
