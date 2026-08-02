# ELA-Bot「完整 UI 功能版」演示网页 — Design Document

> 阶段：Stage 2（solutions-architect）
> 范围分类：BOUNDED 偏高沿（Stage 0 requirement-triage 结论）
> 基线：`frontend-vue/examples/` 现有 6 套风格示例页（aurora / matrix / zen / synthwave / ink / pixel）+ `index.html` 总览
> 输出：本文档 + 待实现文件 `frontend-vue/examples/full-ui/` 下 7 个新文件（实现阶段由 implementer 完成）
> 硬约束：零外部依赖、零网络请求、`file://` 双击可开、**不修改 `frontend-vue/src` 生产端与现有 examples 9 个文件**

---

## 0. 三个开放问题的裁决（先行给出）

### Q1. aurora/matrix 特效 id 集合与装饰补齐；zen 是否放面板

**裁决：**

| 页面 | 特效面板 | fx id 全集（按面板顺序） | 缺省装饰补齐 |
|------|----------|--------------------------|--------------|
| aurora | 渲染 | `aurora`、`glassblur`、`glow` | 补 glow（aurora/glassblur 装饰已有） |
| matrix | 渲染 | `grid`、`scanline`、`blink`、`glow` | 补 glow（网格/扫描线/闪烁装饰已有） |
| zen | 渲染（空态） | `[]`（无 id） | 不补齐（设计哲学即零装饰） |
| synthwave | 渲染 | `sunset`、`grid`、`scanline`、`glow` | 不补齐（原样迁移现有实现） |
| ink | 渲染 | `wash`、`fade` | 不补齐（原样迁移现有实现） |
| pixel | 渲染 | `blink`、`scanline`、`shine` | 不补齐（原样迁移现有实现） |

理由：

1. **6 页统一渲染面板组件**，消除「README 声称有、实际 3 页缺」的契约偏差（Stage 1 修正结论）。zen 页面板传入空 id 列表，显示生产端同款空态文案「当前风格无特效开关」（对齐 `AppearanceSettingsPage` 行为），而非移除面板——组件结构统一，行为诚实。
2. **fx id 对齐生产端 `EFFECT_DEFS` 语义**（grid / scanline / glow / blink / glassblur），风格专有 id（aurora / sunset / wash / fade / shine）为演示页专用，未来可注册进生产端。aurora 玻璃拟态用 `glassblur`（与生产端同名，避免再造词）。
3. **补齐规范**（aurora 需新增 `glow` 装饰、matrix 需新增 `glow` 装饰）：

```css
/* aurora: 渐变文字与按钮辉光归属 glow 特效（新增装饰规范） */
.brand, .page-title { transition: color .2s ease; }          /* glow 关闭时的降级底 */
html.fx-off-glow .brand,
html.fx-off-glow .page-title { background:none; -webkit-text-fill-color:var(--fg); color:var(--fg); }
html.fx-off-glow .stat-card::before,
html.fx-off-glow .card::before { background:none; }           /* 高光线属 glow */
html.fx-off-glow .btn-primary { box-shadow:none; }
html.fx-off-glow .btn-primary:hover { transform:none; box-shadow:none; }

/* matrix: 荧光外发光归属 glow（新增装饰规范） */
html.fx-off-glow .bot-card.active,
html.fx-off-glow .provider-card:hover { box-shadow:none; border-color:var(--card-border); }
html.fx-off-glow .status-dot.error { box-shadow:none; }
```

4. **固定径向光斑（body 背景）不属于特效开关**——按生产端语义「关闭特效仅消失动画/滤镜/装饰层；风格骨架保留」（README 第 3 节）。光斑是风格底色的一部分，不在任何 fx id 下。

### Q2. file:// 跨页存储策略

**裁决：每页独立存储（不共享）。**

- 事实前提：`file://` 下每页存储域隔离（Stage 1 已确认），规范不保证跨页共享，共享方案依赖浏览器特定行为，违反「零外部依赖」精神。
- 独立存储最简、零耦合、单文件自包含（与现有 6 页哲学一致）。**外观设置只影响本页**——可接受：每页入口的默认风格即该页风格，逐页体验天然符合预期。
- 6 页共用**相同的 key 名**（存储域已隔离，不会冲突），代码可复制、实现一致。
- 附带裁决：外观设置页的「风格切换」不做跨风格 token 注入预览（避免每页内嵌 6 套 token 变量导致体积爆炸），改为：当前风格卡片可切换子项（zen 亮/暗），其余 5 个风格卡片以链接跳转到对应 full-ui 页。

### Q3. 单文件体积上限

**裁决：单文件 ≤ 120KB / ≤ 2200 行（HTML+CSS+JS 合计），结构纪律强制。**

- 预估 10 模块全交互 + 四态 + i18n ≈ 80-100KB / 1500-1900 行，上限留 20% 余量防蔓延。
- 结构纪律（每页强制，implementer 切片验收项）：
  1. 文件头注释块（固定模板，见 §12.2）；
  2. CSS 按 §12.3 区块顺序 + 区块分隔注释 `/* ===== xxx ===== */`；
  3. JS 按 §12.4 六分区（I18N / MOCK / STATE / UI / 模块 render / 入口）；
  4. 组件函数化：每个可复用 UI 结构 = 一个命名函数（`renderBotList()` / `renderSkeleton()` / `openModal()`…），禁止在视图 render 内联重复 DOM 字符串；
  5. 单视图 render 函数 ≤ 60 行，超出则拆子函数。

---

## 1. 架构决策

### 1.1 单文件 vs 共享 assets：**单文件 × 7（否决共享 assets 方案）**

| 方案 | file:// 可行性 | 裁决理由 |
|------|----------------|----------|
| A. 共享 assets（shared.css + shared.js + 每页 HTML） | 技术上可行（`<link rel="stylesheet" href="shared.css">` 相对路径在 file:// 下可加载） | 否决：① 违背现有 6 页「单文件自包含」先例与「双击即开、拖一个文件即可分享」的交付语义；② 共享文件改动影响全部页面，回归面大；③ 收益有限——6 页共享的仅布局骨架 CSS（约 6-8KB），风格差异与模块交互逻辑无法共享；④ 部分浏览器安全策略对 file:// 子资源加载存在不可预测行为 |
| B. 单文件 × 7（每页自包含全部 CSS/JS） | 完全可行 | 采纳：与现有 6 页完全一致；零加载失败路径；体积预算内（Q3）可承受重复骨架成本 |

**配套措施**：骨架 CSS 的「标准块」在 §12.3 给出（实现时逐页复制保持一致），切片 S7 做骨架一致性验证（关键类名 diff 清单，见 §12.5）。

### 1.2 视图切换机制：**data-view 显示隐藏 + hash 同步（双机制，零依赖）**

- 主机制：7 个 `.view` 容器，`hidden` 属性切换显示隐藏：

