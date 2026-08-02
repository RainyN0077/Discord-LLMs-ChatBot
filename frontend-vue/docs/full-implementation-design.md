# ELA-Bot 前端「演示页 → 生产端正式实现」Design Document

> 角色：solutions-architect · 阶段：Stage 2 设计评审
> 日期：2026-08-02 · 基线：前端 vitest 12 文件 / 149 用例全绿
> 范围：Playground 单模型测试对话、调试器 Trace 时间线（三态降级）、捕获删除/清空（前后端）、提示词工坊占位符点击插入、i18n zh/en 同步
> 只做设计，不写实现代码（文中片段为契约示意）

---

## 0. 事实核验记录（相对 Context Brief 的修正与确认）

| 项 | Context Brief 说法 | 代码核验结果 | 设计影响 |
|---|---|---|---|
| 端点 | POST /api/chat/direct | ✅ 一致（`backend/app/routers/chat.py` L174） | 定稿 |
| bot_id | "必带" | ⚠️ 实为 Optional（chat.py L180-183）：提供且 bot_manager 有实例时取该 Bot 配置，缺省回退全局 `load_config()` | 前端 Playground **总是携带** bot_id；后端无需改 |
| debug 路由挂载 | "注册到 main.py" | ⚠️ 不需要：main.py L169 `app.include_router(debug_router)` 已挂载且无 prefix，路由自带完整路径 | S0 无需动 main.py |
| intermediate_llm_responses | 后端恒写 []，TS 类型 string[] | ✅ models.py L309 `default_factory=list`；debug.py L185 经 `_safe_str_list` 输出 | 三态降级解析器是正确策略 |
| 404 模式 | debug.py L160-161 | ✅ `HTTPException(status_code=404, detail="Capture not found.")` | 新 DELETE 端点沿用 |
| DELETE 范本 | bots.py L84-88 | ✅ 返回 `{"message": f"Bot '{bot_id}' deleted."}` | 新端点返回 `{"message": ...}` |
| 存储 | deque maxlen=80 + _lock + deepcopy | ✅ `debug_capture_store.py`（_lock 为 **asyncio.Lock**，非 threading） | 新函数必须 async + 持锁 |
| ModelSettingsPage 接入点 | L476 后、draft 深拷贝、seq 守卫 | ✅ CustomParamsCard L476-482 为最后一张卡；draft L107 JSON 深拷贝；testSeq 守卫 L205-243；resetTransient L118-126 | PlaygroundCard 插在 L482 后 |
| CapturesTab | 330 行、L197-203 为接入点 | ✅ 中间区块 L197-203；工具栏 L111-124；listSeq/detailSeq 守卫（perf LOW-2：列表刷新与详情加载独立序号）；safeJson L102-105 | **新增问题**：行容器是 `<button>`（L136-159），内部再嵌删除按钮属非法嵌套，需重构为 `div[role=button]` |
| TemplateEditor | 271 行、n-input 无 ref、占位符 n-tag L133-135 | ✅ L117-123 无 ref；L133-135 n-tag | 需加 ref + 获取内部 textarea |
| 后端路由测试模式 | — | `backend/tests/routes/test_debug.py`：`app_client`/`auth_headers` fixture + `@pytest.mark.integration` | DELETE 端点测试扩展至此文件 |
| 工作区 | 6 个未提交文件 | ✅ `en.ts/zh.ts/AppearanceSettingsPage.vue/theme.test.ts/theme.ts/global.css`（特效开关）+ `examples/` 未跟踪 | **特例（H1）**：en.ts/zh.ts 双重身份——既是特效改动载体、又是本功能 i18n 目标。裁决见 §12：hunk 级暂存（`git add -p`）仅挑本功能键 hunks 提交；`examples/` 与其余 4 个特效文件整体不提交 |
| 演示页参考 | 各段落行号 | ✅ 全部存在（Playground 797-972 / Reasoning 1520-1521 / Trace 1622-1656 / 降级 1625-1632 / 删除清空 1657-1677 / 占位符 1384-1396） | 只读参考 |

---

## 1. 架构决策（Stage 1 §8 开放点裁决）

### D1 — 端点定稿 + debug_mode 开关

- **端点定稿为 `POST /api/chat/direct`**（以实际代码为准，任务描述中的 `/api/chat` 为笔误）。
- **Playground 不暴露 debug_mode 开关，请求恒置 `debug_mode: false`**。
  - 理由：`debug_mode=true` 会走完整 Discord 模拟链路（人设注入、消息格式化、debug_context 数值 ID 校验），语义是"模拟 Discord 渠道"，与 Playground"用当前草稿的提供商/模型直连 LLM（推理参数按已保存配置，M2）"的目标不同；演示页 Playground 亦无此开关。
  - 边界：`include_system_prompt=true` 保持默认（非 debug 路径会注入 `config.system_prompt`，与演示页"附带当前系统提示词"语义一致）。
- 错误语义（前端需处理）：400（messages 空 / 非法 role / 附件问题）、500（`LLM_PROVIDER_ERROR:` 前缀，后端 500 detail）、503（provider pool 不可用）。**sec-M1**：500 且 `LLM_PROVIDER_ERROR:` 前缀的文案前端**泛化展示**（「LLM 提供商错误，请查看后端日志」，`playground.providerError` 键），detail 详情仅进日志；400/503 统一展示 `detail` 原文。均有重试入口。

### D2 — Trace 以「空态 + 三态降级解析器」交付

- **不补后端写入**（超出批准范围；pipeline 恒写 `[]`）。
- 解析器三态：`empty`（空数组/空值）→ 空态提示；`texts`（string[]，真实数据形态）→ 文本节点列表；`timeline`（对象数组，演示页自定契约的前瞻兼容）→ 时间线。
- 语义：真实数据永远命中 `empty`/`texts`；`timeline` 是防御未来后端补写的扩展点，不为其做任何后端配合。
- Reasoning 折叠与详情降级是**渲染层**职责，与解析器解耦。

### D3 — 单家检测裁剪（记录裁剪理由）

- **裁剪**：演示页含"单家检测"（单提供商一键连通+对话），生产端 **Playground 已覆盖其核心用例**（用当前 draft 的 provider/model 直连 LLM 对话，推理参数按已保存配置——M2；api_key 由后端按 bot_id 读取，不出前端）；且生产端无"单家检测"专用后端支撑（`/api/models_test` 仅连通性测试，非对话链路）。为避免重复入口与语义重叠，本轮不实现。
- **未来扩展方向**：基于 `POST /api/chat/direct` 增加"预设测试模板一键发送"（如 ping/角色扮演/工具调用样例），即可在不新增后端的前提下补齐单家检测的批量验证能力。

### D4 — Playground 请求参数取**实时 draft**（限 provider/model_name/bot_id，M2 修正）

