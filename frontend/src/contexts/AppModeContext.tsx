import { useMemo, useState, type ReactNode } from 'react';
import { AppModeContext, type AppMode } from './app-mode';

export function AppModeProvider({ children }: { children: ReactNode }) {
  const [appMode, setAppMode] = useState<AppMode>('user');
  const value = useMemo(() => ({ appMode, setAppMode }), [appMode]);
  return (
    <AppModeContext.Provider value={value}>
      {children}
    </AppModeContext.Provider>
  );
}