```html
<main class="content">
  <div class="content-inner">
    <section class="view" id="view-providers" data-view="providers"></section>
    <section class="view" id="view-model-settings" data-view="model-settings" hidden></section>
    <!-- ... 共 7 个 -->
  </div>
</main>
```
```css
.view[hidden]{display:none}
```
```js
function showView(id){
  if (hasDirtyForm()) return        // 脏表单确认（见下）：取消则中止切换
  document.querySelectorAll('.view').forEach(function(v){ v.hidden = v.dataset.view !== id })
  navItems.forEach(function(n){ var on = n.dataset.view === id; n.classList.toggle('active', on); on ? n.setAttribute('aria-current','page') : n.removeAttribute('aria-current') })
  window.location.hash = id      // 同步 hash（hidden 容器无滚动副作用）
  if (!renderedViews[id]) { viewRenderers[id](); renderedViews[id] = true }   // 懒渲染：首次进入才 render
  if (viewRefreshHooks[id]) viewRefreshHooks[id]()  // 视图激活刷新钩子：每次激活调用（幂等，见下）
}
var HASH_VIEWS = {providers:1, 'model-settings':1, config:1, 'prompt-studio':1, debugger:1, 'user-options':1, appearance:1}
window.addEventListener('hashchange', function(){ var v = location.hash.slice(1); if (HASH_VIEWS[v]) showView(v) })
```
- 启动：读 `location.hash`（白名单 `providers|model-settings|config|prompt-studio|debugger|user-options|appearance`），非法/缺省 → `config`（控制面板，与现有页面默认 active 一致）。
- 懒渲染：视图首次激活时渲染，状态缓存于 `App.state`，再次切换不重渲染（防数据丢失）——但**每次激活都调用该视图的刷新钩子**（见下），解决「config 为默认视图启动即渲染 → 切换 Bot/提供商后不再重渲染」导致的联动失效（HIGH-1）。
- **视图激活刷新钩子**（`viewRefreshHooks`，HIGH-1 修复机制）：
  - 每个「消费全局状态（`currentBotId` / `currentProvider`）」的视图注册 `refreshX()`；`showView()` 在每次激活视图时调用（首次渲染之后）。
  - 钩子**幂等**：记录上次渲染时的 `lastBotId` / `lastProvider`，仅当检测到变化才局部重渲染对应区块（config 字段子集、model-settings 模型下拉预设 + 请求体摘要），无变化时零操作（不重置输入焦点、不打断本地编辑态）。
  - 当前注册清单：`config` → `refreshConfig()`（M8 Bot 选中联动）、`model-settings` → `refreshModelSettings()`（M1 提供商切换联动）；其他视图不注册（无跨视图状态消费）。
  - 除 `showView()` 外，M1「设为当前」与 M8「选中 Bot」两个**视图内/全局操作**在改变 `currentProvider`/`currentBotId` 后也直接调用对应钩子（不等待下次激活），行为定义见 §3 M1/M8 行。
- **脏表单检测**（`hasDirtyForm()`，HIGH-1 补充）：表单视图（config / model-settings / prompt-studio / user-options）维护「已加载快照」与 `dirty` 标志（input/textarea/select 的 change/input 事件置位，保存/重置后清除）。`showView()` 切换前、以及 M1「设为当前」/ M8「选中 Bot」发起前，若当前激活视图 `dirty` → `confirmDialog`「当前表单有未保存的更改，确定切换？」——确认 → 丢弃本地编辑并继续；取消 → 中止操作（不更新状态、不发联动）。
- 不选纯 hash 路由的理由：零依赖下 URL 解析与历史栈管理收益有限，data-view 显隐是唯一可靠的「当前视图」来源；hash 仅作增强（刷新保持视图、可链接直达）。

### 1.3 存储裁决（见 Q2）+ key 设计（见 §5）

### 1.4 全局横切组件定位

Bot CRUD（侧栏）、日志面板（底部）、toast/弹窗（浮层）是**全局组件**，每页常驻，不隶属于任何视图。视图只负责 `.content-inner` 内部。

---

## 2. 每页模块清单与导航

### 2.1 导航结构（7 项，全部视图化）

| 导航项 | 视图 id | 承载模块 |
|--------|---------|----------|
| 提供商 | `providers` | 提供商管理 |
| 模型设置 | `model-settings` | 模型设置 + Playground（单模型测试对话） |
| 控制面板 | `config` | Bot 配置（默认视图，对齐现有页面 active 项） |
| 提示词工坊 | `prompt-studio` | 模板 + 占位符 + 情景模拟 |
| 调试器 | `debugger` | 捕获列表 + Trace 时间线 + Reasoning 折叠 |
| 用户选项 | `user-options` | 黑白名单规则 CRUD |
| 外观设置 | `appearance` | 风格 / 配色 / 特效 / 动画开关 |

### 2.2 全局组件（7 视图之外，每页常驻）

| 全局能力 | 承载模块 | 位置 |
|----------|----------|------|
| 侧栏 Bot 列表 + 新建/启动/停止/重启/删除/重命名/导入/导出 | Bot CRUD | `.sider` |
| 日志面板（拖拽/折叠/自动追加/清空/级别着色） | 日志面板 | `.log-footer` |
| toast + 确认/输入弹窗 | toast/弹窗 | `.toast` / `.modal` 浮层 |
| 特效面板 + 语言切换 | 外观设置（子集） | 顶栏 `.topbar-right` |

### 2.3 页面内视图渲染规划

每个视图按四态组件规范（§7）组织：`empty-state` / `skeleton` / `error-banner` 三选一 + `success` 内容。每视图结构 = 页头（`page-head`）+ 1..n 个 `card` 区块（复用现有 `.card` 体系）。

---

## 3. 10 模块最小功能集矩阵

> 列定义：**功能点**（最小实现，防范围蔓延）· **交互** · **四态**（E=empty / L=loading / R=error / S=success）· **mock 延迟**。
> 统一 mock 层约定：`mockDelay(base, jitter)`，延迟 = base ± 30% 随机；加载类 400-800ms、保存类 500-700ms、网络类 800-1500ms、生成类 1200-2000ms、删除/清空类 300ms（即时反馈；M5 删除/清空、M9 清空日志、M8 删除 Bot 均属此类）。

### M1 提供商管理（视图：providers）
| 功能点 | 交互 | 四态 | mock 延迟 |
|--------|------|------|-----------|
| 11 家提供商卡片（名称/模型/健康/延迟/当前标记） | 卡片 hover；当前提供商角标 | L：整页 skeleton；R：加载失败+重试；S：11 卡渲染；E：不适用（mock 恒有数据） | 加载 600ms |
| 健康检测（单家刷新） | 卡片「测试」→ 健康 chip + 延迟刷新 | L：按钮「检测中…」；R：置 offline；S：置 ok/slow | 检测 900ms |
| 切换当前提供商 | 「设为当前」→ 更新 is_current + 模型设置联动；切换成功 → 调 `refreshModelSettings()`（model-settings 视图检测 `currentProvider` 变化后局部重渲染模型下拉预设 + 请求体摘要，不整视图重建） | S：toast「已切换」；R：mock 失败演示；发起前若 model-settings 参数表单有脏编辑 → confirmDialog 确认 | 切换 700ms |
| 连接测试（API Key + base_url 表单） | 弹窗内「测试连接」→ 结果区 | L：按钮「正在测试连接…」；S：成功+延迟；R：失败信息 | 测试 1200ms |

### M2 模型设置 + Playground（视图：model-settings）
| 功能点 | 交互 | 四态 | mock 延迟 |
|--------|------|------|-----------|
| 推理参数表单（temperature 0-2 / max_tokens / top_p 0-1 / top_k / frequency_penalty ±2 / presence_penalty ±2，范围校验） | 输入/滑杆；越界即时标红 | S：表单渲染；R：校验错误行内提示 | — |
| 模型名 + 提供商联动 | 下拉（11 家模型预设，可手输） | S：联动更新 | — |
| Playground 对话（单模型） | 输入 → 发送 → 回复；会话内多条 | E：初始引导「输入消息开始测试」；L：气泡「正在思考…」；S：回复气泡；R：失败气泡+重试 | 回复 1600ms |
| 模拟失败开关 | checkbox「模拟失败」→ 发送必走 error 态 | R：error-banner + 重试 | — |
| 参数 → 请求体摘要联动 | 参数变更后显示请求体摘要（只读 JSON） | S：摘要更新 | — |

### M3 控制面板 · Bot 配置（视图：config）
| 功能点 | 交互 | 四态 | mock 延迟 |
|--------|------|------|-----------|
| 配置表单（字段子集见 §4.2：基础/推理/上下文/自动化/记忆/关键词） | 输入/下拉/开关 | L：首载 skeleton；S：表单填充 | 加载 500ms |
| 保存 / 重置 | 「保存更改」→ toast+日志；「重置」→ 恢复未保存态 | S：toast「已保存」；R：校验失败（temperature 越界等） | 保存 600ms |
| 高级折叠区（custom_headers 计数 / interaction_history 摘要 / plugins 计数，只读） | `<details>` 展开 | S：只读渲染 | — |
| api_secret_key 展示 | 遮罩 + 显示/隐藏切换 | S：遮罩态 | — |