- **裁决：发送时实时读取 draft（props）**，但 **M2 修正范围**——draft 仅驱动 `provider` / `model_name` / `bot_id`（未保存的这三项即时生效）；`temperature/top_p/max_tokens` 等推理参数**不进请求**，由后端按该 Bot **已保存配置**驱动（`/api/chat/direct` 请求模型无参数位，前后端契约决定）。因此 Playground 定位精确表述为「用当前选中的提供商/模型测试，推理参数以已保存配置为准」，hint 文案见 §2.2/§6.1。
- 失败/边界：
  - 无 draft（`!configsStore.config || !draft`）：PlaygroundCard 位于 `<template v-if="configsStore.config && draft">` 块内（ModelSettingsPage L436），天然不渲染 → 不存在"无 draft 时发送"路径；`disabled` prop 作为防御兜底。
  - 参数变化：不做强制提示（这是 Playground 的预期语义），但卡片内常驻 hint 文案说明「测试基于该 Bot **已保存**的配置；当前未保存的修改保存后生效」（M2 定稿文案，见 §2.2/§6.1）。
  - 发送中切换 Bot：**真正风险不是同 Bot 并发发送**（`sending` 标志已拦截重复发送），而是**发送中切换 Bot → 旧 Bot 的响应异步返回后写入新 Bot 的会话**（H2 修正）。修复设计（§2.4）：`watch(() => props.botId, () => { pgSeq++; clearChat() })` 使序号失效 + 清空会话；或挂载处 `:key="botId"` 强制重挂载（二选一，推荐前者——保留组件内部态更可控）。页面级 `loadSeq` 仅废弃旧 draft，不足以拦截 PlaygroundCard 内部 in-flight 响应。

---

## 2. PlaygroundCard 组件设计

### 2.1 文件与挂载

- 新文件：`src/pages/model-settings/PlaygroundCard.vue`（含同名测试 `PlaygroundCard.test.ts`）
- 挂载点：`ModelSettingsPage.vue` `<CustomParamsCard ... />`（L476-482）之后、`</template>`（L483）之前：

```html
<PlaygroundCard
  :provider="draft.llm_provider"
  :model-name="draft.model_name"
  :bot-id="selectedBot!.bot_id"
  :disabled="!!configsStore.loading"
/>
```
（LOW-14：无 params 传参——推理参数由后端按已保存配置驱动，见 §2.2 契约注意；可选 `:key="botId"` 作为 H2 备选重挂载方案）

### 2.2 Props / 消息模型 / 状态

```ts
// props
interface PlaygroundCardProps {
  provider: string
  modelName: string
  botId: string
  disabled: boolean
}
// 注（LOW-14）：不设 params prop——/api/chat/direct 请求模型无参数位，推理参数由后端按已保存配置驱动（见下方契约注意），
//   传参只会形成「看似生效实则无效」的误导接口；需要展示 draft 参数时用既有卡片，Playground 不重复。

// 消息模型（本地会话态，不持久化）
interface PlaygroundMessage {
  id: number                      // 单调递增，供 :key 与重试定位
  role: 'user' | 'assistant' | 'error'
  text: string
  thinking?: boolean              // 发送中的占位气泡（演示页 thinking 语义）
}

// 状态
const messages = ref<PlaygroundMessage[]>([])
const input = ref('')
const sending = ref(false)
const errorText = ref('')          // 列表内 error 消息亦承载错误文案（消息与提示双轨）
let pgSeq = 0                      // H2 序号守卫：由 watch(botId) 递增以作废 in-flight 响应（非并发拦截——sending 已拦截）
let nextId = 1
```

- 注意：**不传 api_key**——后端 `direct_chat` 从 `config`（按 bot_id）读取，api_key 不出前端。
- 注意（M2 契约修正）：`temperature/top_p/max_tokens` 等推理参数**不进请求**——`/api/chat/direct` 的请求模型没有参数位，后端 `runtime_config` 直接取 bot 配置。draft 参数的作用域是"用户编辑的配置"，保存后生效；Playground 发送时若参数尚未保存，后端用的是**已保存配置**。**D4 的裁决仅适用于 provider/model_name/bot_id 取 draft；推理参数由后端配置驱动**（前后端契约决定，非设计取舍）。hint 文案按 M2 定稿表述：「测试基于该 Bot **已保存**的配置；当前未保存的修改保存后生效」（原「使用当前提供商/模型测试」表述易误导用户以为未保存参数即时生效，删除）。

### 2.3 API 封装：新建 `src/api/chat.ts`

```ts
/** 后端契约：POST /api/chat/direct（backend/app/routers/chat.py） */
export interface DirectChatMessage { role: 'user' | 'assistant' | 'system'; content: string }
export interface DirectChatRequest {
  messages: DirectChatMessage[]
  include_system_prompt?: boolean  // 默认 true
  debug_mode?: boolean             // Playground 恒 false（D1）
  bot_id?: string                  // Playground 恒携带（D1）
  // attachments 类型预留（DirectChatAttachment），本轮 UI 不暴露文件选择 —— 见 §9
}
export interface DirectChatResponse {
  success: boolean
  response: string                 // 后端已 encode_output（HTML 实体编码）
  usage: Record<string, number> | null
  provider: string
  model: string
  debug_mode: boolean
  formatted_user_messages?: string[] | null
  debug_user_details?: unknown[] | null
}

export async function sendDirectChat(payload: DirectChatRequest): Promise<DirectChatResponse> {
  return fetchWithAuth<DirectChatResponse>('/api/chat/direct', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
```

- **sec-M1 错误泛化（前端收敛，后端零改动）**：`toApiError` 解析响应时，若 `status === 500` 且 message 以 `LLM_PROVIDER_ERROR:` 开头（后端 500 detail 前缀，见 D1），则将**对外文案替换为泛化提示**（`playground.providerError` 键），原始 detail 只写入 `console.error`/日志、不渲染给用户（500 detail 可能内嵌提供商原始报错，含模型名/配额等内部信息）；其余状态（400/503 等）维持展示 detail 原文。该逻辑放 `toApiError`（复用层，单点收敛），PlaygroundCard 直接使用转换后的文案。
  - **实现落点（qa LOW-4 单源）**：`toApiError` 将 500 provider 错误归一化为 `LLM_PROVIDER_ERROR_MESSAGE = `${PROVIDER_ERROR_PREFIX}. Check backend logs.``（`PROVIDER_ERROR_PREFIX = 'LLM provider error'` 由 `src/api/client.ts` **导出**，原始 detail 经 `console.error` 截断 500 字符）；PlaygroundCard 以 `status === 500 && detail.startsWith(PROVIDER_ERROR_PREFIX)` 判定后映射为 i18n `playground.providerError` 键（zh/en 本地化）展示——**归一化文案与 UI 判定前缀共用 client.ts 的 `PROVIDER_ERROR_PREFIX` 单一来源**，避免两处独立字符串漂移；`LLM_PROVIDER_ERROR:` 后端前缀为第二处常量，仅存在于 client.ts。

### 2.4 发送流程（四态 + 重试）

```
sendChat():
  text = input.trim()
  if (!text) → warn 提示，return
  if (sending || disabled) → return
  if (!modelName) → error 提示「请先配置模型名称」，return   // M2：该守卫是「基于 draft 的前端护栏」——model_name 取 draft，未配置时阻断，避免误导性请求
  seq = ++pgSeq
  push {role:'user', text} + {role:'assistant', text: t('playground.thinking'), thinking:true}
  input = ''
  sending = true
  try:
    resp = await sendDirectChat({
      messages: [{role:'user', content: text}],   // 单轮：Playground 为无状态测试对话（演示页同语义）
      include_system_prompt: true,
      debug_mode: false,
      bot_id: botId,
    })
    if (seq !== pgSeq) return
    替换 thinking 气泡 → {role:'assistant', text: resp.response}
    记录 usage（resp.usage）→ 展示「Token 用量」；total 兜底 total = resp.usage.total ?? (prompt + completion)  // LOW-16
  catch (err):
    if (seq !== pgSeq) return
    替换 thinking 气泡 → {role:'error', text: 错误消息}   // sec-M1：错误消息经 toApiError 泛化（见下）
  finally:
    if (seq === pgSeq) sending = false

// H2 守卫（防「发送中切换 Bot → 旧响应写入新 Bot 会话」）：
watch(() => props.botId, () => { pgSeq++; clearChat() })
// 备选：挂载处 :key="botId" 强制重挂载（二选一，推荐 watch——组件内部态保留、重挂载成本更低）

retry(): 定位最后一条 role==='user' 的消息文本，删除其后的 error/assistant 消息，复用 sendChat 逻辑重发

clearChat(): messages = []; usage 清零
```

