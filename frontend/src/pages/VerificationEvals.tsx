import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppMode } from '../contexts/AppModeContext';
import { verificationApi, evalsApi } from '../api/client';
import type { VerificationConfig, EvalCase, EvalResult, EvalSummary, EvalCriterionResult, ToolCallDetail } from '../api/client';

// Configurable constants
const SAVED_INDICATOR_DURATION_MS = 2000;
const POLLING_MAX_ATTEMPTS = 30;
const POLLING_INTERVAL_MS = 1000;

const defaultConfig: VerificationConfig = {
  fact_checking: true,
  hallucination_detection: true,
  confidence_scoring: true,
  hitl_enabled: false,
  confidence_threshold: 70,
};

const emptySummary: EvalSummary = {
  total_cases: 0,
  passed: 0,
  failed: 0,
  pass_rate: 0,
  avg_latency_ms: 0,
  hallucination_rate: 0,
};

// Check type descriptions for legend
const CHECK_TYPE_DESCRIPTIONS: Record<string, string> = {
  tool_called: 'Verifies expected tool was invoked',
  tool_not_called: 'Ensures dangerous/unwanted tools aren\'t called',
  field_present: 'Checks output contains expected field',
  field_matches: 'Validates field value (with tolerance)',
  value_in_range: 'Ensures numeric value is in valid range',
  timestamp_fresh: 'Validates data isn\'t stale',
  not_contains: 'Ensures response doesn\'t contain forbidden terms',
  verification_gate: 'Runs single gate from 4-gate system',
  verification_verdict: 'Full 4-gate verification with confidence',
};

// Verification gate descriptions
const VERIFICATION_GATES = [
  {
    name: 'Syntactic Gate',
    icon: 'code',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/20',
    checks: [
      'Validates required fields exist',
      'Checks numeric fields are valid numbers',
      'Ensures scores are in 0-100 range',
      'Validates OHLC constraints (high >= open/close)',
    ],
  },
  {
    name: 'Temporal Gate',
    icon: 'schedule',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/20',
    checks: [
      'Checks timestamp freshness',
      'Quotes: max 5min stale',
      'Portfolio data: max 24h stale',
    ],
  },
  {
    name: 'Cross-Source Gate',
    icon: 'compare_arrows',
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/20',
    checks: [
      'Compares prices against independent sources',
      '0.05% price tolerance, 1% value tolerance',
      'Validates holdings match between sources',
    ],
  },
  {
    name: 'Economic Plausibility Gate',
    icon: 'trending_up',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/20',
    checks: [
      'No negative prices/values',
      'Bid < Ask for quotes',
      'Allocation percentages sum to ~100%',
      'Warns on high concentration (>50% in one asset)',
    ],
  },
];

// Toggle card data with impact info
const VERIFICATION_LAYERS = [
  {
    key: 'fact_checking' as const,
    label: 'Fact Checking',
    icon: 'fact_check',
    description: 'Verify against data sources',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/20',
    impactIfDisabled: 'Agent responses won\'t be validated against Ghostfolio data. Errors and hallucinations may go undetected.',
  },
  {
    key: 'hallucination_detection' as const,
    label: 'Hallucination Detection',
    icon: 'psychology_alt',
    description: 'Flag fabricated info',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/20',
    impactIfDisabled: 'Responses may contain fabricated data or claims that appear plausible but have no basis in actual data.',
  },
  {
    key: 'confidence_scoring' as const,
    label: 'Confidence Scoring',
    icon: 'speed',
    description: 'Report confidence levels',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/20',
    impactIfDisabled: 'You won\'t know how reliable a response is. Low-quality responses may appear as trustworthy as high-quality ones.',
  },
];

