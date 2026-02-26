import { NavLink } from 'react-router-dom';

interface NavItem {
  label: string;
  path: string;
  icon: string;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: 'dashboard' },
  { label: 'Strategy', path: '/strategy', icon: 'hub' },
  { label: 'Tools', path: '/tools', icon: 'handyman' },
  { label: 'Verification', path: '/verification', icon: 'verified_user' },
  { label: 'Observability', path: '/observability', icon: 'monitoring' },
  { label: 'Evaluations', path: '/evaluations', icon: 'assessment' },
  { label: 'Finances', path: '/finances', icon: 'payments' },
];

export function Navigation() {
  return (
    <header className="sticky top-0 z-50 flex items-center justify-between whitespace-nowrap border-b border-solid border-surface-border bg-background-dark/80 backdrop-blur-md px-6 py-3">
      <div className="flex items-center gap-6">
        {/* Brand */}
        <div className="flex items-center gap-3 text-white">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-primary/20 text-primary">
            <span className="material-symbols-outlined">smart_toy</span>
          </div>
          <h2 className="text-lg font-bold leading-tight tracking-[-0.015em]">
            Ghostfolio AI Integrator
          </h2>
        </div>

        {/* Nav Links */}
        <nav className="hidden md:flex items-center gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `px-3 py-2 text-sm font-medium leading-normal rounded-lg transition-colors ${
                  isActive
                    ? 'text-white bg-surface-dark'
                    : 'text-text-dim hover:text-white hover:bg-surface-dark'
                }`
              }
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
