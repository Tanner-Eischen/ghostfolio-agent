import type { AppMode } from '../contexts/app-mode';

interface ModeToggleProps {
  mode: AppMode;
  onChange: (mode: AppMode) => void;
}

export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  return (
    <div className="flex items-center bg-surface-darker rounded-lg p-1 border border-surface-border">
      <button
        onClick={() => onChange('developer')}
        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
          mode === 'developer'
            ? 'bg-primary text-white'
            : 'text-slate-400 hover:text-white'
        }`}
      >
        <span className="material-symbols-outlined text-sm">code</span>
        Developer
      </button>
      <button
        onClick={() => onChange('user')}
        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
          mode === 'user'
            ? 'bg-emerald-500 text-white'
            : 'text-slate-400 hover:text-white'
        }`}
      >
        <span className="material-symbols-outlined text-sm">person</span>
        User
      </button>
    </div>
  );
}
