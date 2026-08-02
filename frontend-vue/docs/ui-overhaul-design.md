# UI 重构设计文档：6 种演示页风格实装 + 按演示页重构 + 深度 UX 优化

> 状态：Design Review APPROVED（qa 修订复审 6/6 + security APPROVE WITH MINOR）→ 实现 Review APPROVED（fidelity/perf REVISE + qa/sec APPROVE WITH MINOR，remediator 16 项修复，integrator 复核 READY FOR DELIVERY）
> 工作目录：`E:\ELA-Bot`
> 范围：`frontend-vue/` 样式层（themes / stores / global.css / 渲染层 / i18n / 测试）
> 前置约束：页面结构、路由、功能冻结 —— 本设计**只动样式层**
> 对应演示设计：`frontend-vue/examples/full-ui-design.md`（§8 特效统一方案、§6.2 特效文案）
> 基线核实：`themes/themes.ts`（1559 行）、`stores/theme.ts`（330 行）、`styles/global.css`（709 行）、`themes/naiveMapping.ts`（46 行）、`AppearanceSettingsPage.vue`（366 行）、`App.vue`（135 行）、`MainLayout.vue`（484 行）、`stores/theme.test.ts`（373 行）

---

## 1. 目标与范围

### 1.1 目标

把 `frontend-vue/examples/full-ui/` 下 6 个演示页（aurora / matrix / zen / synthwave / ink / pixel）的视觉风格与特效系统实装到生产端：

1. **风格注册**：6 新风格进入 `STYLES` / `BASE_COLORS` / `STYLE_ORDER`（现 9 风格 → 15 风格），通过 DEV 硬约束 `assertThemeDataIntegrity`（48 键封闭、STYLE_ORDER ↔ STYLES 一一对应、每风格 ≥1 scheme、merged 48 键非空）。
2. **特效注册**：5 个新特效 id（aurora / sunset / wash / fade / shine）+ 4 个既有 id 的 styles 扩展，进入 `EFFECT_DEFS`，面板按 `availableEffects` 自动渲染，`readInitialEffects` 缺省 true 逻辑自动向后兼容。
3. **装饰层**：独立装饰节点（`.fv-decor`）承载 4 个全屏 fixed 层，解决 body::before/::after 竞争；所有新特效钩子遵守 global.css 正/off 成对契约。
4. **UX 深度优化**：reduced-motion、FOUC 防护、焦点态、滚动条、对比度、切换流畅度（边界内清单见 §5）。
5. **测试**：219 用例基线全绿；theme.test.ts 语义化扩展（只增不改现有断言）。

### 1.2 In-Scope（本次改动清单）

| 类别 | 内容 |
|------|------|
| 数据层 | `themes.ts`：BASE_COLORS +6 组、STYLES +6 风格、STYLE_ORDER +6、zen 双 scheme |
| 状态层 | `stores/theme.ts`：EFFECT_DEFS 扩展（+5 新 id、4 旧 id 追加 styles） |
| 样式层 | `global.css`：6 风格区块（底色 / 装饰层 / 字体 / 滚动条 / 焦点 / reduced-motion） |
| 渲染层 | `App.vue`：注入 `.fv-decor` 装饰容器；`AppearanceSettingsPage.vue`：**零结构改动确认**（+ 可选预览卡 hover 提示） |
| 映射层 | `naiveMapping.ts`：per-style 字体通道 + pixel 圆角特判 |
| i18n | `locales/zh.ts` / `en.ts`：5 个新特效 labelKey |
| 测试 | `theme.test.ts`：EFFECT_ID_LIST 扩展 + availableEffects 新断言 + integrity 断言 |

### 1.3 Out-of-Scope（冻结项，明确不动）

- **信息架构 / 路由 / 页面结构**：MainLayout 布局（topbar 48px / sider 260px / footer 180px / 7 导航项）、页面组件、子页过渡。
- **功能逻辑**：Bot 管理、配置、知识库、日志等任何业务行为。
- **后端**：FastAPI、NoneBot、数据库零接触。
- **演示页**：`examples/full-ui/*.html` 不提交、不修改（它们是本次的参照物）。
- **CSS_VAR_KEYS**：48 键封闭，严禁新增 token（硬约束 3）。
- **现有 9 风格**：BASE_COLORS / STYLES 现有条目逐字不动；global.css 只追加区块；现有特效规则不动（零回归约束 4）。
- **cyberpunk WIP 弹窗**：保留现状（`AppearanceSettingsPage.vue` L41-63 特判不动）。

---

## 2. 架构决策（5 个裁决 + 特效注册 + 装饰节点 + 分波次计划）

### 2.1 裁决 1：特效层元素竞争 → 独立装饰节点方案（`.fv-decor` 容器）

**背景**：body::before 已被 neon grid（global.css L169）、body::after 已被 cyberpunk scanline（L317）占用；新风格需要 4 个全屏 fixed 层（aurora 极光 / matrix 网格 / synthwave 太阳+网格 / pixel 扫描线，其中 synthwave 单风格内太阳+网格需共存）。

**证据**：6 个演示页全部使用独立 `<div>` 装饰元素（参照源为 `frontend-vue/examples/full-ui/` 完整功能版 —— 根目录 `examples/` 下另有精简原型，本设计特效 id 全集（§2.6）与 full-ui 版一致（如 aurora 页 FX_IDS=['aurora','glassblur','glow']），故以 full-ui/ 为参照；实测：aurora.html L107 `.aurora-layer`、matrix.html L636-637 `.grid-layer`+`.scanline`、synthwave.html L519-520 `.sun-layer`+`.grid-layer`、ink.html L151-152 `.ink-wash`+`.seal`、pixel.html L703 `.scanline`），且 full-ui-design.md §8.2 matrix 注记明确推荐「独立层可将底色保留 / 特效关闭分离」。

**裁决：独立装饰节点方案** —— App.vue 注入一个固定容器与若干固定子层，纯 CSS 门控显隐，零 JS 渲染逻辑：

```html
<div class="fv-decor" aria-hidden="true">
  <div class="fv-layer fv-aurora"></div>      <!-- aurora 极光层 -->
  <div class="fv-layer fv-grid"></div>        <!-- matrix/synthwave 网格层 -->
  <div class="fv-layer fv-sun"></div>         <!-- synthwave 太阳层 -->
  <div class="fv-layer fv-scanline"></div>    <!-- matrix/synthwave/pixel 扫描线 -->
  <div class="fv-layer fv-wash"></div>        <!-- ink 水墨晕染 -->
  <div class="fv-layer fv-seal">雅</div>      <!-- ink 朱砂印章 -->
  <div class="fv-layer fv-shine"></div>       <!-- 保留位：pixel shine 装饰（CSS 未引用，见 §4.2 注记） -->
  <div class="fv-layer fv-fade"></div>        <!-- 保留位：ink fade 过渡（CSS 未引用，见 §4.2 注记） -->
</div>
```

