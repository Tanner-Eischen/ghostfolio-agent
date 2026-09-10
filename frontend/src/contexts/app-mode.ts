import { createContext, useContext } from 'react';

export type AppMode = 'developer' | 'user';

export const AppModeContext = createContext<{
  appMode: AppMode;
  setAppMode: (mode: AppMode) => void;
} | null>(null);

export function useAppMode() {
  const context = useContext(AppModeContext);
  if (!context) throw new Error('useAppMode must be used within AppModeProvider');
  return context;
}
