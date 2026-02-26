const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
}

async function fetchApi<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {} } = options;

  const config: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Health API
export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  agent_ready: boolean;
  dependencies: {
    openai: boolean;
    langsmith: boolean;
    ghostfolio: boolean;
    tracing_enabled: boolean;
  };
}

export const healthApi = {
  check: () => fetchApi<HealthResponse>('/health'),
};

// Chat API
export interface ChatRequest {
  message: string;
  session_id?: string;
  user_id?: string;
}

export interface ChatResponse {
  response: string;
  confidence: number;
  confidence_level: string;
  tool_calls: Array<{
    name: string;
    args: Record<string, unknown>;
    result?: unknown;
  }>;
  session_id: string;
  verification_passed: boolean;
  requires_escalation: boolean;
  processing_time_ms: number;
}

export const chatApi = {
  send: (request: ChatRequest) => fetchApi<ChatResponse>('/chat', { method: 'POST', body: request }),
  getTools: () => fetchApi<Array<{ name: string; description: string }>>('/chat/tools'),
};

// Portfolio API
export interface PortfolioSummary {
  total_value: number | null;
  performance_ytd: number | null;
  holdings_count: number;
  top_holdings: Array<{
    symbol: string;
    value: number;
    allocation: number;
  }>;
  diversification_score: number | null;
  risk_level: string | null;
}

export const portfolioApi = {
  getSummary: () => fetchApi<PortfolioSummary>('/portfolio'),
  getRisk: () => fetchApi<Record<string, unknown>>('/portfolio/risk'),
};

// Sessions API
export interface SessionHistory {
  session_id: string;
  message_count: number;
  messages: Array<{
    role: 'user' | 'assistant';
    content: string;
  }>;
}

export const sessionsApi = {
  get: (sessionId: string) => fetchApi<SessionHistory>(`/sessions/${sessionId}`),
  clear: (sessionId: string) => fetchApi<{ cleared: boolean }>(`/sessions/${sessionId}`, { method: 'DELETE' }),
};

// Market API
export const marketApi = {
  get: (symbol: string) => fetchApi<Record<string, unknown>>(`/market/${symbol}`),
};

// Repo API (new)
export interface RepoInfo {
  name: string;
  version: string;
  status: string;
  endpoints: number;
  services: number;
  tool_hooks: number;
}

export interface DependencyNode {
  id: string;
  name: string;
  type: 'agent' | 'service' | 'database' | 'api';
  icon: string;
  color: 'primary' | 'indigo' | 'emerald' | 'slate';
}

export interface DependencyEdge {
  source: string;
  target: string;
  label?: string;
}

export interface DependenciesGraph {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
}

// Repo Connection types
export interface RepoConnectionRequest {
  source: string;
  branch?: string;
  name?: string;
}

export interface RepoConnection {
  id: string;
  name: string;
  source: string;
  branch?: string;
  path: string;
  connected_at: string;
  is_local: boolean;
}

export interface RepoConnectionResponse {
  success: boolean;
  connection?: RepoConnection;
  error?: string;
}

export interface ConnectionsListResponse {
  connections: RepoConnection[];
}

export const repoApi = {
  // Get ghostfolio-agent's own repo info (legacy endpoint)
  get: () => fetchApi<RepoInfo>('/repo'),
  getDependencies: () => fetchApi<DependenciesGraph>('/repo/dependencies'),

  // New connection-based endpoints
  connect: (request: RepoConnectionRequest) =>
    fetchApi<RepoConnectionResponse>('/repo/connect', { method: 'POST', body: request }),
  disconnect: (repoId: string) =>
    fetchApi<{ success: boolean }>(`/repo/${repoId}`, { method: 'DELETE' }),
  listConnections: () =>
    fetchApi<ConnectionsListResponse>('/repo/connections'),

  // Connected repo analysis
  getConnected: (repoId: string) =>
    fetchApi<RepoInfo>(`/repo/${repoId}`),
  getConnectedDependencies: (repoId: string) =>
    fetchApi<DependenciesGraph>(`/repo/${repoId}/dependencies`),

  // Drill-down into a specific module
  getModuleDependencies: (repoId: string, moduleName: string) =>
    fetchApi<DependenciesGraph>(`/repo/${repoId}/dependencies/${moduleName}`),

  // File explorer and code preview
  getFiles: (repoId: string, maxDepth?: number) =>
    fetchApi<FileTreeResponse>(`/repo/${repoId}/files${maxDepth ? `?max_depth=${maxDepth}` : ''}`),
  getInjectionPoints: (repoId: string, limit?: number) =>
    fetchApi<InjectionPointsResponse>(`/repo/${repoId}/injection-points${limit ? `?limit=${limit}` : ''}`),
  getInsights: (repoId: string) =>
    fetchApi<CodebaseInsight>(`/repo/${repoId}/insights`),
};