实现要点：

1. **常驻 DOM + CSS 门控**：8 个子层默认 `display: none`；仅当 `:root[data-style='aurora'][data-effects~='aurora'] .fv-aurora` 等正钩子匹配时显示。风格互斥（同一时刻只有一个 data-style），子层间零冲突；特效关闭（`:not([data-effects~='id'])`）成对 off 规则恢复 `display: none`。这使 FOUC 防护免费获得：`initThemeSync()` 同步写入 `data-style` 前，所有子层不可见。
2. **z-index 分层**（与 neon/cyberpunk 既有体系一致）：
   - 背景型层（aurora / grid / sun / wash / seal）：`z-index: 0`，位于内容之下，仿 neon grid（L189-195）将 `.n-layout` 背景透明化以透出装饰；
   - 覆盖型层（scanline）：`z-index: 9999`，仿 cyberpunk scanline（L317-338），`.n-layout` 无需透明化。**实施期核对项（INFO-2）**：matrix/pixel/synthwave 风格下打开 naive 对话框/消息弹层（useDialog/useMessage，z-index 通常 ≥2000）时目视核对 scanline 不遮挡弹层；若遮挡，将 scanline z-index 限制在 2000 以下（如 1000），并确认仍高于 `.n-layout` 内容层。
3. **性能**：`pointer-events: none` 全层强制；动画只用 `opacity` / `transform` / `background-position`（GPU 合成）；aurora 极光层为单一 blur(60px) 层（演示页同值），不做多层叠加；动画统一双门控 `[data-animations='on']`。
4. **不触碰** body::before/::after 现有规则（neon/cyberpunk 零回归）。

**否决的备选**：
- 每风格复用伪层：synthwave 单风格内太阳+网格无法共存（body::before 一个槽位），且 aurora/matrix/pixel 三风格若共享伪层则特效开关无法独立门控。
- 组合背景（body 多 background-image）：matrix 网格已是演示页明确否决的做法（§8.2：「底色保留 / 特效关闭」分离），且特效开关无法独立控制单层。

### 2.2 裁决 2：zen 亮暗变体 → 第二个私有 scheme（38 键覆盖），不放弃暗色子项

**背景**：zen 演示页 `dark: false`（亮纸感 bg #faf8f5），但 zen.html 含 `html.dark` 暗色变体（L43）且外观页有 chipDark/chipLight 切换并持久化。生产端 `StyleDef.dark` 是静态二元（store L175），决定 naive 明暗主题与 merge 取 scheme.light/dark 集。

**裁决：双 scheme 方案** —— zen 持有两个私有 scheme：`zen-paper`（默认，亮纸感）与 `zen-night`（墨夜暗色变体）：

```ts
// themes.ts 私有常量（不加入 SCHEME_ORDER，避免污染共享方案集合）
const zenPaperScheme: SchemeDef = { id: 'zen-paper', name: { zh: '宣纸', en: 'Paper' }, cssVars: { light: {...38 键亮色}, dark: {...38 键同值占位} } }
const zenNightScheme:  SchemeDef = { id: 'zen-night', name: { zh: '墨夜', en: 'Ink Night' }, cssVars: { light: {...38 键暗色}, dark: {...38 键同值占位} } }
```

要点与理由：

1. **mechanism 推导**：zen `dark: false` → `mergeCssVars`（themes.ts L1464）恒取 `scheme.cssVars.light` 集，因此把变体色值放进 `.light` 集即可。**论据更正（M1）**：原「`.dark` 集填同值满足 integrity 的 light/dark 键集一致检查（L1530-1538）」不成立 —— integrity 的键集一致检查（L1524-1539）只遍历 `SCHEME_ORDER`，zen-paper/zen-night 是**私有 scheme，不入 SCHEME_ORDER** → 键集一致性**无自动检查**；私有 scheme 实际仅被 merged-48-键非空检查覆盖（L1541-1553 遍历 `STYLES[id].schemes` 含私有 scheme）。`.dark` 集填同值仍保留（维持数据对称与未来并入全局序的安全），但**键集 light==dark 且各 38 键的保证改由 §3.8 新增测试断言显式承担**。
2. **UI 呈现零结构改动**：scheme chips 由 `AppearanceSettingsPage.vue` L120-132 按 `currentStyle.schemes` 自动渲染，用户看到「宣纸 / 墨夜」两个 chip，语义即演示页的亮/暗变体切换。
3. **naive 联动正确**：不动 `dark` 标志 → `naiveTheme` 保持 lightTheme、日志 palette（global.css L43-51 `data-theme='light'`）保持亮系，避免「纸感背景 + 深色 naive 控件」的割裂；暗色变体通过 38 键 scheme 覆盖（含 --bg-color/--card-bg/--text-color/--text-light/--primary-color 等 20 键配色 + 4 sidebar 键 + 14 面板类键）达成。
4. **持久化兼容**：老用户 stored scheme 对 zen 无效 → `readInitialScheme`（store L82-87）回退 `schemes[0]`（zen-paper）；`setStyle` 重置 schemes[0]（L193-198）。均已有逻辑，零改动。
5. **工作量可控**：38 键 × 2 套纯色值数据，无新机制。

**否决的备选**：放弃暗色子项 —— 违背演示页语义保真（演示页明确提供变体并持久化）；把 zen 整体做成 dark 风格 —— 违背演示页默认亮纸感，且 naive 深色化割裂。

### 2.3 裁决 3：aurora glow 渐变文字映射 → 导航选中项 + 状态点/焦点环，不做页面标题

**背景**：演示页 aurora/synthwave 的渐变文字（`background: linear-gradient(...); background-clip: text; color: transparent`）挂在 `.brand` 与 `.page-title` 上；生产端无 brand 文字元素（MainLayout topbar 为 NMenu + 语言选择 + 主题切换，无品牌文案），页面标题分散在 10+ 页面组件内部。

**裁决**：渐变文字映射到生产端可触及的 UI 表面，**不触碰页面组件**：