- **H2 说明**：`sending` 标志使同 Bot 并发发送不可能，`pgSeq` 原守卫（"两次快速发送丢弃旧响应"）在本设计中实际不可达；真正的过期响应来源是 **botId 变化**（页面级 `loadSeq` 只废弃旧 draft，不拦截 in-flight 响应）。因此守卫重心迁移为 `watch(botId)` 递增 `pgSeq` + `clearChat()`——旧 Bot 响应返回时 `seq !== pgSeq` 被丢弃，且消息列表已清空，不可能污染新 Bot 会话。
- **sec-M1 错误泛化（前后端契约）**：`toApiError` 对 `status === 500` 且 message 以 `LLM_PROVIDER_ERROR:` 开头（后端 500 detail 前缀，D1）的文案做**泛化展示**——气泡与提示统一显示「LLM 提供商错误，请查看后端日志」（新增 `playground.providerError` 键，zh/en 对称）；原始 `detail` 详情仅 `console.error` 进日志，不渲染给用户。400/503 等其余状态维持展示 `detail` 原文。**后端零改动**（500 detail 透传属既有行为，前端侧收敛）。
- 四态映射：**空态引导**（messages 空 → EmptyState/文案 `playground.empty`）｜**发送中**（thinking 气泡 + 发送按钮 loading + 输入禁用）｜**回复**（assistant 气泡 + usage 行）｜**失败重试**（error 气泡内嵌「重试」按钮，演示页 `role:'fail'` 语义）。
- 消息数上限：>50 条裁剪头部（演示页 `if (arr.length > 50)` 同语义）。
- 清空按钮位于卡片头部（演示页 `pg-clear` 语义）。

### 2.5 XSS 策略

- 后端已 `encode_output`（HTML 实体编码），但前端**一律纯文本渲染**：Vue `{{ }}` 插值（自动转义）+ `white-space: pre-wrap` 样式保格式；**禁止 v-html**（双保险，防后端编码回归与未来契约变更）。
- error 文案同样插值输出。

---

## 3. Trace 解析器设计

### 3.1 新文件：`src/pages/debugger/trace.ts`（纯函数，无 Vue 依赖）

```ts
export type TraceStage = 'request' | 'reasoning' | 'tool_call' | 'tool_result' | 'response' | 'other'

export interface TraceNode {
  stage: TraceStage      // 白名单映射后的阶段；未知归 'other'
  rawStage: string       // 原始 stage 名（'other' 时用于展示）
  name: string           // tool_call 的工具名 / 节点名
  args: string           // tool_call 的参数摘要（演示页 meta 行）
  content: string        // 节点正文（reasoning 折叠 / response 内容）
}

export type TraceParseResult =
  | { kind: 'empty' }
  | { kind: 'texts'; items: string[]; degraded?: boolean }   // M1：degraded=true 表示源为混合/异常形态（见 §3.2），调用方据此渲染 detailFallback
  | { kind: 'timeline'; items: TraceNode[] }

export function parseTraceSteps(input: unknown): TraceParseResult
```

### 3.2 三态降级逻辑（裁决规则）

| 输入形态 | 判定 | 结果 |
|---|---|---|
| `null` / `undefined` / 非数组 / `[]` | — | `{kind:'empty'}` |
| 数组且元素全为 string | 真实数据形态（后端 `_safe_str_list`） | `{kind:'texts', items}`（过滤空串后仍为空 → 回退 empty；degraded 缺省 `false`） |
| 数组且元素全为 object、每项 `stage` 为 string | 演示页自定契约（前瞻兼容） | `{kind:'timeline', items}`；stage 不在白名单（`request/reasoning/tool_call/tool_result/response`）→ `'other'` 并保留 `rawStage`；字段缺失以 `''` 兜底 |
| 混合数组（string 与 object 混杂）/ 元素类型异常（含元素为 `null`） | 不可预测形态 | 整体降级：`{kind:'texts', items: items.map(String), degraded: true}`，且调用方渲染"降级提示 + 原始 JSON 折叠"（§3.4） |

- 解析器**永不抛异常**（所有分支收敛到三态之一）；`Object` 判定用 `typeof === 'object' && item !== null && !Array.isArray(item)`。

### 3.3 时间线渲染（CapturesTab 详情内，替换 L197-203 区块）

```html
<div class="capture-section">
  <h4>{{ t('debugger.trace') }}</h4>
  <!-- 三态分发 -->
  <p v-if="trace.kind === 'empty'" class="trace-empty">{{ t('debugger.traceEmpty') }}</p>
  <div v-else-if="trace.kind === 'texts'" class="trace-texts">
    <!-- M1：trace.degraded === true 时顶部渲染 detailFallback（role=alert）+ 原始 JSON 折叠（L4 纯文本插值，禁 v-html，见 §3.4） -->
    <pre v-for="(item, i) in trace.items" :key="i" class="capture-code">{{ item }}</pre>
  </div>
  <div v-else class="timeline">
    <div v-for="(node, i) in trace.items" :key="i" class="tl-node" :data-stage="node.stage">
      <span class="tl-dot" :class="{ warn: node.stage === 'tool_call' }"></span>
      <div class="tl-body">
        <div class="tl-head">{{ stageLabel(node) }}</div>
        <div v-if="node.stage === 'tool_call'" class="tl-meta">{{ node.name }}{{ node.args ? ' · ' + node.args : '' }}</div>
        <details v-if="node.stage === 'reasoning' && node.content" class="reasoning-fold">
          <summary>{{ t('debugger.traceReasoning') }}</summary>
          <div class="reasoning-content">{{ node.content }}</div>
        </details>
        <div v-else-if="node.content" class="tl-meta">{{ node.content }}</div>
      </div>
    </div>
  </div>
</div>
```

- **UI 选型裁决**：时间线**自绘 div**（与演示页 1643-1651 结构一致：dot + body + head/meta；零组件依赖、测试断言直接、样式 scoped 可控）；Reasoning 折叠用**原生 `<details>`**（演示页 1521 同款；默认折叠零状态管理；n-collapse 作为备选但引入额外状态）。
- `stageLabel(node)`：白名单 → `t('debugger.trace' + PascalCase(stage))`；`'other'` → `t('debugger.traceOther')`（或直接显示 rawStage）。
- usage 行复用现有 `formatBytes`（L94-99）+ `captureUsage` 键，**不新增键**。

### 3.4 详情降级

