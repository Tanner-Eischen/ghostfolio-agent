import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export type AppMode = 'developer' | 'user';

const AppModeContext = createContext<{
  appMode: AppMode;
  setAppMode: (mode: AppMode) => void;
}>({ appMode: 'user', setAppMode: () => {} });

export function useAppMode() {
  const ctx = useContext(AppModeContext);
  if (!ctx) throw new Error('useAppMode must be used within AppModeProvider');
  return ctx;
}

export function AppModeProvider({ children }: { children: ReactNode }) {
  const [appMode, setAppMode] = useState<AppMode>('user');
  const value = { appMode, setAppMode: useCallback(setAppMode, []) };
  return (
    <AppModeContext.Provider value={value}>
      {children}
    </AppModeContext.Provider>
  );
}