### M4 提示词工坊（视图：prompt-studio）
| 功能点 | 交互 | 四态 | mock 延迟 |
|--------|------|------|-----------|
| 模板编辑（4 必填键 + 10 可选键，对齐 prompts.py DEFAULT_TEMPLATES） | 左侧导航树（4 组）→ 右侧 textarea；必填键空值标红 | L：加载预设；S：模板载入；R：载入失败 | 加载 500ms |
| operational_instructions 列表 | 添加/移除/编辑条目 | S：条目操作 | — |
| 占位符面板 | 占位符清单点击插入光标位置 | S：插入 + toast | — |
| 情景模拟器（用户消息/角色/图片数/是否回复/回复内容） | 「生成预览」→ 系统提示词预览 + 用户请求预览 + 构建日志 | L：按钮「正在生成…」；S：三栏预览；R：用户消息为空 → 失败 | 生成 1400ms |
| 预设管理（默认预设「(默认)开箱即用」+ 另存为/加载/删除） | 下拉选择 → 载入；另存为弹窗 | L：加载/保存中；S：toast 成功；R：默认预设覆盖拒绝（生产语义） | 各 500ms |

### M5 调试器（视图：debugger）
| 功能点 | 交互 | 四态 | mock 延迟 |
|--------|------|------|-----------|
| 捕获列表（DebugCaptureSummary 8 条 mock，表格式） | 点击行 → 详情 | E：全清后「暂无捕获」+ 新建演示按钮；L：skeleton 行；S：列表；R：加载失败 | 列表 600ms |
| 捕获详情（system_prompt / history_for_llm 折叠） | `<details>` 展开 | L：详情加载；S：详情渲染 | 详情 400ms |
| Trace 时间线（request → tool_call → response 链，来自 intermediate_llm_responses） | 垂直时间线；tool_call 节点可展开 | S：时间线；R：解析失败 → 降级显示原文 | — |
| Reasoning 折叠气泡 | Reasoning 段默认折叠，点击展开 | S：折叠/展开 | — |
| 清空 / 删除捕获 | 行删除 + 全清 | S：删除 + 日志追加；E：空态 | 300ms |

### M6 用户选项（视图：user-options）
| 功能点 | 交互 | 四态 | mock 延迟 |
|--------|------|------|-----------|
| 总开关 + member_search_timeout_ms | 开关 + 数字输入（1000-30000 校验） | S：渲染 | — |
| 规则列表（rules: Dict[name, UserOptionRule]） | 规则卡：名称/scope_type(global|guild|channel|dm)/scope_id/mode(blacklist|whitelist)/whitelist_behavior | E：空态「暂无规则」；L：加载；S：规则卡；R：加载失败 | 加载 500ms |
| 规则 CRUD | 弹窗表单；删除确认 | S：toast 保存成功；R：scope_id 缺失/非法 → 行内错误 | 保存 600ms |
| 用户条目（users: Dict[str, UserBlocklistEntry]） | 规则内展开：user_id / user_display_name / blacklist_mode / negative_portrait | S：条目增删改 | — |
| 优先级说明 | 静态提示条「规则优先级：频道 > 服务器 > 全局」 | — | — |

### M7 外观设置（视图：appearance）
| 功能点 | 交互 | 四态 | mock 延迟 |
|--------|------|------|-----------|
| 风格选择（6 风格卡） | 当前风格高亮 + 子项切换（zen 亮/暗）；其余 5 卡链接跳转对应页 | S：卡片渲染 | — |
| 配色展示 | 当前页色板 swatch（只读） | S：色板渲染 | — |
| 特效开关（内嵌 fx 面板完整版） | 全量 fx checkbox（本页 id 集合；zen 页空态文案） | S：持久化 + 即时生效 | — |
| 动画开关 | 「界面动画」总开关（`html.anim-off`） | S：即时生效 + 持久化 | — |
| 亮暗变体（zen） | 亮/暗单选（持久化 `html.dark`） | S：即时生效 | — |

### M8 Bot CRUD（全局：侧栏）
| 功能点 | 交互 | 四态 | mock 延迟 |
|--------|------|------|-----------|
| Bot 列表（4 个默认 mock：bot_main/bot_alpha/bot_stats/bot_legacy，含 running/stopped/error 三态） | 点击选中 → `currentBotId` 更新 → 调 `refreshConfig()`（config 视图检测 `currentBotId` 变化后按新 bot 局部重渲染字段子集）；发起前若 config 表单有脏编辑 → confirmDialog 确认 | L：刷新 skeleton；S：列表；E：全删后空态「暂无 Bot，点击新建」 | 刷新 500ms |
| 新建 Bot | 弹窗：bot_id（`^[a-z0-9_-]+$` 实时校验+重复检测）/ bot_name / platform / llm_provider / model_name | L：创建中；S：toast + 插入 + 自动选中；R：非法 id / 重复 → 弹窗内错误 | 创建 700ms |
| 启动 / 停止 / 重启 | 卡片操作按钮 + 状态机 stopped→starting→running / running→stopped | L：starting 过渡 1.2s；S：toast + 日志；R：启动失败 → error | 启停 800ms |
| 删除 / 重命名 | 删除确认弹窗；重命名弹窗（同 id 校验） | S：toast + 更新；R：校验失败 | 删除 300ms / 重命名 600ms |
| 导出 / 导入 | 导出 = Blob 下载 JSON；导入 = file input + FileReader 解析 | L：解析中；S：toast 导入成功；R：JSON 损坏 → error-banner | 导入 400ms |

### M9 日志面板（全局：底部）
| 功能点 | 交互 | 四态 | mock 延迟 |
|--------|------|------|-----------|
| 日志流（预置 10 行混合级别 + 运行追加） | 自动滚动到底 | S：持续渲染 | 追加即时 |
| 拖拽高度（120-500px）/ 折叠 | 拖拽把手 + 折叠按钮（现有实现迁移） | — | — |
| 级别着色 / 清空 | 级别色（info/warn/error/debug）；清空按钮 | E：清空后「暂无日志」 | 300ms |

### M10 toast / 弹窗（全局：浮层）
| 功能点 | 交互 | 四态 | mock 延迟 |
|--------|------|------|-----------|
| toast（success/error/warn 三变体，1.8s 自动消失） | 操作反馈统一入口 | — | — |
| 确认弹窗（删除/覆盖类操作） | 遮罩 + 焦点圈闭 + Esc 关闭 + 取消/确认 | — | — |
| 输入弹窗（新建/重命名/预设另存为） | 同上 + 校验行内错误 | — | — |

---

## 4. mock 数据模型（对齐生产端语义）

> 字段命名与生产端 `models.py` / `config_cache.py` 逐字对齐，仅值为 mock。统一放每页 JS 的 `MOCK` 区（§12.4）。

### 4.1 Provider（11 家，对齐 ProviderListResponse 语义）

```js
MOCK.providers = [
  // {name, model, healthy: null|true|false, latency_ms: number|null, configured, is_current}
  {name:'openai',      model:'gpt-4o',                     healthy:true,  latency_ms:243,  configured:true,  is_current:true},
  {name:'google',      model:'gemini-1.5-pro',             healthy:true,  latency_ms:812,  configured:true,  is_current:false}, // slow 阈值 600ms
  {name:'anthropic',   model:'claude-3-opus',              healthy:true,  latency_ms:318,  configured:true,  is_current:false},
  {name:'grok',        model:'grok-4',                     healthy:false, latency_ms:null, configured:false, is_current:false},
  {name:'deepseek',    model:'deepseek-v4-pro',            healthy:true,  latency_ms:156,  configured:true,  is_current:false},
  {name:'siliconflow', model:'deepseek-ai/DeepSeek-V3',    healthy:true,  latency_ms:289,  configured:true,  is_current:false},
  {name:'volcengine',  model:'ep-20250101000000-xxxxx',    healthy:null,  latency_ms:null, configured:false, is_current:false},
  {name:'dashscope',   model:'qwen-plus',                  healthy:true,  latency_ms:178,  configured:true,  is_current:false},
  {name:'moonshot',    model:'moonshot-v1-32k',            healthy:null,  latency_ms:null, configured:false, is_current:false},
  {name:'zhipu',       model:'glm-4-plus',                 healthy:true,  latency_ms:224,  configured:true,  is_current:false},
  {name:'stepfun',     model:'step-2-16k',                 healthy:null,  latency_ms:null, configured:false, is_current:false},
]
// 展示名映射：逐字复制 zh.ts llmProvider.providers（顺序 + 格式「英文名 (中文名)」均对齐）
MOCK.providerNames = {openai:'OpenAI', google:'Google Gemini', anthropic:'Anthropic Claude', deepseek:'DeepSeek (深度求索)',
  siliconflow:'SiliconFlow (硅基流动)', volcengine:'Volcano Ark (火山方舟)', dashscope:'Alibaba Bailian (阿里百炼)',
  moonshot:'Moonshot (月之暗面)', zhipu:'Zhipu GLM (智谱)', stepfun:'StepFun (阶跃星辰)', grok:'Grok (xAI)'}
```