- 调用点：`const trace = computed(() => parseTraceSteps(detail.value?.intermediate_llm_responses))`——解析器不抛，天然兜底。
- 显式降级路径：**判定条件改为 `trace.kind === 'texts' && trace.degraded === true`**（M1：降级标志由解析器显式携带，不再依赖调用方猜测形态；未来 detail 字段形态变化时同样命中）。命中后：在 intermediate 区块顶部渲染 `detailFallback` 提示（role=alert）+ `<details>` 折叠原始 JSON。
- **L4 安全约束**：降级「原始 JSON 折叠」区块一律用**纯文本插值**渲染（`<pre>{{ safeJson(...) }}</pre>`），**禁止 v-html**——原始 JSON 可能含 `<script>`/标签字符，插值保证按字面显示（XSS 双保险：后端 `encode_output` 只覆盖 LLM 回复字段，`intermediate_llm_responses` 不在其列）。
- 保留现有 `safeJson` 与既有区块（system_prompt / history / llm_messages / raw / cleaned / usage）不变；Trace 区块只替换 L197-203。

---

## 4. 捕获删除/清空（前端 + 后端）

### 4.1 后端：`backend/app/debug_capture_store.py` 扩展

```python
async def delete_capture(capture_id: str) -> bool:
    """按 ID 删除单条捕获（持锁）。不存在返回 False。"""
    if not capture_id:
        return False
    async with _lock:
        for idx, row in enumerate(_captures):
            if row.get("id") == capture_id:
                del _captures[idx]
                return True
    return False

async def clear_captures() -> int:
    """清空全部捕获（持锁），返回删除条数。"""
    async with _lock:
        count = len(_captures)
        _captures.clear()
        return count
```

- 保持既有模式：async + `_lock` + 不 deepcopy 返回（delete/clear 无返回体）。

### 4.2 后端：`backend/app/routers/debug.py` 新增端点（main.py 无需改动，见 §0）

```python
@router.delete("/api/debug/captures/{capture_id}", dependencies=[Depends(get_api_key)])
async def delete_debug_capture(capture_id: str):
    """删除单条截取记录。"""
    if not await delete_capture(capture_id):
        raise HTTPException(status_code=404, detail="Capture not found.")   # 沿用 L160-161 404 语义
    return {"message": f"Capture '{capture_id}' deleted."}                  # 沿用 bots.py L88 范本

@router.delete("/api/debug/captures", dependencies=[Depends(get_api_key)])
async def clear_debug_captures():
    """清空全部截取记录。"""
    count = await clear_captures()
    return {"message": f"All debug captures cleared ({count})."}
```

- 导入更新：`from ..debug_capture_store import ... delete_capture, clear_captures`（并入 L10 现有导入）。
- 路径匹配：`/api/debug/captures/{capture_id}` 与 `/api/debug/captures` 段数不同，FastAPI 无冲突；两条 DELETE 各自独立。
- **L1 破坏面说明（文档化）**：两条 DELETE 端点与既有端点同级受 `get_api_key` 认证保护，信任模型一致（**未引入新认证层级**）——即「任何持有 X-API-Key 者均可删除/清空调试捕获」，与既有「持有 Key 者可删除 Bot、清空知识库」的破坏面**同级**，设计上可接受、无需额外加固才合入。
  - **可选加固（非阻断建议，本轮不做）**：① audit 日志——`delete_capture/clear_captures` 成功路径记 `logger.info("capture deleted/cleared by ...")`（含请求方标识）；② `?confirm=1` 查询参数二次确认——仅对**清空**端点生效，未带参数返回 400 提示（防误触脚本）。两者均列为后续增量，不影响本轮验收。

### 4.3 前端：`src/api/debug.ts` 扩展

```ts
/** 删除单条截取记录；404 → 抛错（detail: "Capture not found."）。 */
export async function deleteCapture(captureId: string): Promise<{ message: string }> {
  return fetchWithAuth<{ message: string }>(`/api/debug/captures/${encodeURIComponent(captureId)}`, {
    method: 'DELETE',
  })
}

/** 清空全部截取记录。 */
export async function clearCaptures(): Promise<{ message: string }> {
  return fetchWithAuth<{ message: string }>('/api/debug/captures', { method: 'DELETE' })
}
```

### 4.4 前端：`CapturesTab.vue` 增强

1. **行容器重构（前置条件）**：`.captures-row` 由 `<button>` 改为 `<div role="button" tabindex="0">` + `@click` + `@keydown.enter` + **`@keydown.space.prevent`**（LOW-15：role=button 语义下 Space 与 Enter 同为激活键；合法嵌套删除按钮、键盘可访问性、既有测试选择器 `.captures-row` 不变）。
2. **工具栏清空按钮**：位于「刷新」按钮旁（L121-123 后）：

```html
<n-popconfirm :positive-text="t('generic.confirm')" :negative-text="t('generic.cancel')"
              :disabled="captures.length === 0 || loading"
              @positive-click="handleClearCaptures">
  <template #trigger>
    <n-button secondary :disabled="captures.length === 0 || loading" :loading="clearing">
      {{ t('debugger.capClear') }}
    </n-button>
  </template>
  {{ t('debugger.capClearConfirm') }}
</n-popconfirm>
```

3. **行内删除按钮**（row 右上角）：`n-button size="tiny" quaternary circle @click.stop="handleDeleteCapture(capture)"` + `title/aria-label = t('debugger.capDel')`；单条删除**不弹确认**（进程内存数据、可重建、演示页同语义）。
4. **逻辑**：
   - `handleDeleteCapture`：`await deleteCapture(id)` → `message.success(t('debugger.capDeleted'))` → 若 `detail?.id === id` 关闭 drawer → `loadCaptures()`；失败 → `message.error(t('debugger.capDelFailed', {error}))`。
   - `handleClearCaptures`：`await clearCaptures()` → `message.success(t('debugger.capClearSuccess'))` → 关闭 drawer → `loadCaptures()`；失败 → `message.error(t('debugger.capClearFailed', {error}))`。
   - 新增 `clearing` 状态；删除/清空期间禁用按钮；`listSeq` 守卫不变（loadCaptures 已带；详情加载另由 `detailSeq` 守卫，perf LOW-2）。

---

## 5. 占位符点击插入（TemplateEditor）

### 5.1 ref 获取内部 textarea

```ts
// M4 修正：naive-ui NInput（type=textarea）实例暴露的是 textareaElRef（Ref<HTMLTextAreaElement>，需 .value 解包），非 textareaEl
const editorInput = ref<{ textareaElRef?: Ref<HTMLTextAreaElement | null> } | null>(null)

// 取内部 textarea 的统一辅助（实现时按 naive-ui 实际版本取其一，测试与实现解耦）：
function getTextareaEl(): HTMLTextAreaElement | null {
  const inst = editorInput.value
  return inst?.textareaElRef?.value
    ?? (inst as unknown as { $el?: HTMLElement })?.$el?.querySelector('textarea')
    ?? null
}
```

- 模板：`<n-input ref="editorInput" ...>`（L117）。
- **主方案**：`editorInput.value?.textareaElRef?.value`（Ref 解包）；**回退方案**：`$el.querySelector('textarea')`（两者均需在实现时以实际 naive-ui 版本验证，`getTextareaEl` 统一封装、失败返回 null 并静默降级——插入失败不阻塞编辑）。**测试通过 `wrapper.find('textarea')` 断言，与实现解耦**。

### 5.2 插入函数与键盘可访问

```ts
function insertPlaceholder(ph: string): void {
  const el = getTextareaEl()        // M4：统一取内部 textarea（textareaElRef 解包 / $el.querySelector 兜底）
  if (!el) return
  const start = el.selectionStart
  const end = el.selectionEnd
  const value = el.value
  const next = value.slice(0, start) + ph + value.slice(end)
  updateValue(selectedKey.value, next)          // 全量 emit（既有 updateValue L36-38）
  requestAnimationFrame(() => {                  // 等 Vue 更新绑定值后置位光标
    el.focus()
    el.setSelectionRange(start + ph.length, start + ph.length)
  })
  message.success?.(t('promptStudio.editor.phInserted', { ph }))
}
```

