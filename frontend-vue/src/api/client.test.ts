/**
 * Unit tests for the API client (src/api/client.ts).
 *
 * Covers the module-level fetch wrapper: `_ak` sessionStorage token
 * read/write, key bootstrap via /api/auth/status, the 401/403 re-auth
 * retry, unified error normalization and network-error propagation.
 * All assertions follow the actual implementation in client.ts.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  AuthError,
  clearApiKey,
  fetchWithAuth,
  getStoredApiKey,
  storeApiKey,
  toApiError,
  type ApiErrorBody,
} from '@/api/client'

const AUTH_STATUS_URL = '/api/auth/status'
const KEY_STORAGE = '_ak'

/** Await a rejected promise and normalize it to the unified error shape. */
async function captureError(promise: Promise<unknown>): Promise<ApiErrorBody & Error> {
  try {
    await promise
  } catch (err) {
    return err as ApiErrorBody & Error
  }
  throw new Error('expected the promise to reject')
}

/** Build a minimal Response-like object (jsdom-independent). */
function makeRes(
  body: unknown,
  status = 200,
  statusText = 'OK',
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: async () => body,
    text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
    headers: new Headers(),
  } as unknown as Response
}

/** Stub global fetch with an ordered queue of responses; returns the mock. */
function stubFetchWith(responses: Response[] | Error): ReturnType<typeof vi.fn> {
  const fn = vi.fn()
  if (responses instanceof Error) {
    fn.mockRejectedValue(responses)
  } else {
    responses.forEach((r) => fn.mockResolvedValueOnce(r))
  }
  vi.stubGlobal('fetch', fn)
  return fn
}

describe('api key storage (_ak in sessionStorage)', () => {
  it('stores and reads back a key (base64 roundtrip)', () => {
    storeApiKey('secret-key-123')
    expect(getStoredApiKey()).toBe('secret-key-123')
    // The raw key is never stored in plain text.
    expect(sessionStorage.getItem(KEY_STORAGE)).not.toBe('secret-key-123')
  })

  it('roundtrips non-ASCII keys via the encode/decode pair', () => {
    storeApiKey('密钥/äöü+=/')
    expect(getStoredApiKey()).toBe('密钥/äöü+=/')
  })

  it('returns null when nothing is stored', () => {
    expect(getStoredApiKey()).toBeNull()
  })

  it('clears the stored key', () => {
    storeApiKey('abc')
    clearApiKey()
    expect(getStoredApiKey()).toBeNull()
    expect(sessionStorage.getItem(KEY_STORAGE)).toBeNull()
  })
})

