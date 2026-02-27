import { useEffect, useState, useCallback } from 'react';
import { healthApi, repoApi } from '../api/client';
import type {
  HealthResponse,
  RepoInfo,
  DependenciesGraph,
  RepoConnection,
  FileNode,
  InjectionPoint,
  CodebaseInsight,
} from '../api/client';
import { Sidebar } from '../components/layout/Sidebar';
import { RepoConnector } from '../components/RepoConnector';
import { DependencyGraph, type DependencyGraphLayout } from '../components/DependencyGraph';
import { ModuleDetails } from '../components/ModuleDetails';
import type { DependencyNode } from '../api/client';

type MapMode = 'full' | 'services';

// File tree item component
function FileTreeItem({ node, depth = 0, selectedPath, onSelect }: {
  node: FileNode;
  depth?: number;
  selectedPath: string | null;
  onSelect: (node: FileNode) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const isDirectory = node.type === 'directory';
  const isSelected = selectedPath === node.path;

  const getIcon = () => {
    if (isDirectory) return expanded ? 'folder_open' : 'folder';
    if (node.name.endsWith('.py')) return 'terminal';
    if (node.name.endsWith('.ts') || node.name.endsWith('.tsx')) return 'javascript';
    if (node.name.endsWith('.json')) return 'data_object';
    return 'description';
  };

  return (
    <div>
      <div
        className={`group flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors ${
          isSelected
            ? 'bg-primary/10 border border-primary/20 text-primary'
            : 'hover:bg-surface-dark text-slate-300'
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={() => {
          if (isDirectory) setExpanded(!expanded);
          else onSelect(node);
        }}
      >
        <span className="material-symbols-outlined text-slate-400 text-lg">{getIcon()}</span>
        <span className="truncate">{node.name}</span>
        {isDirectory && node.children && (
          <span className="text-xs text-slate-500 ml-auto">{node.children.length}</span>
        )}
        {isSelected && <span className="size-2 rounded-full bg-primary animate-pulse ml-auto" />}
      </div>
      {isDirectory && expanded && node.children && (
        <div className="relative">
          {depth < 2 && <div className="absolute left-3 top-0 bottom-0 w-px bg-slate-700" />}
          {node.children.map((child) => (
            <FileTreeItem
              key={child.path}
              node={child}
              depth={depth + 1}
              selectedPath={selectedPath}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function RepoAnalysis() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [repo, setRepo] = useState<RepoInfo | null>(null);
  const [dependencies, setDependencies] = useState<DependenciesGraph | null>(null);
  const [fileTree, setFileTree] = useState<FileNode | null>(null);
  const [injectionPoints, setInjectionPoints] = useState<InjectionPoint[]>([]);
  const [insights, setInsights] = useState<CodebaseInsight | null>(null);
  const [loading, setLoading] = useState(true);
  const [mapMode, setMapMode] = useState<MapMode>('full');
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(null);
  const [selectedGraphNode, setSelectedGraphNode] = useState<DependencyNode | null>(null);
  const [graphLayout, setGraphLayout] = useState<DependencyGraphLayout>('hierarchical');
  const [mapSearchTerm, setMapSearchTerm] = useState('');

  // Repo connection state
  const [connectedRepo, setConnectedRepo] = useState<RepoConnection | null>(null);

  // Fetch data based on connection status
  const fetchData = useCallback(async () => {
    try {
      const healthData = await healthApi.check();
      setHealth(healthData);

      if (connectedRepo) {
        // Fetch all data from connected repo
        const [repoData, depsData, filesData, pointsData, insightsData] = await Promise.all([
          repoApi.getConnected(connectedRepo.id).catch(() => null),
          repoApi.getConnectedDependencies(connectedRepo.id).catch(() => null),
          repoApi.getFiles(connectedRepo.id, 2).catch(() => null),
          repoApi.getInjectionPoints(connectedRepo.id, 5).catch(() => null),
          repoApi.getInsights(connectedRepo.id).catch(() => null),
        ]);
        setRepo(repoData);
        setDependencies(depsData);
        if (filesData?.root) setFileTree(filesData.root);
        if (pointsData?.points) setInjectionPoints(pointsData.points);
        if (insightsData) setInsights(insightsData);
      } else {
        // Use ghostfolio-agent's own repo as fallback
        const [repoData, depsData] = await Promise.all([
          repoApi.get().catch(() => null),
          repoApi.getDependencies().catch(() => null),
        ]);
        setRepo(repoData);
        setDependencies(depsData);
        setFileTree(null);
        setInjectionPoints([]);
        setInsights(null);
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
    setSelectedFile(null);
  };

  const handleDisconnect = () => {
    setConnectedRepo(null);
    setRepo(null);
    setDependencies(null);
    setFileTree(null);
    setInjectionPoints([]);
    setInsights(null);
    setLoading(true);
    setSelectedFile(null);
    setSelectedGraphNode(null);
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
        {fileTree ? (
          <FileTreeItem
            node={fileTree}
            selectedPath={selectedFile?.path || null}
            onSelect={setSelectedFile}
          />
        ) : (
          <div className="text-slate-500 text-sm px-2 py-4">
            {connectedRepo ? 'Loading files...' : 'Connect a repository to view files'}
          </div>
        )}
      </Sidebar>

      <main className="flex-1 flex flex-col bg-background-dark overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-background-dark/95 backdrop-blur-sm border-b border-surface-border px-6 py-4 flex justify-between items-center">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-slate-400 text-sm">Repo Analysis</span>
              <span className="text-slate-500">/</span>
              <span className="text-primary font-mono text-sm">
                {connectedRepo ? connectedRepo.name : 'No repository connected'}
              </span>
              {connectedRepo && (
                <span className="ml-2 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs">
                  Connected
                </span>
              )}
            </div>
            <h1 className="text-xl font-bold text-white">Connect &amp; analyze</h1>
          </div>
          {repo && (
            <div className="flex gap-2 items-center text-xs text-slate-400">
              <span>{repo.endpoints} endpoints</span>
              <span>·</span>
              <span>{repo.services} modules</span>
            </div>
          )}
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
            <div className="flex flex-col gap-4">
              {/* Injection Points */}
              <div className="bg-surface-darker rounded-xl border border-surface-border overflow-hidden shadow-sm flex-1 min-h-[400px]">
                <div className="flex items-center justify-between px-4 py-2 bg-surface-dark border-b border-surface-border">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                      Detected Injection Points
                    </span>
                    <span className="bg-primary/20 text-primary text-[10px] px-1.5 rounded">
                      {injectionPoints.length} Found
                    </span>
                  </div>
                  {injectionPoints.length > 0 && (
                    <span className="text-xs text-slate-500">{injectionPoints[0]?.file_path}</span>
                  )}
                </div>
                <div className="p-4 font-mono text-sm leading-6 text-slate-400 overflow-x-auto">
                  {injectionPoints.length > 0 ? (
                    injectionPoints.slice(0, 3).map((point, idx) => (
                      <div key={idx} className="mb-4">
                        <div className="text-xs text-slate-500 mb-1">
                          {point.route_type} {point.route_path}
                        </div>
                        {point.code_snippet.map((line, lineIdx) => (
                          <div key={lineIdx} className="flex">
                            <span className="w-8 text-slate-500 select-none">{point.line_number + lineIdx - 2}</span>
                            <span className={lineIdx >= 2 && lineIdx <= 5 ? 'text-primary' : ''}>{line}</span>
                          </div>
                        ))}
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-500">
                      {connectedRepo ? 'Scanning for injection points...' : 'Connect a repository to detect injection points'}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Insight + Health + Mapper */}
            <div className="flex flex-col gap-6">
              <div className="p-5 rounded-xl bg-surface-dark border border-surface-border">
                <div className="flex items-start gap-4">
                  <div className="p-2 rounded-lg bg-primary/20 text-primary">
                    <span className="material-symbols-outlined text-2xl">auto_fix_high</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-lg font-bold text-white mb-1">Codebase Insight</h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      {insights?.summary || (connectedRepo
                        ? 'Analyzing codebase structure...'
                        : 'Connect a repository to get insights')}
                    </p>
                    {insights?.entry_points && insights.entry_points.length > 0 && (
                      <div className="mt-2">
                        <span className="text-xs text-slate-500">Entry points: </span>
                        {insights.entry_points.map((ep, i) => (
                          <span key={i} className="text-slate-300 text-xs font-mono mr-2">{ep}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* System Health - compact */}
              {health?.dependencies && (
                <div className="bg-surface-dark rounded-xl border border-surface-border p-3">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2">System Health</h4>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                    {Object.entries(health.dependencies).map(([key, value]) => (
                      <span key={key} className={value ? 'text-emerald-400' : 'text-red-400'}>
                        {key.replace(/_/g, ' ')}: {value ? 'OK' : 'Unavailable'}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Dependency Mapper - React Flow with layout and drill-down */}
              <div className="flex-1 rounded-xl bg-surface-dark border border-surface-border flex flex-col overflow-hidden min-h-[300px] relative">
                <div className="px-5 py-3 border-b border-surface-border flex flex-wrap items-center justify-between gap-2 bg-surface-darker">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-300">Dependency Mapper</h3>
                    <span className="size-2 rounded-full bg-primary" />
                    <span className="text-xs text-slate-500">Agent</span>
                    <span className="size-2 rounded-full bg-indigo-400 ml-2" />
                    <span className="text-xs text-slate-500">Services</span>
                    <span className="size-2 rounded-full bg-emerald-400 ml-2" />
                    <span className="text-xs text-slate-500">DB</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="text"
                      placeholder="Search modules..."
                      value={mapSearchTerm}
                      onChange={(e) => setMapSearchTerm(e.target.value)}
                      className="w-36 bg-surface-dark border border-surface-border rounded px-2 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-primary/50"
                    />
                    {(['hierarchical', 'horizontal', 'radial'] as const).map((layout) => (
                      <button
                        key={layout}
                        onClick={() => setGraphLayout(layout)}
                        className={`px-2 py-1 text-xs rounded transition-colors capitalize ${
                          graphLayout === layout ? 'bg-primary/20 text-primary border border-primary/30' : 'text-slate-400 hover:text-white border border-transparent'
                        }`}
                      >
                        {layout}
                      </button>
                    ))}
                    <button
                      onClick={() => setMapMode('full')}
                      className={`px-2 py-1 text-xs rounded transition-colors ${mapMode === 'full' ? 'bg-primary/20 text-primary border border-primary/30' : 'text-slate-400 hover:text-white'}`}
                    >
                      Full
                    </button>
                    <button
                      onClick={() => setMapMode('services')}
                      className={`px-2 py-1 text-xs rounded transition-colors ${mapMode === 'services' ? 'bg-primary/20 text-primary border border-primary/30' : 'text-slate-400 hover:text-white'}`}
                    >
                      Services
                    </button>
                  </div>
                </div>

                <div className="relative flex-1 min-h-[280px]">
                  {dependencies ? (
                    <DependencyGraph
                      nodes={filteredNodes}
                      edges={filteredEdges}
                      layout={graphLayout}
                      onNodeSelect={setSelectedGraphNode}
                      selectedNodeId={selectedGraphNode?.id ?? null}
                      searchTerm={mapSearchTerm}
                      className="min-h-[280px]"
                    />
                  ) : (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-surface-dark/50 p-4 text-center">
                      <span className="text-slate-400 text-sm">
                        {connectedRepo ? 'Loading dependency graph...' : 'Connect a repository to view dependencies'}
                      </span>
                    </div>
                  )}
                  {selectedGraphNode && dependencies && (
                    <ModuleDetails
                      node={selectedGraphNode}
                      dependencies={{ nodes: filteredNodes, edges: filteredEdges }}
                      onClose={() => setSelectedGraphNode(null)}
                    />
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
