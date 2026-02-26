import { useEffect, useState, useRef, useCallback } from 'react';
import { healthApi, repoApi } from '../api/client';
import type { HealthResponse, RepoInfo, DependenciesGraph, RepoConnection } from '../api/client';
import { Sidebar } from '../components/layout/Sidebar';
import { RepoConnector } from '../components/RepoConnector';

type MapMode = 'full' | 'services';

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  'agent-core': { x: 200, y: 150 },
  'database': { x: 80, y: 60 },
  'auth-service': { x: 320, y: 60 },
  'module-tools': { x: 80, y: 240 },
  'module-verification': { x: 320, y: 240 },
  'module-api': { x: 200, y: 280 },
};

const COLOR_MAP: Record<string, { bg: string; border: string; text: string }> = {
  primary: { bg: 'rgba(6, 182, 212, 0.1)', border: '#06b6d4', text: '#06b6d4' },
  indigo: { bg: 'rgba(129, 140, 248, 0.1)', border: '#818cf8', text: '#818cf8' },
  emerald: { bg: 'rgba(16, 185, 129, 0.1)', border: '#10b981', text: '#10b981' },
  slate: { bg: 'rgba(100, 116, 139, 0.1)', border: '#64748b', text: '#f1f5f9' },
};

export function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [repo, setRepo] = useState<RepoInfo | null>(null);
  const [dependencies, setDependencies] = useState<DependenciesGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [mapMode, setMapMode] = useState<MapMode>('full');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  // Repo connection state
  const [connectedRepo, setConnectedRepo] = useState<RepoConnection | null>(null);

  // Fetch data based on connection status
  const fetchData = useCallback(async () => {
    try {
      const healthData = await healthApi.check();
      setHealth(healthData);

      if (connectedRepo) {
        // Fetch data from connected repo
        const [repoData, depsData] = await Promise.all([
          repoApi.getConnected(connectedRepo.id).catch(() => null),
          repoApi.getConnectedDependencies(connectedRepo.id).catch(() => null),
        ]);
        setRepo(repoData);
        setDependencies(depsData);
      } else {
        // Use ghostfolio-agent's own repo as fallback
        const [repoData, depsData] = await Promise.all([
          repoApi.get().catch(() => null),
          repoApi.getDependencies().catch(() => null),
        ]);
        setRepo(repoData);
        setDependencies(depsData);
      }
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  }, [connectedRepo]);

  // Load existing connections on mount
  useEffect(() => {
    async function loadConnections() {
      try {
        const response = await repoApi.listConnections();
        // Auto-connect to the first connection if any exist
        if (response.connections && response.connections.length > 0) {
          setConnectedRepo(response.connections[0]);
        }
      } catch (error) {
        console.error('Failed to load connections:', error);
      }
    }
    loadConnections();
  }, []);

  // Fetch data when connection changes
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleConnected = (connection: RepoConnection) => {
    setConnectedRepo(connection);
    setLoading(true);
  };

  const handleDisconnect = () => {
    setConnectedRepo(null);
    setRepo(null);
    setDependencies(null);
    setLoading(true);
  };

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  }, [pan]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.2, 2));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.2, 0.5));

  const getNodePosition = (nodeId: string): { x: number; y: number } => {
    return NODE_POSITIONS[nodeId] || { x: 200, y: 150 };
  };

  const filteredNodes = dependencies?.nodes.filter(node => {
    if (mapMode === 'services') {
      return node.type !== 'database';
    }
    return true;
  }) || [];

  const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
  const filteredEdges = dependencies?.edges.filter(edge =>
    filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)
  ) || [];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-dim">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <Sidebar title="File Explorer">
        <div className="group flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-dark cursor-pointer text-slate-300">
          <span className="material-symbols-outlined text-slate-400 text-lg">folder_open</span>
          <span>src</span>
        </div>
        <div className="pl-4 relative tree-line">
          <div className="group flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-dark cursor-pointer text-slate-300">
            <span className="material-symbols-outlined text-slate-400 text-lg">folder</span>
            <span>api</span>
          </div>
          <div className="pl-4 relative tree-line">
            <div className="group flex items-center justify-between px-2 py-1.5 rounded bg-primary/10 border border-primary/20 cursor-pointer text-primary">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-lg">javascript</span>
                <span>routes.py</span>
              </div>
              <span className="size-2 rounded-full bg-primary animate-pulse" />
            </div>
          </div>
          <div className="group flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-dark cursor-pointer text-slate-300">
            <span className="material-symbols-outlined text-slate-400 text-lg">folder</span>
            <span>agent</span>
          </div>
          <div className="group flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-dark cursor-pointer text-slate-300">
            <span className="material-symbols-outlined text-slate-400 text-lg">folder</span>
            <span>tools</span>
          </div>
        </div>
      </Sidebar>

      <main className="flex-1 flex flex-col bg-background-dark overflow-y-auto">
        {/* Top Alert Bar - Missing Dependencies */}
        {health?.dependencies && Object.entries(health.dependencies).some(([_, value]) => !value) && (
          <div className="bg-amber-500/10 border-b border-amber-500/30 px-6 py-2 flex items-center gap-3">
            <span className="material-symbols-outlined text-amber-400 text-lg">warning</span>
            <span className="text-amber-200 text-sm">
              Missing Critical API Keys:{' '}
              {Object.entries(health.dependencies)
                .filter(([_, value]) => !value)
                .map(([key]) => key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()))
                .join(', ')}
            </span>
          </div>
        )}

        {/* Header */}
        <div className="sticky top-0 z-10 bg-background-dark/95 backdrop-blur-sm border-b border-surface-border px-6 py-4 flex justify-between items-end">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-slate-400 text-sm">Repo Analysis /</span>
              <span className="text-primary font-mono text-sm">
                {connectedRepo ? connectedRepo.name : 'ghostfolio-agent'}
              </span>
              {connectedRepo && (
                <span className="ml-2 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs">
                  Connected
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold text-white">Codebase Analysis & Mapping</h1>
          </div>
          <div className="flex gap-3">
            {health?.dependencies && (
              <>
                <span className="px-3 py-1 rounded-full border border-green-500/30 bg-green-500/10 text-green-400 text-xs font-medium flex items-center gap-1">
                  <span className="material-symbols-outlined text-sm">check_circle</span>
                  {repo?.endpoints || 12} Endpoints
                </span>
                <span className="px-3 py-1 rounded-full border border-surface-border bg-surface-dark text-slate-400 text-xs font-medium flex items-center gap-1">
                  <span className="material-symbols-outlined text-sm">account_tree</span>
                  {repo?.services || 3} Service Links
                </span>
              </>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Repo Connector */}
          <RepoConnector
            onConnected={handleConnected}
            onDisconnect={handleDisconnect}
            connectedRepo={connectedRepo}
          />

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Structural Breakdown */}
          <div className="flex flex-col gap-4">
            <div className="bg-surface-dark border border-surface-border rounded-xl p-4 flex justify-between items-center shadow-sm">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg bg-indigo-500/20 text-indigo-400">
                  <span className="material-symbols-outlined text-2xl">schema</span>
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-100">Structural Breakdown</h3>
                  <div className="flex gap-4 mt-1">
                    <span className="text-xs text-slate-400">
                      Total Routes: <span className="text-white font-mono">{repo?.endpoints || 24}</span>
                    </span>
                    <span className="text-xs text-slate-400">
                      Detected Services: <span className="text-white font-mono">{repo?.services || 8}</span>
                    </span>
                    <span className="text-xs text-slate-400">
                      Tool Hooks: <span className="text-primary font-mono">{repo?.tool_hooks || 5}</span>
                    </span>
                  </div>
                </div>
              </div>
              <button className="text-xs text-slate-400 hover:text-white border border-surface-border rounded px-3 py-1.5 transition-colors">
                View Report
              </button>
            </div>

            {/* Code Preview */}
            <div className="bg-surface-darker rounded-xl border border-surface-border overflow-hidden shadow-sm flex-1 min-h-[400px]">
              <div className="flex items-center justify-between px-4 py-2 bg-surface-dark border-b border-surface-border">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Detected Injection Points
                  </span>
                  <span className="bg-primary/20 text-primary text-[10px] px-1.5 rounded">3 Found</span>
                </div>
              </div>
              <div className="p-4 font-mono text-sm leading-6 text-slate-400 overflow-x-auto">
                <div className="flex">
                  <span className="w-8 text-slate-500 select-none">14</span>
                  <span>@Controller('api')</span>
                </div>
                <div className="flex">
                  <span className="w-8 text-slate-500 select-none">15</span>
                  <span>export class AppController {'{'}</span>
                </div>
                <div className="relative group my-2">
                  <div className="absolute inset-0 bg-primary/10 border-l-2 border-primary -ml-4 w-[calc(100%+2rem)]" />
                  <div className="relative flex text-primary">
                    <span className="w-8 text-primary/50 select-none">+</span>
                    <span>  @Post('agent/query')</span>
                  </div>
                  <div className="relative flex text-primary">
                    <span className="w-8 text-primary/50 select-none">+</span>
                    <span>  async handleAgentQuery(@Body() query: AgentDto) {'{'}</span>
                  </div>
                  <div className="relative flex text-primary">
                    <span className="w-8 text-primary/50 select-none">+</span>
                    <span>    return this.agentService.process(query);</span>
                  </div>
                  <div className="relative flex text-primary">
                    <span className="w-8 text-primary/50 select-none">+</span>
                    <span>  {'}'}</span>
                  </div>
                </div>
                <div className="flex">
                  <span className="w-8 text-slate-500 select-none">21</span>
                  <span>{'}'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Insight Panel */}
          <div className="flex flex-col gap-6">
            <div className="p-5 rounded-xl bg-gradient-to-br from-surface-dark to-surface-darker border border-primary/30 shadow-lg relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/10 blur-[50px] rounded-full pointer-events-none" />
              <div className="flex items-start gap-4">
                <div className="p-2 rounded-lg bg-primary/20 text-primary">
                  <span className="material-symbols-outlined text-2xl">auto_fix_high</span>
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white mb-1">Codebase Insight</h3>
                  <p className="text-sm text-slate-400 leading-relaxed mb-4">
                    I've mapped the full dependency tree. The <code className="text-primary">AppController</code> is
                    the optimal entry point as it sits upstream of <code className="text-primary">UserService</code>{' '}
                    and <code className="text-primary">PortfolioService</code>. Injecting here minimizes latency for
                    AI-driven portfolio queries.
                  </p>
                  <div className="flex gap-3">
                    <button className="text-xs font-medium bg-primary text-surface-darker px-3 py-1.5 rounded hover:bg-cyan-400 transition-colors">
                      Accept Mapping
                    </button>
                    <button className="text-xs font-medium text-slate-400 hover:text-white px-3 py-1.5 transition-colors">
                      View Alternatives
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Health Status */}
            <div className="bg-surface-dark rounded-xl border border-surface-border p-4">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-3">System Health</h4>
              <div className="space-y-2">
                {health?.dependencies && Object.entries(health.dependencies).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-sm text-white capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className={`flex items-center gap-1.5 text-xs font-medium ${
                      value ? 'text-emerald-400' : 'text-red-400'
                    }`}>
                      <span className={`h-2 w-2 rounded-full ${value ? 'bg-emerald-500' : 'bg-red-500'} animate-pulse`} />
                      {value ? 'Operational' : 'Unavailable'}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Dependency Mapper */}
            <div className="flex-1 rounded-xl bg-surface-dark border border-surface-border flex flex-col overflow-hidden min-h-[300px]">
              <div className="px-5 py-3 border-b border-surface-border flex justify-between items-center bg-surface-darker">
                <h3 className="text-sm font-semibold text-slate-300">Dependency Mapper</h3>
                <div className="flex gap-2">
                  <span className="size-2 rounded-full bg-primary" />
                  <span className="text-xs text-slate-500">Agent</span>
                  <span className="size-2 rounded-full bg-indigo-400 ml-2" />
                  <span className="text-xs text-slate-500">Services</span>
                  <span className="size-2 rounded-full bg-emerald-400 ml-2" />
                  <span className="text-xs text-slate-500">Database</span>
                </div>
              </div>

              {/* SVG Graph Container */}
              <div
                className="relative flex-1 overflow-hidden cursor-grab active:cursor-grabbing"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              >
                <svg
                  ref={svgRef}
                  className="w-full h-full"
                  viewBox="0 0 400 340"
                  style={{
                    transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
                    transformOrigin: 'center',
                  }}
                >
                  {/* Background grid pattern */}
                  <defs>
                    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(100,116,139,0.1)" strokeWidth="0.5"/>
                    </pattern>
                    <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
                      <stop offset="0%" stopColor="rgba(6,182,212,0.1)" />
                      <stop offset="100%" stopColor="transparent" />
                    </radialGradient>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#grid)" />
                  <circle cx="200" cy="150" r="120" fill="url(#centerGlow)" />

                  {/* Edges (connections) */}
                  {filteredEdges.map((edge, i) => {
                    const source = getNodePosition(edge.source);
                    const target = getNodePosition(edge.target);
                    return (
                      <g key={i}>
                        <line
                          x1={source.x}
                          y1={source.y}
                          x2={target.x}
                          y2={target.y}
                          stroke="rgba(100,116,139,0.4)"
                          strokeWidth="2"
                          strokeDasharray="4 4"
                          className="animate-pulse"
                        />
                        {edge.label && (
                          <text
                            x={(source.x + target.x) / 2}
                            y={(source.y + target.y) / 2 - 8}
                            fill="rgba(148,163,184,0.6)"
                            fontSize="8"
                            textAnchor="middle"
                          >
                            {edge.label}
                          </text>
                        )}
                      </g>
                    );
                  })}

                  {/* Nodes */}
                  {filteredNodes.map((node) => {
                    const pos = getNodePosition(node.id);
                    const colors = COLOR_MAP[node.color] || COLOR_MAP.slate;
                    const isAgent = node.type === 'agent';
                    const size = isAgent ? 40 : 28;

                    return (
                      <g key={node.id} className="cursor-pointer hover:opacity-80 transition-opacity">
                        {/* Node circle */}
                        <circle
                          cx={pos.x}
                          cy={pos.y}
                          r={size}
                          fill={colors.bg}
                          stroke={colors.border}
                          strokeWidth={isAgent ? 3 : 2}
                          className={isAgent ? 'animate-pulse' : ''}
                        />
                        {/* Icon */}
                        <text
                          x={pos.x}
                          y={pos.y + 5}
                          fill={colors.text}
                          fontSize={isAgent ? 24 : 16}
                          textAnchor="middle"
                          fontFamily="Material Symbols Outlined"
                        >
                          {node.icon}
                        </text>
                        {/* Label */}
                        <text
                          x={pos.x}
                          y={pos.y + size + 16}
                          fill={colors.text}
                          fontSize="10"
                          fontWeight="bold"
                          textAnchor="middle"
                        >
                          {node.name}
                        </text>
                      </g>
                    );
                  })}
                </svg>

                {/* Loading state */}
                {!dependencies && (
                  <div className="absolute inset-0 flex items-center justify-center bg-surface-dark/50">
                    <span className="text-slate-400 text-sm">Loading dependencies...</span>
                  </div>
                )}
              </div>

              {/* Footer with controls */}
              <div className="px-4 py-2 border-t border-surface-border bg-surface-darker flex justify-between items-center">
                <div className="flex items-center gap-4">
                  <span className="text-xs text-slate-500">Map Mode:</span>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setMapMode('full')}
                      className={`px-2 py-1 text-xs rounded transition-colors ${
                        mapMode === 'full'
                          ? 'bg-primary/20 text-primary border border-primary/30'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      Full Architecture
                    </button>
                    <button
                      onClick={() => setMapMode('services')}
                      className={`px-2 py-1 text-xs rounded transition-colors ${
                        mapMode === 'services'
                          ? 'bg-primary/20 text-primary border border-primary/30'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      Services Only
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">Zoom: {Math.round(zoom * 100)}%</span>
                  <button
                    onClick={handleZoomOut}
                    className="p-1 text-slate-400 hover:text-white border border-surface-border rounded transition-colors"
                  >
                    <span className="material-symbols-outlined text-sm">remove</span>
                  </button>
                  <button
                    onClick={handleZoomIn}
                    className="p-1 text-slate-400 hover:text-white border border-surface-border rounded transition-colors"
                  >
                    <span className="material-symbols-outlined text-sm">add</span>
                  </button>
                  <button
                    onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
                    className="p-1 text-slate-400 hover:text-white border border-surface-border rounded transition-colors"
                    title="Reset view"
                  >
                    <span className="material-symbols-outlined text-sm">center_focus_strong</span>
                  </button>
                  <button
                    className="p-1 text-slate-400 hover:text-white border border-surface-border rounded transition-colors"
                    title="Expand"
                  >
                    <span className="material-symbols-outlined text-sm">open_in_full</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
          </div>
        </div>
      </main>
    </div>
  );
}
