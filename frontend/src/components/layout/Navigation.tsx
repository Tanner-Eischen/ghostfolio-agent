import { Link, NavLink } from 'react-router-dom';

interface NavItem {
  label: string;
  path: string;
  icon: string;
  description: string;
}

const navItems: NavItem[] = [
  { label: 'Repo Analysis', path: '/', icon: 'dashboard', description: 'Connect and analyze repositories' },
  { label: 'Agent Chat', path: '/chat', icon: 'chat', description: 'Interact with the AI agent' },
  { label: 'Verification', path: '/verification', icon: 'verified_user', description: 'Configure checks and run evaluations' },
  { label: 'Observability', path: '/observability', icon: 'monitoring', description: 'View traces and cost metrics' },
];

export function Navigation() {
  return (
    <header className="sticky top-0 z-50 flex items-center justify-between flex-wrap gap-2 border-b border-solid border-surface-border bg-background-dark/80 backdrop-blur-md px-4 sm:px-6 py-3">
      <div className="flex items-center gap-4 sm:gap-6 flex-wrap">
        {/* Brand - clickable home */}
        <Link
          to="/"
          className="flex items-center gap-3 text-white hover:opacity-90 transition-opacity rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50"
          title="Repo Analysis"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded bg-primary/20 text-primary">
            <span className="material-symbols-outlined">smart_toy</span>
          </div>
          <h2 className="text-lg font-bold leading-tight tracking-[-0.015em]">
            Ghostfolio Agent
          </h2>
        </Link>

        {/* Nav Links - always visible */}
        <nav className="flex items-center gap-1" aria-label="Main navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `px-3 py-2 text-sm font-medium leading-normal rounded-lg transition-colors ${
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

      {/* Right side */}
      <div className="flex items-center gap-4">
        {/* Repo pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-dark border border-surface-border">
          <span className="material-symbols-outlined text-text-dim text-sm">fork_right</span>
          <span className="text-sm font-medium text-slate-300">ghostfolio/core</span>
          <span className="text-xs bg-primary/20 text-primary px-1.5 py-0.5 rounded ml-2">
            v2.4.0
          </span>
        </div>

        {/* User avatar */}
        <div className="size-9 rounded-full bg-surface-dark bg-center bg-cover border border-surface-border" />
      </div>
    </header>
  );
}
