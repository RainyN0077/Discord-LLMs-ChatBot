/**
 * User Options scope helpers (legacy parity with the old UserOptions.svelte).
 */

/** Global scope maps to '*'; everything else is '{scopeType}:{scopeId}'. */
export function makeKey(scopeType: string, scopeId?: string | null): string {
  if (scopeType === 'global' || !scopeId) return '*'
  return `${scopeType}:${scopeId}`
}