// Expandable Eval Result Card Component
function EvalResultCard({ result, testCase }: { result: EvalResult | undefined; testCase: EvalCase }) {
  const [expanded, setExpanded] = useState(false);

  const passedCriteria = result?.criteria_results?.filter(c => c.passed).length ?? 0;
  const totalCriteria = result?.criteria_results?.length ?? 0;

  return (
    <div className="border border-surface-border rounded-lg overflow-hidden">
      {/* Header row - always visible */}
      <div
        className={`flex items-center gap-4 px-4 py-3 cursor-pointer hover:bg-surface-border/30 transition-colors ${expanded ? 'bg-surface-darker' : ''}`}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-white text-sm font-medium truncate">{testCase.name}</span>
            {result?.criteria_results && result.criteria_results.length > 0 && (
              <span className="text-xs text-text-dim">
                ({passedCriteria}/{totalCriteria} criteria)
              </span>
            )}
          </div>
          <p className="text-[10px] text-text-dim mt-0.5 truncate">{testCase.description}</p>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-xs text-text-dim hidden sm:block">{testCase.category}</span>

          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${
            result?.passed
              ? 'bg-emerald-500/20 text-emerald-400'
              : result
              ? 'bg-red-500/20 text-red-400'
              : 'bg-slate-500/20 text-slate-400'
          }`}>
            <span className="material-symbols-outlined text-xs">
              {result?.passed ? 'check_circle' : result ? 'cancel' : 'pending'}
            </span>
            {result?.passed ? 'Passed' : result ? 'Failed' : 'Pending'}
          </span>

          {result && (
            <div className="flex items-center gap-3 text-xs text-text-dim">
              {result.confidence !== undefined && (
                <span className="hidden sm:flex items-center gap-1">
                  <span className="material-symbols-outlined text-sm">speed</span>
                  {result.confidence.toFixed(1)}%
                </span>
              )}
              <span>{result.duration_ms}ms</span>
            </div>
          )}

          <span className={`material-symbols-outlined text-text-dim transition-transform ${expanded ? 'rotate-180' : ''}`}>
            expand_more
          </span>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && result && (
        <div className="border-t border-surface-border bg-surface-darker/50 p-4 space-y-4">
          {/* Input */}
          {result.input && (
            <div>
              <div className="text-[10px] uppercase text-text-dim font-semibold tracking-wider mb-1">Input</div>
              <div className="text-sm text-white bg-surface-dark rounded px-3 py-2 border border-surface-border">
                "{result.input}"
              </div>
            </div>
          )}

          {/* Criteria Results */}
          {result.criteria_results && result.criteria_results.length > 0 && (
            <div>
              <div className="text-[10px] uppercase text-text-dim font-semibold tracking-wider mb-2">
                Criteria Results ({passedCriteria}/{totalCriteria} passed)
              </div>
              <div className="space-y-2">
                {result.criteria_results.map((criterion) => (
                  <CriterionResult key={criterion.id} criterion={criterion} />
                ))}
              </div>
            </div>
          )}

          {/* Tool Calls */}
          {result.tool_calls && result.tool_calls.length > 0 && (
            <div>
              <div className="text-[10px] uppercase text-text-dim font-semibold tracking-wider mb-1">
                Tool Calls ({result.tool_calls.length})
              </div>
              <div className="flex flex-wrap gap-2">
                {result.tool_calls.map((tool, idx) => (
                  <span key={idx} className="inline-flex items-center gap-1 px-2 py-1 bg-primary/20 text-primary rounded text-xs font-mono">
                    <span className="material-symbols-outlined text-sm">terminal</span>
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Tool Call Details with Args */}
          {result.tool_call_details && result.tool_call_details.length > 0 && (
            <div>
              <div className="text-[10px] uppercase text-text-dim font-semibold tracking-wider mb-1">Tool Call Details</div>
              <div className="space-y-1">
                {result.tool_call_details.map((tc, idx) => (
                  <ToolCallDetailRow key={idx} detail={tc} />
                ))}
              </div>
            </div>
          )}

          {/* Tool Output */}
          {result.tool_outputs && result.tool_outputs.length > 0 && (
            <div>
              <div className="text-[10px] uppercase text-text-dim font-semibold tracking-wider mb-1">Tool Output</div>
              <pre className="text-xs text-text-dim bg-surface-dark rounded px-3 py-2 border border-surface-border overflow-x-auto max-h-48 overflow-y-auto">
                {JSON.stringify(result.tool_outputs, null, 2)}
              </pre>
            </div>
          )}

          {/* Agent Response */}
          {result.response && (
            <div>
              <div className="text-[10px] uppercase text-text-dim font-semibold tracking-wider mb-1">Agent Response</div>
              <div className="text-sm text-white bg-surface-dark rounded px-3 py-2 border border-surface-border max-h-32 overflow-y-auto">
                {result.response}
              </div>
            </div>
          )}

          {/* Error */}
          {result.error && (
            <div>
              <div className="text-[10px] uppercase text-red-400 font-semibold tracking-wider mb-1">Error</div>
              <div className="text-sm text-red-400 bg-red-500/10 rounded px-3 py-2 border border-red-500/30">
                {result.error}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Criterion Result Component
function CriterionResult({ criterion }: { criterion: EvalCriterionResult }) {
  return (
    <div className={`p-2 rounded border ${criterion.passed ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 min-w-0">
          <span className={`material-symbols-outlined text-sm mt-0.5 ${criterion.passed ? 'text-emerald-400' : 'text-red-400'}`}>
            {criterion.passed ? 'check_circle' : 'cancel'}
          </span>
          <div className="min-w-0">
            <div className="text-xs text-white font-medium">{criterion.id}: {criterion.description}</div>
            <div className="flex flex-wrap items-center gap-2 mt-1 text-[10px]">
              <span className="text-text-dim">Type:</span>
              <span className="text-primary font-mono">{criterion.check_type}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-0.5 text-[10px]">
              <span className="text-text-dim">Expected:</span>
              <span className="text-emerald-400 font-mono truncate max-w-32" title={JSON.stringify(criterion.expected)}>
                {formatValue(criterion.expected)}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-0.5 text-[10px]">
              <span className="text-text-dim">Actual:</span>
              <span className={`${criterion.passed ? 'text-emerald-400' : 'text-red-400'} font-mono truncate max-w-32`} title={JSON.stringify(criterion.actual)}>
                {formatValue(criterion.actual)}
              </span>
            </div>
          </div>
        </div>
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${criterion.passed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
          {criterion.passed ? 'PASS' : 'FAIL'}
        </span>
      </div>
      {criterion.error && (
        <div className="mt-1 text-[10px] text-red-400 ml-6">
          {criterion.error}
        </div>
      )}
    </div>
  );
}

// Tool Call Detail Row Component
function ToolCallDetailRow({ detail }: { detail: ToolCallDetail }) {
  return (
    <div className="text-xs font-mono bg-surface-dark rounded px-2 py-1 border border-surface-border">
      <span className="text-primary">{detail.tool}</span>
      {detail.input && Object.keys(detail.input).length > 0 && (
        <span className="text-text-dim">({JSON.stringify(detail.input)})</span>
      )}
    </div>
  );
}

// Format value for display
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'string') return value.length > 30 ? value.slice(0, 30) + '...' : value;
  if (Array.isArray(value)) return `[${value.length} items]`;
  if (typeof value === 'object') return JSON.stringify(value).slice(0, 40) + (JSON.stringify(value).length > 40 ? '...' : '');
  return String(value);
}