| 演示页语义 | 生产端映射目标 | 说明 |
|------------|----------------|------|
| `.brand` / `.page-title` 渐变 | `.n-menu-item-content--selected .n-menu-item-content-header` 渐变文字 | 生产端导航选中项 ≈ 演示页 `.nav-item.active` 角色；naive 水平菜单选中类已核实（global.css L228 同款用法） |
| 顶部渐变下划线 | `.n-menu-item-content--selected::after` 渐变条 + 辉光 | 仿 neon glow 下划线（L228-238）模式 |
| `.page-title` 辉光 | 状态点（`.status-dot`）辉光、`:focus-visible` 焦点环 | 辉光语义保留，不做文字渐变 |
| 按钮辉光 | `.n-button` 盒阴影辉光 | 仿 neon glow（L208-214）模式 |

要点：aurora 的渐变专用色（#22d3ee→#a78bfa→#f499b6）作为 aurora 风格**装饰层常量**写死在 global.css 区块内（非 cssVar，48 键封闭约束下不允许 token 化）；`fx-off-glow` 关闭时渐变降级为 `var(--primary-color)` 实色 + `text-shadow: none`（遵守「补静态观感」规范，full-ui-design.md §8.2 规则②）。synthwave 的 glow 采用演示页迁移豁免：`fx-off-glow` 仅 `animation: none`，渐变文字关闭动画后保留静态渐变（full-ui-design.md §8.2 明确豁免 aurora 静态降级规范不套用于 synthwave）。

**否决的备选**：放弃渐变仅保留辉光 —— 丢失演示页核心视觉语义（渐变标题是 aurora/synthwave 的标志性观感）；映射页面标题 —— 需要触碰 10+ 页面组件，超出「只动样式层」边界。

### 2.4 裁决 4：matrix 等宽 / ink serif 字体 → 双通道方案（naive 动态字体 + 装饰层选择器）

**背景**：演示页 matrix 全站等宽（`--font` 换用 mono 值，终端语义），ink 的 serif 只用于标题/印章类（`.brand`/`.page-title`/`.card-title`/`.data-table th`）。生产端 `--font-family` 在 global.css :root（L27-29）与 `styles/theme.ts` `FONT_FAMILY`（L19-20）静态定义，naive 组件字体由 `common.fontFamily` 决定且**无 per-style 通道**。

**裁决：双通道**：

1. **naive 通道（matrix 全局等宽）**：`naiveMapping.ts` 新增 `STYLE_FONT_STACKS` 常量 + `deriveNaiveOverrides` 增加第三参数 `styleId`：

```ts
// naiveMapping.ts 新增
export const STYLE_FONT_STACKS: Partial<Record<string, { fontFamily?: string; fontFamilyMono?: string }>> = {
  matrix: { fontFamily: 'var(--font-mono)', fontFamilyMono: 'var(--font-mono)' },
}
// deriveNaiveOverrides(vars, base, styleId) 内：
const stack = styleId ? STYLE_FONT_STACKS[styleId] : undefined
if (stack) { common.fontFamily = stack.fontFamily; common.fontFamilyMono = stack.fontFamilyMono }
```

   - 调用方 `stores/theme.ts` L184-186 传 `styleId.value`；`fontFamily: 'var(--font-mono)'` 让 naive 组件字体引用 global.css 的 mono 栈（naive 运行时把字符串当 font-family 使用，CSS 变量引用在 `font-family: var(...)` 场景合法）。
   - 同时 global.css matrix 区块给 `body { font-family: var(--font-mono) }`，覆盖继承文本（页面自定义组件、日志等），naive 内部由动态 overrides 跟随 —— 两层合起来达到全站等宽。
   - 测试风险低：theme.test.ts 未断言 naiveOverrides 内容（仅断言 naiveTheme，L149-154）。

2. **装饰层通道（ink serif 标题）**：ink 风格下 `body` 保持 sans（避免全站宋体），global.css ink 区块用选择器集合给标题类元素设 serif：

```css
:root[data-style='ink'] .n-card-header,      /* naive-ui Card 头部（Card.mjs L196 实测 `n-card-header`，无 `__` 分隔） */
:root[data-style='ink'] .section-card-title { font-family: "Songti SC", "STSong", "SimSun", serif; }  /* SectionCard.vue L22 实测存在 */
```

   - 生产端无 `.page-title` 元素（演示页专属），选择器集合不含它；实施期以视觉核对为准收敛选择器集合（≤5 个类），**不映射** naive 全局 fontFamily（ink 是「标题 serif」，不是全站 serif）。
   - 朱砂印章（`.fv-seal` 内文字）天然是装饰层子层，直接 `font-family: serif`。

**否决的备选**：整体降级不做字体 —— 丢失 matrix 终端语义与 ink 水墨气质（演示页核心辨识点）；ink 也走 naive 全局 fontFamily —— 全站宋体过激，且 `common.fontFamily` 影响所有组件包括按钮/输入框，与演示页不符。

### 2.5 裁决 5：pixel 偏移投影 / 圆角清零 → cssVars 通道（圆角）+ 装饰层通道（投影/边框）

**背景**：pixel 演示页全站 `border-radius: 0`、2-3px 硬边框、`box-shadow: 3px 3px 0` 类偏移投影（--shadow-sm/--shadow 硬投影，:active 时 translate(2px,2px)+投影消失）。生产端 naive 组件圆角由已映射 token（NAIVE_MAP：`--radius-md → borderRadius`、`--radius-lg → borderRadiusLarge`）控制，但 `borderRadiusSmall`（styles/theme.ts L30 静态 6px）与 box-shadow token 无 cssVar 映射 —— naive 组件 box-shadow 是**组件内部内联 token**，不读 `--shadow`。

**裁决：双通道**：

1. **圆角 —— cssVars 通道（主）**：pixel 风格 `cssVars` 内 `--radius-md: 0px`、`--radius-lg: 0px`（naive borderRadius/borderRadiusLarge 自动跟随）。**补漏（H1 修订）**：`deriveNaiveOverrides` 增加 pixel 圆角特判，触发条件为**双条件**：`styleId === 'pixel' && vars['--radius-md'] === '0px'` 时 `common.borderRadiusSmall = '0px'`。**禁止按值单判** —— minimal（themes.ts L1269-1270）与 cyberpunk（L1397-1398）的 `--radius-md/--radius-lg` 已是 `'0px'`，若仅按值判断会把二者 borderRadiusSmall 从 styles/theme.ts L30 的静态 6px 漂移到 0px，破坏既有基线；故 styleId 过滤必须在前，值判断只作数据校验。
2. **投影/边框 —— 装饰层通道（主）**：naive 组件 box-shadow 由组件 token 决定，token 化不可行（CSS_VAR_KEYS 封闭）→ global.css pixel 区块用选择器覆盖：

