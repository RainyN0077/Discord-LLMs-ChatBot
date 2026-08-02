# ELA-Bot UI 重构 · 同类产品 UI 设计调研报告

> 调研时间：2026-08-02
> 目的：为 ELA-Bot（Vue3 + Naive UI 的 Bot/LLM 管理控制面板）全面重构提供外部设计参考，
> 与现有 6 套风格（Aurora / Matrix / Zen / Synthwave / Ink / Pixel）对照融合。
> 结论先行：**现有 6 套风格的美术方向成立且可作主线**；外部参考主要贡献在「设计系统刻度、
> token 分层、状态设计、信息密度」四个通用层，以及若干功能页面的交互范式。

---

## 1. 调研对象（同类产品 6 款）

| 产品 | 定位 | Stars | UI 特征（与本项目相关） |
|------|------|-------|--------------------------|
| **Open WebUI** | 自托管 AI 界面（Ollama/OpenAI/RAG） | 148k | 暗色优先、自定义主题与品牌（企业版 theming）、侧栏会话管理、PWA/移动端、多语言 i18n、模型下拉与多模型并行 |
| **LobeHub / LobeChat** | AI Agent 工作台/聊天 | 81k | 拥有完整公开设计系统（DESIGN.md）：语义化 token、主题色可选、Geist 字体、克制动效、组件分层；移动端一等公民 |
| **LibreChat** | 多提供商 AI 聊天平台 | 41k | ChatGPT 风格 + **Admin Panel**（用户/组/角色管理）、**Reasoning UI**（思维链展示）、可定制界面（适配新手与重度用户）、35+ 语言 |
| **Dify** | LLM 应用开发平台 | 151k | 可视化工作流画布、**Prompt IDE**（提示词编辑/对比/测试）、模型提供商管理（数百家）、RAG 流水线、LLMOps 观测 |
| **Langfuse** | LLM 可观测性平台 | 32k | **Traces 追踪**（调用时间线/树、成本/延迟指标卡）、**Prompt 版本管理**、**Playground**（参数+模型试验场）、Datasets/Evaluations |
| （生态补充） | LiteLLM / Flowise / RAGFlow / Langflow | — | 模型网关管理、可视化编排、知识库管理——与 ELA-Bot 的知识库/提供商模块同类 |

## 2. 提炼的通用设计规律（可直接借鉴）

### 2.1 设计 Token 体系（LobeHub DESIGN.md 最完整，作为基准）

- **色彩语义分层**（名称即职责，亮/暗自动切换）：
  - 文字 4 级：`colorText`（主）/ `Secondary`（标签）/ `Tertiary`（占位/元数据）/ `Quaternary`（禁用）
  - 表面 4 级：`BgLayout`（页面画布）/ `BgContainer`（卡片）/ `BgContainerSecondary`（次级区分）/ `BgElevated`（弹层）
  - 边框与填充半透明：`colorBorder`（强边）/ `colorBorderSecondary`（日常分隔线）+ `colorFill` 4 级（hover/active 洗涤）
  - 功能色 4 个（成功/警告/错误/信息），**主色默认单色（近黑/近白），用户选色后才上色**——保持默认界面安静
- **主题色可选**：主色 12 色选项 + 中性色 5 种（mauve/slate/sage/olive/sand）——与 ELA-Bot 现有「13 套配色 scheme」机制同构，方向一致
- **排版刻度**：正文 14px（12/14/16 三档，无 13px）、行高 1.57；标题 38/30/24/20/16
- **间距刻度**：4px 基准（4/8/12/16/20/24/32）；圆角独立刻度：4（标签）/6（输入）/8（默认）/12（弹层）
- **阴影三级且克制**：卡片 barely-there（`0 3px 1px -1px rgba(26,26,26,.06)`）、弹层中等、弹窗最强——**优先用边框而非阴影表达层级**
- **动效标准**：状态变化 100-200ms、弹窗 ≤300ms、不做循环装饰动画；AI 等待用专用 loader（骨架屏/神经网络动画）而非随意 spinner；尊重 `prefers-reduced-motion`
- **文案规范**：动词+名词命名动作（Create Agent 而非 OK/Submit）；进行中状态用「正在…」（Generating…）；80% 信息 20% 温度；**所有界面设计四态：empty / loading / error / success**
- **组件层级**：无头原语（headless primitives）优先，组合组件其次，禁止重复造轮子

### 2.2 功能页面范式（对应 ELA-Bot 的页面）

