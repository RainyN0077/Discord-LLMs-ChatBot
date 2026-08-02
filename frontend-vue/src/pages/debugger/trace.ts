/**
 * Trace step parser — debug capture detail 的中间阶段解析器（三态降级）。
 *
 * 真实后端契约（DebugCaptureDetail.intermediate_llm_responses）恒为 string[]
 * （pipeline 经 `_safe_str_list` 输出）；演示页自定对象契约（{stage,...}）
 * 作为前瞻兼容扩展。纯函数、永不抛异常——所有输入形态收敛到三态之一。
 * 详见 docs/full-implementation-design.md §3。
 */

/** 时间线阶段白名单；未知 stage 归 'other'（§3.1）。 */
export type TraceStage =
  | 'request'
  | 'reasoning'
  | 'tool_call'
  | 'tool_result'
  | 'response'
  | 'other'

export interface TraceNode {
  stage: TraceStage
  /** 通用展示标签（可选）。 */
  label?: string
  /** tool_call 的工具名 / 节点名。 */
  name?: string
  /** 节点正文（reasoning 折叠 / response 内容）。 */
  content?: string
  /** tool_call 的参数摘要（演示页 meta 行）。 */
  args?: string
  /** 原始 stage 名——'other' 时用于展示。 */
  raw?: string
}

export type TraceParseResult =
  | { kind: 'empty' }
  | { kind: 'texts'; items: string[]; degraded?: boolean }
  | { kind: 'timeline'; items: TraceNode[] }

const STAGE_WHITELIST: readonly string[] = [
  'request',
  'reasoning',
  'tool_call',
  'tool_result',
  'response',
]

/**
 * Record 判定（§3.2）：typeof === 'object' && !== null && !Array.isArray。
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** 字符串兜底：非字符串 / 缺失 → ''（§3.2「字段缺失以 '' 兜底」）。 */
function toStr(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

/**
 * 安全字符串化（降级分支用，永不抛）：
 * - Symbol：经 toString() 显式转换（裸 Symbol 的 String() 不抛，但 String(含
 *   Symbol 的数组) 会因 join 隐式 ToString 抛 TypeError）；
 * - 数组：递归安全字符串化（避免隐式 ToString 链）；
 * - 其余：try/catch 兜底（自定义 toString 抛异常的对象 → '[object Object]'）。
 */
function safeString(value: unknown): string {
  if (typeof value === 'symbol') {
    try {
      return value.toString()
    } catch {
      return value.description ?? ''
    }
  }
  if (Array.isArray(value)) {
    return value.map(safeString).join(',')
  }
  try {
    return String(value)
  } catch {
    return '[object Object]'
  }
}

/** 单节点解析：stage 白名单映射、未知归 'other' 并保留 raw。 */
function parseTimelineNode(item: Record<string, unknown>): TraceNode {
  const rawStage = toStr(item.stage)
  const stage: TraceStage = STAGE_WHITELIST.includes(rawStage)
    ? (rawStage as TraceStage)
    : 'other'
  const node: TraceNode = {
    stage,
    label: toStr(item.label),
    name: toStr(item.name),
    content: toStr(item.content),
    args: toStr(item.args),
  }
  // 未知阶段保留原始 stage 名供展示（白名单节点无需）。
  if (stage === 'other' && rawStage) node.raw = rawStage
  return node
}

/**
 * 解析 intermediate_llm_responses 为三态结果（永不抛异常）。
 *
 * - 非数组 / null / undefined / [] → {kind:'empty'}
 * - 全 string（真实数据形态）→ {kind:'texts'}（过滤空串；过滤后为空回退
 *   empty；degraded 缺省 false）
 * - 全对象且每项 `stage` 为 string（前瞻契约）→ {kind:'timeline'}；stage
 *   不在白名单 → 'other' 并保留 raw；字段缺失以 '' 兜底
 * - 混合数组 / 元素类型异常（含 null）→ 整体降级 {kind:'texts',
 *   degraded:true}，元素经 String() 兜底（永不抛）
 */
export function parseTraceSteps(input: unknown): TraceParseResult {
  // perf LOW-3: 输入规模护栏——超过 500 项只处理前 500 项（当前后端契约
  // 不会触发，但成本极低；防止极端/异常负载下解析与渲染开销失控）。
  if (Array.isArray(input) && input.length > 500) {
    input = input.slice(0, 500)
  }

  if (!Array.isArray(input) || input.length === 0) {
    return { kind: 'empty' }
  }

  const allStrings = input.every((item) => typeof item === 'string')
  if (allStrings) {
    const items = input.filter((item) => item !== '')
    if (items.length === 0) return { kind: 'empty' }
    return { kind: 'texts', items }
  }

  const records = input as Array<Record<string, unknown>>
  const allTimelineNodes =
    records.every(isRecord) &&
    records.every((item) => typeof item.stage === 'string')
  if (allTimelineNodes) {
    return { kind: 'timeline', items: records.map(parseTimelineNode) }
  }

  // 混合 / 异常形态：整体降级为文本列表，safeString 兜底——用户永远可看到数据。
  return {
    kind: 'texts',
    items: records.map((item) => safeString(item)),
    degraded: true,
  }
}