### 4.2 Bot 配置字段子集策略（控制面板）

生产端 `Config` 有 70+ 字段。演示页不全部展示，三级策略：

| 级别 | 字段 | 说明 |
|------|------|------|
| **可编辑** | bot_name / platform(discord\|qq) / enabled / discord_token / llm_provider / api_key(遮罩可编辑) / model_name / base_url / temperature(0-2) / max_tokens / top_p(0-1) / top_k / frequency_penalty(-2~2) / presence_penalty / system_prompt / trigger_keywords[] / trigger_match_mode(只读 contains) / trigger_case_sensitive / auto_interject_enabled / auto_interject_interval / repeat_parrot_enabled / repeat_parrot_threshold / auto_memory_enabled / auto_memory_recall_top_k / auto_memory_recall_char_limit / auto_memory_recall_max_age_days / context_mode(只读 channel) / channel_context_settings{message_limit,char_limit} / memory_context_settings{message_limit,char_limit} | 覆盖「基础/推理/上下文/自动化/记忆/关键词」6 分区 |
| **只读展示** | bot_id（编辑走重命名弹窗）/ api_secret_key（遮罩）/ custom_headers 计数 / interaction_history{enabled,max_storage_bytes,auto_prune} 摘要 / plugins 计数 / custom_parameters 计数 | 高级折叠区 `<details>` |
| **省略** | discord_intents / bot_nickname / 各提供商 base_url 变体（openai_base_url、anthropic_base_url、grok_base_url 可空 + deepseek_base_url、siliconflow_base_url、volcengine_base_url、dashscope_base_url、moonshot_base_url、zhipu_base_url、stepfun_base_url，共 10 个；通用 base_url 已可编辑）/ ocr_* / embedding_* / rerank_*（含 memory_embedding_enabled、memory_rerank_enabled）/ auto_memory_min_length / auto_memory_cooldown_seconds / auto_memory_promote_min_observations / auto_memory_promote_min_distinct_users / auto_memory_quality_threshold / auto_memory_direct_promote_ai_tag / user_personas / role_based_config / scoped_prompts 编辑 / quota_alert / prompt_templates（归工坊视图）/ memory_dedup_threshold / world_book_dedup_threshold / llm_is_multimodal / stream_response / blocked_prompt_response / runtime_type（恒 'nonebot'） | 不属于 10 模块最小集；页面注释标注「省略字段清单」便于扩展 |

Bot 列表项 mock（对齐 BotInstanceStatus + 现有示例页）：`{bot_id, bot_name, platform, enabled, status, uptime_seconds, llm_provider, model_name, trigger_keywords[]}`。4 个默认 bot 沿用现有示例语义（bot_main=discord/running、bot_alpha=qq/running、bot_stats=discord/stopped、bot_legacy=discord/error）。

### 4.3 Debug 捕获（对齐 DebugCaptureSummary / DebugCaptureDetail）

```js
MOCK.captures = [
  // summary 字段
  {id:'cap_01', captured_at:'2026-08-02T11:04:12+08:00', trigger_message_id:'129123456789',
   channel_id:'128000000001', guild_id:'127000000001', user_id:'user_8842', user_name:'张三',
   user_display_name:'张三', trigger_sources:['keyword'], raw_user_message:'帮我写一份周报模板',
   provider:'openai', model:'gpt-4o',
   detail:null}   // detail 懒加载时填充
  // ... 共 8 条，覆盖 provider/model/trigger_sources 多样性
]
// detail 结构（懒加载填充）
{system_prompt:'你是一个乐于助人的 AI 助手…',
 history_for_llm:[{role:'user',content:'…'},{role:'assistant',content:'…'}],
 intermediate_llm_responses:[
   {stage:'reasoning', content:'用户在索要模板，需要先检索知识库…'},
   {stage:'tool_call', name:'search_knowledge', args:'{"query":"周报模板"}'},
   {stage:'tool_result', content:'命中 3 条记忆…'},
   {stage:'response', content:'好的，这是周报模板…'}
 ],
 usage:{prompt_tokens:1204, completion_tokens:382, total_tokens:1586},
  raw_llm_response:'…', cleaned_llm_response:'…'}
```

**与生产端 DebugCaptureDetail 的契约差异（演示页自定）**：
- 生产端 `intermediate_llm_responses` 为 `List[str]`（原文分段数组），演示页 mock 用 `{stage, name?, args?, content}` 对象数组——**演示页自定契约**（供 Trace 时间线结构化解析），非生产字段形态；注释标注即可。
- 生产端 detail 另有 `llm_messages: Record<string,unknown>[]`、`plugin_outputs: string[]`、`formatted_user_request: string` 三字段，演示页 detail **省略**（页面注释标注「省略字段清单」），Trace 时间线的 `request` 节点由 detail 头部合成（provider/model/时间），`formatted_user_request` 语义由情景模拟器（M4）承载。

**Trace 时间线契约**：`intermediate_llm_responses` 每条解析为 `{stage:'request'|'tool_call'|'tool_result'|'reasoning'|'response', name?, args?, content}`；`request` 由 detail 头部合成（provider/model/时间），`response` 取末条。时间线 = 节点 + 节点间 mock 耗时标注（request→tool_call 120ms、tool_call→tool_result 340ms、tool_result→response 610ms）。**Reasoning 折叠气泡** = `stage:'reasoning'` 节点渲染为可折叠气泡（默认折叠，`aria-expanded` 同步）。

### 4.4 模板（对齐 prompts.py DEFAULT_TEMPLATES 14 键）

4 必填：`message_format`（「{author_id_str}」说：\n{content}）/ `user_request_block`（<user_request>\n{parts}\n</user_request>）/ `system_prompt_foundation_header` / `operational_instructions:[]`；10 可选：`image_note / reply_context / deleted_reply_context / tool_context / memory_context / worldbook_context / system_prompt_persona_header / system_prompt_situation_header / system_prompt_participants_header / system_prompt_security_header`。占位符清单**按键分组**（逐字对齐生产端 `TEMPLATE_PLACEHOLDERS`，仅以下 7 键有占位符组；面板按当前选中模板键显示对应组，点击插入光标位置）：

| 模板键 | 占位符 |
|--------|--------|
| `message_format` | `{author_id_str}`、`{content}`、`{image_note}` |
| `image_note` | `{count}` |
| `reply_context` | `{author_info}`、`{replied_content}` |
| `tool_context` / `memory_context` / `worldbook_context` | `{data}` |
| `user_request_block` | `{parts}` |

（`deleted_reply_context` 及 5 个 system_prompt_* 头键无占位符组；其余占位符字面量如 `{data}` 为**键名所属组的占位符值**，`{placeholder}` 之类的泛型占位符不存在。）

### 4.5 用户选项（对齐 UserOptionsConfig / UserOptionRule / UserBlocklistEntry）