| ELA-Bot 页面 | 同类参考 | 借鉴点 |
|--------------|----------|--------|
| Providers 提供商 | Dify 模型管理、LiteLLM | 卡片网格 + 健康状态 + 延迟/成本指标；「当前模型」高亮；点卡即切换 |
| ModelSettings 模型设置 | Langfuse Playground、Dify Prompt IDE | **试验场范式**：参数滑块（temperature/top_p/max_tokens）实时联动 + 测试对话 + 多模型并排对比 |
| PromptStudio 提示词工坊 | Langfuse Prompt 管理、Dify Prompt IDE | 模板列表（版本化）+ 编辑器 + 占位符插入 + 情景模拟；可加「版本历史」 |
| Debugger 调试器 | Langfuse Traces、LibreChat Reasoning | **Trace 时间线/树**（调用链、耗时、token 成本）；思维链 Reasoning UI（思考过程可折叠展示）；捕获 JSON 详情 |
| UserOptions 用户选项 | LibreChat Admin Panel | 用户/组/角色列表 + 权限开关 + 黑白名单表格 |
| ConfigPanel 控制面板 | Open WebUI 设置 | 分组卡片 + 导入导出 + 标签编辑 |
| 日志面板 | Langfuse/LibreChat | 级别过滤 + 时间线 + 自动滚动 + 暂停，行内展开详情 |

### 2.3 信息架构与体验

- **侧栏 + 顶栏**仍是 AI 工具主流（Open WebUI / LibreChat / LobeChat 均如此），ELA-Bot 现有布局正确
- 移动端不是事后补（LobeHub 有独立 mobile 路由）；至少保证 768/640 断点可用
- 弹窗/确认尽量用「轻提示 + 可撤销」（LobeHub 建议 restore control），非破坏性操作不做二次确认

## 3. 与现有 6 套风格及主题系统的对照

### 3.1 现有系统的强项（保持）

- 48 CSS 变量 + 9 风格 × 13 配色 scheme + `data-effects` 特效开关 + `[data-style]` 装饰层机制——**比多数同类产品（含 Open WebUI）的主题体系更完整**；LobeHub 的「主色可选」我们已有（scheme chips）
- 六套风格方向独特（Aurora 玻璃 / Matrix 终端 / Zen 极简 / Synthwave 蒸汽波 / Ink 水墨 / Pixel 像素），无同类产品覆盖
- 特效开关 + 动画总开关 + reduced-motion 三权分立，业界少见

### 3.2 差距清单（外部参考提示的改进空间）

| # | 差距 | 参考来源 | 建议 |
|---|------|----------|------|
| G1 | 变量刻度不统一：`--radius-md` 10px / `--radius-lg` 16px，间距用 rem 随意；无 fill 刻度 | LobeHub DESIGN.md | 统一为 4px 刻度（4/8/12/16/20/24/32）+ 圆角 4/6/8/12；补齐 `--fill-*` hover/active 刻度 |
| G2 | 阴影偏大（`0 18px 36px` 级），层级靠阴影而非边框 | LobeHub | 默认边框优先，阴影收敛到三级且克制 |
| G3 | 四态不完备：空态/加载态/错误态在部分页面缺失（如无 Bot、无日志、加载中） | LobeHub 文案规范 | 完整版统一实现 EmptyState / Skeleton / ErrorBanner / Success 反馈 |
| G4 | 无 Playground 试验场：模型参数与提示词测试分离 | Langfuse / Dify | ModelSettings 加「测试对话」区（参数实时生效）；PromptStudio 已有 ScenarioSimulator 雏形 |
| G5 | Debugger 无调用链视图（Trace 树） | Langfuse | 捕获页加时间线/树形展开（request → response → tool_call 链） |
| G6 | 动效时长无标准（组件各自 transition .15-.3s 混用） | LobeHub | 定义统一动效刻度：交互 150ms、弹层 250ms、页切换 280ms |
| G7 | 思考过程（Reasoning）无展示 | LibreChat | 模拟对话支持「思考中…」→ 可折叠思维链气泡 |
| G8 | 文案规范（动作命名/四态文案/进行时）未统一 | LobeHub Voice & Content | 完整版 zh/en 文案按「动词+名词」「正在…」规范重写 |
| G9 | 字体刻度缺标题层级（h1-h5）与等宽数值对齐 | LobeHub | 定义标题刻度 20/18/16 + 数值表格用等宽 + tabular-nums |

## 4. 融合建议（执行方向）

1. **通用层（所有风格共享）**：按 G1/G2/G6/G9 建立统一刻度 token（间距/圆角/阴影/动效/字号），六套风格只覆盖色板与质感，刻度一致——这是重构的「地基」
2. **功能层**：按 2.2 表格补 Playground（G4）、Trace 视图（G5）、Reasoning 气泡（G7）、四态（G3）、文案规范（G8）
3. **风格层**：维持 6 套风格不变（用户认可），对照外部参考微调质感上限（如 Aurora 玻璃参考 Open WebUI 暗色深度、Zen 对齐 LobeHub 克制哲学）
4. **主题层**：保留 48 变量 + scheme + 特效开关；可选增强：主色「默认单色、选色上色」哲学（LobeHub）已在 default scheme 体现，无需改动

## 5. 参考链接

- LobeHub DESIGN.md（设计系统全文）：https://github.com/lobehub/lobehub/blob/canary/DESIGN.md
- Open WebUI：https://github.com/open-webui/open-webui
- Dify：https://github.com/langgenius/dify
- LibreChat：https://github.com/danny-avila/LibreChat
- Langfuse：https://github.com/langfuse/langfuse
- 本项目现有风格示例：`frontend-vue/examples/`（6 套 + 特效开关演示）
