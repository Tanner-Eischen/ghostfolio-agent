interface SidebarProps {
  title?: string;
  children?: React.ReactNode;
}

export function Sidebar({ title = 'File Explorer', children }: SidebarProps) {
  return (
    <aside className="w-80 bg-surface-darker border-r border-surface-border flex flex-col z-10">
      <div className="p-4 border-b border-surface-border flex justify-between items-center">
        <span className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </span>
        <div className="flex gap-2">
          <button className="text-slate-400 hover:text-white transition-colors">
            <span className="material-symbols-outlined text-lg">create_new_folder</span>
          </button>
          <button className="text-slate-400 hover:text-white transition-colors">
            <span className="material-symbols-outlined text-lg">expand_all</span>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 font-mono text-sm">
        {children || (
          <div className="text-slate-500 p-4 text-center">
            No content available
          </div>
        )}
      </div>

      {/* Indexing progress */}
      <div className="p-4 border-t border-surface-border bg-surface-darker">
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center">
            <span className="text-xs font-semibold text-slate-400">Indexing Progress</span>
            <span className="text-xs font-mono text-primary">68%</span>
          </div>
          <div className="w-full h-1.5 bg-surface-border rounded-full overflow-hidden">
            <div className="h-full bg-primary w-2/3 animate-pulse" />
          </div>
          <span className="text-[10px] text-slate-500">Traversing src/api/...</span>
        </div>
      </div>
    </aside>
  );
}
