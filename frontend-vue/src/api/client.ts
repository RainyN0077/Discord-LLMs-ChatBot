/**
 * API client — auth key bootstrap + fetch wrapper with unified errors.
 *
 * Flow:
 *   1. The API secret key is stored in sessionStorage under `_ak` (btoa/atob
 *      encoded, degraded gracefully if btoa/atob are unavailable).
 *   2. Without a key, `GET /api/auth/status` is called to obtain
 *      `api_secret_key` (localhost only), then stored.
 *   3. Requests are sent with the `X-API-Key` header.
 *   4. On 401/403 without `_noRetry`: the stored key is cleared, the key is
 *      re-fetched from `/api/auth/status`, and the request is retried once.
 *   5. If it still fails, an `AuthError` is thrown.
 *   All errors are normalized to `{ status, message }`.
 */

const KEY_STORAGE = '_ak'
const AUTH_STATUS_URL = '/api/auth/status'

/**
 * sec-M1: the backend signals LLM provider failures with a 500 whose detail
 * starts with `LLM_PROVIDER_ERROR:` (backend/app/llm_providers/base.py). The
 * raw detail may embed provider internals (model names, quotas, raw SDK
 * errors), so toApiError replaces it with this generic message — the detail
 * is kept for the logs only, never rendered to the user. The user-facing
 * i18n text lives in the UI layer (playground.providerError), not here.
 */
const LLM_PROVIDER_ERROR_PREFIX = 'LLM_PROVIDER_ERROR:'

/**
 * 泛化文案的统一前缀（qa LOW-4）——PlaygroundCard 复用它识别 provider
 * 错误，避免「client.ts 泛化文案」与「UI 层判定前缀」两处独立字符串漂移。
 */
export const PROVIDER_ERROR_PREFIX = 'LLM provider error'
const LLM_PROVIDER_ERROR_MESSAGE = `${PROVIDER_ERROR_PREFIX}. Check backend logs.`

export class AuthError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'AuthError'
    this.status = status
  }
}

export interface ApiErrorBody {
  status?: number
  message?: string
}

/** Encode the key for sessionStorage with safe fallbacks. */
function encodeKey(raw: string): string {
  try {
    return btoa(unescape(encodeURIComponent(raw)))
  } catch {
    return `raw:${raw}`
  }
}

/** Decode the key stored in sessionStorage with safe fallbacks. */
function decodeKey(stored: string): string {
  if (stored.startsWith('raw:')) return stored.slice(4)
  try {
    return decodeURIComponent(escape(atob(stored)))
  } catch {
    return stored
  }
}

/** Read the current API key from sessionStorage, or null. */
export function getStoredApiKey(): string | null {
  const raw = sessionStorage.getItem(KEY_STORAGE)
  return raw ? decodeKey(raw) : null
}

/** Persist the API key into sessionStorage. */
export function storeApiKey(key: string): void {
  try {
    sessionStorage.setItem(KEY_STORAGE, encodeKey(key))
  } catch {
    // Storage unavailable (private mode etc.) — the key simply won't persist.
  }
}

/** Clear the stored API key. */
export function clearApiKey(): void {
  try {
    sessionStorage.removeItem(KEY_STORAGE)
  } catch {
    // ignore
  }
}

/**
 * M2: a stalled auth bootstrap must never hang the first-frame loader
 * forever — every `/api/auth/status` request is time-bounded (10s). Regular
 * API requests keep the previous no-timeout behavior.
 * AbortSignal.timeout() is avoided for old-browser compatibility; a manual
 * AbortController + setTimeout behaves identically everywhere.
 */
const AUTH_STATUS_TIMEOUT_MS = 10_000

/** fetch with a hard abort timeout; aborts surface as an Error (not the
 *  raw AbortError DOMException) so callers see a readable message. */
