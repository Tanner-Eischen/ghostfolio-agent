import { useRef, useEffect, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useAppMode } from '../../contexts/AppModeContext';
import { useGhostfolioToken } from '../../contexts/GhostfolioTokenContext';
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
  const { isConnected, setToken, clearToken } = useGhostfolioToken();
  const [avatarOpen, setAvatarOpen] = useState(false);
  const [tokenInput, setTokenInput] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!avatarOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setAvatarOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [avatarOpen]);

  const visibleNavItems = appMode === 'developer' ? navItems : navItems.filter((item) => !item.developerOnly);

  const handleSaveToken = () => {
    const t = tokenInput.trim();
    if (t) {
      setToken(t);
      setTokenInput('');
    }
  };

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

      {/* Right side: mode toggle and avatar with dropdown */}
      <div className="flex items-center gap-2 sm:gap-4 shrink-0">
        <ModeToggle mode={appMode} onChange={setAppMode} />

        {/* Avatar: circle with dropdown for settings / Connect Ghostfolio */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setAvatarOpen((o) => !o)}
            className="relative flex items-center justify-center size-8 sm:size-9 rounded-full bg-surface-dark border-2 border-surface-border hover:border-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors"
            aria-expanded={avatarOpen}
            aria-haspopup="true"
            aria-label="Account and settings"
            title="Account & settings"
          >
            {isConnected && (
              <span className="absolute bottom-0 right-0 size-2.5 rounded-full bg-emerald-400 ring-2 ring-background-dark" aria-hidden />
            )}
            <span className="material-symbols-outlined text-lg text-slate-400">person</span>
          </button>

          {avatarOpen && (
            <div className="absolute right-0 top-full mt-2 w-72 rounded-xl border border-surface-border bg-surface-dark shadow-xl py-2 z-[100]">
              <div className="px-3 py-2 border-b border-surface-border">
                <span className="text-xs font-medium text-slate-400 uppercase tracking-wide">Settings</span>
              </div>

              {/* Connect Ghostfolio */}
              <div className="px-3 py-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-white">Ghostfolio</span>
                  {isConnected && (
                    <span className="flex items-center gap-1 text-xs text-emerald-400">
                      <span className="size-1.5 rounded-full bg-emerald-400" />
                      Connected
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500">
                  Token from Ghostfolio → Settings → Security. Stored only in this browser.
                </p>
                {isConnected ? (
                  <>
                    <button
                      type="button"
                      onClick={() => { clearToken(); setAvatarOpen(false); }}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-red-500/40 text-xs text-red-400 hover:bg-red-500/10"
                    >
                      Disconnect
                    </button>
                    <input
                      type="password"
                      value={tokenInput}
                      onChange={(e) => setTokenInput(e.target.value)}
                      placeholder="Paste new token to replace"
                      className="w-full px-2.5 py-1.5 rounded-lg bg-surface-darker border border-surface-border text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-primary/50"
                      aria-label="New Ghostfolio token"
                    />
                    {tokenInput.trim() && (
                      <button
                        type="button"
                        onClick={() => { handleSaveToken(); setAvatarOpen(false); }}
                        className="w-full px-2.5 py-1.5 rounded-lg bg-primary text-primary-contrast text-sm font-medium"
                      >
                        Save new token
                      </button>
                    )}
                  </>
                ) : (
                  <>
                    <input
                      type="password"
                      value={tokenInput}
                      onChange={(e) => setTokenInput(e.target.value)}
                      placeholder="Paste access token"
                      className="w-full px-2.5 py-1.5 rounded-lg bg-surface-darker border border-surface-border text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-primary/50"
                      aria-label="Ghostfolio access token"
                    />
                    <button
                      type="button"
                      onClick={() => { handleSaveToken(); setAvatarOpen(false); }}
                      disabled={!tokenInput.trim()}
                      className="w-full px-2.5 py-1.5 rounded-lg bg-primary text-primary-contrast text-sm font-medium disabled:opacity-50 hover:enabled:opacity-90"
                    >
                      Connect
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