describe('fetchWithAuth — bootstrap & success path', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  afterEach(() => {
    clearApiKey()
  })

  it('bootstraps the key from /api/auth/status when none is stored, then sends it', async () => {
    const fetchMock = stubFetchWith([
      makeRes({ api_secret_key: 'bootstrapped-key' }),
      makeRes({ ok: true }),
    ])

    const result = await fetchWithAuth<{ ok: boolean }>('/api/test')

    expect(result).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0][0]).toBe(AUTH_STATUS_URL)
    expect(fetchMock.mock.calls[1][0]).toBe('/api/test')
    // Header check: the bootstrapped key must be attached.
    const headers = fetchMock.mock.calls[1][1].headers as Headers
    expect(headers.get('X-API-Key')).toBe('bootstrapped-key')
    // The key is persisted for subsequent calls.
    expect(getStoredApiKey()).toBe('bootstrapped-key')
  })

  it('uses the stored key without hitting the auth endpoint', async () => {
    storeApiKey('stored-key')
    const fetchMock = stubFetchWith([makeRes({ ok: true })])

    await fetchWithAuth('/api/test')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/test')
    const headers = fetchMock.mock.calls[0][1].headers as Headers
    expect(headers.get('X-API-Key')).toBe('stored-key')
  })

  it('sets Content-Type for string bodies (POST)', async () => {
    storeApiKey('k')
    const fetchMock = stubFetchWith([makeRes({ ok: true })])

    await fetchWithAuth('/api/test', { method: 'POST', body: '{"a":1}' })

    const headers = fetchMock.mock.calls[0][1].headers as Headers
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('returns undefined for 204 No Content', async () => {
    storeApiKey('k')
    stubFetchWith([makeRes(null, 204, 'No Content')])

    await expect(fetchWithAuth('/api/delete', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('continues without a key when the bootstrap endpoint fails', async () => {
    const fetchMock = stubFetchWith([
      makeRes({}, 500, 'Internal Server Error'),
      makeRes({ ok: true }),
    ])

    const result = await fetchWithAuth<{ ok: boolean }>('/api/test')

    expect(result).toEqual({ ok: true })
    const headers = fetchMock.mock.calls[1][1].headers as Headers
    expect(headers.get('X-API-Key')).toBeNull()
    expect(getStoredApiKey()).toBeNull()
  })
})

describe('fetchWithAuth — 401/403 retry & re-auth', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('clears the stale key, refetches and retries exactly once on 401', async () => {
    storeApiKey('stale-key')
    const fetchMock = stubFetchWith([
      makeRes({ detail: 'Unauthorized' }, 401, 'Unauthorized'),
      makeRes({ api_secret_key: 'fresh-key' }),
      makeRes({ ok: true }),
    ])

    const result = await fetchWithAuth<{ ok: boolean }>('/api/private')

    expect(result).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    // The retried request must carry the fresh key.
    const retryHeaders = fetchMock.mock.calls[2][1].headers as Headers
    expect(retryHeaders.get('X-API-Key')).toBe('fresh-key')
    expect(getStoredApiKey()).toBe('fresh-key')
  })

  it('throws AuthError and clears the key when the retry still fails with 401', async () => {
    storeApiKey('stale-key')
    const fetchMock = stubFetchWith([
      makeRes({ detail: 'Unauthorized' }, 401, 'Unauthorized'),
      makeRes({ api_secret_key: 'fresh-key' }),
      makeRes({ detail: 'Unauthorized' }, 401, 'Unauthorized'),
    ])

    const attempt = fetchWithAuth('/api/private')
    await expect(attempt).rejects.toBeInstanceOf(AuthError)
    await expect(attempt).rejects.toMatchObject({
      name: 'AuthError',
      status: 401,
      message: 'Unauthorized',
    })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    // Stale and fresh keys are both gone.
    expect(getStoredApiKey()).toBeNull()
  })

  it('throws AuthError for 403 on the retry as well', async () => {
    storeApiKey('stale-key')
    stubFetchWith([
      makeRes({ error: 'Forbidden' }, 403, 'Forbidden'),
      makeRes({ api_secret_key: 'fresh-key' }),
      makeRes({ error: 'Still forbidden' }, 403, 'Forbidden'),
    ])

    await expect(fetchWithAuth('/api/private')).rejects.toMatchObject({
      name: 'AuthError',
      status: 403,
      message: 'Still forbidden',
    })
  })

  it('skips the re-auth retry when _noRetry is set', async () => {
    storeApiKey('stale-key')
    const fetchMock = stubFetchWith([makeRes({ detail: 'Unauthorized' }, 401, 'Unauthorized')])

    const attempt = fetchWithAuth('/api/private', { _noRetry: true })
    // Plain Error (not AuthError), no second request, key untouched.
    await expect(attempt).rejects.toMatchObject({ status: 401 })
    await expect(attempt).rejects.not.toBeInstanceOf(AuthError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(getStoredApiKey()).toBe('stale-key')
  })
})

describe('fetchWithAuth — error normalization', () => {
  beforeEach(() => {
    storeApiKey('k')
  })

  afterEach(() => {
    clearApiKey()
  })

  it('normalizes a 403 {error} body into a unified {status, message} error', async () => {
    stubFetchWith([makeRes({ error: 'Forbidden resource' }, 403, 'Forbidden')])

    // _noRetry keeps the test on the direct error path (403 would otherwise
    // trigger the re-auth retry, which is covered by the tests above).
    const err = await captureError(fetchWithAuth('/api/x', { _noRetry: true }))
    expect(err.message).toBe('Forbidden resource')
    expect(err.status).toBe(403)
  })

  it('normalizes a 403 {error} body on the retry path after re-auth', async () => {
    storeApiKey('stale-key')
    stubFetchWith([
      makeRes({ error: 'Forbidden resource' }, 403, 'Forbidden'),
      makeRes({ api_secret_key: 'fresh-key' }),
      makeRes({ error: 'Still forbidden' }, 500, 'Internal Server Error'),
    ])

    const err = await captureError(fetchWithAuth('/api/x'))
    // The retried request returned 500: normalized from the {error} body.
    expect(err.message).toBe('Still forbidden')
    expect(err.status).toBe(500)
    expect(getStoredApiKey()).toBe('fresh-key')
  })

  it('prefers detail (string) over error when both are present', async () => {
    stubFetchWith([makeRes({ detail: 'Rate limited', error: 'nope' }, 429, 'Too Many Requests')])

    const err = await captureError(fetchWithAuth('/api/x'))
    expect(err.message).toBe('Rate limited')
    expect(err.status).toBe(429)
  })

  it('flattens Pydantic v2 validation arrays into a joined message', async () => {
    stubFetchWith([
      makeRes(
        {
          detail: [
            { type: 'string_too_short', loc: ['body', 'api_key'], msg: 'too short' },
            { type: 'extra_forbidden', loc: ['body'], msg: 'unexpected field' },
          ],
        },
        422,
        'Unprocessable Entity',
      ),
    ])

    const err = await captureError(fetchWithAuth('/api/x'))
    expect(err.message).toBe('too short; unexpected field')
    expect(err.status).toBe(422)
  })

  it('falls back to the response text for non-JSON error bodies', async () => {
    const fn = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => {
        throw new SyntaxError('Unexpected token')
      },
      text: async () => 'boom: backend exploded',
      headers: new Headers(),
    } as unknown as Response)
    vi.stubGlobal('fetch', fn)

    const err = await captureError(fetchWithAuth('/api/x'))
    expect(err.message).toBe('boom: backend exploded')
    expect(err.status).toBe(500)
  })

  it('propagates network errors as-is (no normalization)', async () => {
    stubFetchWith(new TypeError('Failed to fetch'))

    await expect(fetchWithAuth('/api/x')).rejects.toThrow(TypeError)
  })

  it('propagates network errors even without a stored key', async () => {
    clearApiKey()
    stubFetchWith(new TypeError('network down'))

    await expect(fetchWithAuth('/api/x')).rejects.toThrow(TypeError)
  })
})

describe('toApiError — direct extraction', () => {
  it('extracts message from a {detail: string} body', async () => {
    const body = await toApiError(makeRes({ detail: 'bad request' }, 400))
    expect(body).toEqual({ status: 400, message: 'bad request' })
  })

  it('extracts message from a {message: string} body', async () => {
    const body = await toApiError(makeRes({ message: 'whoops' }, 400))
    expect(body).toEqual({ status: 400, message: 'whoops' })
  })

  it('extracts message from a {error: string} body', async () => {
    const body = await toApiError(makeRes({ error: 'nope' }, 400))
    expect(body).toEqual({ status: 400, message: 'nope' })
  })

  it('falls back to statusText when the body is empty', async () => {
    const body = await toApiError(makeRes({}, 500, 'Server Error'))
    expect(body).toEqual({ status: 500, message: 'Server Error' })
  })
})
