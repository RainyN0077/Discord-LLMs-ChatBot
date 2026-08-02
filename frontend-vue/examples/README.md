# ELA-Bot 前端美术方案 — 设计文档

> 本文档回答四件事：
> 1. **现状审计** —— 检查本项目前端代码后的结论（旧 Svelte 版 / 新 Vue 版）
> 2. **美术方案** —— 6 套视觉方案原型（Aurora / Matrix / Zen / Synthwave / Ink / Pixel）的定位、色板与接入方式
> 3. **特效开关** —— 已落地生产的「特效开关」机制（华丽风格装饰特效可控）
> 4. **组件库评估** —— Naive UI 现状问题、备选组件库对比、基于现有组件库的打包/工程化方案
>
> 原型页面在 `frontend-vue/examples/` 下，为**纯静态单文件**（零外部依赖、零网络请求），
> `file://` 协议下双击即可打开。

---

## 1. 项目前端现状审计

### 1.1 两个前端的关系

| 目录 | 技术栈 | 状态 |
|------|--------|------|
| `frontend/`（旧） | Svelte 4 + Vite，无组件库，纯手写 CSS | 旧版，已由 Vue 版取代 |
| `frontend-vue/`（新） | **Vue 3.5 + TypeScript + Naive UI 2.44 + Pinia + vue-i18n + vue-router + @vicons/ionicons5** | 现行版本，本文档只针对它 |

### 1.2 主题系统现状（新版）

- `src/themes/themes.ts`：**9 种风格**（light / dark / neon / glass / minimal / dawn / midnight / nature / cyberpunk）× **13 套配色**（default / miku / tianyi / sakura / shion / sunset / forest / samurai / combat / netrunner / mox / corpo / nomad），共 **48 个 CSS 变量**（20 基础色 + 24 样式级 + 4 专属侧栏键）
- `src/stores/theme.ts`：把合并后的 48 键注入 `#fv-theme-vars` 到 `:root{}`，并在 `<html>` 上写 `data-style` / `data-theme` / `data-animations` / `data-effects`（特效开关）
- `src/themes/naiveMapping.ts`：仅把 **11 个** CSS 变量映射到 naive-ui 的 `common` token（primaryColor、bodyColor、borderRadius 等）
- `src/styles/global.css`：基础样式 + 路由过渡 + 日志色（`--log-*`）+ **NEON/CYBERPUNK/GLASS 装饰层**（网格、扫描线、切角角标、辉光、毛玻璃，全部挂接 `data-effects` 特效开关）

### 1.3 审计发现的问题（改进空间）

| # | 问题 | 位置 | 影响 | 状态 |
|---|------|------|------|------|
| P1 | **`data-style` 属性没有任何 CSS 消费**——风格差异完全靠变量驱动，布局级装饰（发光、玻璃、角标、扫描线）无处安放 | `stores/theme.ts` L96-102 写属性；全库无 `[data-style]` 选择器 | 新增风格只能改颜色，无法加质感层 | ✅ 已修复（装饰层移植 + `[data-style]` 规则） |
| P2 | **硬编码颜色不随风格变化**：`rgba(148,163,184,…)`（slate 灰）、`rgba(69,163,230,…)`（旧主蓝）散落在 BotCard / LogPanel / TemplateEditor 等 8+ 文件 | 抽样见下表 | neon（青）、cyberpunk（黄）风格下观感突兀 | ⏳ 待清理 |
| P3 | **日志色只分亮/暗两态**，不随 9 风格变化 | `global.css` L33-51 | 日志面板在风格切换后配色脱节 | ⏳ 待清理 |
| P4 | **naive-ui 组件级主题零覆盖**：Menu / Tabs / DataTable / Form / Input 全是 naive 默认外观 | `naiveMapping.ts` 只返回 `{ common }` | 顶部菜单、表格、表单观感"素" | ⏳ 部分（装饰层已覆盖菜单/卡片/按钮外观） |
| P5 | 顶部水平菜单、NLayoutSider、NDataTable 无任何定制 CSS | `MainLayout.vue` | 视觉层级单一 | ✅ 已改善（菜单激活指示/辉光、侧栏条纹、卡片切角） |

硬编码颜色抽样（`<style>` 内）：

