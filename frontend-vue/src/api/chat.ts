/**
 * Chat API — direct (stateless) LLM conversation used by the Playground.
 *
 * Backend contract (backend/app/routers/chat.py):
 *   POST /api/chat/direct → DirectChatResponse
 *
 * Playground contract (docs/full-implementation-design.md §2.3, D1):
 *   - messages: single-turn `[{ role: 'user', content }]`
 *   - include_system_prompt: 恒 true（注入该 Bot 已保存的 system_prompt）
 *   - debug_mode / debug_context / attachments: 本轮 UI 不暴露（后端契约已
 *     支持，Playground 恒走非 debug 路径；attachments 属后续增量）
 *   - bot_id: 恒携带——后端按该 Bot 的已保存配置读取 api_key 与推理参数，
 *     api_key 不出前端
 */

import { fetchWithAuth } from './client'

/** 单条对话消息（后端 DirectChatMessage 契约子集）。 */
export interface DirectChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

/** POST /api/chat/direct 请求体（Playground 暴露子集）。 */
export interface DirectChatRequest {
  messages: DirectChatMessage[]
  /** 是否注入已保存的 system_prompt（后端默认 true）。 */
  include_system_prompt?: boolean
  /** Bot ID——后端按该 Bot 的已保存配置读取 api_key / 推理参数。 */
  bot_id?: string
}

/** Token 用量（后端为 Dict[str, int]；字段名以实际响应为准，防御式读取）。 */
export interface DirectChatUsage {
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
}

/** POST /api/chat/direct 响应（后端 DirectChatResponse，字段宽松可选）。 */
export interface DirectChatResponse {
  success: boolean
  /** 后端已 encode_output（HTML 实体编码）。 */
  response: string
  usage?: DirectChatUsage | null
  provider?: string
  model?: string
  debug_mode?: boolean
  formatted_user_messages?: string[] | null
}

/** 直连对话：Playground 用当前 Bot 的已保存配置直连 LLM。 */
export async function sendDirectChat(
  payload: DirectChatRequest,
): Promise<DirectChatResponse> {
  return fetchWithAuth<DirectChatResponse>('/api/chat/direct', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