```js
MOCK.userOptions = {enabled:true, member_search_timeout_ms:5000, rules:{
  'rule_global': {scope_type:'global', scope_id:'', mode:'blacklist',
    whitelist_behavior:'triggers_only', users:{
      'user_6666': {user_id:'user_6666', user_display_name:'恶意用户', blacklist_mode:'deny_response', negative_portrait:''}}},
  'rule_guild': {scope_type:'guild', scope_id:'127000000001', mode:'whitelist',
    whitelist_behavior:'messages_only', users:{
      'user_8842': {user_id:'user_8842', user_display_name:'张三', blacklist_mode:'negative_portrait', negative_portrait:'重视效率，偏好简洁回复'}}}
}}
```

### 4.6 日志预置（10 行，级别混合）+ 运行时追加（操作 → 日志映射见 §12.4 LOG 区）

---

## 5. localStorage schema

### 5.1 Key 命名裁决

- **key 名**：`elabot-demo-state-v1`（单 key 存全量演示状态）。
- 命名理由：`elabot-demo-` 前缀表明「演示页专属」（与生产端 `frontend-vue-*` 先例区分，避免误混）；`-v1` 版本后缀支持未来演进。**每页共用同一 key 名**（存储域隔离，见 Q2）。
- 分域拆分（`logPanel.*` 风格）**否决**：单 key 读写最简，损坏兜底只有一处。

### 5.2 结构

```json
{
  "v": 1,
  "bots": [ {bot 全量配置 + status} ],
  "currentBotId": "bot_main",
  "providers": [ {ProviderInfo} ],
  "currentProvider": "openai",
  "captures": [ {DebugCaptureSummary} ],
  "templates": { 14 键模板 + presets: {"(默认)开箱即用": {...}} },
  "userOptions": {UserOptionsConfig},
  "appearance": { "scheme": "light|dark|null", "fx": {"aurora": true, "glassblur": true, "glow": true}, "anim": true },
  "logEntries": [ {"t":"09:41:02.318","l":"info","m":"…"} ],
  "logCollapsed": false,
  "playground": null
}
```

### 5.3 读写与兜底

- **写**：`App.state` 任何变更 → `schedulePersist()`（300ms 防抖）。
- **读**：`<head>` 内联脚本（防 FOUC）先同步读 `appearance.fx/anim/scheme` 写入 `<html>` class（`fx-off-*` / `anim-off` / `dark`）；正文脚本再读全量。
- **损坏兜底**（三层）：① `JSON.parse` 失败 → 回退 `DEFAULT_STATE`（深拷贝 MOCK）；② 结构校验（`v !== 1` 或关键键缺失）→ 回退默认；③ 字段级非法值 → 单项重置默认。字段级校验清单（非法即重置该字段为默认值）：`temperature` 0-2、`max_tokens` 1-128000、`top_p` 0-1、`frequency_penalty` / `presence_penalty` ±2、`auto_memory_recall_top_k` ≥1、`channel_context_settings.message_limit` / `memory_context_settings.message_limit` 1-100、`char_limit` 1-20000（两处 context settings）、`auto_interject_interval` ≥1、`member_search_timeout_ms` 1000-30000（M6 同区间）。任一兜底触发 → 启动后 toast 一次「演示数据已重置为默认」+ 日志追加 WARN。
- 演示语义：**保留「重置演示数据」入口**（外观设置页底部按钮，二次确认弹窗）。

---

## 6. i18n 结构

### 6.1 裁决：6 页均渲染 lang 按钮；en 仅结构预留

- 每页顶栏 `lang-btn` + 下拉（对齐现有 `.lang-menu` 组件）：`简体中文`（当前）/ `English`（disabled，标注「预留」）。
- 点击 English → toast「英文版为结构预留，当前仅提供简体中文」，语言不切换。字典结构完整支持未来加入 en（`I18N.en` 空壳对象 + 注释）。
- lang 选择不持久化（仅 zh 可用，持久化无意义）。

### 6.2 字典组织（组名参考 frontend-vue `zh.ts`，键名演示页自洽）

```js
I18N.zh = {
  appNav:      {providers:'提供商', modelSettings:'模型设置', config:'控制面板', promptStudio:'提示词工坊', debugger:'调试器', userOptions:'用户选项', appearance:'外观设置'},
  providersPage:{title:'提供商管理', current:'当前提供商', test:'测试连接', testing:'正在测试连接…', setCurrent:'设为当前', latency:'延迟', healthy:{ok:'正常', slow:'缓慢', off:'离线'}, unconfigured:'未配置'},
  modelSettings:{title:'模型设置', playground:'单模型测试', send:'发送', thinking:'正在思考…', simulateFail:'模拟失败', reqSummary:'请求体摘要'},
  configPanel: {title:'控制面板', save:'保存更改', saving:'正在保存…', reset:'重置', advanced:'高级设置', apiSecret:'API 密钥'},
  promptStudio:{title:'提示词工坊', editor:'模板编辑', placeholders:'可用占位符', simulator:'场景模拟器', generate:'生成预览', generating:'正在生成…', presets:'预设', saveAs:'另存为…'},
  debugger:    {title:'调试器', captures:'捕获列表', trace:'Trace 时间线', reasoning:'Reasoning', empty:'暂无捕获', newCapture:'新建捕获'},
  userOptions: {title:'用户选项', enabled:'启用用户选项', rules:'规则列表', newRule:'新建规则', priority:'规则优先级：频道 > 服务器 > 全局'},
  appearance:  {title:'外观设置', style:'风格', palette:'配色', effects:'特效开关', animations:'界面动画', noFx:'当前风格无特效开关', resetData:'重置演示数据',
    // fx/fxDesc：按 §8.2 FX_IDS 全集定义；键集合随各页 FX_IDS 变化（页内仅渲染本页 FX_IDS 子集，缺少的键回退显示 id 本身）
    // 与生产端 zh.ts appearance.effect* 键的映射：grid→effectGrid、scanline→effectScanline、glow→effectGlow、blink→effectBlink、glassblur→effectGlassblur（文案逐字对齐）；aurora/sunset/wash/fade/shine 为风格专有 id，生产端无对应键，演示页自定
    fx:     {aurora:'极光流动', glassblur:'毛玻璃模糊', glow:'辉光特效', grid:'网格 / 条纹背景', scanline:'扫描线（CRT）', blink:'状态点闪烁', sunset:'日落渐变', wash:'水墨晕染', fade:'渐显过渡', shine:'光泽扫过'},
    fxDesc: {aurora:'背景极光动画与渐变流动', glassblur:'卡片与面板的毛玻璃模糊', glow:'文字辉光、高光线与按钮光晕', grid:'网格 / 条纹背景', scanline:'CRT 扫描线扫过全屏', blink:'状态点闪烁', sunset:'日落渐变背景', wash:'水墨晕染背景', fade:'内容渐显过渡', shine:'标题光泽扫过'}},
  sidebar:     {title:'Bots', new:'新建 Bot', refresh:'刷新列表', start:'启动', stop:'停止', restart:'重启', delete:'删除', rename:'重命名', export:'导出', import:'导入'},
  logPanel:    {title:'日志面板', empty:'暂无日志', clear:'清空'},
  actionBtn:   {save:'保存', cancel:'取消', confirm:'确认', delete:'删除', retry:'重试', close:'关闭'},
  fourState:   {empty:{title:'暂无数据', desc:'…'}, loading:'加载中…', error:'加载失败', retry:'点击重试'},
  status:      {loading:'正在加载…', saving:'正在保存…', saved:'已保存', failed:'操作失败：{error}'},
  toast:       {saved:'已保存', deleted:'已删除', started:'已启动', stopped:'已停止', switched:'已切换至 {name}', langReserved:'英文版为结构预留，当前仅提供简体中文', resetData:'演示数据已重置为默认'}
}
```

### 6.3 插值

`t('status.failed', {error:'…'})` → 正则 `/\{(\w+)\}/g` 替换；字典按 `I18N.zh[group][key]` 扁平 path 读取，无嵌套函数。

### 6.4 文案规范（G8）

