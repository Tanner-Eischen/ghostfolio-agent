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
import { computeFileStats } from '../components/RepoStats';
import { RepoChat } from '../components/RepoChat';
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

// Route type badge for Integration Points
function RouteTypeBadge({ type }: { type: string }) {
  const upperType = type.toUpperCase();
  const config: Record<string, { color: string; icon: string }> = {
    GET: { color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', icon: 'download' },
    POST: { color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', icon: 'upload' },
    PUT: { color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', icon: 'edit' },
    PATCH: { color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', icon: 'edit' },
    DELETE: { color: 'bg-red-500/20 text-red-400 border-red-500/30', icon: 'delete' },
  };

  const frameworkConfig: Record<string, { color: string; icon: string }> = {
    FASTAPI: { color: 'bg-primary/20 text-primary border-primary/30', icon: 'bolt' },
    FLASK: { color: 'bg-green-500/20 text-green-400 border-green-500/30', icon: 'science' },
    EXPRESS: { color: 'bg-slate-500/20 text-slate-300 border-slate-500/30', icon: 'api' },
  };

  // Check if it's an HTTP method or framework
  const isHttpMethod = upperType in config;
  const style = isHttpMethod
    ? config[upperType]
    : frameworkConfig[upperType] || { color: 'bg-slate-500/20 text-slate-400 border-slate-500/30', icon: 'api' };

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono border ${style.color}`}
    >
      <span className="material-symbols-outlined text-xs">{style.icon}</span>
      {upperType}
    </span>
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
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [fileContentLoading, setFileContentLoading] = useState(false);
  const [selectedGraphNode, setSelectedGraphNode] = useState<DependencyNode | null>(null);
  const [graphLayout, setGraphLayout] = useState<DependencyGraphLayout>('hierarchical');
  const [mapSearchTerm, setMapSearchTerm] = useState('');

  // Repo connection state
  const [connectedRepo, setConnectedRepo] = useState<RepoConnection | null>(null);

  // Fetch data based on connection status
  const fetchData = useCallback(async (repo: RepoConnection | null) => {
    console.log('=== FETCH DATA CALLED === repo:', repo?.id, repo?.name);
    try {
      const healthData = await healthApi.check();
      setHealth(healthData);

      if (repo) {
        console.log('Fetching CONNECTED repo data for:', repo.id);
        // Fetch all data from connected repo
        const [repoData, depsData, filesData, pointsData, insightsData] = await Promise.all([
          repoApi.getConnected(repo.id).catch(() => null),
          repoApi.getConnectedDependencies(repo.id).catch(() => null),
          repoApi.getFiles(repo.id, 2).catch(() => null),
          repoApi.getInjectionPoints(repo.id, 5).catch(() => null),
          repoApi.getInsights(repo.id).catch(() => null),
        ]);
        console.log('CONNECTED depsData:', depsData?.nodes?.length, 'nodes,', depsData?.edges?.length, 'edges');
        console.log('CONNECTED node IDs:', depsData?.nodes?.map(n => n.id));
        console.log('CONNECTED edge sources:', depsData?.edges?.map(e => e.source));
        console.log('CONNECTED edge targets:', depsData?.edges?.map(e => e.target));
        setRepo(repoData);
        setDependencies(depsData);
        if (filesData?.root) setFileTree(filesData.root);
        if (pointsData?.points) setInjectionPoints(pointsData.points);
        if (insightsData) setInsights(insightsData);
      } else {
        console.log('Fetching FALLBACK (ghostfolio-agent) repo data');
        // Use ghostfolio-agent's own repo as fallback
        const [repoData, depsData] = await Promise.all([
          repoApi.get().catch(() => null),
          repoApi.getDependencies().catch(() => null),
        ]);
        console.log('FALLBACK depsData:', depsData?.nodes?.length, 'nodes,', depsData?.edges?.length, 'edges');
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
  }, []);

  // Load existing connections on mount, then fetch data
  useEffect(() => {
    async function loadConnections() {
      try {
        const response = await repoApi.listConnections();
        console.log('=== LOAD CONNECTIONS ===', response.connections?.length, 'connections');
        if (response.connections && response.connections.length > 0) {
          const connection = response.connections[0];
          console.log('Setting connectedRepo to:', connection.id, connection.name);
          setConnectedRepo(connection);
          // Fetch data immediately with the connection (don't wait for re-render)
          fetchData(connection);
        } else {
          // No connections, fetch fallback data
          fetchData(null);
        }
      } catch (error) {
        console.error('Failed to load connections:', error);
        fetchData(null);
      }
    }
    loadConnections();
  }, [fetchData]);

  // Load file content when a file is selected in the explorer
  useEffect(() => {
    if (!connectedRepo || !selectedFile || selectedFile.type !== 'file') {
      setFileContent(null);
      return;
    }
    let cancelled = false;
    setFileContentLoading(true);
    setFileContent(null);
    repoApi
      .getFileContent(connectedRepo.id, selectedFile.path)
      .then((res) => {
        if (!cancelled) {
          setFileContent(res.content);
        }
      })
      .catch(() => {
        if (!cancelled) setFileContent(null);
      })
      .finally(() => {
        if (!cancelled) setFileContentLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [connectedRepo?.id, selectedFile?.path, selectedFile?.type]);

  const handleConnected = (connection: RepoConnection) => {
    setConnectedRepo(connection);
    setLoading(true);
    setSelectedFile(null);
    // Fetch data for the newly connected repo
    fetchData(connection);
  };

  const handleDisconnect = async () => {
    // Clear connection on backend
    if (connectedRepo) {
      try {
        await repoApi.disconnect(connectedRepo.id);
      } catch (e) {
        console.error('Failed to disconnect on backend:', e);
      }
    }
    // Clear local state
    setConnectedRepo(null);
    setRepo(null);
    setDependencies(null);
    setFileTree(null);
    setInjectionPoints([]);
    setInsights(null);
    setLoading(false);  // Not loading anymore - show the connect form
    setSelectedFile(null);
    setFileContent(null);
    setSelectedGraphNode(null);
  };

  // Debug: log raw data from API
  console.log('RAW API data:', {
    nodes: dependencies?.nodes.length,
    edges: dependencies?.edges.length,
    nodeIds: dependencies?.nodes.map(n => n.id),
    edgeSources: dependencies?.edges.map(e => e.source),
    edgeTargets: dependencies?.edges.map(e => e.target),
  });

  const filteredNodes = dependencies?.nodes.filter(node => {
    if (mapMode === 'services') {
      return node.type !== 'database';
    }
    return true;
  }) || [];

  const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
  console.log('Filtered node IDs:', Array.from(filteredNodeIds));

  // Debug: log why edges are being filtered
  const filteredEdges = dependencies?.edges.filter(edge => {
    const hasSource = filteredNodeIds.has(edge.source);
    const hasTarget = filteredNodeIds.has(edge.target);
    if (!hasSource || !hasTarget) {
      console.log('Edge filtered out:', edge.source, '->', edge.target, { hasSource, hasTarget });
    }
    return hasSource && hasTarget;
  }) || [];

  console.log('Filtered:', filteredNodes.length, 'nodes,', filteredEdges.length, 'edges', 'mode:', mapMode);

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
        {/* Consolidated Header */}
        <div className="sticky top-0 z-10 bg-background-dark/95 backdrop-blur-sm border-b border-surface-border px-6 py-4">
          {connectedRepo ? (
            /* Connected state: Show repo info inline */
            (() => {
              const fileStats = fileTree ? computeFileStats(fileTree) : null;
              const topExtensions = fileStats
                ? Object.entries(fileStats.byExtension).sort((a, b) => b[1] - a[1]).slice(0, 4)
                : [];
              return (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400">
                      <span className="material-symbols-outlined text-xl">folder_open</span>
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h1 className="text-lg font-bold text-white">{connectedRepo.name}</h1>
                        <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-medium">
                          Connected
                        </span>
                      </div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-slate-500 font-mono truncate max-w-xs">
                          {connectedRepo.source}
                        </span>
                        {connectedRepo.branch && (
                          <span className="text-xs text-slate-500">
                            Branch: <span className="text-primary">{connectedRepo.branch}</span>
                          </span>
                        )}
                        {repo && (
                          <>
                            <span className="text-slate-600">·</span>
                            <span className="text-xs text-slate-400">{repo.endpoints} endpoints</span>
                            <span className="text-xs text-slate-400">{repo.services} modules</span>
                          </>
                        )}
                      </div>
                      {/* Quick Stats inline */}
                      {fileStats && (
                        <div className="flex items-center gap-3 mt-1.5">
                          <span className="text-[10px] text-slate-500">
                            {fileStats.totalFiles} files · {fileStats.totalDirs} dirs
                          </span>
                          {topExtensions.length > 0 && (
                            <div className="flex items-center gap-1.5">
                              {topExtensions.map(([ext, count]) => (
                                <span
                                  key={ext}
                                  className="px-1.5 py-0.5 rounded text-[9px] bg-surface-dark text-slate-400 border border-surface-border"
                                >
                                  {ext.toUpperCase()} {count}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {/* System Health */}
                    {health?.dependencies && (
                      <div className="flex flex-wrap gap-x-3 text-[10px]">
                        {Object.entries(health.dependencies).map(([key, value]) => (
                          <span key={key} className={`flex items-center gap-1 ${value ? 'text-emerald-400' : 'text-red-400'}`}>
                            <span className={`size-1.5 rounded-full ${value ? 'bg-emerald-400' : 'bg-red-400'}`} />
                            {key.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    )}
                    <button
                      onClick={handleDisconnect}
                      className="text-xs text-red-400 hover:text-red-300 border border-red-500/30 hover:border-red-500/50 rounded px-3 py-1.5 transition-colors flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-sm">link_off</span>
                      Disconnect
                    </button>
                  </div>
                </div>
              );
            })()
          ) : (
            /* Not connected: Show connect form inline */
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-slate-400 text-sm">Repo Analysis</span>
                <span className="text-slate-500">/</span>
                <span className="text-slate-500 text-sm">No repository connected</span>
              </div>
              <RepoConnector
                onConnected={handleConnected}
                onDisconnect={handleDisconnect}
                connectedRepo={connectedRepo}
              />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Show RepoConnector in content area only when not connected (it's already in header when not connected) */}
          {connectedRepo && (
            <></>
          )}

          {/* When a file is selected: code viewer (file explorer wired to code) */}
          {selectedFile?.type === 'file' && connectedRepo ? (
            <div className="flex flex-col gap-3 flex-1 min-h-0">
              <div className="flex items-center justify-between px-3 py-2 bg-surface-dark rounded-lg border border-surface-border">
                <span className="font-mono text-sm text-primary truncate">{selectedFile.path}</span>
                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  className="text-xs text-slate-400 hover:text-white shrink-0 ml-2"
                  aria-label="Close file view"
                >
                  <span className="material-symbols-outlined text-lg">close</span>
                </button>
              </div>
              <div className="flex-1 min-h-[320px] rounded-xl border border-surface-border overflow-hidden bg-surface-darker flex flex-col">
                {fileContentLoading ? (
                  <div className="flex items-center justify-center flex-1 text-slate-500 text-sm">Loading...</div>
                ) : fileContent !== null ? (
                  <pre className="p-4 font-mono text-xs leading-5 text-slate-300 overflow-auto flex-1 m-0">
                    {fileContent.split('\n').map((line, i) => (
                      <div key={i} className="flex">
                        <span className="w-10 shrink-0 select-none text-slate-500 text-right pr-3">{i + 1}</span>
                        <span className="break-all">{line || ' '}</span>
                      </div>
                    ))}
                  </pre>
                ) : (
                  <div className="flex items-center justify-center flex-1 text-slate-500 text-sm">Could not load file</div>
                )}
              </div>
              {/* Compact integration points strip */}
              {injectionPoints.length > 0 && (
                <div className="rounded-xl border border-surface-border overflow-hidden bg-surface-dark max-h-[200px] flex flex-col">
                  <div className="px-3 py-1.5 border-b border-surface-border flex items-center gap-2 shrink-0">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Integration points</span>
                    <span className="bg-primary/20 text-primary text-[10px] px-1.5 rounded">{injectionPoints.length}</span>
                  </div>
                  <div className="overflow-y-auto p-2 font-mono text-[11px] text-slate-400">
                    {injectionPoints.slice(0, 8).map((point, idx) => (
                      <div key={idx} className="flex items-baseline gap-2 py-0.5">
                        <RouteTypeBadge type={point.route_type} />
                        <span className="text-slate-500 shrink-0">{point.route_path}</span>
                        <span className="truncate text-slate-600">{point.file_path}:{point.line_number}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
          <div className="space-y-6">
            {/* Top row: Integration Points + Repo Chat (flush heights) */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              {/* Integration Points: cards with badges */}
              <div className="bg-surface-darker rounded-xl border border-surface-border overflow-hidden flex flex-col">
                <div className="flex items-center justify-between px-4 py-3 bg-surface-dark border-b border-surface-border shrink-0">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-slate-200">
                        Integration Points
                      </span>
                      <span className="bg-primary/20 text-primary text-[10px] px-1.5 rounded">
                        {injectionPoints.length}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Endpoints accepting external input (API routes, webhooks, handlers)
                    </p>
                  </div>
                </div>
                <div className="p-3 space-y-2 overflow-y-auto h-[300px]">
                  {injectionPoints.length > 0 ? (
                    injectionPoints.slice(0, 6).map((point, idx) => (
                      <div
                        key={idx}
                        className="bg-surface-dark rounded-lg p-3 border border-surface-border hover:border-primary/30 transition-colors"
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <RouteTypeBadge type={point.route_type} />
                          <span className="font-mono text-sm text-slate-200">{point.route_path}</span>
                        </div>
                        <div className="text-[11px] text-slate-500 mb-2">
                          {point.file_path}:{point.line_number}
                        </div>
                        {point.code_snippet && point.code_snippet.length > 0 && (
                          <pre className="font-mono text-[10px] text-slate-400 bg-surface-darker rounded p-2 overflow-x-auto">
                            {point.code_snippet.slice(0, 3).map((line, lineIdx) => (
                              <div key={lineIdx} className="flex">
                                <span className="w-5 text-slate-600 select-none shrink-0">
                                  {point.line_number + lineIdx - 1}
                                </span>
                                <span className={lineIdx === 1 ? 'text-primary' : ''}>{line}</span>
                              </div>
                            ))}
                          </pre>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-500 text-sm py-4 text-center">
                      {connectedRepo ? 'Scanning...' : 'Connect a repository to detect integration points'}
                    </div>
                  )}
                </div>
              </div>

              {/* Repo Chat - Interactive chat about the codebase */}
              {connectedRepo ? (
                <div className="rounded-xl bg-surface-dark border border-surface-border overflow-hidden h-[370px] flex flex-col">
                  <RepoChat
                    repoId={connectedRepo.id}
                    repoName={connectedRepo.name}
                    initialInsight={insights?.summary}
                  />
                </div>
              ) : (
                <div className="p-5 rounded-xl bg-surface-dark border border-surface-border h-[370px] flex items-center justify-center">
                  <div className="text-center">
                    <div className="p-3 rounded-lg bg-primary/20 text-primary inline-block mb-3">
                      <span className="material-symbols-outlined text-3xl">chat</span>
                    </div>
                    <h3 className="text-lg font-bold text-white mb-1">Repo Chat</h3>
                    <p className="text-sm text-slate-400">
                      Connect a repository to start chatting about the codebase
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Dependency Mapper - Full width */}
            <div className="rounded-xl bg-surface-dark border border-surface-border flex flex-col overflow-hidden min-h-[400px] relative">
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

              <div className="relative h-[350px]">
                {dependencies ? (
                  <DependencyGraph
                    nodes={filteredNodes}
                    edges={filteredEdges}
                    layout={graphLayout}
                    onNodeSelect={setSelectedGraphNode}
                    selectedNodeId={selectedGraphNode?.id ?? null}
                    searchTerm={mapSearchTerm}
                    className="h-full w-full"
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
          )}
        </div>
      </main>
    </div>
  );
}