```css
:root[data-style='pixel'][data-effects~='shine'] .n-button,
:root[data-style='pixel'][data-effects~='shine'] .n-card,
:root[data-style='pixel'][data-effects~='shine'] .bot-card { box-shadow: 3px 3px 0 rgba(0, 0, 0, .45); border-radius: 0; }
:root[data-style='pixel'][data-effects~='shine'] .n-button:not(:disabled):active { transform: translate(2px, 2px); box-shadow: 0 0 0 rgba(0, 0, 0, .45); }
```

   - 偏移投影挂在 **shine 特效**上（演示页投影/按压动效属于 pixel 交互语义；且特效关闭时可一键回归平面观感，符合「特效只动动画/装饰，不动布局」契约 —— 投影属于装饰）。
   - naive 内联样式优先级问题：装饰层规则用「class 选择器 + 属性选择器」双段特异性（`[data-style='pixel'][data-effects~='shine'] .n-button`）压过 naive 单类规则；naive 若用内联 style（极少，验证于实施期）则加 `!important` 兜底。
   - 3px 硬边框：演示页 border 2-3px，生产端映射为 `.n-button/.n-card/.bot-card` 装饰层 `border-width: 2px` + 已映射的 `--border-color` 变色（pixel 的 --border-color 用金色系 rgba(255,210,63,.35) 等）。
   - 圆角清零的完整性由装饰层兜底（`.n-*` 关键组件选择器集合在实施期对照演示页核对），避免 borderRadiusSmall 之外的残留圆角。

**否决的备选**：全走 cssVars（--radius-md/--shadow 覆盖）—— `--shadow` 只有 2 个键且 naive 组件不消费它，投影无法传达；全走装饰层 —— 圆角大量重复且丢失 naive borderRadiusLarge 跟随收益。

### 2.6 特效 id 注册方案

`stores/theme.ts` EFFECT_DEFS（L45-51）扩展，**现有 5 条目仅追加 styles 数组元素、不删改原值**：

| id | 原 styles | 扩展后 styles | 新增 labelKey |
|----|-----------|---------------|----------------|
| grid | neon, cyberpunk | neon, cyberpunk, **matrix, synthwave** | 沿用 effectGrid |
| scanline | cyberpunk | cyberpunk, **matrix, synthwave, pixel** | 沿用 effectScanline |
| glow | neon, cyberpunk | neon, cyberpunk, **aurora, matrix, synthwave** | 沿用 effectGlow |
| blink | neon, cyberpunk | neon, cyberpunk, **matrix, pixel** | 沿用 effectBlink |
| glassblur | glass | glass, **aurora** | 沿用 effectGlassblur |
| **aurora** | — | **aurora** | appearance.effectAurora「极光流动」 |
| **sunset** | — | **synthwave** | appearance.effectSunset「日落渐变」 |
| **wash** | — | **ink** | appearance.effectWash「水墨晕染」 |
| **fade** | — | **ink** | appearance.effectFade「渐显过渡」 |
| **shine** | — | **pixel** | appearance.effectShine「光泽扫过」 |

推论（全部自动成立，零额外改动）：
- `EFFECT_IDS`（L53）由 EFFECT_DEFS map 派生 → 自动 5 → 10；
- `readInitialEffects`（L107-124）缺省 true → 老用户 localStorage 5 键 JSON 里缺失的新 id 自动开启（向后兼容）；
- `availableEffects`（L188-190）`styles.includes(styleId)` → 新风格自动出面板项、zen 空态复用现有 `noEffects` 文案；
- `applyEffectsDataset`（L161-165）→ `data-effects` 自动携带新 id；
- `toggleEffect` / `resetAll` → 通用逻辑无需改。

**zen 无特效**（FX_IDS=[]）→ 不注册任何 id，面板空态（AppearanceSettingsPage L146-148 已支持）。

### 2.7 装饰节点方案（App.vue 注入）

- 注入位置：`App.vue` template 内、`NConfigProvider` 内顶部（与 FeedbackBinder 同级、router-view 之前）。NConfigProvider 是普通 div 渲染，装饰层放其内不破坏 naive 主题上下文；`position: fixed` 脱离文档流，布局零影响。
- 结构：单个 `.fv-decor` 容器 + 8 个固定子层（见 §2.1），全部 `aria-hidden="true"`，scoped style 不需要（全部样式在 global.css）。
- 门控规则示例（每特效正/off 成对，遵守 global.css L117-143 契约）：

```css
/* 正钩子（默认开） */
:root[data-style='aurora'][data-effects~='aurora'] .fv-aurora { display: block; ... }
/* off 规则 */
:root[data-style='aurora']:not([data-effects~='aurora']) .fv-aurora { display: none; }
```

- 风格切换隔离：子层显示条件含 `data-style='<id>'`，切回 light/dark 时全部子层自动隐藏 ——「样式隔离零残留」由选择器结构天然保证。

### 2.8 分波次计划（每波独立可验证）

| Wave | 内容 | 独立验证点 |
|------|------|-----------|
| **Wave 1：aurora + 基础设施** | ① `themes.ts`：BASE_COLORS/STYLES/STYLE_ORDER 注册 aurora；② `stores/theme.ts`：EFFECT_DEFS **全量**扩展（10 id 一次到位，EFFECT_IDS/持久化/数据集自动跟随）；③ `App.vue`：.fv-decor 容器 + 全 8 子层（CSS 门控，未实现的风格子层无匹配规则自动不可见）；④ `naiveMapping.ts`：STYLE_FONT_STACKS + styleId 参数 + pixel 圆角特判（数据就位，未注册风格不触发）；⑤ `global.css`：aurora 区块完整（底色/极光层/glassblur/glow/滚动条）+ 全局 :focus-visible + reduced-motion 基础区块；⑥ i18n：5 新特效键 +（zen/synthwave/ink/pixel 风格名内联在 themes.ts）；⑦ theme.test.ts：EFFECT_ID_LIST 10 项 + **仅 aurora 段** availableEffects 断言（aurora→3）与「新风格数据完整性」aurora 骨架断言（其余风格断言随 Wave 2-4 注册分批补入，见 §3.8；availableEffects 由 EFFECT_DEFS 派生，EFFECT_DEFS Wave 1 全量就位后断言稳定，但完整性 describe 依赖 STYLES 注册，必须分批） | 6 风格 integrity 通过（15 风格注册前先注册 6 个风格**骨架**？否 —— **Wave 1 只注册 aurora**，integrity 检查 10 风格；Wave 2-4 增量注册）—— 注：Wave 1 测试需先扩展 EFFECT_ID_LIST 与断言（EFFECT_DEFS 全量就位后断言稳定） |
| **Wave 2：synthwave + matrix** | themes.ts 注册 2 风格（含 synthwave sun 层 + 10 keyframes 裁剪映射、synthwave 56px 网格 + matrix 42px 网格 + 等宽字体双通道）；global.css 两区块 | 切换 3 新风格各自装饰层 checklist；naive 字体跟随验证 |
| **Wave 3：zen + ink** | themes.ts 注册 2 风格 + zen 双 scheme（38×2×2 键数据）；global.css 两区块（zen 无特效区块仅底色/滚动条/焦点；ink wash/fade/印章/serif） | zen 宣纸/墨夜 chip 切换即时生效并持久化；ink 印章与晕染 off 规则 |
| **Wave 4：pixel + 收尾** | themes.ts 注册 pixel；global.css pixel 区块（scanline steps(40)/硬边框/偏移投影/圆角）；reduced-motion 全风格核对、对比度自查表执行、全量回归（219 基线 + 新增）、typecheck、dev integrity | 15 风格切换矩阵全绿；验收矩阵 §6 全项 |