async function fetchWithAuthTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(url, { ...init, signal: controller.signal })
  } catch (err) {
    if (controller.signal.aborted) {
      throw new Error(`Auth request timed out after ${timeoutMs}ms`)
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

/** Fetch the API secret key via the unauthenticated auth/status endpoint. */
async function fetchApiKey(): Promise<string | null> {
  try {
    const res = await fetchWithAuthTimeout(
      AUTH_STATUS_URL,
      {},
      AUTH_STATUS_TIMEOUT_MS,
    )
    if (!res.ok) return null
    const body = (await res.json().catch(() => ({}))) as { api_secret_key?: string }
    return body.api_secret_key || null
  } catch {
    // Network error / backend offline / timeout — normalized to null (see
    // module doc); the request then proceeds keyless and follows the
    // normal 401/403 fail path.
    return null
  }
}

/**
 * Extract a readable message from a FastAPI validation error item.
 * Pydantic v2 emits `detail` as an array like:
 *   [{ type: 'string_too_short', loc: ['body', 'api_key'], msg: '...', input: '...' }]
 */
function detailMessage(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg: unknown }).msg)
        }
        return null
      })
      .filter((m): m is string => m !== null)
    if (msgs.length > 0) return msgs.join('; ')
  }
  return null
}

/** Parse an error response body into a unified { status, message }. */
export async function toApiError(res: Response): Promise<ApiErrorBody> {
  let message = res.statusText || `HTTP ${res.status}`
  try {
    const body = await res.json()
    if (body?.detail !== undefined) {
      const dm = detailMessage(body.detail)
      if (dm) message = dm
    } else if (typeof body?.message === 'string') message = body.message
    else if (typeof body?.error === 'string') message = body.error
  } catch {
    const text = await res.text().catch(() => '')
    if (text) message = text.slice(0, 500)
  }
  // sec-M1: 500 errors carrying the provider-error prefix are surfaced as a
  // generic message; the original detail goes to console.error only —
  // truncated to 500 chars (perf LOW-3 / qa LOW-1: the raw detail can embed
  // long SDK error bodies and must not flood the console unbounded).
  if (res.status === 500 && message.startsWith(LLM_PROVIDER_ERROR_PREFIX)) {
    console.error(`LLM provider error detail: ${message.slice(0, 500)}`)
    message = LLM_PROVIDER_ERROR_MESSAGE
  }
  return { status: res.status, message }
}

export interface RequestOptions extends RequestInit {
  /** Skip the 401/403 retry-and-reauth flow (used by the retry itself). */
  _noRetry?: boolean
}

/**
 * Perform an authenticated fetch against the backend API.
 *
 * @param path - API path starting with `/api/...`
 * @param options - fetch options; `_noRetry` suppresses the reauth retry
 * @returns parsed JSON body
 * @throws AuthError when authentication fails after reauth
 * @throws Error with `{ status, message }` for other failures
 */
export async function fetchWithAuth<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { _noRetry, ...init } = options
  const headers = new Headers(init.headers)

  let apiKey = getStoredApiKey()
  if (!apiKey) {
    apiKey = await fetchApiKey()
    if (apiKey) storeApiKey(apiKey)
  }

  const doRequest = async (key: string | null): Promise<Response> => {
    if (key) headers.set('X-API-Key', key)
    else headers.delete('X-API-Key')
    if (init.body && typeof init.body === 'string') {
      headers.set('Content-Type', 'application/json')
    }
    const requestInit = { ...init, headers }
    // M2: the auth/status requests are time-bounded (both the internal
    // fetchApiKey and the explicit one from authStore.init); every other
    // API request keeps the previous no-timeout behavior.
    return path === AUTH_STATUS_URL
      ? fetchWithAuthTimeout(path, requestInit, AUTH_STATUS_TIMEOUT_MS)
      : fetch(path, requestInit)
  }

  let res = await doRequest(apiKey)

  if ((res.status === 401 || res.status === 403) && !_noRetry) {
    // Re-auth: clear the stale key, refetch, retry exactly once.
    clearApiKey()
    const freshKey = await fetchApiKey()
    if (freshKey) storeApiKey(freshKey)
    res = await doRequest(freshKey)
    if (res.status === 401 || res.status === 403) {
      clearApiKey()
      throw new AuthError(
        res.status,
        (await toApiError(res)).message || 'Authentication failed',
      )
    }
  }

  if (!res.ok) {
    const err = await toApiError(res)
    throw Object.assign(new Error(err.message || `HTTP ${res.status}`), {
      status: err.status ?? res.status,
    })
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
