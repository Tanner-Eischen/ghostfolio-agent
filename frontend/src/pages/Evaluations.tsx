import { useEffect, useState } from 'react';
import { evalsApi } from '../api/client';
import type { EvalCase, EvalResult, EvalSummary } from '../api/client';

const mockCases: EvalCase[] = [
  { id: 'e1', name: 'Portfolio Value Query', description: 'Test agent ability to retrieve accurate portfolio values', category: 'Data Retrieval' },
  { id: 'e2', name: 'Risk Assessment', description: 'Validate risk level calculations and recommendations', category: 'Analysis' },
  { id: 'e3', name: 'Tax Impact Calculation', description: 'Test capital gains tax estimation accuracy', category: 'Calculations' },
  { id: 'e4', name: 'Compliance Check', description: 'Verify wash-sale rule detection', category: 'Compliance' },
  { id: 'e5', name: 'Market Data Lookup', description: 'Test real-time price fetching', category: 'Data Retrieval' },
];

const mockSummary: EvalSummary = {
  total_cases: 5,
  passed: 4,
  failed: 1,
  pass_rate: 80,
  avg_latency_ms: 1250,
  hallucination_rate: 5,
};

const mockResults: EvalResult[] = [
  { case_id: 'e1', passed: true, score: 0.95, duration_ms: 890 },
  { case_id: 'e2', passed: true, score: 0.88, duration_ms: 1234 },
  { case_id: 'e3', passed: false, score: 0.42, duration_ms: 2100, error: 'Calculation mismatch: expected 15.5%, got 14.2%' },
  { case_id: 'e4', passed: true, score: 0.91, duration_ms: 1560 },
  { case_id: 'e5', passed: true, score: 0.97, duration_ms: 520 },
];

export function Evaluations() {
  const [cases, setCases] = useState<EvalCase[]>(mockCases);
  const [results, setResults] = useState<EvalResult[]>(mockResults);
  const [summary, setSummary] = useState<EvalSummary>(mockSummary);
  const [running, setRunning] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');

  useEffect(() => {
    async function fetchData() {
      try {
        const [casesData, resultsData] = await Promise.all([
          evalsApi.getCases(),
          evalsApi.getResults(),
        ]);
        if (casesData.length > 0) setCases(casesData);
        if (resultsData.results.length > 0) {
          setResults(resultsData.results);
          setSummary(resultsData.summary);
        }
      } catch (error) {
        console.error('Failed to fetch eval data:', error);
      }
    }
    fetchData();
  }, []);

  const handleRunAll = async () => {
    setRunning(true);
    try {
      await evalsApi.runAll();
      // In real implementation, poll for results
      setTimeout(() => setRunning(false), 3000);
    } catch (error) {
      console.error('Failed to run evals:', error);
      setRunning(false);
    }
  };

  const categories = ['All', ...new Set(cases.map(c => c.category))];

  const filteredCases = selectedCategory === 'All'
    ? cases
    : cases.filter(c => c.category === selectedCategory);

  const getResult = (caseId: string) => results.find(r => r.case_id === caseId);

  return (
    <main className="flex-1 px-6 md:px-10 py-8 overflow-y-auto">
      <div className="mx-auto max-w-[1200px]">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8">
          <div>
            <div className="flex items-center gap-2 mb-2 text-sm">
              <span className="text-text-dim">Home</span>
              <span className="text-surface-border">/</span>
              <span className="text-white font-medium">Evaluations</span>
            </div>
            <h1 className="text-white text-3xl font-black mb-2">Systematic Evaluation Dashboard</h1>
            <p className="text-text-dim">Run comprehensive tests to validate agent behavior and response quality.</p>
          </div>
          <div className="flex gap-3">
            <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-text-dim bg-surface-dark border border-surface-border rounded-lg hover:text-white transition-colors">
              <span className="material-symbols-outlined text-lg">download</span>
              Export Report
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

        {/* KPI Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="bg-surface-dark border border-surface-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-text-dim text-sm">Pass Rate</span>
              <span className="material-symbols-outlined text-emerald-400">check_circle</span>
            </div>
            <div className="text-3xl font-bold text-white">{summary.pass_rate}%</div>
            <div className="text-xs text-emerald-400 mt-1">{summary.passed}/{summary.total_cases} passed</div>
          </div>

          <div className="bg-surface-dark border border-surface-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-text-dim text-sm">Avg Latency</span>
              <span className="material-symbols-outlined text-blue-400">speed</span>
            </div>
            <div className="text-3xl font-bold text-white">{summary.avg_latency_ms}ms</div>
            <div className="text-xs text-text-dim mt-1">Per query</div>
          </div>

          <div className="bg-surface-dark border border-surface-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-text-dim text-sm">Hallucination Rate</span>
              <span className="material-symbols-outlined text-amber-400">psychology_alt</span>
            </div>
            <div className="text-3xl font-bold text-white">{summary.hallucination_rate}%</div>
            <div className="text-xs text-amber-400 mt-1">Low risk</div>
          </div>

          <div className="bg-surface-dark border border-surface-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-text-dim text-sm">Total Cases</span>
              <span className="material-symbols-outlined text-primary">assessment</span>
            </div>
            <div className="text-3xl font-bold text-white">{summary.total_cases}</div>
            <div className="text-xs text-text-dim mt-1">{cases.length} available</div>
          </div>
        </div>

        {/* Category Filter */}
        <div className="flex gap-3 mb-6 overflow-x-auto pb-2">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                selectedCategory === cat
                  ? 'bg-primary/20 text-primary border border-primary/30'
                  : 'bg-surface-dark text-text-dim hover:border-surface-border hover:text-white border border-transparent'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Results Table */}
        <div className="bg-surface-dark border border-surface-border rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-surface-darker text-xs uppercase text-text-dim font-semibold tracking-wider">
                <th className="px-6 py-4 text-left">Test Case</th>
                <th className="px-6 py-4 text-left">Category</th>
                <th className="px-6 py-4 text-center">Status</th>
                <th className="px-6 py-4 text-center">Score</th>
                <th className="px-6 py-4 text-center">Latency</th>
                <th className="px-6 py-4 text-left">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {filteredCases.map((testCase) => {
                const result = getResult(testCase.id);
                return (
                  <tr key={testCase.id} className="hover:bg-surface-border/30 transition-colors">
                    <td className="px-6 py-4">
                      <div>
                        <span className="text-white font-medium">{testCase.name}</span>
                        <p className="text-xs text-text-dim mt-0.5">{testCase.description}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-text-dim">{testCase.category}</span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        result?.passed
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : result
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-slate-500/20 text-slate-400'
                      }`}>
                        <span className="material-symbols-outlined text-sm">
                          {result?.passed ? 'check_circle' : result ? 'cancel' : 'pending'}
                        </span>
                        {result?.passed ? 'Passed' : result ? 'Failed' : 'Pending'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className={`font-mono ${result && result.score >= 0.8 ? 'text-emerald-400' : result && result.score >= 0.5 ? 'text-amber-400' : 'text-text-dim'}`}>
                        {result ? `${Math.round(result.score * 100)}%` : '-'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className="text-text-dim font-mono text-sm">
                        {result ? `${result.duration_ms}ms` : '-'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {result?.error && (
                        <span className="text-xs text-red-400">{result.error}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
