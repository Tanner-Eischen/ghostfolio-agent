import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { verificationApi, evalsApi } from '../api/client';
import type { VerificationConfig, EvalCase, EvalResult, EvalSummary } from '../api/client';

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

export function VerificationEvals() {
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
      await evalsApi.runAll();

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
                {/* Fact Checking */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-surface-darker border border-surface-border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400">
                      <span className="material-symbols-outlined text-lg">fact_check</span>
                    </div>
                    <div>
                      <h4 className="text-white text-sm font-medium">Fact Checking</h4>
                      <p className="text-xs text-text-dim">Verify against data sources</p>
                    </div>
                  </div>
                  <label className="relative inline-flex h-5 w-9 items-center rounded-full bg-surface-border cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.fact_checking}
                      onChange={(e) => updateConfig('fact_checking', e.target.checked)}
                      className="peer sr-only"
                    />
                    <span className={`h-3 w-3 transform rounded-full bg-white transition-transform ${config.fact_checking ? 'translate-x-5 bg-primary' : 'translate-x-1'}`} />
                  </label>
                </div>

                {/* Hallucination Detection */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-surface-darker border border-surface-border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400">
                      <span className="material-symbols-outlined text-lg">psychology_alt</span>
                    </div>
                    <div>
                      <h4 className="text-white text-sm font-medium">Hallucination Detection</h4>
                      <p className="text-xs text-text-dim">Flag fabricated info</p>
                    </div>
                  </div>
                  <label className="relative inline-flex h-5 w-9 items-center rounded-full bg-surface-border cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.hallucination_detection}
                      onChange={(e) => updateConfig('hallucination_detection', e.target.checked)}
                      className="peer sr-only"
                    />
                    <span className={`h-3 w-3 transform rounded-full bg-white transition-transform ${config.hallucination_detection ? 'translate-x-5 bg-primary' : 'translate-x-1'}`} />
                  </label>
                </div>

                {/* Confidence Scoring */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-surface-darker border border-surface-border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400">
                      <span className="material-symbols-outlined text-lg">speed</span>
                    </div>
                    <div>
                      <h4 className="text-white text-sm font-medium">Confidence Scoring</h4>
                      <p className="text-xs text-text-dim">Report confidence levels</p>
                    </div>
                  </div>
                  <label className="relative inline-flex h-5 w-9 items-center rounded-full bg-surface-border cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.confidence_scoring}
                      onChange={(e) => updateConfig('confidence_scoring', e.target.checked)}
                      className="peer sr-only"
                    />
                    <span className={`h-3 w-3 transform rounded-full bg-white transition-transform ${config.confidence_scoring ? 'translate-x-5 bg-primary' : 'translate-x-1'}`} />
                  </label>
                </div>
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

            {/* Results Table */}
            <div className="bg-surface-dark border border-surface-border rounded-xl overflow-hidden">
              {cases.length === 0 ? (
                <div className="p-8 text-center">
                  <span className="material-symbols-outlined text-4xl text-surface-border">assessment</span>
                  <p className="text-text-dim mt-2">No eval cases found. Check that evals/eval_cases/mvp_evals.json exists.</p>
                </div>
              ) : (
                <table className="w-full">
                  <thead>
                    <tr className="bg-surface-darker text-[10px] uppercase text-text-dim font-semibold tracking-wider">
                      <th className="px-4 py-3 text-left">Test Case</th>
                      <th className="px-4 py-3 text-left">Category</th>
                      <th className="px-4 py-3 text-center">Status</th>
                      <th className="px-4 py-3 text-center">Score</th>
                      <th className="px-4 py-3 text-center">Latency</th>
                      <th className="px-4 py-3 text-left">Error</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {filteredCases.map((testCase) => {
                      const result = getResult(testCase.id);
                      return (
                        <tr key={testCase.id} className="hover:bg-surface-border/30 transition-colors">
                          <td className="px-4 py-3">
                            <div>
                              <span className="text-white text-sm font-medium">{testCase.name}</span>
                              <p className="text-[10px] text-text-dim mt-0.5">{testCase.description}</p>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-xs text-text-dim">{testCase.category}</span>
                          </td>
                          <td className="px-4 py-3 text-center">
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
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className={`font-mono text-sm ${result && result.score >= 0.8 ? 'text-emerald-400' : result && result.score >= 0.5 ? 'text-amber-400' : 'text-text-dim'}`}>
                              {result ? `${Math.round(result.score * 100)}%` : '-'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className="text-text-dim font-mono text-xs">
                              {result ? `${result.duration_ms}ms` : '-'}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {result?.error && (
                              <span className="text-[10px] text-red-400">{result.error}</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
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
