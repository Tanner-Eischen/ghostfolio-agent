const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

async function fetchApi<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {}, signal } = options;

  const config: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    signal,
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
  repo_id?: string;
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
  tool_outputs: unknown[];  // Tool execution results
  session_id: string;
  verification_passed: boolean;
  requires_escalation: boolean;
  processing_time_ms: number;
  /** LangSmith run ID; use as message_id when submitting feedback so it attaches to the trace */
  run_id?: string | null;
  /** URL to view this run in LangSmith */
  trace_url?: string | null;
}

export const chatApi = {
  send: (request: ChatRequest, signal?: AbortSignal) => fetchApi<ChatResponse>('/chat', { method: 'POST', body: request, signal }),
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
  type: 'agent' | 'service' | 'database' | 'api' | string;
  icon: string;
  color: 'primary' | 'indigo' | 'emerald' | 'slate' | string;
  file_count?: number;
  line_count?: number;
  external_deps?: string[];
  has_circular?: boolean;
}

export interface DependencyEdge {
  source: string;
  target: string;
  label?: string;
  weight?: number;
  import_types?: string[];
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
  getFileContent: (repoId: string, path: string) =>
    fetchApi<{ path: string; content: string }>(`/repo/${repoId}/file?path=${encodeURIComponent(path)}`),
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
  source?: 'core' | 'generated';
}

export interface ToolRegistrationRequest {
  name: string;
  description: string;
  generated_code: string;
  source_suggestion_id?: string;
  parameters?: Record<string, unknown>;
}

export interface ToolRegistrationResponse {
  success: boolean;
  message: string;
  tool_name: string | null;
  tool_id: string | null;
  warnings: string[];
  agent_reloaded: boolean;
}

export const toolsApi = {
  list: () => fetchApi<Tool[]>('/tools'),
  get: (toolName: string) => fetchApi<ToolDetail>(`/tools/${toolName}`),
  execute: (toolName: string, params: Record<string, unknown>, repoId?: string) =>
    fetchApi<ToolExecuteResponse>(`/tools/${toolName}/execute`, {
      method: 'POST',
      body: { parameters: params, repo_id: repoId },
    }),
  create: (tool: Omit<Tool, 'id'>) => fetchApi<Tool>('/tools', { method: 'POST', body: tool }),
  register: (request: ToolRegistrationRequest) =>
    fetchApi<ToolRegistrationResponse>('/tools/register', { method: 'POST', body: request }),
  deleteGenerated: (toolName: string) =>
    fetchApi<{ success: boolean; message: string }>(`/tools/generated/${toolName}`, { method: 'DELETE' }),
};

// Tool Detail types
export interface ToolDetail {
  id: string;
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  status: string;
  args_schema: Record<string, unknown> | null;
  execution_count: number;
}

// Tool Execute types
export interface ToolExecuteResponse {
  tool_name: string;
  success: boolean;
  result: unknown;
  execution_time_ms: number;
  repo_context: string | null;
}

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
  /** Recorded cost for this run when linked via run_id; null if not available */
  cost_usd: number | null;
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

export interface EvalCriterionResult {
  id: string;
  description: string;
  check_type: string;
  expected: unknown;
  actual: unknown;
  passed: boolean;
  error?: string;
}

export interface ToolCallDetail {
  tool: string;
  input?: Record<string, unknown>;
  output?: unknown;
}

export interface EvalResult {
  case_id: string;
  category: string;
  passed: boolean;
  score: number;
  duration_ms: number;
  error?: string;
  // Full details for expandable UI
  input?: string;
  response?: string;
  tool_calls?: string[];
  tool_call_details?: ToolCallDetail[];
  tool_outputs?: unknown[];
  confidence?: number;
  criteria_results?: EvalCriterionResult[];
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
  runAll: (config?: Partial<VerificationConfig>) =>
    fetchApi<{ run_id: string }>('/evals/run', {
      method: 'POST',
      body: config ? { config } : {},
    }),
  getResults: () => fetchApi<{ summary: EvalSummary; results: EvalResult[] }>('/evals/results'),
};

// Finances API (new)
export interface UsageByModel {
  requests: number;
  tokens: number;
  cost: number;
}

export interface UsageStats {
  total_cost: number;
  total_tokens: number;
  requests_count: number;
  avg_cost_per_request: number;
  by_model: Record<string, UsageByModel>;
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

// Tool Suggestions API (Page 2 - Tool Library)
export interface ToolSuggestionParameter {
  name: string;
  type: string;
  description: string;
  required: boolean;
}

export interface ToolSuggestion {
  id: string;
  name: string;
  description: string;
  source_type: string;
  source_file: string | null;
  source_line: number | null;
  parameters: ToolSuggestionParameter[];
  priority: string;
  reasoning: string;
}

export interface ToolSuggestionsResponse {
  repo_id: string;
  repo_name: string;
  suggestions: ToolSuggestion[];
  total_suggestions: number;
  analysis_summary: string;
}

export interface GeneratedToolResponse {
  id: string;
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  generated_code: string;
  status: string;
  source_suggestion_id: string;
}

export interface GenerateToolRequest {
  suggestion_id: string;
  custom_name?: string;
  custom_description?: string;
}

export const toolSuggestionsApi = {
  getForRepo: (repoId: string) =>
    fetchApi<ToolSuggestionsResponse>(`/repo/${repoId}/tool-suggestions`),
  generateTool: (repoId: string, request: GenerateToolRequest) =>
    fetchApi<GeneratedToolResponse>(`/repo/${repoId}/generate-tool`, { method: 'POST', body: request }),
};

// Feedback API
export interface FeedbackRequest {
  message_id: string;
  session_id: string;
  rating: -1 | 1 | 2 | 3 | 4 | 5;  // -1=thumbs down, 1=thumbs up, 2-5=stars
  comment?: string;
}

export interface FeedbackResponse {
  status: string;
  message_id: string;
  logged: boolean;
}

export const feedbackApi = {
  send: (request: FeedbackRequest) =>
    fetchApi<FeedbackResponse>('/feedback', { method: 'POST', body: request }),
};