| 文件 | hex | rgb | 示例 |
|------|-----|-----|------|
| BotCard.vue | 5 | 7 | `rgba(148,163,184,.12)`、`rgba(69,163,230,.16)` |
| LogPanel.vue | 0 | 4 | `rgba(69,163,230,.5)`、`rgba(148,163,184,.08)` |
| TemplateEditor.vue | 2 | 0 | `#fff`、`border-left: 3px solid #f0a020` |
| ProvidersPage.vue | 1 | 0 | fallback `#45a3e6` |

---

## 2. 六套美术方案（示例网页）

| 文件 | 方案 | 设计定位 | 对应现有 style 方向 |
|------|------|----------|---------------------|
| `index.html` | 总览页 | 方案选型入口，6 张方案卡 + 迷你预览 | — |
| `aurora.html` | A · Aurora 极光 | 深邃宇宙 + 流动极光 + 玻璃拟态 | `glass` 进阶 |
| `matrix.html` | B · Matrix 终端矩阵 | 黑底荧光绿纯终端 | `neon` / `cyberpunk` 终端化 |
| `zen.html` | C · Zen 极简纸感 | 日式纸感极简，克制排版（Linear/Notion 方向） | `minimal` / `dawn` 精致化 |
| `synthwave.html` | D · Synthwave 蒸汽波 | 80 年代复古未来：紫粉日落 + 网格地平线 + 霓虹 | `cyberpunk` 复古化 |
| `ink.html` | E · Ink 水墨禅意 | 宣纸质感 + 墨色 + 朱砂点缀，安静雅致 | `minimal` / `dawn` 东方化 |
| `pixel.html` | F · Pixel 复古像素 | 8-bit 游戏机：硬边框 + 硬投影 + 方块状态点 | `neon` 游戏化 |

六套原型共用同一布局骨架（复刻 `MainLayout.vue`：48px 顶栏 + 260px Bot 侧栏 + 内容区 + 180px 可拖拽日志面板），差异集中在色板与质感层。**每个方案页顶栏带「⚡ 特效」按钮**，演示特效开关机制（切换 `html.fx-off-<id>` class 即时关闭对应装饰动画）。

### A · Aurora 极光

| token 组 | 值 |
|----------|-----|
| `--bg-color` | `#070b16`（近黑深蓝） |
| `--primary-color` | `#5eead4`（青），辅助 `#a78bfa`（紫） |
| 成功 / 错误 | `#34d399` / `#fb7185` |
| 卡片 | `rgba(255,255,255,.055)` + `backdrop-filter: blur(18px) saturate(150%)` |
| 主按钮 | `linear-gradient(135deg, #22d3ee, #818cf8)`，hover 发光 `rgba(99,102,241,.35)` |
| 装饰层 | 3 处固定径向光斑（青/紫/粉）+ 18s 极光漂移层（blur 60px，opacity .45） |
| 特效开关 | `sunset`（光带漂移）、`grid`（透视网格）、`scanline`（CRT 扫描线）、`glow`（霓虹辉光） |

### B · Matrix 终端矩阵

| token 组 | 值 |
|----------|-----|
| `--bg-color` | `#020604`（近黑墨绿），42px 网格线 `rgba(0,255,136,.045)` |
| `--primary-color` | `#00ff88`（荧光绿），辅助 `#00d8ff`（青） |
| 警告 / 错误 | `#ffd479` / `#ff5c5c` |
| 卡片 | `#060d09` + 边框 `rgba(0,255,136,.16)` + 左上角 8px 角标（`::before` 双边框） |
| 字体 | 正文系统无衬线；bot_id / 日志 / 标题前缀 / 数值用等宽栈 |
| 装饰层 | 2px 扫描亮线 7s 循环扫过全屏；运行态状态点 `steps` 硬切换闪烁 |
| 约束 | `prefers-reduced-motion` 下关闭扫描线与闪烁 |

### C · Zen 极简纸感

| token 组 | 值 |
|----------|-----|
| `--bg-color` | `#faf8f5`（米白纸色），仅极淡径向渐变（opacity .03） |
| `--primary-color` | `#3b5bdb`（靛蓝，单一强调色） |
| 成功 / 错误 / 警告 | `#1a7f4e` / `#c0392b` / `#b7791f` |
| 文字 | `#1f2430` 主 / `#6b7280` 次，正文 14px/1.7 |
| 卡片 | `#ffffff` + 边框 `#ece7e0` + 圆角 10px，无阴影（或 `0 1px 2px rgba(31,36,48,.04)`） |
| 装饰层 | 标题左侧 2px 靛蓝竖线；日志级别小圆点；亮/暗纸感变体见 `html.dark` |
| 约束 | 全页无阴影、无渐变按钮、无装饰动画 |

