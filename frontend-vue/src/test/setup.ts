/**
 * Vitest global setup — jsdom environment shims + per-test state cleanup.
 *
 * jsdom does not implement ResizeObserver or matchMedia, both of which are
 * used by naive-ui components (and can be touched transitively when store
 * modules are imported). The mocks below keep imports side-effect free.
 *
 * sessionStorage is cleared after every test (per the B4 Wave 1-Y spec);
 * localStorage is cleared as well so stores that persist settings
 * (theme/logs) cannot leak state between tests.
 */

import { afterEach, vi } from 'vitest'

class ResizeObserverMock {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver
}

if (typeof window.matchMedia === 'undefined') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string): MediaQueryList =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList,
  })
}

/** In-memory Storage shim (see note below). */
function createMemoryStorage(): Storage {
  const store = new Map<string, string>()
  return {
    get length(): number {
      return store.size
    },
    clear(): void {
      store.clear()
    },
    getItem(key: string): string | null {
      return store.has(key) ? (store.get(key) as string) : null
    },
    key(index: number): string | null {
      return Array.from(store.keys())[index] ?? null
    },
    removeItem(key: string): void {
      store.delete(key)
    },
    setItem(key: string, value: string): void {
      store.set(key, String(value))
    },
  } as Storage
}

// jsdom 29 + Node ≥22.5: window.localStorage/sessionStorage are backed by
// Node's experimental webstorage, which warns on every getter access when no
// `--localstorage-file` path is set (and exposes a broken localStorage API).
// Overriding both unconditionally avoids touching those getters and gives
// tests a stable in-memory Storage implementation.
Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: createMemoryStorage(),
})
Object.defineProperty(window, 'sessionStorage', {
  configurable: true,
  value: createMemoryStorage(),
})

afterEach(() => {
  vi.unstubAllGlobals()
  sessionStorage.clear()
  localStorage.clear()
})