模板（L133-135 改造）：

```html
<n-tag v-for="p in selectedPlaceholders" :key="p" size="small" class="placeholder-tag"
       tabindex="0" role="button"
       :title="t('promptStudio.editor.phInserted', { ph: p })"
       @click="insertPlaceholder(p)"
       @keydown.enter="insertPlaceholder(p)"
       @keydown.space.prevent="insertPlaceholder(p)">
  {{ p }}
</n-tag>
```

### 5.3 依赖与提示

- `useMessage()`：生产端需在 `NMessageProvider` 内（PromptStudioPage 若未包裹则页面级补包——实现时确认；测试挂 NMessageProvider，与 ProvidersPage.test.ts 同款）；`message.success?.()` 可选链兜底。
- 选中文本替换语义：选中一段文字再点占位符 → 选中区域被占位符替换（演示页 1387-1391 同款 slice 逻辑）。

---

## 6. i18n 键清单（zh/en 逐键）

### 6.1 新增键

**`modelSettings.playground.*`（新子组，modelSettings 现有 8 键不动）**

| 键 | zh | en |
|---|---|---|
| `modelSettings.playground.title` | Playground 测试对话 | Playground |
| `modelSettings.playground.hint` | 测试基于该 Bot **已保存**的配置；当前未保存的修改保存后生效 | Testing uses this bot's **saved** config; unsaved changes take effect after saving |
| `modelSettings.playground.placeholder` | 输入测试消息...（Enter 发送，Shift+Enter 换行） | Type a test message... (Enter to send, Shift+Enter for newline) |
| `modelSettings.playground.send` | 发送 | Send |
| `modelSettings.playground.sending` | 发送中... | Sending... |
| `modelSettings.playground.empty` | 在这里用当前模型测试对话，无需保存配置。 | Test a conversation with the current model here — no save needed. |
| `modelSettings.playground.thinking` | 正在思考... | Thinking... |
| `modelSettings.playground.error` | 发送失败：{error} | Send failed: {error} |
| `modelSettings.playground.providerError` | LLM 提供商错误，请查看后端日志 | LLM provider error; check backend logs |
| `modelSettings.playground.retry` | 重试 | Retry |
| `modelSettings.playground.clear` | 清空对话 | Clear chat |
| `modelSettings.playground.usage` | Token 用量：输入 {p} · 输出 {c} · 总计 {t} | Tokens: {p} in · {c} out · {t} total |
| `modelSettings.playground.noModel` | 请先配置模型名称 | Model name is not configured |
| `modelSettings.playground.emptyInput` | 请输入消息内容 | Please enter a message |

- **LOW-13**：`error` 与 `sendFailed` 原为同文案双键，**合并为 `error` 一键**（error 气泡与重试提示共用）。
- **sec-M1**：`providerError` 为新增键——500 且 `LLM_PROVIDER_ERROR:` 前缀时替代 `error` 展示（泛化文案，见 §2.4）。
- **LOW-16**：`usage` 的「总计 {t}」渲染时 total 兜底 `total ?? prompt + completion`（响应缺 total 字段时求和展示；i18n 文案不含字段名，后端字段名变化不影响）。

**`debugger.*`（现有 68 键不动，以下全部为新键；命名 cap/trace 前缀，不与 directChat 组冲突）**

| 键 | zh | en | 使用点 |
|---|---|---|---|
| `debugger.trace` | Trace 时间线 | Trace Timeline | §3.3 中间区块标题（原 `captureIntermediateOutputs` 保留给设置开关） |
| `debugger.traceEmpty` | 无中间阶段输出 | No intermediate outputs | §3.3 空态 |
| `debugger.traceRequest` | 请求 | Request | stageLabel 白名单映射 |
| `debugger.traceReasoning` | 推理 | Reasoning | reasoning 折叠 summary |
| `debugger.traceToolCall` | 工具调用 | Tool Call | stageLabel 白名单映射 |
| `debugger.traceToolResult` | 工具结果 | Tool Result | stageLabel 白名单映射 |
| `debugger.traceResponse` | 响应 | Response | stageLabel 白名单映射 |
| `debugger.traceOther` | 阶段 | Stage | `'other'` 通用标签 |
| `debugger.capClear` | 清空 | Clear All | §4.4 工具栏清空按钮 |
| `debugger.capClearConfirm` | 确认清空全部截取记录？此操作不可恢复。 | Clear all captured records? This cannot be undone. | n-popconfirm 文案 |
| `debugger.capDel` | 删除 | Delete | 行内删除按钮 title/aria-label |
| `debugger.capDeleted` | 已删除该条截取记录 | Capture deleted | 删除成功 message |
| `debugger.capClearSuccess` | 已清空全部截取记录 | All captures cleared | 清空成功 message |
| `debugger.capDelFailed` | 删除失败：{error} | Delete failed: {error} | 删除失败 message |
| `debugger.capClearFailed` | 清空失败：{error} | Clear failed: {error} | 清空失败 message |
| `debugger.detailFallback` | 详情解析失败，已降级显示原始内容。 | Failed to parse detail; showing raw content instead. | §3.4 role=alert 降级提示（`texts && degraded`） |
| `debugger.detailRaw` | 原始 JSON | Raw JSON | §3.4 降级 `<details>` summary |
| `debugger.detailHistory` | 历史消息（{count}） | History ({count}) | **替换 CapturesTab.vue L190 硬编码 `"History ({{ n }})"`**（LOW-12 确认：L190 现为写死文案，本次收编为新键并替换） |

- **LOW-12 闭环**：`detailSys` / `detailUsage` / `detailParseFail` 三个键**删除**——既有区块（system_prompt / history / llm_messages / raw / cleaned / usage）标题沿用现有键不变，无新使用点；`detailParseFail` 与 `detailFallback` 语义重叠（后者已覆盖"解析失败"提示），避免双键冗余。usage 数值行复用现有 `debugger.captureUsage`（zh.ts L460）+ `formatBytes`，不新增标题键。

**`promptStudio.editor.*`（现有 8 键不动 + 新增 1 键 = 共 9 键；§0 事实核验口径同步为 9）**

| 键 | zh | en |
|---|---|---|
| `promptStudio.editor.phInserted` | 已插入占位符 {ph} | Placeholder {ph} inserted |

**键数对账（LOW-10，以实际清单为准）**：新键总数 **33** = `modelSettings.playground.*` 14 + `debugger.*` 18 + `promptStudio.editor.phInserted` 1。对账路径：原始清单 36（playground 14 + debugger 21 + phInserted 1）→ 合并 `error`/`sendFailed`（-1，LOW-13）→ 删除 `detailSys`/`detailUsage`/`detailParseFail`（-3，LOW-12）→ 新增 `providerError`（+1，sec-M1）→ **33**。zh/en 两文件此数必须一致（A10 键数 diff = 0 以此为基准）。

### 6.2 避让清单（硬性约束）

