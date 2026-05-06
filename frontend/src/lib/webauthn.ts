/**
 * WebAuthn browser helpers.
 *
 * Wraps @simplewebauthn/browser to add JSON↔ArrayBuffer conversion and
 * hits our Django endpoints for options / verify.
 */

import {
  startAuthentication,
  startRegistration,
  browserSupportsWebAuthn,
} from '@simplewebauthn/browser';
import { apiPost } from './api';

export const webauthnSupported = (): boolean => browserSupportsWebAuthn();

/**
 * Register a new passkey for the currently-logged-in user.
 * Returns the new credential record on success.
 */
export async function registerPasskey(nickname: string = ''): Promise<any> {
  // 1. Get options from server
  const options = await apiPost<any>('/passkeys/register/options/', {});
  // 2. Browser triggers OS-level biometric / device prompt
  const attResp = await startRegistration(options);
  // 3. Send result to server for verification
  return apiPost('/passkeys/register/verify/', {
    nickname,
    credential: attResp,
  });
}

/**
 * Authenticate – prove identity using an existing passkey.
 * `username` must be supplied (this can be unauthenticated).
 */
export async function authenticatePasskey(username: string): Promise<{
  matched: boolean;
  user_id?: number;
  username?: string;
}> {
  const options = await apiPost<any>(
    '/passkeys/auth/options/',
    { username },
    { skipAuth: true },
  );
  const assertion = await startAuthentication(options);
  return apiPost(
    '/passkeys/auth/verify/',
    { username, credential: assertion },
    { skipAuth: true },
  );
}

/**
 * Phone-side: redeem a pickup token using a passkey.
 */
export async function authorizePickup(
  token: string,
  username: string,
): Promise<{ status: string; detail?: string }> {
  const options = await apiPost<any>(
    '/passkeys/auth/options/',
    { username },
    { skipAuth: true },
  );
  const assertion = await startAuthentication(options);
  return apiPost(
    `/passkeys/pickup-tokens/${token}/authorize/`,
    { username, credential: assertion },
    { skipAuth: true },
  );
}
