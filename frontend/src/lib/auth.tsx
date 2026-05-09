'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import { useRouter } from 'next/navigation';
import { apiGet, apiPost, tokenStore } from './api';

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  cnic: string;
  role: 'ADMIN' | 'DRIVER';
  trust_level?: 'TRUSTED' | 'NORMAL' | 'SUSPICIOUS';
  trust_score?: number;
  is_active: boolean;
  has_biometric: boolean;
  driving_license_doc?: string | null;
  cnic_doc?: string | null;
  documents_verified?: boolean;
  last_activity_at?: string | null;
  created_at: string;
}

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refresh = useCallback(async () => {
    if (!tokenStore.getAccess()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await apiGet<User>('/auth/me/');
      setUser(me);
    } catch {
      setUser(null);
      tokenStore.clear();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = async (username: string, password: string) => {
    const res = await apiPost<{ access: string; refresh: string; user: User }>(
      '/auth/login/',
      { username, password },
      { skipAuth: true },
    );
    tokenStore.set(res.access, res.refresh);
    setUser(res.user);
  };

  const logout = () => {
    tokenStore.clear();
    setUser(null);
    router.push('/login');
  };

  return (
    <Ctx.Provider value={{ user, loading, login, logout, refresh }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