- **appearance 组特效 7 键**（`enablePageTransitions` / `effectGrid` / `effectScanline` / `effectGlow` / `effectBlink` / `effectGlassblur` / `noEffects`，zh.ts L823-831）——本次新增键**零触碰**（工作区未提交改动保持原样）。
- **提交策略（H1 裁决）**：zh.ts/en.ts 中本功能新键与特效 7 键**可能同处一个文件**。提交时对两文件执行 `git add -p` 逐 hunk 选择，**仅暂存本功能键所在 hunks**；若特效键与新键处于同一 hunk 无法拆分（`git add -e` 编辑 hunk 也失败时），采用后备方案：临时 `git stash push -- <file>`（仅特效改动）→ 提交 i18n → `git stash pop` 恢复。验收口径见 A12（以 `git show --stat <commit>` 与 `git status` 双口径核验）。
- 现有 `debugger.captureUsage` 已存在——复用而非新增同名键。
- `directChat` 组 31 键只读参考，不引用、不重名（新键均以 `playground.` / `trace` / `cap` / `detail` 前缀隔离）。
- zh/en 两文件**逐键对称**（新增键必须同时落两文件，i18n 完整性由 §7 测试兜底）。

---

## 7. 测试计划

### 7.1 新增/扩展文件与用例清单（估算新增 ≈ 50 用例：trace 10 + CapturesTab 14 + PlaygroundCard 12 + TemplateEditor 4 + store 6 + routes 4）

| 文件 | 类型 | 用例要点 | Mock 策略 |
|---|---|---|---|
| `src/pages/debugger/trace.test.ts`（新建） | 纯函数单测 | ① null/undefined/非数组/[] → empty；② 全 string → texts（`degraded` 缺省 false）；③ 空串过滤后为空 → empty；④ 全对象 + 白名单 stage → timeline（stage 映射正确）；⑤ 未知 stage → other 且保留 rawStage；⑥ 字段缺失 → 空串兜底；⑦ 混合数组 → texts 降级且 `degraded: true`；⑧ 元素为 null 的数组 → 降级不抛且 `degraded: true`（`items` 含 `"null"` 字符串）；⑨ tool_call 节点 name/args 解析；⑩ 解析器永不抛（fuzz 少量畸形输入） | 无（纯函数） |
| `src/pages/debugger/CapturesTab.test.ts`（新建） | 组件单测 | ① 列表加载 + 空态；② 删除单条：点击行内删除 → deleteCapture(id) 被调 → 成功 reload 列表；③ 删除当前打开详情的行 → drawer 关闭；④ 删除失败 → error 提示 + 列表不变；⑤ 清空：确认弹窗 → clearCaptures 被调 → reload；⑥ 清空取消 → 不调用；⑦ Trace 三态渲染：empty 提示 / texts 渲染 pre / timeline 渲染 tl-node；**⑦b degraded 降级：`degraded:true` 的 texts → detailFallback 提示渲染、正常 texts → 不渲染**；⑧ reasoning 节点默认折叠（details 无 open）；⑨ tool_call 节点显示 name/args；⑩ 详情加载失败 → detailError；⑪ 行容器键盘可访问（enter 打开详情）；⑫ 删除按钮点击不触发行点击（stopPropagation）；⑬ **L4：intermediate 含 `<script>` 的混合数据 → 降级 JSON 折叠内文本按字面显示（`<pre>` 内容含 `<script>` 字面、无元素被创建）** | `vi.mock('@/api/debug')`（deleteCapture/clearCaptures/listCaptures/getCapture 全 mock）+ NMessageProvider + i18n（ProvidersPage.test.ts 范本） |
| `src/pages/model-settings/PlaygroundCard.test.ts`（新建） | 组件单测 | ① 空态引导文案；② 空输入发送 → 不调用 API + 提示；③ 发送成功：thinking 气泡 → assistant 文本 + usage 展示（total 兜底 `total ?? prompt + completion` 断言）；④ 发送失败：error 气泡 + 重试按钮；⑤ 重试复用最后 user 消息；⑥ **H2 守卫：发送中切换 botId（`botId` prop 变化）→ 旧响应丢弃 + 消息列表清空**（assert 旧 response resolve 后不产生 assistant 消息；同 Bot 重复点击被 `sending` 拦截）；⑦ disabled 时发送按钮禁用；⑧ 清空清空消息与 usage；⑨ 消息 >50 裁剪；⑩ 纯文本渲染（response 含 `<script>` 不被解析，插值转义断言）；⑪ 无 modelName 时阻止发送（draft 护栏）；⑫ 500 `LLM_PROVIDER_ERROR:` → 泛化提示「LLM 提供商错误，请查看后端日志」（sec-M1，mock toApiError 或 fetchWithAuth 500 响应） | `vi.mock('@/api/chat')`（sendDirectChat 可控 resolve/reject，含挂起 Promise 供 ⑥）+ NMessageProvider + i18n |
| `src/pages/prompt-studio/TemplateEditor.test.ts`（扩展 +4） | 组件单测 | ① 点击占位符 → 光标处插入 → emit update:templates 含新值；② 选中文本被占位符替换；③ 插入后光标置于占位符之后（setSelectionRange 断言）；④ 键盘 enter/space 触发插入 | 既有 mount 模式（无 API mock）；`wrapper.find('textarea')` 直接设 `selectionStart/End` 后触发 tag click |
| `backend/tests/test_debug_capture_store.py`（扩展 +6） | 后端单测 | ① delete_capture 存在 → True 且列表减少；② 不存在/空 ID → False；③ delete 后 get_capture → None；④ clear_captures 返回条数；⑤ clear 后 list 为空；⑥ 并发 add+delete 不抛（持锁验证） | 沿用现有模式（直接调用 + `_captures.clear()` 隔离） |
| `backend/tests/routes/test_debug.py`（扩展 +4） | 后端集成 | ① DELETE 单条需认证（401/403）；② DELETE 单条不存在 → 404；③ DELETE 单条成功 → `{"message": ...}`；④ DELETE 全部成功 → `{"message": ...}` 且随后 GET 为空 | 沿用 `app_client`/`auth_headers` fixture + `@pytest.mark.integration`；**M3 隔离策略**：`conftest._reset_global_state` 不清空 `debug_capture_store` 模块级全局 `_captures`，故新用例（尤其 ③④ 与既有 GET 用例同文件执行时）必须**在每个用例内显式 `debug_capture_store._captures.clear()`**（或 fixture `autouse` 清空），避免用例间状态泄漏；同时 `delete_capture/clear_captures` 为 async，集成用例用 `pytest.mark.asyncio` 或既有 fixture 的 event loop 执行 |

### 7.2 断言要点与既有基线保障

- 组件测试统一模式：`vi.mock('@/api/xxx')` + **真实 pinia/naive-ui** + `flushPromises()`（ProvidersPage.test.ts 范本）；CapturesTab 无 store 依赖（直接 mock api）。
- 基线保障：**149 用例保持全绿**；新增文件不触碰既有 12 个测试文件（仅 TemplateEditor.test.ts 扩展追加 describe 块，不改既有用例断言）。
- i18n 对称性：新增键 zh/en 同步由 `TemplateEditor.test.ts`/组件测试中文断言 + 实现后 `grep` 核对（en.ts 键数 = zh.ts 键数）。
- 后端：`pytest backend/tests/ -m "not integration"` 快速回归 + 全量运行确认无破坏。

---

## 8. 切片计划（每片独立验证）

