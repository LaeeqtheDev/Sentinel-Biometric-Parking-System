/**
 * Tiny typed fetch wrapper around the Django backend.
 *
 * Handles:
 *   - Attaching the JWT access token from localStorage
 *   - Auto-refreshing once when a request returns 401
 *   - Tossing the user back to /login if refresh also fails
 */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

const ACCESS_KEY = 'sentinel_access';
const REFRESH_KEY = 'sentinel_refresh';

export const tokenStore = {
  getAccess: () =>
    typeof window !== 'undefined' ? localStorage.getItem(ACCESS_KEY) : null,
  getRefresh: () =>
    typeof window !== 'undefined' ? localStorage.getItem(REFRESH_KEY) : null,
  set: (access: string, refresh?: string) => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(message: string, status: number, data: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

// Single-flight refresh: when several requests hit 401 at once they share
// one refresh call. The backend rotates refresh tokens and blacklists the
// old one, so parallel refreshes would otherwise log the user out.
let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccess(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  const refresh = tokenStore.getRefresh();
  if (!refresh) return null;
  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_URL}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      tokenStore.set(data.access, data.refresh); // refresh is rotated
      return data.access as string;
    } catch {
      return null;
    } finally {
      setTimeout(() => (refreshInFlight = null), 0);
    }
  })();
  return refreshInFlight;
}

interface ApiOptions extends Omit<RequestInit, 'body'> {
  body?: any;
  isFormData?: boolean;
  skipAuth?: boolean;
  /**
   * Retries on network errors / 502-504. Default: 2 for GET/HEAD, 0 for
   * everything else. Gate actions (POST) must never be silently replayed:
   * a retried verify-exit could act twice.
   */
  retries?: number;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function api<T = any>(
  path: string,
  opts: ApiOptions = {},
): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_URL}${path}`;
  const method = (opts.method || 'GET').toUpperCase();
  const idempotent = method === 'GET' || method === 'HEAD';
  const {
    body,
    isFormData,
    skipAuth,
    headers,
    retries = idempotent ? 2 : 0,
    ...rest
  } = opts;

  const buildHeaders = (token: string | null): HeadersInit => {
    const h: Record<string, string> = { ...((headers as any) || {}) };
    if (!isFormData && body !== undefined) {
      h['Content-Type'] = 'application/json';
    }
    if (token && !skipAuth) {
      h['Authorization'] = `Bearer ${token}`;
    }
    return h;
  };

  const doFetch = async (token: string | null) =>
    fetch(url, {
      ...rest,
      headers: buildHeaders(token),
      body: isFormData
        ? (body as FormData)
        : body !== undefined
          ? JSON.stringify(body)
          : undefined,
    });

  let token = tokenStore.getAccess();
  let response: Response;
  let attempt = 0;
  // Network or 5xx errors get retried with exponential backoff.
  while (true) {
    try {
      response = await doFetch(token);
    } catch (networkErr) {
      if (attempt < retries) {
        await sleep(300 * Math.pow(2, attempt));
        attempt++;
        continue;
      }
      throw new ApiError(
        'Network error: could not reach the server.',
        0,
        null,
      );
    }
    // Retry transient gateway failures only (not 500: that is a real bug
    // and replaying it just repeats the side effect).
    if ([502, 503, 504].includes(response.status) && attempt < retries) {
      await sleep(300 * Math.pow(2, attempt));
      attempt++;
      continue;
    }
    break;
  }

  // Auto-refresh once on 401
  if (response.status === 401 && !skipAuth) {
    const fresh = await refreshAccess();
    if (fresh) {
      response = await doFetch(fresh);
    } else {
      tokenStore.clear();
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
  }

  let data: any = null;
  const ct = response.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    data = await response.json().catch(() => null);
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const firstFieldError =
      data && typeof data === 'object' && !data.detail
        ? Object.values(data).flat().find((v) => typeof v === 'string')
        : null;
    const msg =
      response.status === 429
        ? 'Too many attempts. Please wait a moment and try again.'
        : (data && (data.detail || data.message)) ||
          (firstFieldError as string) ||
          `Request failed (${response.status})`;
    throw new ApiError(msg, response.status, data);
  }

  return data as T;
}

// Convenience HTTP verbs
export const apiGet = <T = any>(p: string, o: ApiOptions = {}) =>
  api<T>(p, { ...o, method: 'GET' });
export const apiPost = <T = any>(p: string, body?: any, o: ApiOptions = {}) =>
  api<T>(p, { ...o, method: 'POST', body });
export const apiPut = <T = any>(p: string, body?: any, o: ApiOptions = {}) =>
  api<T>(p, { ...o, method: 'PUT', body });
export const apiPatch = <T = any>(p: string, body?: any, o: ApiOptions = {}) =>
  api<T>(p, { ...o, method: 'PATCH', body });
export const apiDelete = <T = any>(p: string, o: ApiOptions = {}) =>
  api<T>(p, { ...o, method: 'DELETE' });