### D · Synthwave 蒸汽波

| token 组 | 值 |
|----------|-----|
| `--bg-color` | `#12082a`（深紫黑） |
| `--primary-color` | `#ff6ec7`（粉霓虹），辅助 `#2de2e6`（青）、`#ffd319`（黄） |
| 错误 | `#ff3860` |
| 卡片 | `#1c0f38` + 边框 `rgba(255,110,199,.25)`，hover 变青 + 外发光 |
| 装饰层 | 顶部「太阳」径向渐变圆（黄→粉）+ 底部透视网格（`perspective(600px) rotateX(55deg)`）+ 霓虹文字（text-shadow） |
| 特效开关 | `sunset`（日落光带）、`grid`（透视网格）、`scanline`（CRT 扫描线）、`glow`（霓虹辉光） |

### E · Ink 水墨禅意

| token 组 | 值 |
|----------|-----|
| `--bg-color` | `#f6f2ea`（宣纸米黄） |
| `--primary-color` | `#2f2b26`（暖墨），强调朱砂 `#b3402a`、青瓷 `#5d8a7d` |
| 卡片 | `#fbf8f2` 白纸底 + 1px `#e2dacb` 墨线 + 圆角 6px + 极浅阴影 |
| 标题字体 | 中文衬线栈 `"Songti SC", "STSong", "SimSun", serif`，字距 0.12em |
| 装饰层 | 墨色晕染 + 右下「雅」印章（rotate -8deg）+ 小标题朱砂竖线 |
| 约束 | 全页无发光、无渐变按钮、无扫描动画；特效开关仅 `wash`（晕染/印章）与 `fade`（淡入）两项 |

### F · Pixel 复古像素

| token 组 | 值 |
|----------|-----|
| `--bg-color` | `#141821`（深蓝灰） |
| `--primary-color` | `#ffd23f`（金），辅助 `#4cc9f0`（蓝）、`#f72585`（粉）、`#00e054`（绿） |
| 卡片 | `#1e2430` + 3px 硬边框 + 硬投影 `4px 4px 0 rgba(0,0,0,.45)`，零圆角 |
| 字体 | 等宽粗体 + 字距 .08em；标题 `█▌` `▐█` 装饰块 |
| 装饰层 | 顶栏三色分段条（粉/金/蓝）；方块状态点 `steps` 硬切换闪烁；按钮按下位移模拟 |
| 特效开关 | `blink`（方块闪烁）、`scanline`（像素扫描线）、`shine`（标题彩虹周期） |

### 打开方式

直接双击 `frontend-vue/examples/index.html`，从总览页进入 6 套方案；或分别打开各方案页。每个方案页顶栏的「⚡ 特效」按钮可即时演示特效开关。

---

## 3. 特效开关（已落地生产）

生产端「特效开关」机制已实现并通过测试（`npx vitest run` 149 用例全绿），**默认全开，与既往渲染一致**：

- **注册表**：`src/stores/theme.ts` 的 `EFFECT_DEFS` 定义 5 个特效：`grid`（网格/条纹，neon+cyberpunk）、`scanline`（CRT 扫描线，cyberpunk）、`glow`（辉光，neon+cyberpunk）、`blink`（状态点闪烁，neon+cyberpunk）、`glassblur`（毛玻璃，glass）
- **状态与持久化**：`effects` ref 默认全开，localStorage key `frontend-vue-effects`（JSON，损坏/未知 id 自动兜底全开）；`toggleEffect(id)` 切换；`resetAll` 恢复全开
- **DOM 注入**：`<html data-effects="grid scanline glow blink glassblur">` 空格分隔，关闭的特效从列表移除（CSS 用 `[data-effects~='id']` 正向 / `:not([data-effects~='id'])` 关闭成对规则）；`initThemeSync` 挂载前同步写入防 FOUC
- **外观设置页**：`src/pages/AppearanceSettingsPage.vue` 新增「特效开关」SectionCard，按当前风格过滤显示可用特效（无可用时提示「当前风格无特效开关」）；i18n 键见 `zh.ts` / `en.ts` appearance 组
- **装饰层**：`src/styles/global.css` 已移植旧前端 neon（网格/输入框发光/按钮光晕/菜单激活/状态点脉冲）、cyberpunk（扫描线/NCard 切角角标/按钮切角/菜单脉冲/侧栏条纹/状态点闪烁/徽章发光/滚动条）、glass（header/sider 毛玻璃）装饰，全部挂接 `data-effects` 与 `data-animations` 双门控
- **语义说明**：关闭特效仅消失**动画/滤镜/装饰层**；风格骨架（切角、角标、黄边框、网格色）属于风格本身，保留不变

