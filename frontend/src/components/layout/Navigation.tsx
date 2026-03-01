import { Link, NavLink } from 'react-router-dom';
import { useAppMode } from '../../contexts/AppModeContext';
import { ModeToggle } from '../ModeToggle';

interface NavItem {
  label: string;
  path: string;
  icon: string;
  description: string;
  developerOnly?: boolean;
}

const navItems: NavItem[] = [
  { label: 'Verification', path: '/verification', icon: 'verified_user', description: 'Configure checks and run evaluations', developerOnly: true },
  { label: 'Observability', path: '/observability', icon: 'monitoring', description: 'View traces and cost metrics', developerOnly: true },
];

export function Navigation() {
  const { appMode, setAppMode } = useAppMode();
  const visibleNavItems = appMode === 'developer' ? navItems : navItems.filter((item) => !item.developerOnly);

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between flex-wrap gap-2 border-b border-solid border-surface-border bg-background-dark/80 backdrop-blur-md px-3 py-2 sm:px-6 sm:py-3">
      <div className="flex items-center gap-2 sm:gap-6 flex-wrap min-w-0">
        {/* Brand - clickable home; icon always, title hidden on narrow */}
        <Link
          to="/"
          className="flex items-center gap-2 sm:gap-3 text-white hover:opacity-90 transition-opacity rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 shrink-0"
          title="Ghostfolio Agent"
        >
          <div className="flex h-9 w-9 sm:h-10 sm:w-10 items-center justify-center rounded-lg bg-primary/20 text-primary">
            <span className="material-symbols-outlined text-xl sm:text-2xl">smart_toy</span>
          </div>
          <h2 className="hidden sm:block text-base sm:text-xl font-bold leading-tight tracking-[-0.015em] truncate">
            Ghostfolio Agent
          </h2>
        </Link>

        {/* Nav Links - wrap on small screens */}
        <nav className="flex items-center gap-1 flex-wrap" aria-label="Main navigation">
          {visibleNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `px-2 py-1.5 sm:px-3 sm:py-2 text-xs sm:text-sm font-medium leading-normal rounded-lg transition-colors ${
                  isActive
                    ? 'text-white bg-surface-dark'
                    : 'text-text-dim hover:text-white hover:bg-surface-dark'
                }`
              }
              title={item.description}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Right side: mode toggle and avatar */}
      <div className="flex items-center gap-2 sm:gap-4 shrink-0">
        <ModeToggle mode={appMode} onChange={setAppMode} />

        {/* User avatar */}
        <div className="size-8 sm:size-9 rounded-full bg-surface-dark bg-center bg-cover border border-surface-border" />
      </div>
    </header>
  );
}