| 切片 | 内容 | 独立验证 |
|---|---|---|
| **S0 后端 DELETE** | `debug_capture_store.py` 新增 delete_capture/clear_captures；`debug.py` 新增 2 个 DELETE 端点；`test_debug_capture_store.py` 扩展 + `routes/test_debug.py` 扩展 | `pytest backend/tests/test_debug_capture_store.py backend/tests/routes/test_debug.py`；手动 curl 验证 404/成功/清空 |
| **S1 api 层 + 解析器** | `api/debug.ts` 增 deleteCapture/clearCaptures；新建 `api/chat.ts`（sendDirectChat + 类型）；新建 `pages/debugger/trace.ts` + `trace.test.ts` | `npx vitest run src/pages/debugger/trace.test.ts`；`npx vue-tsc --noEmit` 类型检查 |
| **S2 CapturesTab 增强** | 行容器 button→div[role=button] 重构、清空按钮（n-popconfirm）、行删除、Trace 三态区块（替换 L197-203）、Reasoning 折叠、详情降级、i18n `debugger.*` 新键（zh/en）；新建 `CapturesTab.test.ts` | `npx vitest run src/pages/debugger/CapturesTab.test.ts` + 既有 debugger 相关测试；手动打开详情验证三态 |
| **S3 PlaygroundCard** | 新建 `PlaygroundCard.vue` + 挂载 ModelSettingsPage L482 后 + i18n `modelSettings.playground.*`（zh/en）+ `PlaygroundCard.test.ts` | `npx vitest run src/pages/model-settings/PlaygroundCard.test.ts`；手动直连验证真实 LLM 链路与 503 降级 |
| **S4 TemplateEditor 插入** | ref 获取 textarea、占位符 tag 点击/键盘插入、光标置位、`message` 提示、i18n `promptStudio.editor.phInserted`（zh/en）、测试扩展 | `npx vitest run src/pages/prompt-studio/TemplateEditor.test.ts`；手动插入验证光标位置 |
| **S5 测试补全 + 回归** | i18n zh/en 对称核对（键数 diff = 0，§6.1 对账 33 键）、全量前端 vitest、后端 pytest、类型检查、**git 提交清单核对（H1：zh.ts/en.ts 用 `git add -p` 仅暂存本功能键 hunks；`git status` 保留特效改动 + `git show --stat <commit>` 不含特效键；排除 examples/ 与特效 4 文件）** | `npx vitest run`（149 + 新增全绿）；`pytest backend/tests`；`git status` + `git show --stat` 双口径核对提交范围 |

---

## 9. 范围外清单（明确不做）

1. **单家检测**：裁剪（理由见 D3），未来以 Playground 预设模板扩展。
2. **后端补写 intermediate_llm_responses**：pipeline 恒写 `[]` 维持现状（超出批准范围）。
3. **Playground debug_mode 开关**：恒 false（D1）；不暴露 debug_context/formatted_user_messages 语义。
4. **演示页视觉风格照搬**：仅语义迁移，样式走生产端 scoped/主题变量。
5. **`examples/` 提交**：含 full-ui/aurora.html 的目录保持未跟踪，不进入任何 commit。
6. **脏表单路由守卫**（未保存离开确认）：无此需求（Playground 不写 store；TemplateEditor 由 PromptStudioPage 既有保存流管理）。
7. **Playground 附件/图片/OCR**：`api/chat.ts` 类型预留 attachments，本轮 UI 不提供文件选择（后端契约已支持，属后续增量）。
8. **usage 定价/格式化增强**：仅展示 Token 计数，不做费用估算。
9. **特效开关特性（工作区 6 个未提交文件）**：叠加存在，不纳入本功能提交，不为其补测试/文档；**例外（H1）**：zh.ts/en.ts 中本功能 i18n 新键按 §12 hunk 级暂存提交（特效 7 键 hunks 留在工作区）。

---

## 10. 验收矩阵

| # | 功能 | 验收标准（全部可验证） |
|---|---|---|
| A1 | Playground 发送 | 选中 Bot 进入模型设置页 → Playground 卡片渲染；输入消息发送 → 请求体 `POST /api/chat/direct` 含 `messages[0]={role:'user',content}` + `bot_id` + `debug_mode:false`；响应文本以纯文本渲染（含 `<`/`&` 字符不回显为 HTML）；usage 行显示 Token 计数 |
| A2 | Playground 四态 | 空态引导文案；发送中 thinking 气泡 + 按钮 loading；成功替换为 assistant 消息；失败出现 error 气泡 + 重试按钮，重试复用最后一条 user 消息；发送期间重复点击被 `sending` 拦截 |
| A3 | Playground 边界 | 空输入 → 提示不发送；未配置 model_name → 阻止发送（draft 护栏）；**H2：发送中切换 Bot → 旧响应被丢弃 + 消息清空**（watch(botId) 或重挂载）；同 Bot 发送期间重复点击被 `sending` 拦截；消息 >50 条裁剪头部；清空按钮清空消息与 usage |
| A4 | Trace 三态 | 真实捕获（后端 `[]`）→ 显示"无中间阶段输出"空态；mock string[] → 逐条 pre 渲染；mock 对象数组 → 时间线节点渲染，白名单 stage 映射正确、未知 stage 显示通用标签、字段缺失不崩溃 |
| A5 | Reasoning 折叠 | timeline 中 reasoning 节点默认折叠（details 无 open 属性），点击展开显示 content |
| A6 | 详情降级 | 畸形 intermediate 数据（混合数组/元素为 null）→ `{kind:'texts', degraded:true}` + `detailFallback` 提示 + 原始 JSON 折叠（纯文本插值渲染，含 `<script>` 不解析）；正常 string[] 无降级提示；解析器对 null/undefined/非数组输入永不抛异常 |
| A7 | 单条删除 | 行内删除按钮点击不触发行详情；`DELETE /api/debug/captures/{id}` 404 时提示删除失败；成功 → success 提示 + 列表刷新；删除当前详情行 → drawer 关闭 |
| A8 | 清空 | 工具栏清空按钮在列表为空/加载中禁用；确认弹窗确认后 `DELETE /api/debug/captures` → 成功提示 + 列表空态；取消不调用 |
| A9 | 占位符插入 | 点击占位符 tag → 插入到光标处（选中区域被替换）→ `update:templates` 全量 emit 新值 → 光标位于插入文本后 → textarea 获得焦点；键盘 Enter/Space 等效触发；成功提示 `phInserted` |
| A10 | i18n 对称 | zh.ts 与 en.ts 新增键逐键成对（键数 diff = 0，以 §6.1 实际清单为准）；appearance 特效 7 键与既有全部键零改动；i18n 提交按 §12 H1 裁决执行 hunk 级暂存（`git add -p` 仅挑本功能键 hunks；特效键与新键同 hunk 时走 stash 后备方案） |
| A11 | 测试基线 | 前端 `npx vitest run` 全绿（149 + 新增 ≈50）；后端 `pytest backend/tests` 全绿（含新增 store 与路由用例） |
| A12 | 提交范围 | `git status` 工作区保留特效改动（en.ts/zh.ts 特效 hunks + AppearanceSettingsPage.vue/theme.test.ts/theme.ts/global.css 4 文件）与本功能文件；`git show --stat <commit>` 不含任何特效键、不含 examples/；提交信息遵循 Conventional Commits（scope: frontend / debugger） |

---

## 11. 文件清单汇总

**后端（4 个文件）**
- `backend/app/debug_capture_store.py` — 修改：+delete_capture / +clear_captures
- `backend/app/routers/debug.py` — 修改：+2 个 DELETE 端点（L10 导入扩展）
- `backend/tests/test_debug_capture_store.py` — 修改：+TestDeleteCapture / +TestClearCaptures
- `backend/tests/routes/test_debug.py` — 修改：+4 集成用例
- `backend/app/main.py` — **不改**（路由已挂载）

