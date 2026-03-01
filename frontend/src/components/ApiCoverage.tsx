import { useState, useEffect } from 'react';
import { toolsApi, type Tool } from '../api/client';

export interface ApiEndpoint {
  path: string;
  method: string;
  file_path: string;
  line_number: number;
  function_name?: string;
}

interface Props {
  endpoints: ApiEndpoint[];
  repoName: string;
  onGenerateTool?: (endpoint: ApiEndpoint) => void;
}

type CoverageStatus = 'is_tool' | 'can_add' | 'not_useful';

function getMethodColor(method: string): string {
  const colors: Record<string, string> = {
    GET: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    POST: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    PUT: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    PATCH: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    DELETE: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  return colors[method.toUpperCase()] || 'bg-slate-500/20 text-slate-400 border-slate-500/30';
}

function getMethodIcon(method: string): string {
  const icons: Record<string, string> = {
    GET: 'download',
    POST: 'upload',
    PUT: 'edit',
    PATCH: 'edit',
    DELETE: 'delete',
  };
  return icons[method.toUpperCase()] || 'api';
}

export function ApiCoverage({ endpoints, repoName, onGenerateTool }: Props) {
  const [agentTools, setAgentTools] = useState<Tool[]>([]);
  const [toolsLoading, setToolsLoading] = useState(true);
  const [filter, setFilter] = useState<CoverageStatus | 'all'>('all');

  useEffect(() => {
    async function loadTools() {
      try {
        const tools = await toolsApi.list();
        setAgentTools(tools);
      } catch (e) {
        console.error('Failed to load tools:', e);
      } finally {
        setToolsLoading(false);
      }
    }
    loadTools();
  }, []);

  // Determine coverage status for each endpoint
  function getCoverageStatus(endpoint: ApiEndpoint): CoverageStatus {
    const pathLower = endpoint.path.toLowerCase();

    // Check if there's already a tool for this endpoint
    const hasTool = agentTools.some(tool => {
      const toolName = tool.name.toLowerCase();
      const endpointPath = pathLower.replace(/[^a-z0-9]/g, '_');
      return toolName.includes(endpointPath) ||
             toolName.includes(endpoint.function_name?.toLowerCase() || '');
    });

    if (hasTool) return 'is_tool';

    // Heuristics for "not useful" endpoints
    const notUsefulPatterns = [
      /\/health/, /\/metrics/, /\/favicon/, /\/static\//,
      /\/docs/, /\/openapi/, /\/redoc/, /\/schema/,
    ];
    if (notUsefulPatterns.some(p => p.test(pathLower))) {
      return 'not_useful';
    }

    return 'can_add';
  }

  // Filter endpoints
  const filteredEndpoints = endpoints.filter(ep => {
    if (filter === 'all') return true;
    return getCoverageStatus(ep) === filter;
  });

  // Calculate stats
  const stats = {
    total: endpoints.length,
    is_tool: endpoints.filter(e => getCoverageStatus(e) === 'is_tool').length,
    can_add: endpoints.filter(e => getCoverageStatus(e) === 'can_add').length,
    not_useful: endpoints.filter(e => getCoverageStatus(e) === 'not_useful').length,
  };
  const coveragePercent = stats.total > 0 ? Math.round((stats.is_tool / stats.total) * 100) : 0;

  if (toolsLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-slate-500">Loading coverage data...</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header with stats */}
      <div className="px-4 py-3 bg-surface-dark border-b border-surface-border shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-200">API Coverage</h3>
            <span className="text-xs text-slate-500">{repoName}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-surface-darker rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all"
                style={{ width: `${coveragePercent}%` }}
              />
            </div>
            <span className="text-xs text-slate-400">{coveragePercent}% covered</span>
          </div>
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setFilter('all')}
            className={`px-2 py-1 text-xs rounded ${
              filter === 'all' ? 'bg-slate-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            All ({stats.total})
          </button>
          <button
            onClick={() => setFilter('is_tool')}
            className={`px-2 py-1 text-xs rounded flex items-center gap-1 ${
              filter === 'is_tool' ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <span className="material-symbols-outlined text-xs">check_circle</span>
            Tools ({stats.is_tool})
          </button>
          <button
            onClick={() => setFilter('can_add')}
            className={`px-2 py-1 text-xs rounded flex items-center gap-1 ${
              filter === 'can_add' ? 'bg-primary text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <span className="material-symbols-outlined text-xs">add_circle</span>
            Can Add ({stats.can_add})
          </button>
          <button
            onClick={() => setFilter('not_useful')}
            className={`px-2 py-1 text-xs rounded ${
              filter === 'not_useful' ? 'bg-slate-500 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            Not Useful ({stats.not_useful})
          </button>
        </div>
      </div>

      {/* Endpoint list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {filteredEndpoints.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-sm">
            {endpoints.length === 0
              ? 'No API endpoints detected in this repository'
              : 'No endpoints match the current filter'}
          </div>
        ) : (
          filteredEndpoints.map((endpoint, idx) => {
            const status = getCoverageStatus(endpoint);
            return (
              <div
                key={`${endpoint.path}-${idx}`}
                className={`bg-surface-dark rounded-lg p-3 border ${
                  status === 'is_tool'
                    ? 'border-emerald-500/30'
                    : status === 'can_add'
                    ? 'border-primary/30'
                    : 'border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono border ${getMethodColor(endpoint.method)}`}
                    >
                      <span className="material-symbols-outlined text-xs">{getMethodIcon(endpoint.method)}</span>
                      {endpoint.method.toUpperCase()}
                    </span>
                    <span className="font-mono text-sm text-slate-200">{endpoint.path}</span>
                  </div>

                  {status === 'is_tool' && (
                    <span className="flex items-center gap-1 text-xs text-emerald-400">
                      <span className="material-symbols-outlined text-sm">check_circle</span>
                      Tool
                    </span>
                  )}
                  {status === 'can_add' && onGenerateTool && (
                    <button
                      onClick={() => onGenerateTool(endpoint)}
                      className="flex items-center gap-1 text-xs text-primary hover:text-primary/80"
                    >
                      <span className="material-symbols-outlined text-sm">add</span>
                      Add as Tool
                    </button>
                  )}
                  {status === 'not_useful' && (
                    <span className="text-xs text-slate-500">Not useful for agent</span>
                  )}
                </div>
                <div className="mt-1 text-[11px] text-slate-500">
                  {endpoint.file_path}:{endpoint.line_number}
                  {endpoint.function_name && (
                    <span className="ml-2 text-slate-600">→ {endpoint.function_name}()</span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
