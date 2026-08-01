/**
 * Models API — fetch available model lists and run connection tests.
 *
 * Backend contract (backend/app/routers/models_test.py):
 *   POST /api/models/list → { models: string[] }   (AvailableModelsRequest)
 *   POST /api/models/test → { success, response?, error?, model_info? }
 *                          (ModelTestRequest; task-specific extra fields)
 */

import { fetchWithAuth } from './client'

export type ModelTask = 'chat' | 'ocr' | 'embedding' | 'rerank'

export interface ModelListResponse {
  models: string[]
}

export interface ModelTestResponse {
  success: boolean
  response?: string
  error?: string
  model_info?: {
    id?: string
    usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number }
  }
}

/** List models for a provider (task filters chat/embedding/ocr lists). */
export async function fetchModelList(
  provider: string,
  apiKey: string,
  baseUrl: string | null,
  task: ModelTask = 'chat',
): Promise<ModelListResponse> {
  return fetchWithAuth<ModelListResponse>('/api/models/list', {
    method: 'POST',
    body: JSON.stringify({ provider, api_key: apiKey, base_url: baseUrl, task }),
  })
}

/**
 * Test a model connection.
 *
 * @param extra - task-specific fields, e.g. `{ ocr_timeout_seconds,
 *   ocr_timeout_disabled }` for the ocr task.
 */
export async function testModel(
  provider: string,
  apiKey: string,
  baseUrl: string | null,
  modelName: string,
  task: ModelTask = 'chat',
  extra: Record<string, unknown> = {},
): Promise<ModelTestResponse> {
  return fetchWithAuth<ModelTestResponse>('/api/models/test', {
    method: 'POST',
    body: JSON.stringify({
      provider,
      api_key: apiKey,
      base_url: baseUrl,
      model_name: modelName,
      task,
      ...extra,
    }),
  })
}
