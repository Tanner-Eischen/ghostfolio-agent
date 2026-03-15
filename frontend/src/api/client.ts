const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

/** localStorage key for stateless Ghostfolio token (user-provided, sent per request). */
export const GHOSTFOLIO_TOKEN_STORAGE_KEY = 'ghostfolio_access_token';
/** Optional Ghostfolio API base URL (e.g. http://localhost:3333 for local). Omit for ghostfolio.io. */
export const GHOSTFOLIO_API_URL_STORAGE_KEY = 'ghostfolio_api_url';

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

async function fetchApi<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {}, signal } = options;

  const reqHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers,
  };
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem(GHOSTFOLIO_TOKEN_STORAGE_KEY);
    if (token?.trim()) {
      reqHeaders['X-Ghostfolio-Access-Token'] = token.trim();
    }
    const apiUrl = localStorage.getItem(GHOSTFOLIO_API_URL_STORAGE_KEY);
    if (apiUrl?.trim()) {
      reqHeaders['X-Ghostfolio-Api-Url'] = apiUrl.trim();
    }
  }

  const config: RequestInit = {
    method,
    headers: reqHeaders,
    signal,
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

  if (!response.ok) {
    const text = await response.text();
    let detail: string | undefined;
    try {
      const json = text ? JSON.parse(text) : {};
      const d = json.detail;
      if (typeof d === 'string') detail = d;
      else if (Array.isArray(d) && d[0]?.msg) detail = d.map((e: { msg?: string }) => e.msg).join('; ');
      else if (d && typeof d === 'object' && 'msg' in d) detail = (d as { msg: string }).msg;
      else if (d != null && typeof d === 'object') detail = JSON.stringify(d).slice(0, 300);
    } catch {
      detail = text?.slice(0, 200) || response.statusText || undefined;
    }
    const fallback =
      response.status >= 500
        ? 'Server error. Check backend logs or try again.'
        : `Request failed (${response.status}).`;
    throw new Error(detail || fallback);
  }

  return response.json();
}

// Health API
export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  mock_mode: boolean;
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

/** One structured tool invocation: call (tool name + input) and its output */
export interface ToolInvocation {
  call: { tool: string; input: Record<string, unknown> };
  output: unknown;
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
  /** Structured list of { call: { tool, input }, output } for each tool invocation */
  tool_invocations?: ToolInvocation[];
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
export interface SessionSummary {
  session_id: string;
  message_count: number;
  last_accessed: string | null;
}

export interface SessionHistory {
  session_id: string;
  message_count: number;
  messages: Array<{
    role: 'user' | 'assistant';
    content: string;
  }>;
}

export const sessionsApi = {
  list: () => fetchApi<{ sessions: SessionSummary[] }>('/sessions'),
  get: (sessionId: string) => fetchApi<SessionHistory>(`/sessions/${sessionId}`),
  clear: (sessionId: string) => fetchApi<{ cleared: boolean }>(`/sessions/${sessionId}`, { method: 'DELETE' }),
};

// Market API
export const marketApi = {
  get: (symbol: string) => fetchApi<Record<string, unknown>>(`/market/${symbol}`),
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
  execute: (toolName: string, params: Record<string, unknown>) =>
    fetchApi<ToolExecuteResponse>(`/tools/${toolName}/execute`, {
      method: 'POST',
      body: { parameters: params },
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

export interface CostComparisonEntry {
  model_id: string;
  label: string;
  input_per_1m: number;
  output_per_1m: number;
  cost_per_query: number;
  monthly_cost: number;
}

export interface CostComparison {
  queries_per_day: number;
  avg_tokens_per_query: number;
  input_ratio_pct: number;
  models: CostComparisonEntry[];
}

export interface SeedDemoUsageResponse {
  entries_added: number;
  models: number;
}

export const financesApi = {
  getUsage: () => fetchApi<UsageStats>('/finances/usage'),
  getProjections: (queriesPerDay?: number) =>
    fetchApi<CostProjections>(`/finances/projections${queriesPerDay ? `?queries_per_day=${queriesPerDay}` : ''}`),
  getCostComparison: (opts?: { queries_per_day?: number; avg_tokens_per_query?: number; input_ratio_pct?: number }) => {
    const params = new URLSearchParams();
    if (opts?.queries_per_day != null) params.set('queries_per_day', String(opts.queries_per_day));
    if (opts?.avg_tokens_per_query != null) params.set('avg_tokens_per_query', String(opts.avg_tokens_per_query));
    if (opts?.input_ratio_pct != null) params.set('input_ratio_pct', String(opts.input_ratio_pct));
    const qs = params.toString();
    return fetchApi<CostComparison>(`/finances/cost-comparison${qs ? `?${qs}` : ''}`);
  },
  seedDemoUsage: (opts?: { entries_per_model?: number; days_back?: number }) => {
    const params = new URLSearchParams();
    if (opts?.entries_per_model != null) params.set('entries_per_model', String(opts.entries_per_model));
    if (opts?.days_back != null) params.set('days_back', String(opts.days_back));
    const qs = params.toString();
    return fetchApi<SeedDemoUsageResponse>(`/finances/seed-demo-usage${qs ? `?${qs}` : ''}`, { method: 'POST' });
  },
};

// Agent config API (developer: switch model)
export interface AgentConfig {
  model: string;
  allowed_models?: string[];
}

export const agentApi = {
  getConfig: () => fetchApi<AgentConfig>('/agent/config'),
  putConfig: (config: { model: string }) =>
    fetchApi<AgentConfig>('/agent/config', { method: 'PUT', body: config }),
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