每波独立提交（提交策略见 §8），波内先数据后样式（themes.ts → store → i18n → global.css → 测试），保证任意波结束时应用可启动、integrity 通过、测试全绿。

---

## 3. 文件级变更清单

### 3.1 `frontend-vue/src/themes/themes.ts`（数据层）

| 位置 | 改动 |
|------|------|
| L240 后（BASE_COLORS 收尾 `}` 前） | 新增 6 组 BASE_COLORS：aurora（bg #070b16 / primary #5eead4）、matrix（bg #020604 / primary #00ff88）、zen（bg #faf8f5 / primary #3b5bdb）、synthwave（bg #12082a / primary #ff6ec7）、ink（bg #f6f2ea / primary 朱砂 #b3402a）、pixel（bg #141821 / primary 金 #ffd23f），各 20 键完整（含 --primary-hover/--save-hover/--log-* 等，48 键 merged 非空硬约束） |
| scheme 常量区（L1122 附近） | 新增私有 `zenPaperScheme` / `zenNightScheme`（各 38 键 light + 38 键 dark 同值占位，键集 light==dark 且各 38 键由 §3.8 新增测试断言保证 —— 私有 scheme 不入 SCHEME_ORDER，integrity L1524-1539 键集一致检查不覆盖它们，仅 L1541-1553 merged 48 键非空检查覆盖；不加入 SCHEME_ORDER） |
| L1423 前（cyberpunk 之后） | 新增 6 个 StyleDef：aurora（dark:true, schemes:[DEFAULT_SCHEMES 或私有]）、matrix（dark:true）、zen（dark:false, schemes:[zenPaper, zenNight]）、synthwave（dark:true）、ink（dark:false）、pixel（dark:true）；每风格 24 键 cssVars 完整（--radius-md/--radius-lg 按演示页：pixel 0px、aurora 12/18px 等；--shadow/--shadow-soft 按演示页投影语义，pixel 用硬投影 rgba 值） |
| L1435 后（STYLE_ORDER） | 追加 `'aurora','synthwave','matrix','zen','ink','pixel'`（与 STYLES 同步，integrity L1492-1499；顺序与 Wave 波次一致：W1 aurora → W2 synthwave/matrix → W3 zen/ink → W4 pixel） |
| 不动 | CSS_VAR_KEYS（L283-335，48 键封闭）、DEFAULTS、现有 9 风格条目、SCHEME_ORDER（zen 私有 scheme 不入全局序） |

### 3.2 `frontend-vue/src/stores/theme.ts`（状态层）

| 位置 | 改动 |
|------|------|
| L45-51 EFFECT_DEFS | 按 §2.6 表扩展：现有 5 条目追加 styles 元素；新增 5 条目（id + labelKey + styles） |
| L184-186 naiveOverrides | 调用 `deriveNaiveOverrides(mergedCssVars.value, dark.value ? 'dark' : 'light', styleId.value)`（第三参数） |
| 不动 | EFFECT_IDS（自动派生）、readInitialEffects（缺省 true 兼容）、availableEffects、applyEffectsDataset、initThemeSync（L314-330，FOUC 防护复用，零改动） |

### 3.3 `frontend-vue/src/styles/global.css`（样式层，最大文件）

| 位置 | 改动 |
|------|------|
| L115 后（滚动条区块内） | 追加全局 `:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px }`（对齐演示页焦点语义；naive 自带焦点环不受影响，此为键盘焦点可见性增强） |
| L709 后（文件尾） | 新增「NEW STYLES FX」总区块，按风格分子区块，每区块含：风格底色（body background，若演示页有）、.fv-decor 子层正/off 成对规则、`.n-layout` 透明化（背景型层风格，仿 neon L189-195）、字体覆盖（matrix body mono）、滚动条适配、keyframes（fx-aurora-drift、fx-sun-drift、fx-px-scan 等，全部 `[data-animations='on']` 门控） |
| 文件尾（总区块之后） | `@media (prefers-reduced-motion: reduce)` 全局降级区块：`* { animation: none !important; transition: none !important }` + 装饰层静态降级（aurora opacity 降、sun opacity 降、scanline 静态保留） |
| 不动 | L1-115 基础层（静态 dark fallback 保持）、L117-143 特效钩子规范注释、L145-709 现有 neon/cyberpunk/glass 三区块 |

新特效正/off 规则模板（每特效必须成对，遵守 L128-142 契约）：

```css
/* 正钩子（默认开，等价于无开关时的演示页渲染） */
:root[data-style='synthwave'][data-animations='on'][data-effects~='sunset'] .fv-sun::before { animation: fx-sun-drift 12s ease-in-out infinite; }
/* off 规则（杀动画，保留静态观感） */
:root[data-style='synthwave']:not([data-effects~='sunset']) .fv-sun::before { animation: none; opacity: .12; }
```

### 3.4 `frontend-vue/src/App.vue`（渲染层）

| 位置 | 改动 |
|------|------|
| template 内 NConfigProvider 顶部 | 注入 `.fv-decor` 容器 + 8 子层（§2.1 结构），`aria-hidden="true"` |
| script / style | 零改动（装饰层样式全在 global.css） |

### 3.5 `frontend-vue/src/themes/naiveMapping.ts`（映射层）

| 位置 | 改动 |
|------|------|
| 文件尾 | 新增 `STYLE_FONT_STACKS` 常量（matrix → mono 双栈） |
| L33-45 deriveNaiveOverrides | 签名加第三参数 `styleId: string`；merge 后应用 STYLE_FONT_STACKS；追加 pixel 圆角特判（**双条件**：`styleId === 'pixel' && vars['--radius-md'] === '0px'` 时 `borderRadiusSmall = '0px'` —— styleId 过滤在前，minimal/cyberpunk 的 '0px' 半径不触发，避免漂移基线） |
| 不动 | NAIVE_MAP 11 键映射（L14-26） |