- 动词 + 名词：`保存更改` / `新建 Bot` / `删除规则` / `测试连接`；
- 进行时统一「正在…」：`正在保存…` / `正在测试连接…` / `正在生成…`；
- 四态文案统一：`加载中…`（L）/ `加载失败`（R）/ `暂无数据`（E）/ `已保存`（S）。

---

## 7. 四态组件规范

### 7.1 empty-state

```html
<div class="empty-state" role="status">
  <div class="empty-icon" aria-hidden="true">◇</div>
  <div class="empty-title">暂无捕获</div>
  <div class="empty-desc">用户与 Bot 的交互捕获会显示在这里</div>
  <button class="btn-secondary" data-action="new-capture">新建捕获</button>   <!-- 可选操作 -->
</div>
```
```css
.empty-state{padding:56px 20px;text-align:center;color:var(--fg-muted)}
.empty-icon{font-size:34px;opacity:.45;margin-bottom:10px}
.empty-title{font-size:14px;font-weight:600;color:var(--fg)}
.empty-desc{font-size:12px;margin-top:4px}
```

### 7.2 skeleton（加载占位）

```html
<div class="skeleton" aria-hidden="true">
  <div class="sk-line" style="width:38%"></div>
  <div class="sk-line" style="width:62%"></div>
  <div class="sk-line" style="width:50%"></div>
</div>
```
```css
.sk-line{height:12px;border-radius:6px;margin:8px 0;background:var(--card-border);opacity:.6;animation:sk-pulse 1.4s ease-in-out infinite}
@keyframes sk-pulse{0%,100%{opacity:.35}50%{opacity:.8}}
/* 卡片骨架：.sk-card 复用 .card 外形 + 内部 sk-line */
/* reduced-motion 下 animation:none（全局规则覆盖） */
```
出现时机：providers 首载、config 首载、captures 列表、详情加载、bot 列表刷新、预设加载。**骨架整体替换内容区**（不闪烁叠加）。

### 7.3 error-banner

```html
<div class="error-banner" role="alert">
  <span class="err-icon" aria-hidden="true">⚠</span>
  <span class="err-msg">加载失败：网络连接中断</span>
  <button class="btn-secondary" data-action="retry">重试</button>
</div>
```
```css
.error-banner{display:flex;align-items:center;gap:10px;padding:12px 16px;margin-bottom:14px;
  border:1px solid var(--error);border-radius:10px;color:var(--fg)}
```
出现时机：任一 mock 加载失败路径、Playground 模拟失败、导入 JSON 损坏、保存校验失败（行内形式）。

### 7.4 统一出现时机清单（按模块）

> 本表为**汇总表**，只列每模块代表性时机；完整且权威的判定以 §3 M1-M10 矩阵（每功能点四态列）为准。

| 模块 | E | L | R |
|------|---|---|---|
| 提供商 | —（恒有 11 家） | 首载 skeleton | 加载失败重试；连接测试失败（弹窗内 error，M1 连接测试行） |
| 模型设置 | Playground 初始引导 | 回复生成中 | 模拟失败开关 |
| 控制面板 | — | 首载 skeleton | 保存校验失败（行内） |
| 提示词工坊 | — | 预设加载 / 模板载入 | 模板载入失败；默认预设覆盖拒绝；模拟器用户消息为空（行内提示，M4 情景模拟器行） |
| 调试器 | 捕获清空后 | 列表/详情 | 列表加载失败（M5 捕获列表行）；详情解析失败降级 |
| 用户选项 | 无规则 | 规则加载 | scope_id 缺失（行内） |
| 外观设置 | zen 页 fx 空态 | — | — |
| Bot CRUD | 列表全删 | 刷新/创建/导入 | 非法 id / 重复 / JSON 损坏 |
| 日志面板 | 清空后「暂无日志」 | — | — |

---

## 8. 特效开关统一方案

### 8.1 面板组件（6 页统一）

```html
<button class="theme-btn" id="fx-btn" title="特效开关（外观设置演示）" aria-label="特效开关" aria-haspopup="dialog" aria-expanded="false">⚡ 特效</button>
<div class="fx-wrap" id="fx-wrap" role="dialog" aria-label="特效开关面板" hidden>
  <div class="fx-title">特效开关</div>
  <div class="fx-note">关闭后对应装饰动画立即消失</div>
  <div id="fx-rows"><!-- JS 按 FX_IDS 渲染 .fx-row --></div>
</div>
```
```css
.fx-wrap{position:absolute;top:calc(100% + 6px);right:0;z-index:80;width:252px;padding:12px;border-radius:12px;
  background:var(--fx-bg, rgba(13,21,38,.94));border:1px solid var(--card-border);box-shadow:0 16px 40px rgba(0,0,0,.45)}
.fx-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:7px 0}
.fx-row small{font-size:11px;color:var(--fg-dim)}
```
```js
/* 面板渲染：zen 页 FX_IDS=[] → 渲染空态行「当前风格无特效开关」 */
function renderFxPanel(){
  var rows = FX_IDS.length ? FX_IDS.map(function(id){
    return '<label class="fx-row"><span>' + t('appearance.fx.' + id) + '<small>' + t('appearance.fxDesc.' + id) + '</small></span>' +
      '<span class="switch"><input type="checkbox" data-fx="' + id + '"' + (state.appearance.fx[id] !== false ? ' checked' : '') + '><span class="track"></span><span class="knob"></span></span></label>'
  }).join('') : '<div class="fx-row">' + t('appearance.noFx') + '</div>'
  document.getElementById('fx-rows').innerHTML = rows
  fxWrap.querySelectorAll('input[data-fx]').forEach(function(cb){
    cb.addEventListener('change', function(){
      document.documentElement.classList.toggle('fx-off-' + cb.dataset.fx, !cb.checked)
      state.appearance.fx[cb.dataset.fx] = cb.checked; schedulePersist()
    })
  })
}
```
> 交互细节：按钮开合（aria-expanded 同步）、点面板外关闭、Esc 关闭；checkbox 状态 = 持久化状态；启动时 `<head>` 内联脚本先应用持久化 class（防 FOUC）。
> **焦点管理（fx-wrap，MEDIUM-4）**：打开 → 聚焦面板首控件（第一个 checkbox；FX_IDS=[] 的空态行无焦点控件时聚焦面板容器并设 `tabindex="-1"`）；Tab / Shift+Tab 在面板内**焦点圈闭**（首末控件间循环，不逃逸到面板外）；关闭（Esc / 点外 / 按钮）→ **焦点还原至 fx-btn**（`fx-btn.focus()`）。面板开启期间 `aria-expanded="true"`，恢复后同步回 false。

### 8.2 fx id 全集表 + 成对关闭规则写法规范

| 页面 | FX_IDS（面板顺序） | 关闭规则 |
|------|--------------------|----------|
| aurora | `['aurora','glassblur','glow']` | `fx-off-aurora`：aurora-layer 动画停 + opacity .15；`fx-off-glassblur`：移除全部 backdrop-filter；`fx-off-glow`：渐变文字降级 + 高光线 + 按钮辉光（§Q1 规范） |
| matrix | `['grid','scanline','blink','glow']` | `fx-off-grid`：**网格层关闭**（注：生产端 matrix.html 网格 = `body` 的 `background-image`（双线性渐变，L49-52），无独立元素 → 关闭规则须处理 body 背景 `html.fx-off-grid body{background-image:none}`，或迁移时新增独立 `.grid-layer` 元素 + 关闭规则 `opacity:0`，后者推荐：body 背景属「风格底色」语义，独立层可将「底色保留 / 特效关闭」分离）；`fx-off-scanline`：扫描线 display:none；`fx-off-blink`：状态点 animation:none；`fx-off-glow`：外发光移除（§Q1 新增） |
| zen | `[]` | 无（面板空态） |
| synthwave | `['sunset','grid','scanline','glow']` | 现有规则原样迁移（synthwave.html L476-481）；**迁移豁免注记**：`fx-off-glow` 原样迁移仅 `animation:none`（L479-481，无静态降级声明）可接受——渐变文字关闭动画后仍显示静态渐变（§8.2 规则②「补静态观感」的迁移豁免，aurora 的 glow 静态降级规范不套用于 synthwave） |
| ink | `['wash','fade']` | 现有规则原样迁移（ink.html L422-424） |
| pixel | `['blink','scanline','shine']` | 现有规则原样迁移（pixel.html L457-460） |

