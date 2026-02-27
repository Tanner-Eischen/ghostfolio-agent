import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Navigation } from './Navigation';
import { AlertBar } from './AlertBar';

const ALERT_DISMISSED_KEY = 'ghostfolio-agent-alert-dismissed';

interface LayoutProps {
  showAlertBar?: boolean;
  alertMessage?: string;
}

export function Layout({ showAlertBar = true, alertMessage }: LayoutProps) {
  const [alertDismissed, setAlertDismissed] = useState(() => {
    try {
      return localStorage.getItem(ALERT_DISMISSED_KEY) === 'true';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    if (!alertDismissed) return;
    try {
      localStorage.setItem(ALERT_DISMISSED_KEY, 'true');
    } catch {
      // ignore
    }
  }, [alertDismissed]);

  const handleDismissAlert = () => setAlertDismissed(true);

  const showBar = showAlertBar && !alertDismissed;

  return (
    <div className="dark bg-background-dark text-slate-100 font-display antialiased overflow-hidden h-screen flex flex-col">
      {showBar && (
        <AlertBar message={alertMessage} onDismiss={handleDismissAlert} />
      )}
      <Navigation />
      <main className="flex-1 min-h-0 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
