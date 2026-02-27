import { Outlet } from 'react-router-dom';
import { Navigation } from './Navigation';
import { AlertBar } from './AlertBar';

interface LayoutProps {
  showAlertBar?: boolean;
  alertMessage?: string;
}

export function Layout({ showAlertBar = true, alertMessage }: LayoutProps) {
  return (
    <div className="dark bg-background-dark text-slate-100 font-display antialiased overflow-hidden h-screen flex flex-col">
      {showAlertBar && <AlertBar message={alertMessage} />}
      <Navigation />
      <main className="flex-1 min-h-0 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