**成对关闭规则写法规范**（每页 CSS 文件尾独立区块）：

```css
/* ===== 特效关闭（html.fx-off-*）===== */
html.fx-off-<id> .<装饰元素>{<关闭声明>}   /* 装饰层：display:none / opacity:0 */
html.fx-off-<id> .<动画元素>{animation:none} /* 动画：animation:none，必要时补静态观感 */
```
规则：① 文件尾集中、逐 fx id 成对；② 关闭动画必须补静态观感声明（如 `color:var(--fg)`）防「动画没了颜色也没了」；③ 装饰层用 `display:none` / `opacity:0`，动画用 `animation:none`；④ 特效关闭**不影响**风格骨架（角标/网格底色/光斑底色）。

### 8.3 动画开关（与特效区分的独立开关）

- `html.anim-off` class 关闭**界面过渡动画**（content fadeUp、卡片 hover transform、skeleton pulse、dot-pulse），特效（装饰层）不受影响——语义对齐生产端 `data-animations` 双门控。
- CSS：`html.anim-off .content-inner > *{animation:none}` + `html.anim-off .sk-line{animation:none}` + `html.anim-off .status-dot.running{animation:none}` 等白名单声明。

---

## 9. 无障碍清单

| 项 | 规范 | 覆盖 |
|----|------|------|
| 焦点可见 | `:focus-visible{outline:2px solid var(--primary);outline-offset:2px}`（现有模式保留） | 全局 |
| 语义标签 | 顶栏 `nav aria-label="主导航"`；侧栏 `aside aria-label="Bot 列表"`；日志 `footer aria-label="日志面板"`；内容 `main` | 全局 |
| 激活导航 | `.nav-item.active` + `aria-current="page"` | 视图切换 |
| 按钮可达 | 所有图标按钮含 `aria-label`（act-btn 4 枚、btn-icon、log-toggle、fx-btn、lang-btn） | 全局 |
| 弹窗 | `role="dialog"` + `aria-labelledby`；打开聚焦首控件；焦点圈闭（Tab/Shift+Tab 循环）；Esc 关闭 + 焦点还原；遮罩点击关闭 | modal |
| 特效面板 | `role="dialog"`、Esc 关闭、`aria-expanded` 同步；**打开聚焦面板首控件；Tab/Shift+Tab 圈闭；关闭还原焦点至 fx-btn**（§8.1 焦点管理） | fx-wrap |
| 状态播报 | toast `role="status" aria-live="polite"`；error-banner `role="alert"`；empty-state `role="status"` | 全局 |
| 键盘操作 | bot-card Enter/Space 选中（现有）；时间线节点可聚焦展开；checkbox/switch 原生可键盘 | 全局 |
| 对比度 | `--fg`/`--fg-muted` 在 `--bg` 上 ≥ 4.5:1（每页色板自查；fg-dim 仅限装饰性文本）；Matrix `#00ff88` 对 `#020604` ≈ 10:1 ✅ | 6 页 |
| reduced-motion | `@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}`（现有模式）；aurora 层静态 opacity .3；**JS 定时器驱动的动画（Trace 时间线节点推进、日志自动滚动等）CSS 媒体查询覆盖不到，须在 JS 侧 `matchMedia('(prefers-reduced-motion: reduce)')` 跳过**（静态展示全部节点/保持当前滚动位置） | 6 页 |
| 断点行为 | 900px 侧栏折叠不损失功能（操作移入弹窗/顶栏） | 响应式 |

---

## 10. 验收矩阵（可勾选清单）

### A. 通用（6 页 + 总览）
- [ ] A1 7 个文件均在 `file://` 下双击可开，无控制台错误、无网络请求（DevTools Network 全空）
- [ ] A2 每页 ≤ 120KB / ≤ 2200 行
- [ ] A3 布局骨架与基线一致：48px topbar / 260px sider / 1240px content-inner / 180px 日志拖拽 120-500px
- [ ] A4 断点 1100/900/768/640 行为与基线一致
- [ ] A5 `prefers-reduced-motion` 下全页无动画
- [ ] A6 7 视图切换正常（导航 + hash 直达 + 刷新保持视图 + 懒渲染数据不丢 + 视图激活刷新钩子联动 + 脏表单确认拦截）
- [ ] A7 四态组件在 §7.4 清单全部时机出现且样式正确
- [ ] A8 localStorage 读写 + 损坏兜底（手动改坏值刷新 → 重置 toast）
- [ ] A9 每个操作产生日志追加；日志拖拽/折叠/清空正常
- [ ] A10 toast 三变体（success/error/warn）与 confirm/input 弹窗（焦点圈闭/Esc）正常
- [ ] A11 lang 按钮：English 显示预留提示；字典插值渲染正确
- [ ] A12 无焦点陷阱：Tab 全流程可达，focus-visible 可见

### B. 分页
- [ ] B1 每页色板 token 与基线 `examples/<style>.html` CSS 变量**逐值复制一致**（对照方式：将该页基线文件 `:root` 块与 full-ui 页 `:root` 块并排 diff 关键 token——`--bg` / `--fg` / `--primary` / `--card-bg` 等；full-ui 页只复制、不新增、不替换基线色值；§0 无色板表格，色板基准 = 基线文件本身）
- [ ] B2 每页特效面板 id 集合与 §8.2 一致；关闭即时生效；启动恢复持久化状态（无 FOUC）
- [ ] B3 aurora：aurora/glassblur/glow 三项可关；matrix：grid/scanline/blink/glow 四项可关
- [ ] B4 zen：面板空态文案；亮暗切换在外观设置视图且持久化 `html.dark`
- [ ] B5 synthwave/ink/pixel：特效行为与基线示例页一致（回归对照）

### C. 模块（每页 × 每模块）
- [ ] C1 提供商：11 卡渲染；单家检测 loading→ok/slow/off；切换联动 toast + 当前标记 + 模型设置局部刷新（refreshModelSettings）
- [ ] C2 模型设置：参数校验（越界标红）；Playground 空态/思考/回复/失败四态；请求体摘要联动
- [ ] C3 控制面板：字段子集与 §4.2 一致；保存/重置/校验失败；只读折叠区；api_secret 遮罩；切换 Bot 局部刷新（refreshConfig）+ 脏表单确认
- [ ] C4 提示词工坊：14 键模板编辑；占位符点击插入；模拟器三栏预览；预设另存/加载/删除 + 默认预设保护
- [ ] C5 调试器：8 条捕获列表；详情（system_prompt/history 折叠）；Trace 时间线 request→tool_call→response；Reasoning 折叠气泡；空态
- [ ] C6 用户选项：总开关/超时；规则 CRUD；用户条目四字段；优先级提示条
- [ ] C7 外观设置：风格卡（当前高亮 + 其余跳转链接）；色板 swatch；特效面板内嵌；动画开关；重置演示数据
- [ ] C8 Bot CRUD：新建（id 正则实时校验 + 重复拒绝）/启动/停止/重启（starting 过渡）/删除确认/重命名/导出下载/导入解析（损坏报错）
- [ ] C9 日志面板与 toast/弹窗在每页可用（M9/M10）

---

## 11. 范围外清单（显式不做）

1. 不修改 `frontend-vue/src`（生产端）任何文件；不修改现有 `examples/` 9 个文件（基线保留可回归对照）
2. 真实后端 API 调用（全部 mock）
3. Playground 多模型对比（仅单模型测试对话）
4. PromptStudio 版本历史、范围覆盖编辑（scoped_prompts）、角色策略、插件集成 tab
5. UserOptions 用户/角色管理（personaHub）、negative_portrait 自动生成
6. 完整打字机（loading 气泡 + 整段渲染即可；打字机列为可选加分项，不承诺）
7. 知识库记忆表格、OCR / Embedding / Rerank 设置（不在 10 模块内）
8. 跨页存储共享（Q2 裁决）
9. en 完整翻译（结构预留）
10. PWA / 离线缓存 / service worker
11. 页内跨风格 token 注入预览（外观页仅当前风格子项 + 链接跳转）
12. 自定义 CSS 编辑器（生产端 `frontend-vue-custom-css` 语义不在演示范围）
13. 拖动排序、虚拟滚动、日期选择器等重组件

