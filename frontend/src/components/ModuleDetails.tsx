import type { DependencyNode, DependencyEdge } from '../api/client';

const COLOR_MAP: Record<string, string> = {
  primary: '#06b6d4',
  indigo: '#818cf8',
  emerald: '#10b981',
  slate: '#64748b',
};

interface ModuleDetailsProps {
  node: DependencyNode;
  dependencies: { nodes: DependencyNode[]; edges: DependencyEdge[] };
  onClose: () => void;
}

export function ModuleDetails({ node, dependencies, onClose }: ModuleDetailsProps) {
  const color = COLOR_MAP[node.color] || COLOR_MAP.slate;
  const dependents = dependencies.edges.filter((e) => e.target === node.id).map((e) => e.source);
  const dependsOn = dependencies.edges.filter((e) => e.source === node.id).map((e) => e.target);

  const getNodeName = (id: string) => dependencies.nodes.find((n) => n.id === id)?.name ?? id;

  return (
    <div className="absolute right-0 top-0 bottom-0 w-80 border-l border-surface-border bg-surface-darker shadow-xl flex flex-col z-10">
      <div className="p-4 border-b border-surface-border flex items-center justify-between">
        <h3 className="text-sm font-bold text-white">Module Details</h3>
        <button
          onClick={onClose}
          className="p-1 rounded text-slate-400 hover:text-white hover:bg-surface-dark transition-colors"
          aria-label="Close"
        >
          <span className="material-symbols-outlined text-lg">close</span>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="flex items-center gap-3">
          <div
            className="p-2 rounded-lg"
            style={{ backgroundColor: `${color}20`, borderColor: color }}
          >
            <span className="material-symbols-outlined text-2xl" style={{ color }}>
              {node.icon || 'extension'}
            </span>
          </div>
          <div>
            <h4 className="font-semibold text-white">{node.name}</h4>
            <p className="text-xs text-slate-500 capitalize">{node.type}</p>
          </div>
        </div>

        {(node.file_count != null && node.file_count > 0) || (node.line_count != null && node.line_count > 0) ? (
          <div className="text-xs text-slate-400">
            <span className="font-medium text-slate-300">Stats:</span>{' '}
            {node.file_count ?? 0} files · {(node.line_count ?? 0).toLocaleString()} lines
          </div>
        ) : null}

        {node.has_circular && (
          <div className="flex items-center gap-2 text-amber-400 text-xs bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
            <span className="material-symbols-outlined text-sm">warning</span>
            This module is part of a circular dependency
          </div>
        )}

        {node.external_deps && node.external_deps.length > 0 && (
          <div>
            <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
              External dependencies
            </h5>
            <div className="flex flex-wrap gap-1">
              {node.external_deps.slice(0, 15).map((dep) => (
                <span
                  key={dep}
                  className="px-2 py-0.5 rounded bg-surface-dark text-slate-400 text-xs font-mono"
                >
                  {dep}
                </span>
              ))}
              {node.external_deps.length > 15 && (
                <span className="text-slate-500 text-xs">+{node.external_deps.length - 15} more</span>
              )}
            </div>
          </div>
        )}

        {dependsOn.length > 0 && (
          <div>
            <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
              Depends on ({dependsOn.length})
            </h5>
            <ul className="space-y-1">
              {dependsOn.map((id) => (
                <li key={id} className="text-sm text-slate-300 flex items-center gap-1">
                  <span className="material-symbols-outlined text-slate-500 text-sm">arrow_forward</span>
                  {getNodeName(id)}
                </li>
              ))}
            </ul>
          </div>
        )}

        {dependents.length > 0 && (
          <div>
            <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
              Used by ({dependents.length})
            </h5>
            <ul className="space-y-1">
              {dependents.map((id) => (
                <li key={id} className="text-sm text-slate-300 flex items-center gap-1">
                  <span className="material-symbols-outlined text-slate-500 text-sm">arrow_back</span>
                  {getNodeName(id)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
