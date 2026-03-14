/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useState } from 'react';
import { GHOSTFOLIO_API_URL_STORAGE_KEY, GHOSTFOLIO_TOKEN_STORAGE_KEY } from '../api/client';

interface GhostfolioTokenContextValue {
  token: string | null;
  isConnected: boolean;
  setToken: (token: string) => void;
  clearToken: () => void;
  apiUrl: string;
  setApiUrl: (url: string) => void;
}

const GhostfolioTokenContext = createContext<GhostfolioTokenContextValue | null>(null);

function readStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(GHOSTFOLIO_TOKEN_STORAGE_KEY);
}

function readStoredApiUrl(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(GHOSTFOLIO_API_URL_STORAGE_KEY) ?? '';
}

export function GhostfolioTokenProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(readStoredToken);
  const [apiUrl, setApiUrlState] = useState<string>(readStoredApiUrl);

  const setToken = useCallback((value: string) => {
    const t = value.trim();
    if (t) {
      localStorage.setItem(GHOSTFOLIO_TOKEN_STORAGE_KEY, t);
      setTokenState(t);
    }
  }, []);

  const clearToken = useCallback(() => {
    localStorage.removeItem(GHOSTFOLIO_TOKEN_STORAGE_KEY);
    setTokenState(null);
  }, []);

  const setApiUrl = useCallback((value: string) => {
    const u = value.trim();
    setApiUrlState(value);
    if (u) {
      localStorage.setItem(GHOSTFOLIO_API_URL_STORAGE_KEY, u);
    } else {
      localStorage.removeItem(GHOSTFOLIO_API_URL_STORAGE_KEY);
    }
  }, []);

  const value: GhostfolioTokenContextValue = {
    token,
    isConnected: !!token?.trim(),
    setToken,
    clearToken,
    apiUrl: apiUrl || '',
    setApiUrl,
  };

  return (
    <GhostfolioTokenContext.Provider value={value}>
      {children}
    </GhostfolioTokenContext.Provider>
  );
}

export function useGhostfolioToken() {
  const ctx = useContext(GhostfolioTokenContext);
  if (!ctx) throw new Error('useGhostfolioToken must be used within GhostfolioTokenProvider');
  return ctx;
}
