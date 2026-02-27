interface SidebarProps {
  title?: string;
  children?: React.ReactNode;
}

export function Sidebar({ title = 'File Explorer', children }: SidebarProps) {
  return (
    <aside className="w-80 bg-surface-darker border-r border-surface-border flex flex-col z-10">
      <div className="p-4 border-b border-surface-border">
        <span className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-2 font-mono text-sm">
        {children ?? (
          <div className="text-slate-500 p-4 text-center text-sm">
            No content available
          </div>
        )}
      </div>
    </aside>
  );
}