**前端（12 个文件）**
- `src/api/client.ts` — 修改：`toApiError` 对 500 且 `LLM_PROVIDER_ERROR:` 前缀的 message 泛化（sec-M1 落点，§2.4/§13 第 1 条）
- `src/api/chat.ts` — 新建：sendDirectChat + DirectChatRequest/Response/Message
- `src/api/debug.ts` — 修改：+deleteCapture / +clearCaptures
- `src/pages/debugger/trace.ts` — 新建：parseTraceSteps + 类型
- `src/pages/debugger/trace.test.ts` — 新建（≈10 用例）
- `src/pages/debugger/CapturesTab.vue` — 修改：行容器重构、工具栏清空、行删除、Trace 区块、降级
- `src/pages/debugger/CapturesTab.test.ts` — 新建（≈14 用例）
- `src/pages/model-settings/PlaygroundCard.vue` — 新建
- `src/pages/model-settings/PlaygroundCard.test.ts` — 新建（≈12 用例）
- `src/pages/ModelSettingsPage.vue` — 修改：挂载 PlaygroundCard（L482 后）
- `src/pages/prompt-studio/TemplateEditor.vue` — 修改：ref + 插入逻辑
- `src/pages/prompt-studio/TemplateEditor.test.ts` — 修改：+4 用例
- `src/locales/zh.ts` / `src/locales/en.ts` — 修改：新增 §6.1 全部键（两文件对称）；**提交方式为 hunk 级暂存**（§12 H1 裁决），仅本功能键 hunks 进入 commit

**不提交**：`frontend-vue/examples/` 整体；特效文件中的 4 个非 i18n 文件（AppearanceSettingsPage.vue/theme.test.ts/theme.ts/global.css）叠加保留、不纳入本功能 commit；en.ts/zh.ts 例外——按 §12 H1 裁决以 `git add -p` 仅暂存本功能键 hunks（特效 7 键 hunks 留在工作区）。

---

## 12. 主要风险与回退

| 风险 | 影响 | 回退/缓解 |
|---|---|---|
| naive-ui NInput 内部 textarea 获取方式随版本变化（M4：暴露的是 `textareaElRef`（Ref 需解包）而非 `textareaEl`；部分版本 `$el` 亦可用） | S4 阻塞 | `getTextareaEl()` 统一封装：`textareaElRef?.value` 主方案 + `$el.querySelector('textarea')` 回退；失败返回 null 静默降级；测试与实现解耦（`wrapper.find('textarea')`） |
| `message` 无 NMessageProvider（生产） | S3/S4 提示静默 | 页面级确认/包裹 provider；组件内 `message.success?.()` 可选链 |
| DELETE 端点与既有路由匹配异常 | S0 | FastAPI 段数区分无冲突；集成测试覆盖 404/200 |
| usage 字段名与前端假设不符（prompt_tokens vs input_tokens） | A1 展示 | 防御式读取（`prompt_tokens ?? input_tokens ?? input ?? 0`，CapturesTab formatBytes 同款模式）；i18n 文案不含字段名 |
| 行容器重构破坏既有交互 | A7 | 保留 `.captures-row` 类名与键盘语义（role=button + tabindex + enter/space），CapturesTab.test.ts 覆盖 |
| **zh.ts/en.ts 双重身份（H1）：既是 6 个不提交特效文件之一、又是本功能 i18n 修改目标** | A10/A12 | **主方案**：`git add -p` hunk 级暂存，仅挑选本功能键所在 hunks（特效 7 键 hunks 留工作区）。**后备**：特效键与新键同 hunk 无法拆分时，`git stash push -- <file>`（仅特效改动）→ 提交 i18n → `git stash pop` 恢复。**验收**：`git status` 工作区保留特效改动（含 zh.ts/en.ts 特效 hunks）；`git show --stat <commit>` 不含任何特效键；S5 做双口径核验 |
| 提交误含 examples/ 或特效文件改动 | A12 | S5 最后 `git add` 仅列白名单路径（含 zh.ts/en.ts 的 `git add -p`），`git status` + `git show --stat <commit>` 双口径复核 |
| trace 解析器对未知形态误判 | A4/A6 | 三态收敛 + 永不抛 + texts 降级 + 原始 JSON 折叠（用户永远可看到数据） |

---

## 13. Resume 关键设计事实（供实现阶段续接）

1. 端点 `POST /api/chat/direct`；bot_id 恒携带；debug_mode 恒 false；include_system_prompt 恒 true；消息仅单轮 `{role:'user'}`。**sec-M1**：500 且 `LLM_PROVIDER_ERROR:` 前缀 → `toApiError` 泛化文案（`playground.providerError`），detail 仅进日志；后端零改动。
2. Trace 解析器签名 `parseTraceSteps(input: unknown): {kind:'empty'|'texts'|'timeline', ...}`，永不抛；白名单 request/reasoning/tool_call/tool_result/response → other 兜底；**M1**：texts 分支带 `degraded?: boolean`（混合/异常形态为 true），`detailFallback` 判定 = `kind==='texts' && degraded`；降级 JSON 折叠纯文本插值禁 v-html（L4）。
3. 后端 store 新函数必须 `async` + `_lock` 持锁；DELETE 端点 404 detail 沿用 `"Capture not found."`，成功返回 `{"message": ...}`；main.py 不改；破坏面与既有认证模型同级，audit 日志/?confirm=1 为非阻断建议（L1）。
4. CapturesTab 行容器必须重构为 `div[role=button tabindex=0]`（现有 `<button>` 嵌套非法）+ enter/**space（LOW-15）**；Trace 区块标题用 `debugger.trace` 键替换 L197-203；usage 行复用 `formatBytes` + `captureUsage`。
5. PlaygroundCard 挂载于 ModelSettingsPage L482 后（`v-if="configsStore.config && draft"` 块内）；纯文本渲染禁 v-html；**H2 守卫**：`watch(botId) → pgSeq++ + clearChat()`（备选 `:key="botId"`）——sending 已拦截并发，守卫目标是「切换 Bot 后旧响应不写入新会话」；无 params prop（LOW-14）；hint 按 M2 定稿（基于已保存配置）；modelName 守卫为 draft 护栏。
6. TemplateEditor 插入：`getTextareaEl()` 统一取内部 textarea（**M4**：`textareaElRef?.value` 主方案 + `$el.querySelector('textarea')` 回退，失败返回 null）→ `updateValue` 全量 emit → `requestAnimationFrame` 内 focus + setSelectionRange(start+ph.length)。
7. i18n 新键共 **33**（playground 14 + debugger 18 + phInserted 1，LOW-10 对账基准）；appearance 特效 7 键与既有键零触碰；zh/en 对称（A10 键数 diff = 0）。
8. 测试基线 149 全绿；新增 ≈50 用例；后端集成测试需 `@pytest.mark.integration` + app_client/auth_headers fixture，**M3**：routes 用例内显式 `debug_capture_store._captures.clear()`（conftest 不清该模块全局）。
9. **提交策略（H1）**：`examples/` 与特效 4 文件（AppearanceSettingsPage.vue/theme.test.ts/theme.ts/global.css）不提交；zh.ts/en.ts 用 `git add -p` hunk 级暂存仅挑本功能键 hunks（同 hunk 时 stash 后备）；验收：`git status` 保留特效改动 + `git show --stat <commit>` 不含特效键。