## 4. 落地接入步骤（把某方案变成第 10 种风格）

1. **新增 style 键**：`src/themes/themes.ts` 按现有结构增加 `aurora` / `matrix` / `zen` 等新风格的 `BASE_COLORS` 条目（20 键）+ `STYLES` 条目（24 键 cssVars + schemes + `dark` 标志）+ `STYLE_ORDER` 插入 id。`assertThemeDataIntegrity()` 会自动校验 48 键一致性。
2. **装饰层**（变量表达不了的部分）：在 `src/styles/global.css` 新增 `:root[data-style='xxx']` 作用域规则（极光层、扫描线、角标、玻璃 backdrop-filter），按第 3 节约定挂接 `[data-effects~='id']` 与 `[data-animations='on']` 双门控，并成对提供关闭规则。三套（六套）原型的 CSS 可直接移植。
3. **日志色入 token**：把 `--log-*` 5 个变量纳入 `themes.ts` 的 `CSS_VAR_KEYS`，每个风格定义自己的日志配色（修复 P3）。
4. **naive-ui 映射**：`themes/naiveMapping.ts` 无需加键（11 键映射是通用名）；如需组件级定制见第 6 节打包方案。
5. **硬编码色清理**（修复 P2）：BotCard / LogPanel / TemplateEditor 等文件的 `rgba(148,163,184,…)` / `rgba(69,163,230,…)` 换成变量。
6. **响应式**：侧栏折叠沿用统一 768px 断点；原型中额外的 900px / 640px 断点仅作演示。

原型与生产实现的差异（已知）：原型为纯静态演示，操作仅给视觉反馈；日志拖拽接入时替换为 `LogPanel.vue`；表格/表单接入时替换为 `NDataTable` / `NForm`。

---

## 5. 组件库评估

### 5.1 Naive UI（现有）—— 建议继续使用

**优势**（本项目的既有投资）：
- 90+ 组件全 TypeScript、tree-shakable、**无需引入任何 CSS**（零样式副作用，主题纯 JS overrides）
- 主题系统类型安全，与项目现有的 48 变量体系天然契合（已跑通 `naiveMapping`）
- 数据组件默认虚拟列表（日志、表格大数据友好）
- 已深度集成：41 个组件 + useDialog/useMessage，测试覆盖 12 个文件

**短板**（本文档 P1-P5 已列出）：组件级主题零覆盖、`data-style` 装饰层机制缺失 —— 这两点与组件库本身无关，是项目实现问题，**换库不能解决**。

### 5.2 备选组件库对比（若未来要换）

| 库 | 设计语言 | 主题定制 | 与现有系统适配成本 | 备注 |
|----|----------|----------|---------------------|------|
| **Element Plus** | 中后台事实标准，蓝白风 | SCSS 变量 + CSS vars | 高（全部组件替换） | 生态最大、中文文档最好，但默认观感与项目现有风格体系不兼容 |
| **Ant Design Vue** | 蚂蚁企业风 | ConfigProvider + less token | 高 | 组件全、企业级，暗色支持好；体积偏大 |
| **Arco Design Vue** | 字节风，现代 | 设计 token 完善 + 暗色 | 高 | 视觉更"设计感"，与 Aurora 方向接近 |
| **TDesign Vue** | 腾讯 | CSS vars + 主题生成器 | 高 | 中规中矩 |
| **PrimeVue** | 中性 | **unstyled mode + Tailwind**（完全自定义） | 中 | 主题自由度最高，适合 Matrix/Zen 类定制 |
| **shadcn-vue / Radix-Vue** | 无头组件 | 复制源码进项目，样式完全自有 | 中 | 无组件库包袱，但维护成本转移到自己团队 |