// File Explorer types
export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileNode[];
}

export interface FileTreeResponse {
  root: FileNode;
}

// Injection Points types
export interface InjectionPoint {
  file_path: string;
  line_number: number;
  code_snippet: string[];
  route_type: string;
  route_path: string;
}

export interface InjectionPointsResponse {
  points: InjectionPoint[];
  total: number;
}

// Codebase Insights types
export interface CodebaseInsight {
  summary: string;
  entry_points: string[];
  architecture: string;
  recommendations: string[];
}
    fetchApi<DependenciesGraph>(`/repo/${repoId}/dependencies/${moduleName}`),
};

// Strategy API (new)
export interface StrategyConfig {
  framework: string;
  model: string;
  temperature: number;
  json_mode: boolean;
  stream_responses: boolean;
  contribution_path: string;
}

export interface StrategyRecommendation {
  framework: string;
  reason: string;
  recommended: boolean;
}

export const strategyApi = {
  get: () => fetchApi<StrategyConfig>('/strategy'),
  save: (config: Partial<StrategyConfig>) =>
    fetchApi<StrategyConfig>('/strategy', { method: 'POST', body: config }),
  getRecommendations: () => fetchApi<StrategyRecommendation[]>('/strategy/recommendations'),
};

// Tools API (new)
export interface Tool {
  id: string;
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  status: 'active' | 'beta' | 'disabled';
}

export const toolsApi = {
  list: () => fetchApi<Tool[]>('/tools'),
  create: (tool: Omit<Tool, 'id'>) => fetchApi<Tool>('/tools', { method: 'POST', body: tool }),
};

// Verification API (new)
export interface VerificationConfig {
  fact_checking: boolean;
  hallucination_detection: boolean;
  confidence_scoring: boolean;
  hitl_enabled: boolean;
  confidence_threshold: number;
}

export const verificationApi = {
  getConfig: () => fetchApi<VerificationConfig>('/verification/config'),
  saveConfig: (config: Partial<VerificationConfig>) =>
    fetchApi<VerificationConfig>('/verification/config', { method: 'PUT', body: config }),
};

// Traces API (new)
export interface Trace {
  id: string;
  timestamp: string;
  duration_ms: number;
  tokens_used: number;
  status: 'success' | 'error';
  tool_calls: string[];
}

export interface TraceDetail extends Trace {
  steps: Array<{
    name: string;
    input: unknown;
    output: unknown;
    duration_ms: number;
  }>;
}

export const tracesApi = {
  list: () => fetchApi<Trace[]>('/traces'),
  get: (traceId: string) => fetchApi<TraceDetail>(`/traces/${traceId}`),
};

// Evals API (new)
export interface EvalCase {
  id: string;
  name: string;
  description: string;
  category: string;
}

export interface EvalResult {
  case_id: string;
  passed: boolean;
  score: number;
  duration_ms: number;
  error?: string;
}

export interface EvalSummary {
  total_cases: number;
  passed: number;
  failed: number;
  pass_rate: number;
  avg_latency_ms: number;
  hallucination_rate: number;
}

export const evalsApi = {
  getCases: () => fetchApi<EvalCase[]>('/evals/cases'),
  runAll: () => fetchApi<{ run_id: string }>('/evals/run', { method: 'POST' }),
  getResults: () => fetchApi<{ summary: EvalSummary; results: EvalResult[] }>('/evals/results'),
};

// Finances API (new)
export interface UsageStats {
  total_cost: number;
  total_tokens: number;
  requests_count: number;
  avg_cost_per_request: number;
}

export interface CostProjections {
  daily_cost: number;
  monthly_cost: number;
  projected_annual: number;
  cost_breakdown: {
    input_tokens: number;
    output_tokens: number;
  };
}

export const financesApi = {
  getUsage: () => fetchApi<UsageStats>('/finances/usage'),
  getProjections: (queriesPerDay?: number) =>
    fetchApi<CostProjections>(`/finances/projections${queriesPerDay ? `?queries_per_day=${queriesPerDay}` : ''}`),
};