### 3.6 `frontend-vue/src/pages/AppearanceSettingsPage.vue`（渲染层）

| 位置 | 改动 |
|------|------|
| 全文件 | **零结构改动确认**：style-grid v-for STYLE_ORDER 自动渲染 15 卡；scheme chips v-for currentStyle.schemes 自动渲染 zen 双 chip；特效面板 v-for availableEffects 自动渲染新行 |
| 可选（不影响测试） | L225-233 hover 态加 `transition: border-color .2s, transform .2s`（已存在）—— 无必要改动，确认不动 |
| 不动 | cyberpunk WIP 特判（L41-63）、预览卡机制（L26-30 用 mergeCssVars 自动带新风格色值） |

### 3.7 `frontend-vue/src/locales/zh.ts` + `en.ts`（i18n）

| 位置 | 改动 |
|------|------|
| zh.ts L859-865 appearance 区块 | 追加 5 键：effectAurora「极光流动」、effectSunset「日落渐变」、effectWash「水墨晕染」、effectFade「渐显过渡」、effectShine「光泽扫过」 |
| en.ts L1072-1078 对应区块 | 追加 5 键：Aurora Flow / Sunset Gradient / Ink Wash / Fade In / Shine Sweep（实现采用标题大小写） |
| 不动 | 风格名（内联在 themes.ts NamePair，沿用现有机制）、cyberpunk WIP 键、noEffects 键 |

### 3.8 `frontend-vue/src/stores/theme.test.ts`（测试）

| 位置 | 改动（只增不改） |
|------|------------------|
| L23 EFFECT_ID_LIST | 扩展为 10 项 `['grid','scanline','glow','blink','glassblur','aurora','sunset','wash','fade','shine']`（现有遍历型断言自动覆盖新 id，L261-304 循环全兼容） |
| L323-339 availableEffects 测试 | 追加断言段**按波次分批**（与 §2.8 每波测试全绿对齐；availableEffects 由 EFFECT_DEFS 派生，但完整性 describe 依赖 STYLES 注册，故统一按注册节奏分批）：**Wave 1** 仅 aurora→3（aurora/glassblur/glow）段；**Wave 2** 加 matrix→4（grid/scanline/blink/glow）、synthwave→4（sunset/grid/scanline/glow）段；**Wave 3** 加 zen→0、ink→2（wash/fade）段；**Wave 4** 加 pixel→3（blink/scanline/shine）段；现有 neon/cyberpunk/glass 断言原样保留 |
| 新增 describe | 「新风格数据完整性」**按波次增量断言**：`assertThemeDataIntegrity()` 不抛错（直接 import 调用，dev 硬约束的测试化）；6 新风格 `STYLES[id].dark` 断言与 `mergeCssVars(id, schemes[0].id)` 覆盖 48 键非空（循环 CSS_VAR_KEYS）随注册波次增量（Wave 1 仅 aurora，Wave 2 加 matrix/synthwave，Wave 3 加 zen/ink，Wave 4 加 pixel）；**zen 双 scheme 专项（M1）**：`STYLES.zen.schemes` 两枚且首枚为 zen-paper；显式断言 `zenPaperScheme`/`zenNightScheme` 两私有 scheme 的 cssVars.light 与 cssVars.dark 键集相同（deep-equal）且各 38 键 —— 补上 integrity L1524-1539 只遍历 SCHEME_ORDER 而不覆盖私有 scheme 的键集一致性缺口 |
| 新增用例 | 老 localStorage 5 键 JSON + 新 id 缺省 true（`{grid:false}` 时 aurora 仍 true）；naiveOverrides 在 matrix 风格下 fontFamily 含 mono（可选）；**pixel 圆角特判回归（H1）**：minimal 与 cyberpunk 风格下 `deriveNaiveOverrides(vars, 'light', 'minimal'/'cyberpunk')` 返回的 `common.borderRadiusSmall === '6px'`（不变量，防按值判断漂移基线），pixel 风格下 `=== '0px'`；**i18n 双语键（INFO-4）**：5 个新特效 labelKey（effectAurora/effectSunset/effectWash/effectFade/effectShine）在 zh.ts 与 en.ts 均存在且非空 |
| 不动 | 其余 34 个既有 it 断言零删减 |

---

## 4. 接口与契约

### 4.1 保持不变的对外接口

- `mergeCssVars(styleId, schemeId)`：签名不变（zen 双 scheme 由数据驱动）。
- `localizedName` / `isValidStyleId` / `cssVarsToStyleObject`：不变。
- Store 对外方法（setStyle/setScheme/toggleEffect/resetAll/...）：不变。
- `data-style` / `data-theme` / `data-animations` / `data-effects` 数据集契约：不变（新 id 只是更多枚举值）。
- localStorage 键（frontend-vue-style/scheme/custom-css/animations/effects）：不变，值格式不变（老 5 键 JSON 兼容）。

### 4.2 新增契约

- `.fv-decor` 容器与 8 子层类名（`.fv-aurora/.fv-grid/.fv-sun/.fv-scanline/.fv-wash/.fv-seal/.fv-shine/.fv-fade`）—— global.css 与 App.vue 的私有契约，子层仅由 data-style+data-effects 门控。**注记**：`.fv-shine` 与 `.fv-fade` 为保留位 —— 当前 global.css 对 shine/fade 特效的目标分别是 `.n-card-header` 标题装饰与 `.page-enter-*` 过渡，不引用这两个子层；子层默认 `display: none` 且无门控规则命中，恒不可见、零副作用（实施期若需独立装饰层可接入）。
- `STYLE_FONT_STACKS`（naiveMapping.ts 导出常量）—— per-style naive 字体覆盖表，键为风格 id。
- `deriveNaiveOverrides(vars, base, styleId)` —— 第三参数必传（store 唯一调用方同步更新）。
- zen 私有 scheme（zen-paper / zen-night）—— 仅 zen.schemes 引用，不入 SCHEME_ORDER。

---

## 5. UX 优化清单（深度，边界内）

