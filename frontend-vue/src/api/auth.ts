/**
 * Auth API — backend authentication status.
 */

import { fetchWithAuth } from './client'

export interface AuthStatus {
  authenticated: boolean
  api_secret_key: string
}

/** Fetch the unauthenticated auth/status payload. */
export async function getAuthStatus(): Promise<AuthStatus> {
  return fetchWithAuth<AuthStatus>('/api/auth/status')
}
