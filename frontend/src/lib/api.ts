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

async function refreshAccess(): Promise<string | null> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) return null;
  try {
    const res = await fetch(`${API_URL}/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    tokenStore.set(data.access);
    return data.access;
  } catch {
    return null;
  }
}

interface ApiOptions extends Omit<RequestInit, 'body'> {
  body?: any;
  isFormData?: boolean;
  skipAuth?: boolean;
}

export async function api<T = any>(
  path: string,
  opts: ApiOptions = {},
): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_URL}${path}`;
  const { body, isFormData, skipAuth, headers, ...rest } = opts;

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
  let response = await doFetch(token);

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
    const msg =
      (data && (data.detail || data.message)) ||
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