// Verification Docs Section Component
function VerificationDocsSection() {
  const [expanded, setExpanded] = useState(false);

  return (
    <section className="rounded-xl border border-surface-border bg-surface-dark overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-5 py-3 flex items-center justify-between hover:bg-surface-border/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">school</span>
          <h3 className="text-white font-bold">How Verification Works</h3>
        </div>
        <span className={`material-symbols-outlined text-text-dim transition-transform ${expanded ? 'rotate-180' : ''}`}>
          expand_more
        </span>
      </button>

      {expanded && (
        <div className="px-5 pb-4 border-t border-surface-border">
          <p className="text-sm text-text-dim mt-3 mb-4">
            The agent uses a 4-gate verification system to ensure data quality and catch errors:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {VERIFICATION_GATES.map((gate) => (
              <div key={gate.name} className="p-3 rounded-lg bg-surface-darker border border-surface-border">
                <div className="flex items-center gap-2 mb-2">
                  <div className={`p-1.5 rounded ${gate.bgColor}`}>
                    <span className={`material-symbols-outlined text-sm ${gate.color}`}>{gate.icon}</span>
                  </div>
                  <h4 className="text-white text-sm font-medium">{gate.name}</h4>
                </div>
                <ul className="space-y-1">
                  {gate.checks.map((check, idx) => (
                    <li key={idx} className="flex items-start gap-1.5 text-xs text-text-dim">
                      <span className={`material-symbols-outlined text-xs ${gate.color} mt-0.5`}>check</span>
                      {check}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

// Check Type Legend Component
function CheckTypeLegend() {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-surface-darker rounded-lg border border-surface-border overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-2 flex items-center justify-between hover:bg-surface-border/30 transition-colors"
      >
        <span className="text-xs text-text-dim font-medium">Check Types Reference</span>
        <span className={`material-symbols-outlined text-text-dim text-sm transition-transform ${expanded ? 'rotate-180' : ''}`}>
          expand_more
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-3 border-t border-surface-border">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 mt-2">
            {Object.entries(CHECK_TYPE_DESCRIPTIONS).map(([type, desc]) => (
              <div key={type} className="flex items-start gap-2 py-1">
                <code className="text-[10px] text-primary bg-primary/10 px-1.5 py-0.5 rounded font-mono whitespace-nowrap">
                  {type}
                </code>
                <span className="text-[10px] text-text-dim">{desc}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function VerificationEvals() {
  const { appMode } = useAppMode();
  const navigate = useNavigate();
  useEffect(() => {
    if (appMode === 'user') navigate('/', { replace: true });
  }, [appMode, navigate]);

  // Verification state
  const [config, setConfig] = useState<VerificationConfig>(defaultConfig);
  const [configLoading, setConfigLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Evaluations state
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [results, setResults] = useState<EvalResult[]>([]);
  const [summary, setSummary] = useState<EvalSummary>(emptySummary);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hasRun, setHasRun] = useState(false);

  // Refs for cleanup and mounted state tracking
  const mountedRef = useRef(true);
  const pollingRef = useRef<boolean>(false);
  const configAbortControllerRef = useRef<AbortController | null>(null);
  const dataAbortControllerRef = useRef<AbortController | null>(null);

  // Fetch verification config
  useEffect(() => {
    mountedRef.current = true;
    configAbortControllerRef.current = new AbortController();

    async function fetchConfig() {
      try {
        const data = await verificationApi.getConfig();
        if (mountedRef.current) {
          setConfig(data);
          setConfigLoading(false);
        }
      } catch (error) {
        if (mountedRef.current) {
          console.error('Failed to fetch config:', error);
          setLoadError('Failed to load verification config');
          setConfigLoading(false);
        }
      }
    }
    fetchConfig();

    return () => {
      mountedRef.current = false;
      configAbortControllerRef.current?.abort();
    };
  }, []);

  // Fetch eval data
  useEffect(() => {
    mountedRef.current = true;
    dataAbortControllerRef.current = new AbortController();

    async function fetchData() {
      setLoading(true);
      try {
        const [casesData, resultsData] = await Promise.all([
          evalsApi.getCases(),
          evalsApi.getResults(),
        ]);
        if (mountedRef.current) {
          setCases(casesData);
          if (resultsData.results.length > 0) {
            setResults(resultsData.results);
            setSummary(resultsData.summary);
            setHasRun(true);
          } else {
            setHasRun(false);
          }
        }
      } catch (error) {
        if (mountedRef.current) {
          console.error('Failed to fetch eval data:', error);
          setLoadError('Failed to load evaluation data');
        }
      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    }
    fetchData();

    return () => {
      mountedRef.current = false;
      dataAbortControllerRef.current?.abort();
    };
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await verificationApi.saveConfig(config);
      if (mountedRef.current) {
        setSaved(true);
        setTimeout(() => {
          if (mountedRef.current) {
            setSaved(false);
          }
        }, SAVED_INDICATOR_DURATION_MS);
      }
    } catch (error) {
      if (mountedRef.current) {
        console.error('Failed to save:', error);
        setSaveError('Failed to save configuration. Please try again.');
      }
    } finally {
      if (mountedRef.current) {
        setSaving(false);
      }
    }
  };

  const updateConfig = <K extends keyof VerificationConfig>(key: K, value: VerificationConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  // Validated threshold update - prevents NaN
  const updateThreshold = (value: string) => {
    const parsed = parseInt(value, 10);
    if (!isNaN(parsed) && parsed >= 0 && parsed <= 100) {
      updateConfig('confidence_threshold', parsed);
    }
    // If invalid, silently ignore - keeps current value
  };

  const handleRunAll = async () => {
    setRunning(true);
    setRunError(null);
    pollingRef.current = true;

    try {
      // Pass current verification config to eval run
      await evalsApi.runAll(config);

      // Poll for results (evals run async)
      let attempts = 0;
      while (attempts < POLLING_MAX_ATTEMPTS && pollingRef.current && mountedRef.current) {
        await new Promise(r => setTimeout(r, POLLING_INTERVAL_MS));

        // Check if still mounted before proceeding
        if (!mountedRef.current) break;

        try {
          const resultsData = await evalsApi.getResults();
          if (resultsData.results.length > 0) {
            if (mountedRef.current) {
              setResults(resultsData.results);
              setSummary(resultsData.summary);
              setHasRun(true);
            }
            break;
          }
        } catch (pollError) {
          // Continue polling on transient errors
          console.warn('Polling attempt failed:', pollError);
        }
        attempts++;
      }

      // If we exhausted attempts without results, show error
      if (attempts >= POLLING_MAX_ATTEMPTS && mountedRef.current) {
        setRunError('Evaluation timed out. Please try again or check backend logs.');
      }
    } catch (error) {
      if (mountedRef.current) {
        console.error('Failed to run evals:', error);
        setRunError('Failed to run evaluations. Please check backend connection.');
      }
    } finally {
      if (mountedRef.current) {
        setRunning(false);
      }
      pollingRef.current = false;
    }
  };

  // Cancel polling if component unmounts during run
  useEffect(() => {
    return () => {
      pollingRef.current = false;
    };
  }, []);

  // Memoized computed values for performance
  const categories = useMemo(() =>
    ['All', ...new Set(cases.map(c => c.category))],
    [cases]
  );

  const filteredCases = useMemo(() =>
    selectedCategory === 'All' ? cases : cases.filter(c => c.category === selectedCategory),
    [cases, selectedCategory]
  );

  const getResult = useCallback((caseId: string) =>
    results.find(r => r.case_id === caseId),
    [results]
  );

  const formatCategory = (cat: string) =>
    cat === 'All' ? 'All' : cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  if (loading || configLoading) {
    return (
      <main className="flex-1 px-6 md:px-10 py-8 overflow-y-auto">
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center gap-3">
            <div className="animate-spin">
              <span className="material-symbols-outlined text-primary text-2xl">progress_activity</span>
            </div>
            <div className="text-text-dim">
              {configLoading ? 'Loading configuration...' : 'Loading evaluation data...'}
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex-1 px-6 md:px-10 py-8 overflow-y-auto">
      <div className="mx-auto max-w-[1200px]">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8">
          <div>
            <div className="flex items-center gap-2 mb-2 text-sm">
              <span className="text-text-dim">Home</span>
              <span className="text-surface-border">/</span>
              <span className="text-white font-medium">Verification & Evaluations</span>
            </div>
            <h1 className="text-white text-3xl font-black mb-2">Quality Assurance Dashboard</h1>
            <p className="text-text-dim">Configure verification layers and run systematic evaluations to validate agent behavior.</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
                saveError
                  ? 'bg-red-500 text-white'
                  : saved
                  ? 'bg-emerald-500 text-white'
                  : 'bg-surface-dark border border-surface-border text-text-dim hover:text-white hover:border-text-dim'
              }`}
            >
              <span className="material-symbols-outlined text-lg">{saveError ? 'error' : saved ? 'check_circle' : 'save'}</span>
              {saveError ? 'Error' : saved ? 'Saved!' : saving ? 'Saving...' : 'Save Config'}
            </button>
            <button
              onClick={handleRunAll}
              disabled={running}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-primary text-background-dark rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-lg">{running ? 'hourglass_empty' : 'play_arrow'}</span>
              {running ? 'Running...' : 'Run All Tests'}
            </button>
          </div>
        </div>

        {/* Error Banners */}
        {loadError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6 flex items-center gap-3">
            <span className="material-symbols-outlined text-red-400 text-2xl">error</span>
            <div className="flex-1">
              <p className="text-red-200 text-sm font-medium">Failed to load data</p>
              <p className="text-red-200/70 text-xs">{loadError}</p>
            </div>
            <button
              onClick={() => setLoadError(null)}
              className="text-red-400 hover:text-red-200"
              aria-label="Dismiss error"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        )}

        {runError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6 flex items-center gap-3">
            <span className="material-symbols-outlined text-red-400 text-2xl">error</span>
            <div className="flex-1">
              <p className="text-red-200 text-sm font-medium">Evaluation failed</p>
              <p className="text-red-200/70 text-xs">{runError}</p>
            </div>
            <button
              onClick={() => setRunError(null)}
              className="text-red-400 hover:text-red-200"
              aria-label="Dismiss error"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        )}

        {saveError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6 flex items-center gap-3">
            <span className="material-symbols-outlined text-red-400 text-2xl">error</span>
            <div className="flex-1">
              <p className="text-red-200 text-sm font-medium">Failed to save configuration</p>
              <p className="text-red-200/70 text-xs">{saveError}</p>
            </div>
            <button
              onClick={() => setSaveError(null)}
              className="text-red-400 hover:text-red-200"
              aria-label="Dismiss error"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        )}

        {/* How Verification Works Documentation */}
        <div className="mb-6">
          <VerificationDocsSection />
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Verification Config */}
          <div className="lg:col-span-1 space-y-6">
            {/* Verification Layers */}
            <section className="rounded-xl border border-surface-border bg-surface-dark overflow-hidden">
              <div className="px-5 py-3 border-b border-surface-border bg-surface-darker">
                <h3 className="text-white font-bold flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">verified_user</span>
                  Verification Layers
                </h3>
              </div>
              <div className="p-4 space-y-3">
                {VERIFICATION_LAYERS.map((layer) => (
                  <div key={layer.key} className="p-3 rounded-lg bg-surface-darker border border-surface-border">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${layer.bgColor}`}>
                          <span className={`material-symbols-outlined text-lg ${layer.color}`}>{layer.icon}</span>
                        </div>
                        <div>
                          <h4 className="text-white text-sm font-medium">{layer.label}</h4>
                          <p className="text-xs text-text-dim">{layer.description}</p>
                        </div>
                      </div>
                      <label className="relative inline-flex h-5 w-9 items-center rounded-full bg-surface-border cursor-pointer">
                        <input
                          type="checkbox"
                          checked={config[layer.key]}
                          onChange={(e) => updateConfig(layer.key, e.target.checked)}
                          className="peer sr-only"
                        />
                        <span className={`h-3 w-3 transform rounded-full bg-white transition-transform ${config[layer.key] ? 'translate-x-5 bg-primary' : 'translate-x-1'}`} />
                      </label>
                    </div>
                    {!config[layer.key] && (
                      <div className="flex items-start gap-2 mt-2 p-2 rounded bg-amber-500/10 border border-amber-500/20">
                        <span className="material-symbols-outlined text-amber-400 text-sm">warning</span>
                        <p className="text-[10px] text-amber-200/80">{layer.impactIfDisabled}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>

            {/* HITL Configuration */}
            <section className="rounded-xl border border-surface-border bg-surface-dark overflow-hidden">
              <div className="px-5 py-3 border-b border-surface-border bg-surface-darker">
                <h3 className="text-white font-bold flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">support_agent</span>
                  Human-in-the-Loop
                </h3>
              </div>
              <div className="p-4 space-y-4">
                {/* HITL Toggle */}
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-white text-sm font-medium">Enable HITL</h4>
                    <p className="text-xs text-text-dim">Route low-confidence to review</p>
                  </div>
                  <label className="relative inline-flex h-5 w-9 items-center rounded-full bg-surface-border cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.hitl_enabled}
                      onChange={(e) => updateConfig('hitl_enabled', e.target.checked)}
                      className="peer sr-only"
                    />
                    <span className={`h-3 w-3 transform rounded-full bg-white transition-transform ${config.hitl_enabled ? 'translate-x-5 bg-primary' : 'translate-x-1'}`} />
                  </label>
                </div>

                {/* Confidence Threshold */}
                <div className="pt-2 border-t border-surface-border">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs text-text-dim">Confidence Threshold</span>
                    <span className="text-lg font-bold text-primary">{config.confidence_threshold}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={config.confidence_threshold}
                    onChange={(e) => updateThreshold(e.target.value)}
                    className="w-full h-1.5 bg-surface-border rounded-lg appearance-none cursor-pointer accent-primary"
                    aria-label="Confidence threshold percentage"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={config.confidence_threshold}
                  />
                  <div className="flex justify-between text-[10px] text-text-dim mt-1">
                    <span>Relaxed</span>
                    <span>Strict</span>
                  </div>
                </div>
              </div>
            </section>
          </div>

          {/* Right Column: Evaluation Results */}
          <div className="lg:col-span-2 space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-4 gap-3">
              <div className="bg-surface-dark border border-surface-border rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-text-dim text-xs">Pass Rate</span>
                  <span className="material-symbols-outlined text-emerald-400 text-lg">check_circle</span>
                </div>
                <div className="text-2xl font-bold text-white">
                  {hasRun ? `${summary.pass_rate}%` : '-'}
                </div>
                <div className="text-[10px] text-emerald-400">
                  {hasRun ? `${summary.passed}/${summary.total_cases} passed` : 'Run evals to see results'}
                </div>
              </div>

              <div className="bg-surface-dark border border-surface-border rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-text-dim text-xs">Avg Latency</span>
                  <span className="material-symbols-outlined text-blue-400 text-lg">speed</span>
                </div>
                <div className="text-2xl font-bold text-white">
                  {hasRun ? `${summary.avg_latency_ms}ms` : '-'}
                </div>
                <div className="text-[10px] text-text-dim">
                  {hasRun ? 'Per query' : 'Run evals to measure'}
                </div>
              </div>

              <div className="bg-surface-dark border border-surface-border rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-text-dim text-xs">Hallucination</span>
                  <span className="material-symbols-outlined text-amber-400 text-lg">psychology_alt</span>
                </div>
                <div className="text-2xl font-bold text-white">
                  {hasRun ? `${summary.hallucination_rate}%` : '-'}
                </div>
                <div className="text-[10px] text-amber-400">
                  {hasRun ? 'Low risk' : 'Run evals to detect'}
                </div>
              </div>

              <div className="bg-surface-dark border border-surface-border rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-text-dim text-xs">Total Cases</span>
                  <span className="material-symbols-outlined text-primary text-lg">assessment</span>
                </div>
                <div className="text-2xl font-bold text-white">{cases.length}</div>
                <div className="text-[10px] text-text-dim">Available test cases</div>
              </div>
            </div>

            {/* Category Filter */}
            {cases.length > 0 && (
              <div className="flex gap-2 overflow-x-auto pb-2">
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                      selectedCategory === cat
                        ? 'bg-primary/20 text-primary border border-primary/30'
                        : 'bg-surface-dark text-text-dim hover:border-surface-border hover:text-white border border-transparent'
                    }`}
                  >
                    {formatCategory(cat)}
                  </button>
                ))}
              </div>
            )}

            {/* Check Type Legend */}
            {hasRun && <CheckTypeLegend />}

            {/* Results List */}
            <div className="bg-surface-dark border border-surface-border rounded-xl overflow-hidden">
              {cases.length === 0 ? (
                <div className="p-8 text-center">
                  <span className="material-symbols-outlined text-4xl text-surface-border">assessment</span>
                  <p className="text-text-dim mt-2">No eval cases found. Check that evals/eval_cases/mvp_evals.json exists.</p>
                </div>
              ) : (
                <div className="divide-y divide-surface-border">
                  {filteredCases.map((testCase) => {
                    const result = getResult(testCase.id);
                    return (
                      <EvalResultCard key={testCase.id} result={result} testCase={testCase} />
                    );
                  })}
                </div>
              )}
            </div>

            {/* Run Evals Prompt */}
            {cases.length > 0 && !hasRun && (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex items-center gap-3">
                <span className="material-symbols-outlined text-amber-400 text-2xl">info</span>
                <div>
                  <p className="text-amber-200 text-sm font-medium">No evaluation results yet</p>
                  <p className="text-amber-200/70 text-xs">Click "Run All Tests" above to execute all {cases.length} test cases.</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
