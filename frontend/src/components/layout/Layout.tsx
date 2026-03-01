import { Outlet } from 'react-router-dom';
import { AppModeProvider } from '../../contexts/AppModeContext';
import { Navigation } from './Navigation';

interface LayoutProps {
  showAlertBar?: boolean;
  alertMessage?: string;
}

export function Layout(_props?: LayoutProps) {
  return (
    <AppModeProvider>
      <div className="dark bg-background-dark text-slate-100 font-display antialiased overflow-hidden h-screen min-h-[100dvh] flex flex-col">
        <Navigation />
        <main className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </AppModeProvider>
  );
}