| # | 优化项 | 实现 | 边界 |
|---|--------|------|------|
| 1 | **风格切换流畅度** | body/.n-layout 加 `transition: background-color .3s ease`（基础层）；`.fv-decor` 子层 `transition: opacity .3s ease`（显示/隐藏淡入淡出）；**门控（L2）**：补 `:root[data-animations='off'] body, :root[data-animations='off'] .n-layout, :root[data-animations='off'] .fv-decor * { transition: none }` —— 参照 global.css L70-79 现有 page transition off 先例（`[data-animations='off']` 下杀过渡），确保动画关闭时背景/装饰层过渡一并禁用 | 不引入 CSS 变量过渡（不支持）；切换仍是瞬时变色，但装饰层平滑浮现 |
| 2 | **prefers-reduced-motion 全降级** | 文件尾全局区块：动画/过渡 `none !important`；装饰层静态降级（aurora 极光 opacity .3 静止、sun opacity 静止、wash 静止、scanline 静态线保留）；与 `[data-animations='off']` 双门控并存（演示页同语义） | 不动功能性状态（hover 变色仍保留 —— 用 transition:none 而非禁用 hover 规则） |
| 3 | **特效默认值** | `readInitialEffects` 缺省 true 由现有逻辑保证（§2.6 推论）；新 id 对老用户自动开启 | 零改动 |
| 4 | **焦点态统一** | 全局 `:focus-visible` outline 2px var(--primary-color)（基础层，全 15 风格受益）；aurora/ink 的辉光焦点环在各自区块（正/off 成对） | 只增强键盘焦点可见性，naive 焦点环不冲突 |
| 5 | **滚动条适配 6 风格** | per-style 滚动条：aurora（半透明冷灰）、matrix（绿 rgba(0,255,136,.2) + 直角）、synthwave（紫）、ink（纸色 + 细线）、pixel（金色 + `border-radius: 0`）；off 规则恢复基础层 L99-115 | 仿 cyberpunk 滚动条先例（L621-659） |
| 6 | **空态统一** | zen 无特效 → 现有 `noEffects` 文案自动复用；新风格不新增空态 | 零改动 |
| 7 | **对比度自查** | 明色风格（zen/ink）正文/次要文字对底色 WCAG ≥4.5:1 自查表（§7 风险表附），实施期用色板计算核验；暗色风格（aurora/matrix/synthwave/pixel）主体文字 ≥7:1（演示页已满足） | 数据层定色时执行 |
| 8 | **FOUC 防护** | `initThemeSync` 复用（同步写 data-style + #fv-theme-vars + data-effects）；新装饰层默认 display:none 且仅 data-style 匹配才显示 → 首帧零闪烁；global.css :root 静态 fallback 保持 dark | 零改动（验证项） |
| 9 | **样式隔离** | 切回旧风格零残留：所有新规则锚定 `[data-style='<新id>']`，子层含 style 条件 → 结构保证（验收矩阵覆盖） | 零改动 |

---

## 6. 验收矩阵（可测）

| # | 验收项 | 判定方法 | 波次 |
|---|--------|----------|------|
| 1 | 15 风格切换矩阵 | Appearance 页逐风格点击：scheme 重置、dark/light 正确、data-style/data-theme/data-effects 更新、localStorage 持久化、刷新恢复 | 每波 |
| 2 | 无 FOUC | 刷新（含 cold load）：首帧即正确风格（initThemeSync 同步注入）；装饰层不闪现 | 每波 |
| 3 | 逐风格装饰层 checklist | 对照演示页逐项：aurora 极光层 blur(60px) 渐变动画；matrix 42px 网格 + 扫描线 + 全站等宽；synthwave 太阳 + 56px 网格（synthwave.html L81 实测 `background-size:56px 56px`）+ 渐变标题辉光；zen 纸感/墨夜双变体；ink 晕染 + 朱砂印章 + serif 标题；pixel 直角 + 硬边框 + 偏移投影 + steps(40) 扫描线 | Wave 2-4 |
| 4 | 特效开关逐 id | 面板关闭某特效 → 装饰层消失/静态化（正/off 成对）；重置后恢复；localStorage JSON 含新 id | 每波 |
| 5 | 219 测试基线全绿 | `vitest run` 全量；theme.test.ts 新增断言全过 | 每波 |
| 6 | typecheck 0 错误 | `vue-tsc --noEmit`（或项目脚本） | 每波 |
| 7 | dev integrity 通过 | `npm run dev` 启动无 `Theme data integrity check failed`（15 风格 × schemes 48 键 merged 非空） | 每波 |
| 8 | i18n 双语 | 中/英切换：特效面板 5 新键、风格名双语、无缺失键告警 | Wave 1 |
| 9 | reduced-motion | OS 开启「减少动态效果」：动画全停、装饰静态化、页面可正常操作 | Wave 4 |
| 10 | 样式隔离 | 切回 light/dark/minimal：无新风格残留（子层隐藏、字体还原、滚动条还原、焦点环还原） | 每波 |
| 11 | 对比度 | zen/ink 正文 #3b5bdb/#b3402a 系文本对底色 ≥4.5:1（自查表执行记录） | Wave 3 |

---

## 7. 风险与失败模式

| # | 风险 | 失败模式 | 缓解 / 回退 |
|---|------|----------|-------------|
| 1 | **视觉回归（现有 9 风格）** | 误改既有 BASE_COLORS/STYLES 条目、global.css 现有区块、naiveMapping 既有映射 | 硬性纪律：现有条目逐字不动，global.css 只追加；git diff 审查只含新增行；回归用验收矩阵 #10 + 截图对比 |
| 2 | **naive 覆盖不住**（pixel 投影/圆角、matrix 字体） | naive 内联 token 或内联 style 优先级高于装饰层 | 双段特异性选择器（§2.5）；必要时 `!important` 兜底（实施期验证 naive 是否内联 style）；naive 字体走动态 overrides 通道（不靠装饰层） |
| 3 | **性能**（aurora blur(60px) + 多动画层） | 低端机滚动卡顿、GPU 内存 | 装饰层固定 ≤3 层；动画只 opacity/transform/background-position；reduced-motion 与 data-animations off 双降级；aurora-layer 动画期间 blur 层单一 |
| 4 | **测试断言破坏** | EFFECT_DEFS 扩展误写（如把 glow 的 styles 覆盖而非追加）→ availableEffects 既有断言（neon→3/cyberpunk→4/glass→1）变红；EFFECT_ID_LIST 扩展遗漏 → 循环断言漏新 id | §2.6 表逐行核对；现有断言零修改（只追加）；Wave 1 先扩展测试再改 store（TDD 序） |
| 5 | **zen 双 scheme 语义漂移** | scheme 切换被误认为「配色方案」而非「亮暗变体」；或 integrity 38 键检查失败 | chip 名称直白（宣纸/墨夜）；cssVars.light/dark 键集一致且各 38 键；测试覆盖 zen.schemes 结构 |
| 6 | **synthwave 10 个 keyframes 映射失真** | 演示页组件级动画（文本 glow-drop 等）生产端无对应组件 | 裁剪映射：装饰层动画（sun-drift/scan-sweep/neon-pulse 映射到 sun/grid/scanline 层）全量迁移；组件级动画只映射到生产端存在的表面（导航选中项辉光、状态点、输入焦点）；不存在的组件动画放弃并在验收 checklist 记录 |
| 7 | **initThemeSync 与装饰层竞态** | JS 注入 #fv-theme-vars 前装饰层先显示（理论窗口） | 子层默认 display:none（CSS 静态），data-style 由 initThemeSync 同步写入 → 无窗口；custom CSS 用户注入同名类名冲突 → 文档化 `.fv-` 前缀保留：**外观页自定义 CSS 输入框的提示文案需注明「`.fv-` 前缀为保留命名空间，自定义规则请勿使用」（INFO-1，实施时在 AppearanceSettingsPage.vue 加一行提示文案）** |
| 8 | **老用户 effects JSON 与新 id** | 无（缺省 true 已覆盖）；仅「老用户新风格自动全特效开启」可能造成突入感 | 接受（与演示页默认全开一致）；可后续加 per-style 默认集（不在本次范围） |
| 9 | **i18n 键缺失** | zh/en 不同步 → 面板显示键名 | 双语键在 Wave 1 一次补齐；验收 #8 检查 |

