import { useEffect, useState } from 'react';
import { tracesApi } from '../api/client';
import type { Trace, TraceDetail } from '../api/client';

const mockTraces: Trace[] = [
  { id: 't1', timestamp: '2024-02-26T10:30:00Z', duration_ms: 1250, tokens_used: 847, status: 'success', tool_calls: ['portfolio_analysis', 'market_data'] },
  { id: 't2', timestamp: '2024-02-26T10:25:00Z', duration_ms: 890, tokens_used: 512, status: 'success', tool_calls: ['risk_assessment'] },
  { id: 't3', timestamp: '2024-02-26T10:20:00Z', duration_ms: 2340, tokens_used: 1203, status: 'error', tool_calls: ['portfolio_analysis', 'compliance_check'] },
  { id: 't4', timestamp: '2024-02-26T10:15:00Z', duration_ms: 560, tokens_used: 298, status: 'success', tool_calls: ['market_data'] },
  { id: 't5', timestamp: '2024-02-26T10:10:00Z', duration_ms: 1890, tokens_used: 956, status: 'success', tool_calls: ['tax_estimate', 'portfolio_analysis'] },
];

export function Observability() {
  const [traces, setTraces] = useState<Trace[]>(mockTraces);
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null);
  const [_loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    async function fetchTraces() {
      try {
        const data = await tracesApi.list();
        if (data.length > 0) setTraces(data);
      } catch (error) {
        console.error('Failed to fetch traces:', error);
      }
    }
    fetchTraces();
  }, []);

  const handleSelectTrace = async (traceId: string) => {
    setLoading(true);
    try {
      const detail = await tracesApi.get(traceId);
      setSelectedTrace(detail);
    } catch (error) {
      console.error('Failed to fetch trace detail:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredTraces = traces.filter(t =>
    t.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.tool_calls.some(tc => tc.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="flex h-full">
      {/* Trace List Sidebar */}
      <aside className="w-80 bg-surface-darker border-r border-surface-border flex flex-col h-full">
        <div className="p-4 border-b border-surface-border">
          <h2 className="text-white font-bold mb-3">Agent Traces</h2>
          <div className="relative">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-dim text-lg">search</span>
            <input
              type="text"
              placeholder="Search traces..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-surface-dark border border-surface-border rounded-lg py-2 pl-10 pr-4 text-sm text-white placeholder-text-dim focus:ring-1 focus:ring-primary focus:border-primary"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {filteredTraces.map((trace) => (
            <div
              key={trace.id}
              onClick={() => handleSelectTrace(trace.id)}
              className={`p-4 border-b border-surface-border cursor-pointer transition-colors ${
                selectedTrace?.id === trace.id ? 'bg-primary/10 border-l-2 border-l-primary' : 'hover:bg-surface-dark'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-white font-mono text-sm">{trace.id}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  trace.status === 'success' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                }`}>
                  {trace.status}
                </span>
              </div>
              <div className="flex items-center gap-4 text-xs text-text-dim">
                <span>{formatDate(trace.timestamp)}</span>
                <span>{trace.duration_ms}ms</span>
                <span>{trace.tokens_used} tokens</span>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {trace.tool_calls.map((tc) => (
                  <span key={tc} className="text-xs bg-surface-dark px-2 py-0.5 rounded text-text-dim">
                    {tc}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Trace Detail */}
      <main className="flex-1 overflow-y-auto bg-background-dark">
        {selectedTrace ? (
          <div className="p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-text-dim text-sm">Trace Detail</span>
                  <span className="text-surface-border">/</span>
                  <span className="text-primary font-mono text-sm">{selectedTrace.id}</span>
                </div>
                <h1 className="text-2xl font-bold text-white">Agent Execution Trace</h1>
              </div>
              <div className="flex gap-2">
                <button className="flex items-center gap-2 px-3 py-1.5 text-sm text-text-dim bg-surface-dark border border-surface-border rounded-lg hover:text-white transition-colors">
                  <span className="material-symbols-outlined text-base">open_in_new</span>
                  View in LangSmith
                </button>
              </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="bg-surface-dark border border-surface-border rounded-xl p-4">
                <span className="text-text-dim text-xs uppercase tracking-wide">Duration</span>
                <div className="text-2xl font-bold text-white mt-1">{selectedTrace.duration_ms}ms</div>
              </div>
              <div className="bg-surface-dark border border-surface-border rounded-xl p-4">
                <span className="text-text-dim text-xs uppercase tracking-wide">Tokens</span>
                <div className="text-2xl font-bold text-white mt-1">{selectedTrace.tokens_used}</div>
              </div>
              <div className="bg-surface-dark border border-surface-border rounded-xl p-4">
                <span className="text-text-dim text-xs uppercase tracking-wide">Tool Calls</span>
                <div className="text-2xl font-bold text-white mt-1">{selectedTrace.tool_calls?.length || 0}</div>
              </div>
              <div className="bg-surface-dark border border-surface-border rounded-xl p-4">
                <span className="text-text-dim text-xs uppercase tracking-wide">Status</span>
                <div className={`text-2xl font-bold mt-1 ${selectedTrace.status === 'success' ? 'text-emerald-400' : 'text-red-400'}`}>
                  {selectedTrace.status}
                </div>
              </div>
            </div>

            {/* Steps */}
            <div className="bg-surface-dark border border-surface-border rounded-xl overflow-hidden">
              <div className="px-5 py-3 border-b border-surface-border bg-surface-darker">
                <h3 className="text-white font-semibold">Execution Steps</h3>
              </div>
              <div className="p-4 space-y-4">
                {(selectedTrace.steps || [
                  { name: 'User Input Parsing', input: { message: 'What is my portfolio value?' }, output: { intent: 'portfolio_query' }, duration_ms: 45 },
                  { name: 'portfolio_analysis', input: { timeframe: 'YTD' }, output: { total_value: 125000, performance: 12.5 }, duration_ms: 890 },
                  { name: 'Response Generation', input: { data: '...' }, output: { response: 'Your portfolio...' }, duration_ms: 315 },
                ]).map((step, index) => (
                  <div key={index} className="p-4 rounded-lg bg-surface-darker border border-surface-border">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="size-6 rounded-full bg-primary/20 text-primary flex items-center justify-center text-sm font-bold">
                          {index + 1}
                        </span>
                        <span className="text-white font-medium">{step.name}</span>
                      </div>
                      <span className="text-xs text-text-dim">{step.duration_ms}ms</span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 mt-3">
                      <div>
                        <span className="text-xs text-text-dim uppercase">Input</span>
                        <pre className="mt-1 p-2 bg-background-dark rounded text-xs text-slate-300 overflow-x-auto">
                          {JSON.stringify(step.input, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <span className="text-xs text-text-dim uppercase">Output</span>
                        <pre className="mt-1 p-2 bg-background-dark rounded text-xs text-slate-300 overflow-x-auto">
                          {JSON.stringify(step.output, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <span className="material-symbols-outlined text-6xl text-surface-border">monitoring</span>
              <p className="text-text-dim mt-4">Select a trace from the sidebar to view details</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
