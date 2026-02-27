import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { tracesApi, financesApi } from '../api/client';
import type { Trace, TraceDetail, UsageStats, CostProjections } from '../api/client';

const emptyUsage: UsageStats = {
  total_cost: 0,
  total_tokens: 0,
  requests_count: 0,
  avg_cost_per_request: 0,
};

const emptyProjections: CostProjections = {
  daily_cost: 0,
  monthly_cost: 0,
  projected_annual: 0,
  cost_breakdown: {
    input_tokens: 60,
    output_tokens: 40,
  },
};

// Constants for cost calculations
const CIRCLE_CIRCUMFERENCE = 251; // 2 * PI * 40 (radius)
const PERCENT_TO_DASH = CIRCLE_CIRCUMFERENCE / 100; // 2.51

// LangSmith trace URL: set VITE_LANGSMITH_BASE_URL in .env to your project URL (e.g. https://smith.langchain.com/o/.../projects/p/...)
const LANGSMITH_BASE =
  (import.meta as unknown as { env?: { VITE_LANGSMITH_BASE_URL?: string } }).env?.VITE_LANGSMITH_BASE_URL ??
  'https://smith.langchain.com';

export function ObservabilityCost() {
  // Traces state
  const [traces, setTraces] = useState<Trace[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [tracesLoading, setTracesLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  // Finances state
  const [usage, setUsage] = useState<UsageStats>(emptyUsage);
  const [projections, setProjections] = useState<CostProjections>(emptyProjections);
  const [queriesPerDay, setQueriesPerDay] = useState(100);

  // Error state for user feedback
  const [tracesError, setTracesError] = useState<string | null>(null);
  const [financesError, setFinancesError] = useState<string | null>(null);

  // Mounted ref for cleanup
  const mountedRef = useRef(true);
  const financesAbortRef = useRef<number | null>(null);

  // Load traces with cleanup
  useEffect(() => {
    mountedRef.current = true;
    setTracesError(null);

    async function fetchTraces() {
      try {
        const data = await tracesApi.list();
        if (mountedRef.current) {
          setTraces(data);
        }
      } catch (error) {
        if (mountedRef.current) {
          const message = error instanceof Error ? error.message : 'Failed to fetch traces';
          setTracesError(message);
          console.error('Failed to fetch traces:', error);
        }
      } finally {
        if (mountedRef.current) {
          setTracesLoading(false);
        }
      }
    }
    fetchTraces();

    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Load finances with race condition handling
  useEffect(() => {
    // Abort any previous request tracking
    const requestId = Date.now();
    financesAbortRef.current = requestId;
    setFinancesError(null);

    async function fetchData() {
      try {
        const [usageData, projectionsData] = await Promise.all([
          financesApi.getUsage(),
          financesApi.getProjections(queriesPerDay),
        ]);
        // Only update if this is still the latest request
        if (financesAbortRef.current === requestId) {
          setUsage(usageData);
          setProjections(projectionsData);
        }
      } catch (error) {
        if (financesAbortRef.current === requestId) {
          const message = error instanceof Error ? error.message : 'Failed to fetch finance data';
          setFinancesError(message);
          console.error('Failed to fetch finance data:', error);
        }
      }
    }
    fetchData();
  }, [queriesPerDay]);

  const handleSelectTrace = useCallback(async (traceId: string) => {
    setDetailLoading(true);
    setTracesError(null);
    try {
      const detail = await tracesApi.get(traceId);
      if (mountedRef.current) {
        setSelectedTrace(detail);
      }
    } catch (error) {
      if (mountedRef.current) {
        const message = error instanceof Error ? error.message : 'Failed to fetch trace detail';
        setTracesError(message);
        console.error('Failed to fetch trace detail:', error);
      }
    } finally {
      if (mountedRef.current) {
        setDetailLoading(false);
      }
    }
  }, []);

  // Memoized filtered traces for performance
  const filteredTraces = useMemo(() =>
    traces.filter(t =>
      t.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.tool_calls.some(tc => tc.toLowerCase().includes(searchQuery.toLowerCase()))
    ),
    [traces, searchQuery]
  );

  // Handle queries per day change with validation
  const handleQueriesPerDayChange = useCallback((value: string) => {
    const parsed = parseInt(value, 10);
    if (!isNaN(parsed) && parsed >= 10 && parsed <= 1000) {
      setQueriesPerDay(parsed);
    }
  }, []);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="flex h-full min-h-0">
      {/* Trace List Sidebar */}
      <aside className="w-72 min-h-0 bg-surface-darker border-r border-surface-border flex flex-col h-full">
        <div className="p-4 border-b border-surface-border">
          <h2 className="text-white font-bold mb-3 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">monitoring</span>
            Agent Traces
          </h2>
          <div className="relative">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-dim text-base">search</span>
            <input
              type="text"
              placeholder="Search traces..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-surface-dark border border-surface-border rounded-lg py-2 pl-9 pr-3 text-sm text-white placeholder-text-dim focus:ring-1 focus:ring-primary focus:border-primary"
            />
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          {tracesLoading ? (
            <div className="p-4 text-center text-text-dim">Loading traces...</div>
          ) : tracesError ? (
            <div className="p-4 text-center">
              <span className="material-symbols-outlined text-3xl text-red-400">error</span>
              <p className="text-red-400 mt-2 text-sm">{tracesError}</p>
            </div>
          ) : filteredTraces.length === 0 ? (
            <div className="p-4 text-center">
              <span className="material-symbols-outlined text-3xl text-surface-border">monitoring</span>
              <p className="text-text-dim mt-2 text-sm">
                {searchQuery ? 'No traces match your search' : 'No traces yet. Use the Agent Chat to generate traces.'}
              </p>
              {!searchQuery && (
                <p className="text-text-dim/60 text-xs mt-1">Traces are captured from LangSmith when enabled.</p>
              )}
            </div>
          ) : (
            filteredTraces.map((trace) => (
              <div
                key={trace.id}
                onClick={() => handleSelectTrace(trace.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleSelectTrace(trace.id);
                  }
                }}
                tabIndex={0}
                role="button"
                aria-label={`Trace ${trace.id}, status ${trace.status}`}
                className={`p-3 border-b border-surface-border cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 ${
                  selectedTrace?.id === trace.id ? 'bg-primary/10 border-l-2 border-l-primary' : 'hover:bg-surface-dark'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-white font-mono text-xs">{trace.id}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    trace.status === 'success' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                  }`}>
                    {trace.status}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-text-dim">
                  <span>{formatDate(trace.timestamp)}</span>
                  <span>{trace.duration_ms}ms</span>
                  <span>{trace.tokens_used} tok</span>
                </div>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {trace.tool_calls.slice(0, 2).map((tc) => (
                    <span key={tc} className="text-[10px] bg-surface-dark px-1.5 py-0.5 rounded text-text-dim">
                      {tc}
                    </span>
                  ))}
                  {trace.tool_calls.length > 2 && (
                    <span className="text-[10px] text-text-dim">+{trace.tool_calls.length - 2}</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-h-0 h-full bg-background-dark overflow-hidden">
        {/* Header with combined metrics */}
        <header className="sticky top-0 z-10 bg-background-dark/95 backdrop-blur-sm border-b border-surface-border px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-xl font-bold text-white">Observability & Cost</h1>
              <p className="text-text-dim text-sm">Agent traces, token usage, and cost projections</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-dark border border-surface-border rounded-lg">
                <span className="material-symbols-outlined text-primary text-lg">account_balance_wallet</span>
                <span className="text-white font-bold">${usage.total_cost.toFixed(2)}</span>
                <span className="text-text-dim text-xs">this period</span>
              </div>
            </div>
          </div>

          {/* Combined Metrics Bar */}
          <div className="grid grid-cols-5 gap-3">
            <div className="bg-surface-dark rounded-lg p-2.5 border border-surface-border">
              <span className="text-text-dim text-[10px] uppercase">Requests</span>
              <div className="text-lg font-bold text-white">{usage.requests_count.toLocaleString()}</div>
            </div>
            <div className="bg-surface-dark rounded-lg p-2.5 border border-surface-border">
              <span className="text-text-dim text-[10px] uppercase">Tokens</span>
              <div className="text-lg font-bold text-white">
                {usage.total_tokens > 0 ? `${(usage.total_tokens / 1000000).toFixed(2)}M` : '0'}
              </div>
            </div>
            <div className="bg-surface-dark rounded-lg p-2.5 border border-surface-border">
              <span className="text-text-dim text-[10px] uppercase">Avg Latency</span>
              <div className="text-lg font-bold text-white">
                {traces.length > 0 ? `${Math.round(traces.reduce((a, t) => a + t.duration_ms, 0) / traces.length)}ms` : '-'}
              </div>
            </div>
            <div className="bg-surface-dark rounded-lg p-2.5 border border-surface-border">
              <span className="text-text-dim text-[10px] uppercase">Cost/Query</span>
              <div className="text-lg font-bold text-primary">
                {usage.avg_cost_per_request > 0 ? `$${usage.avg_cost_per_request.toFixed(4)}` : '-'}
              </div>
            </div>
            <div className="bg-surface-dark rounded-lg p-2.5 border border-surface-border">
              <span className="text-text-dim text-[10px] uppercase">Success Rate</span>
              <div className="text-lg font-bold text-emerald-400">
                {traces.length > 0
                  ? `${Math.round((traces.filter(t => t.status === 'success').length / traces.length) * 100)}%`
                  : '-'}
              </div>
            </div>
          </div>
        </header>

        {/* Split Content Area */}
        <div className="flex-1 min-h-0 overflow-hidden flex">
          {/* Left: Trace Detail */}
          <div className="flex-1 overflow-y-auto p-6 border-r border-surface-border">
            {detailLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <span className="material-symbols-outlined text-3xl text-primary animate-spin">progress_activity</span>
                  <p className="text-text-dim mt-2">Loading trace details...</p>
                </div>
              </div>
            ) : tracesError ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <span className="material-symbols-outlined text-3xl text-red-400">error</span>
                  <p className="text-red-400 mt-2">{tracesError}</p>
                </div>
              </div>
            ) : selectedTrace ? (
              <div>
                {/* Trace Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <span className="text-primary font-mono text-sm">{selectedTrace.id}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      selectedTrace.status === 'success' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {selectedTrace.status}
                    </span>
                  </div>
                  <button
                    onClick={() => {
                      const url = `${LANGSMITH_BASE}/r/${selectedTrace.id}`;
                      window.open(url, '_blank', 'noopener,noreferrer');
                    }}
                    className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-text-dim bg-surface-dark border border-surface-border rounded-lg hover:text-white transition-colors"
                    aria-label="Open trace in LangSmith"
                  >
                    <span className="material-symbols-outlined text-sm">open_in_new</span>
                    View in LangSmith
                  </button>
                </div>

                {/* Trace Stats */}
                <div className="grid grid-cols-4 gap-3 mb-6">
                  <div className="bg-surface-dark border border-surface-border rounded-lg p-3">
                    <span className="text-text-dim text-[10px] uppercase">Duration</span>
                    <div className="text-xl font-bold text-white mt-1">{selectedTrace.duration_ms}ms</div>
                  </div>
                  <div className="bg-surface-dark border border-surface-border rounded-lg p-3">
                    <span className="text-text-dim text-[10px] uppercase">Tokens</span>
                    <div className="text-xl font-bold text-white mt-1">{selectedTrace.tokens_used}</div>
                  </div>
                  <div className="bg-surface-dark border border-surface-border rounded-lg p-3">
                    <span className="text-text-dim text-[10px] uppercase">Tool Calls</span>
                    <div className="text-xl font-bold text-white mt-1">{selectedTrace.tool_calls?.length || 0}</div>
                  </div>
                  <div className="bg-surface-dark border border-surface-border rounded-lg p-3">
                    <span className="text-text-dim text-[10px] uppercase">Est. Cost</span>
                    <div className="text-xl font-bold text-primary mt-1">
                      {/* Using GPT-4o-mini pricing: $0.60/1M tokens (blended avg of input/output) */}
                      ${((selectedTrace.tokens_used / 1000000) * 0.60).toFixed(4)}
                    </div>
                  </div>
                </div>

                {/* Execution Steps */}
                <div className="bg-surface-dark border border-surface-border rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-surface-border bg-surface-darker">
                    <h3 className="text-white font-semibold text-sm">Execution Steps</h3>
                  </div>
                  <div className="p-4 space-y-3">
                    {selectedTrace.steps && selectedTrace.steps.length > 0 ? (
                      selectedTrace.steps.map((step, index) => (
                        <div key={index} className="p-3 rounded-lg bg-surface-darker border border-surface-border">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className="size-5 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xs font-bold">
                                {index + 1}
                              </span>
                              <span className="text-white text-sm font-medium">{step.name}</span>
                            </div>
                            <span className="text-[10px] text-text-dim">{step.duration_ms}ms</span>
                          </div>
                          <div className="grid grid-cols-2 gap-3 mt-2">
                            <div>
                              <span className="text-[10px] text-text-dim uppercase">Input</span>
                              <pre className="mt-1 p-2 bg-background-dark rounded text-[10px] text-slate-300 overflow-x-auto">
                                {JSON.stringify(step.input, null, 2)}
                              </pre>
                            </div>
                            <div>
                              <span className="text-[10px] text-text-dim uppercase">Output</span>
                              <pre className="mt-1 p-2 bg-background-dark rounded text-[10px] text-slate-300 overflow-x-auto">
                                {JSON.stringify(step.output, null, 2)}
                              </pre>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8">
                        <span className="material-symbols-outlined text-3xl text-surface-border">layers</span>
                        <p className="text-text-dim mt-2 text-sm">No step details available</p>
                        <p className="text-text-dim/60 text-xs mt-1">Child runs may not be captured for this trace</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <span className="material-symbols-outlined text-5xl text-surface-border">monitoring</span>
                  <p className="text-text-dim mt-4">Select a trace to view details</p>
                </div>
              </div>
            )}
          </div>

          {/* Right: Cost Panel */}
          <div className="w-80 overflow-y-auto p-6 bg-surface-darker/50">
            <h2 className="text-white font-bold mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">trending_up</span>
              Cost Projections
            </h2>

            {/* Finances error display */}
            {financesError && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <div className="flex items-start gap-2">
                  <span className="material-symbols-outlined text-red-400 text-lg">error</span>
                  <div>
                    <p className="text-xs text-red-400 font-medium">Failed to load cost data</p>
                    <p className="text-[10px] text-red-400/70 mt-1">{financesError}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Cost Breakdown Pie */}
            <div className="bg-surface-dark border border-surface-border rounded-xl p-4 mb-4">
              <div className="flex items-center gap-4">
                <div className="relative w-24 h-24 flex-shrink-0">
                  <svg viewBox="0 0 100 100" className="transform -rotate-90">
                    <circle cx="50" cy="50" r="40" fill="transparent" stroke="#234248" strokeWidth="16" />
                    <circle
                      cx="50" cy="50" r="40"
                      fill="transparent"
                      stroke="#13c8ec"
                      strokeWidth="16"
                      strokeDasharray={`${projections.cost_breakdown.input_tokens * PERCENT_TO_DASH} ${CIRCLE_CIRCUMFERENCE}`}
                    />
                    <circle
                      cx="50" cy="50" r="40"
                      fill="transparent"
                      stroke="#f59e0b"
                      strokeWidth="16"
                      strokeDasharray={`${projections.cost_breakdown.output_tokens * PERCENT_TO_DASH} ${CIRCLE_CIRCUMFERENCE}`}
                      strokeDashoffset={`-${projections.cost_breakdown.input_tokens * PERCENT_TO_DASH}`}
                    />
                  </svg>
                </div>
                <div className="flex-1 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-primary" />
                      <span className="text-xs text-white">Input</span>
                    </div>
                    <span className="text-xs text-white font-bold">{projections.cost_breakdown.input_tokens}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-amber-500" />
                      <span className="text-xs text-white">Output</span>
                    </div>
                    <span className="text-xs text-white font-bold">{projections.cost_breakdown.output_tokens}%</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Queries Slider */}
            <div className="mb-4">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-text-dim">Est. Queries/Day</span>
                <span className="text-lg font-bold text-primary">{queriesPerDay}</span>
              </div>
              <input
                type="range"
                min="10"
                max="1000"
                step="10"
                value={queriesPerDay}
                onChange={(e) => handleQueriesPerDayChange(e.target.value)}
                aria-label="Estimated queries per day"
                aria-valuemin={10}
                aria-valuemax={1000}
                aria-valuenow={queriesPerDay}
                className="w-full h-1.5 bg-surface-border rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <div className="flex justify-between text-[10px] text-text-dim mt-1">
                <span>10</span>
                <span>500</span>
                <span>1000</span>
              </div>
            </div>

            {/* Projection Cards */}
            <div className="space-y-3">
              <div className="bg-surface-dark rounded-xl p-3 border border-surface-border">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-blue-400 text-lg">today</span>
                  <span className="text-text-dim text-xs">Daily Cost</span>
                </div>
                <div className="text-2xl font-bold text-white">${projections.daily_cost.toFixed(2)}</div>
                <div className="text-[10px] text-text-dim">At {queriesPerDay} queries/day</div>
              </div>

              <div className="bg-surface-dark rounded-xl p-3 border border-surface-border">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-emerald-400 text-lg">calendar_month</span>
                  <span className="text-text-dim text-xs">Monthly Cost</span>
                </div>
                <div className="text-2xl font-bold text-white">${projections.monthly_cost.toFixed(2)}</div>
                <div className="text-[10px] text-text-dim">30-day projection</div>
              </div>

              <div className="bg-surface-dark rounded-xl p-3 border border-primary/30">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-primary text-lg">event</span>
                  <span className="text-text-dim text-xs">Annual Projection</span>
                </div>
                <div className="text-2xl font-bold text-primary">${projections.projected_annual.toFixed(2)}</div>
                <div className="text-[10px] text-text-dim">12-month estimate</div>
              </div>
            </div>

            {/* Pricing Reference */}
            <div className="mt-4 p-3 bg-surface-dark rounded-lg border border-surface-border">
              <h4 className="text-xs font-semibold text-text-dim mb-2">Pricing Reference (GPT-4o-mini)</h4>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-text-dim">Input</span>
                  <span className="text-white">$0.15/1M tok</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-dim">Output</span>
                  <span className="text-white">$0.60/1M tok</span>
                </div>
                <div className="flex justify-between border-t border-surface-border pt-1 mt-1">
                  <span className="text-text-dim">Blended avg</span>
                  <span className="text-white">~$0.60/1M tok</span>
                </div>
              </div>
            </div>

            {/* No usage data message */}
            {usage.requests_count === 0 && (
              <div className="mt-4 p-3 bg-surface-dark rounded-lg border border-amber-500/30">
                <div className="flex items-start gap-2">
                  <span className="material-symbols-outlined text-amber-500 text-lg">info</span>
                  <div>
                    <p className="text-xs text-white font-medium">No usage data yet</p>
                    <p className="text-[10px] text-text-dim mt-1">
                      Projections use default estimates. Actual costs will appear after agent queries are made.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