---

## 8. 提交策略建议

遵循项目 Conventional Commits（AGENTS.md §7），按 Wave 提交，每 Wave 一个 commit（数据→样式→测试同波内原子完成，避免中间态）：

| 顺序 | Commit 建议 | 内容 |
|------|-------------|------|
| 1 | `feat(theme): 实装 aurora 风格 + 特效系统基础设施（fx id 10 项 / 装饰节点 / naive 字体通道）` | Wave 1 全量（themes.ts aurora + EFFECT_DEFS 10 id + App.vue 装饰容器 + naiveMapping 通道 + global.css aurora 区块 + i18n + 测试扩展） |
| 2 | `feat(theme): 实装 synthwave / matrix 风格（日落太阳网格 + 终端等宽）` | Wave 2 |
| 3 | `feat(theme): 实装 zen / ink 风格（纸感双变体 + 水墨印章）` | Wave 3 |
| 4 | `feat(theme): 实装 pixel 风格（像素直角硬投影）+ UX 收尾（reduced-motion/滚动条/对比度）` | Wave 4 |

备选（若评审要求更细粒度）：按文件类型拆分（`feat(theme): 注册 6 新风格数据` → `feat(theme): 6 风格装饰层 CSS` → `test(theme): 新风格断言扩展`）。推荐按 Wave 提交（每波可独立验证、可单独 revert）。

Commit 体例：正文含验证证据（测试通过数、integrity 结果、typecheck 结果），`Signed-off-by: RainyN0077 <gotiyu0407@gmail.com>`。

---

## 9. 评审检查清单

1. [ ] 6 新风格数据（BASE_COLORS 20 键 / STYLES 24 键 / 每风格 ≥1 scheme / STYLE_ORDER 同步）满足 assertThemeDataIntegrity 全部 4 项检查
2. [ ] CSS_VAR_KEYS 48 键未扩展；DEFAULTS / 现有 9 风格 / SCHEME_ORDER 未动
3. [ ] EFFECT_DEFS 现有 5 条目仅追加 styles，新 5 条目 id/labelKey/styles 与 §2.6 表一致
4. [ ] global.css 新区块每特效正/off 成对（含 `:not([data-effects~=...])`），动画双门控 `[data-animations='on']`
5. [ ] `.fv-decor` 子层默认隐藏、aria-hidden、pointer-events:none、z-index 分层正确
6. [ ] naiveMapping 第三参数调用方（store）同步更新；pixel 圆角特判**双条件**（`styleId === 'pixel' && vars['--radius-md'] === '0px'`）——minimal/cyberpunk 的 '0px' 半径不触发（回归断言：二者 borderRadiusSmall 保持 '6px'）
7. [ ] zen 双 scheme 键集 light==dark、各 38 键；zen 为 dark:false —— 键集对称由 §3.8 测试断言显式保证（私有 scheme 无 integrity 自动检查）
8. [ ] 测试只增不改：现有 34 it 零删减；EFFECT_ID_LIST 与 availableEffects 断言与实现一致
9. [ ] i18n 中英 5 新键齐全
10. [ ] 演示页不提交、MainLayout/路由/页面组件零改动（git diff 核实）

## 10. Resume 关键事实（供实施者续接）

- **装饰层**：App.vue 注入 `.fv-decor`（8 子层：fv-aurora/fv-grid/fv-sun/fv-scanline/fv-wash/fv-seal），纯 CSS 门控，默认 display:none。
- **特效 id 全集（10）**：grid[neon,cyberpunk,matrix,synthwave]、scanline[cyberpunk,matrix,synthwave,pixel]、glow[neon,cyberpunk,aurora,matrix,synthwave]、blink[neon,cyberpunk,matrix,pixel]、glassblur[glass,aurora]、aurora[aurora]、sunset[synthwave]、wash[ink]、fade[ink]、shine[pixel]。
- **zen 双 scheme**：zen-paper（默认，亮）/ zen-night（暗），色值放 cssVars.light（因 dark:false 恒取 light 集），dark 集同值占位；两私有 scheme 不入 SCHEME_ORDER，键集 light==dark 且各 38 键由 §3.8 测试断言保证（integrity 的键集检查只遍历 SCHEME_ORDER，不覆盖私有 scheme）。
- **aurora/synthwave 渐变**：装饰层常量色，映射导航选中项 + 状态点 + 焦点环；synthwave glow 关闭仅 animation:none（迁移豁免）。
- **matrix 字体**：naiveMapping STYLE_FONT_STACKS + global.css body mono；ink serif 仅标题选择器。
- **pixel 圆角**：cssVars --radius-md/--radius-lg=0px + deriveNaiveOverrides borderRadiusSmall 特判（**双条件 `styleId === 'pixel' && --radius-md === '0px'`**，minimal/cyberpunk 的 '0px' 不触发，防基线漂移）；投影/硬边框走装饰层（挂 shine）。
- **分波次**：W1 aurora+基础设施（EFFECT_DEFS 全量 10 id 一次到位）→ W2 synthwave+matrix → W3 zen+ink → W4 pixel+UX 收尾。
- **测试纪律**：theme.test.ts 只增不改；先扩 EFFECT_ID_LIST 与断言再改实现（TDD 序）。