---

## 12. 文件结构与实现切片计划

### 12.1 文件清单（新增，不动现有）

```
frontend-vue/examples/full-ui/
├── index.html        # 功能矩阵总览入口（6 方案卡 + 10 模块覆盖矩阵 + 特效 id 差异表）
├── aurora.html       # 母版页：完整 10 模块（先实现，作为移植基线）
├── matrix.html
├── zen.html
├── synthwave.html
├── ink.html
└── pixel.html
```

### 12.2 文件头注释块模板（每页强制）

```html
<!--
  文件：full-ui/<style>.html · <风格名>（全交互演示版）
  定位：ELA-Bot 完整 UI 功能演示 · <一句话风格定位>
  色板：--bg #xxx · --fg #xxx · --primary #xxx · --card-bg #xxx（4 行 token 摘要）
  特效 FX_IDS：[aurora, glassblur, glow]（按面板顺序）
  模块：providers / model-settings / config / prompt-studio / debugger / user-options / appearance
        + Bot CRUD（侧栏）· 日志面板（底部）· toast/弹窗（浮层）
  结构：CSS 区块序 §12.3 → HTML（topbar/shell/sider/content 7 view/log-footer/浮层）→ JS 六分区 §12.4
  省略字段：ocr_*/embedding_*/rerank_*/user_personas/role_based_config/scoped_prompts/quota_alert（见设计文档 §4.2）
-->
```

### 12.3 CSS 区块顺序（每页一致，块间 `/* ===== xxx ===== */`）

`基础与变量` → `滚动条` → `焦点可见` → `布局骨架（app/topbar/nav/lang/shell/sider）` → `Bot 卡片` → `内容区与视图容器` → `通用卡片/统计卡` → `四态组件` → `表单（input/select/switch/slider）` → `表格` → `时间线（Trace）` → `折叠（details/Reasoning）` → `弹窗 modal` → `日志面板` → `toast` → `风格装饰层（按各页）` → `响应式断点` → `特效关闭 html.fx-off-*` → `动画开关 html.anim-off` → `reduced-motion`。

### 12.4 JS 六分区（每页一致）

```js
(function(){
'use strict'
/* 1. I18N —— t() 插值 + zh/en 字典（§6） */
/* 2. MOCK —— 全量 mock 数据（§4）+ DEFAULT_STATE */
/* 3. STATE —— state 加载(localStorage+兜底) / schedulePersist / 启动时 fx+anim+dark 应用 */
/* 4. UI —— toast / openModal / confirmDialog / emptyState / skeleton / errorBanner / renderFxPanel / logAppend / 日志拖拽折叠 */
/* 5. 模块 render —— renderProviders / renderModelSettings / renderConfig / renderPromptStudio / renderDebugger / renderUserOptions / renderAppearance / renderBotList / viewRefreshHooks（refreshConfig / refreshModelSettings，契约见 §1.2）（各 ≤60 行） */
/* 6. 入口 —— hash 初始化视图 / 事件委托绑定 / 预置日志 */
})()
```
**事件绑定纪律**：容器级事件委托（`content-inner` 上监听 click/change/input，`data-action` 属性分发），避免每视图反复 addEventListener；弹窗内事件在 openModal 时绑定、关闭时清理。

### 12.5 切片计划（implementer 原子切片，每片含验证）

| 切片 | 内容 | 交付物 | 验证 |
|------|------|--------|------|
| S0 | aurora 骨架基线：文件头 + 布局 + 7 视图容器 + 视图切换（data-view+hash）+ 四态组件 + toast/modal + 日志面板 + 特效面板机制 | `full-ui/aurora.html` 骨架版 | 布局与基线 diff（类名清单）；视图切换/拖拽/折叠可用 |
| S1a | aurora 视图集 ①：providers + model-settings(Playground) —— 提供商卡片/健康检测/切换联动（含 `refreshModelSettings()` 钩子 + 脏表单确认）+ 推理参数表单/模型联动/Playground 四态/请求体摘要 | aurora 半交互版 | C1/C2 全项；M1→M2 联动（切提供商 → 模型设置局部刷新） |
| S1b | aurora 视图集 ②：config 控制面板 —— 字段子集表单/保存重置/校验/高级折叠区/api_secret 遮罩（含 `refreshConfig()` 钩子 + 脏表单确认） | aurora 交互版 | C3 全项；M8→config 联动（切 Bot → 配置局部刷新） |
| S1c | aurora 视图集 ③：prompt-studio + debugger —— 模板编辑/占位符分组插入/情景模拟器/预设管理 + 捕获列表/详情/Trace 时间线/Reasoning 折叠/清空删除 | aurora 交互版 | C4/C5 全项 |
| S1d | aurora 视图集 ④：user-options + appearance + Bot CRUD + 日志/toast + localStorage + i18n（fx 面板完整版、重置演示数据、导出/导入、脏检测收尾） | aurora 完整版 | C6-C9 全项；A8-A12 |
| S2 | matrix 移植：色板 + 装饰 + FX_IDS 4 项 + glow 补齐 | matrix.html | B1-B3；C 项抽查 |
| S3 | zen 移植：色板 + 亮暗变体（外观页切换 + 持久化）+ fx 空态 | zen.html | B4；C 项抽查 |
| S4 | synthwave 移植（原装饰迁移） | synthwave.html | B5 对照 |
| S5 | ink 移植 | ink.html | B5 对照 |
| S6 | pixel 移植 | pixel.html | B5 对照 |
| S7 | 总览页 + 跨页一致性终检 | index.html | A1-A12 全页；骨架一致性 diff；体积/行数统计表 |

每切片提交前自查：控制台无错、四态各触发一次、localStorage 刷新保持、reduced-motion 模拟（DevTools）无动画。

---

## 13. 主风险与回退

| 风险 | 影响 | 缓解/回退 |
|------|------|-----------|
| 单文件超体积/超行 | 违反 Q3 | 按模块瘦身：删 Playground 请求体摘要、删高级折叠区子项；最终回退为砍 1 个非核心模块（外观页色板只读化） |
| file:// 下 hash 或 Blob 下载行为差异（Safari/Firefox） | 视图保持/导出失败 | hash 仅增强（失败静默）；导出回退：console 输出 JSON + toast 提示复制 |
| 6 页交互逻辑漂移 | 验收不一致 | S7 一致性 diff 清单 + 每页 JS 六分区结构检查 |
| localStorage 损坏连锁 | 页面白屏 | 三层兜底（§5.3）+ 启动 try/catch 全包 |
| 事件委托遗漏导致某交互失效 | 验收失败 | 容器级委托 + 每切片 C 项逐条验证 |

---

## 14. 待 qa-reviewer 审查要点

1. **四态覆盖完整性**：§7.4 清单 × 6 页 × 10 模块逐条可触发
2. **fx 开关正确性**：§8.2 表 × 每页，关闭后「动画消失但风格骨架保留」语义是否成立（重点 aurora glow 降级、matrix glow 新增规则）
3. **契约对齐**：mock 字段名与生产端 models.py 逐字一致（ProviderInfo / DebugCaptureSummary / UserOptionRule / Config 子集）；11 家提供商名与 zh.ts 一致；模板 14 键与 prompts.py 一致
4. **文案规范**：G8 动词+名词 / 正在… / 四态文案统一性
5. **无障碍抽查**：焦点圈闭（modal/fx-wrap）、aria-expanded/current/live 同步、对比度 4.5:1（6 色板）
6. **回归安全**：未修改 `frontend-vue/src` 与现有 examples 9 文件（git status 验证）