**结论**：Naive UI 的组件能力与主题系统并不弱，本项目的"素"是**定制层缺失**而非库的问题。**不建议换库**；建议按第 5 节方案增强现有体系。若未来追求"完全自由样式"，PrimeVue（unstyled）或 shadcn-vue 是相对平滑的迁移方向，但都属于重投入。

---

## 6. 基于 Naive UI 的打包 / 工程化方案

### 6.1 按需自动导入（当前为全量手动 import）

```bash
npm i -D unplugin-vue-components unplugin-auto-import
```

```ts
// vite.config.ts
import Components from 'unplugin-vue-components/vite'
import AutoImport from 'unplugin-auto-import/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    // 自动导入 naive-ui 组件 + 样式
    Components({ resolvers: [NaiveUiResolver()] }),
    // 自动导入 vue / vue-router / pinia / vue-i18n 的 API
    AutoImport({
      imports: ['vue', 'vue-router', 'pinia', 'vue-i18n'],
      dts: 'src/auto-imports.d.ts',
    }),
  ],
})
```

收益：41 个组件的手动 import 全部消除，模板直接用 `<n-button>`；体积维持 tree-shaking。

### 6.2 组件级主题 overrides（修复 P4 的"素"）

`naiveMapping.ts` 当前只派生 `{ common }`。扩展为「common + 组件级」双层映射：

```ts
// 组件级定制示例（按风格可选）
export const COMPONENT_OVERRIDES: Record<string, Record<string, Record<string, unknown>>> = {
  aurora: {
    Menu: { itemTextColorActive: '#5eead4', itemIconColorActive: '#5eead4' },
    DataTable: { thColor: 'rgba(255,255,255,.04)', tdColorHover: 'rgba(255,255,255,.06)' },
    Card: { borderRadius: '18px', color: 'rgba(255,255,255,.055)' },
  },
  matrix: {
    Menu: { itemTextColorActive: '#00ff88' },
    DataTable: { thColor: '#060d09', tdColorHover: 'rgba(0,255,136,.05)' },
  },
  zen: {
    Menu: { itemTextColorActive: '#3b5bdb' },
    DataTable: { thColor: '#f5f2ec', tdColorHover: '#faf8f5' },
  },
}
```

在 `deriveNaiveOverrides` 返回 `{ common, ...COMPONENT_OVERRIDES[styleId] }`，风格切换时组件级观感随之切换。

### 6.3 data-style 装饰层机制（P1）—— 已建立

`src/styles/global.css` 已建立风格装饰层约定：`[data-style='xxx']` 只放**变量表达不了的质感**（backdrop-filter、clip-path、扫描线、角标、文字渐变），统一挂接 `[data-effects~='id']`（特效开关）与 `[data-animations='on']`（全局动画开关）双门控，并成对提供 `:not([data-effects~='id'])` 关闭规则。六套原型的 CSS 均可按此约定移植。

### 6.4 其他工程建议

- **日志色**：`--log-*` 入 48 键 token（修复 P3），每风格独立定义。
- **字体**：保持系统字体栈（中文显示最优）；如需品牌感，`vfonts`（naive 官方字体包）或本地 `@font-face` 均可，避免 CDN 依赖。
- **图标**：现有 `@vicons/ionicons5` 够用；如需更多风格可加 `@vicons/tabler`（线性图标，与 Zen 契合），均按需 tree-shake。
- **性能**：naive-ui 无需 CSS 导入；页面路由已按组件懒加载；保持 `NDataTable` 虚拟滚动。

---

## 7. 落地路线图建议

| 阶段 | 内容 | 风险 |
|------|------|------|
| **P0（进行中）** | 修复 P2/P3：硬编码色 → 变量、`--log-*` 入 token；修复 P4：加组件级 overrides（菜单/表格/表单） | 低，无视觉颠覆 |
| **P1（已完成主体）** | ✅ `[data-style]` 装饰层机制（neon/cyberpunk/glass 已移植）+ ✅ 特效开关机制（store/页面/i18n/测试全绿）；把选定方案（如 Aurora / Synthwave）实现为第 10 种风格，Appearance 页自动出卡片 | 中 |
| **P2（可选）** | 按 6.1 引入自动导入；按 6.2 给每个风格配组件级 override 集 | 低 |
| **P3（可选重投入）** | 若未来要完全自由样式，评估迁移 PrimeVue（unstyled）/ shadcn-vue | 高 |

---

*原型由本仓库 `frontend-vue/examples/` 提供；色板与接入步骤以上述为准。*
