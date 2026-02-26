import { useEffect, useState } from 'react';
import { financesApi } from '../api/client';
import type { UsageStats, CostProjections } from '../api/client';

const mockUsage: UsageStats = {
  total_cost: 12.45,
  total_tokens: 1250000,
  requests_count: 847,
  avg_cost_per_request: 0.0147,
};

const mockProjections: CostProjections = {
  daily_cost: 2.50,
  monthly_cost: 75.00,
  projected_annual: 912.50,
  cost_breakdown: {
    input_tokens: 45,
    output_tokens: 55,
  },
};

export function Finances() {
  const [usage, setUsage] = useState<UsageStats>(mockUsage);
  const [projections, setProjections] = useState<CostProjections>(mockProjections);
  const [queriesPerDay, setQueriesPerDay] = useState(100);

  useEffect(() => {
    async function fetchData() {
      try {
        const [usageData, projectionsData] = await Promise.all([
          financesApi.getUsage(),
          financesApi.getProjections(queriesPerDay),
        ]);
        setUsage(usageData);
        setProjections(projectionsData);
      } catch (error) {
        console.error('Failed to fetch finance data:', error);
      }
    }
    fetchData();
  }, [queriesPerDay]);

  return (
    <main className="flex-1 px-6 md:px-10 py-8 overflow-y-auto">
      <div className="mx-auto max-w-[1000px]">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-2 text-sm">
            <span className="text-text-dim">Home</span>
            <span className="text-surface-border">/</span>
            <span className="text-white font-medium">Finances</span>
          </div>
          <h1 className="text-white text-3xl font-black mb-2">AI Unit Economics & Cost Projections</h1>
          <p className="text-text-dim">Track development spending and forecast production costs.</p>
        </div>

        {/* Current Development Spend */}
        <section className="mb-8">
          <h2 className="text-white text-lg font-bold mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">account_balance_wallet</span>
            Current Development Spend
          </h2>
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-surface-dark border border-surface-border rounded-xl p-5">
              <span className="text-text-dim text-sm">Total Cost</span>
              <div className="text-3xl font-bold text-white mt-2">${usage.total_cost.toFixed(2)}</div>
              <div className="text-xs text-text-dim mt-1">This billing period</div>
            </div>
            <div className="bg-surface-dark border border-surface-border rounded-xl p-5">
              <span className="text-text-dim text-sm">Tokens Used</span>
              <div className="text-3xl font-bold text-white mt-2">{(usage.total_tokens / 1000000).toFixed(2)}M</div>
              <div className="text-xs text-text-dim mt-1">Total tokens</div>
            </div>
            <div className="bg-surface-dark border border-surface-border rounded-xl p-5">
              <span className="text-text-dim text-sm">API Requests</span>
              <div className="text-3xl font-bold text-white mt-2">{usage.requests_count.toLocaleString()}</div>
              <div className="text-xs text-text-dim mt-1">Total requests</div>
            </div>
            <div className="bg-surface-dark border border-surface-border rounded-xl p-5">
              <span className="text-text-dim text-sm">Avg Cost/Query</span>
              <div className="text-3xl font-bold text-white mt-2">${usage.avg_cost_per_request.toFixed(4)}</div>
              <div className="text-xs text-text-dim mt-1">Per request</div>
            </div>
          </div>
        </section>

        {/* Cost Breakdown */}
        <section className="mb-8">
          <h2 className="text-white text-lg font-bold mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">donut_large</span>
            Cost Breakdown
          </h2>
          <div className="bg-surface-dark border border-surface-border rounded-xl p-6">
            <div className="flex gap-8">
              {/* Pie Chart Placeholder */}
              <div className="relative w-48 h-48 flex-shrink-0">
                <svg viewBox="0 0 100 100" className="transform -rotate-90">
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    stroke="#234248"
                    strokeWidth="20"
                  />
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    stroke="#13c8ec"
                    strokeWidth="20"
                    strokeDasharray={`${projections.cost_breakdown.input_tokens * 2.51} 251`}
                  />
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    stroke="#f59e0b"
                    strokeWidth="20"
                    strokeDasharray={`${projections.cost_breakdown.output_tokens * 2.51} 251`}
                    strokeDashoffset={`-${projections.cost_breakdown.input_tokens * 2.51}`}
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <span className="text-2xl font-bold text-white">100%</span>
                  </div>
                </div>
              </div>

              {/* Legend */}
              <div className="flex-1 flex flex-col justify-center gap-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded-full bg-primary" />
                    <span className="text-white">Input Tokens</span>
                  </div>
                  <span className="text-white font-bold">{projections.cost_breakdown.input_tokens}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded-full bg-amber-500" />
                    <span className="text-white">Output Tokens</span>
                  </div>
                  <span className="text-white font-bold">{projections.cost_breakdown.output_tokens}%</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Production Projections */}
        <section>
          <h2 className="text-white text-lg font-bold mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">trending_up</span>
            Production Projections
          </h2>
          <div className="bg-surface-dark border border-surface-border rounded-xl p-6">
            {/* Queries Slider */}
            <div className="mb-8">
              <div className="flex justify-between items-center mb-3">
                <span className="text-white font-medium">Estimated Queries per Day</span>
                <span className="text-2xl font-bold text-primary">{queriesPerDay}</span>
              </div>
              <input
                type="range"
                min="10"
                max="1000"
                step="10"
                value={queriesPerDay}
                onChange={(e) => setQueriesPerDay(parseInt(e.target.value))}
                className="w-full h-2 bg-surface-border rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <div className="flex justify-between text-xs text-text-dim mt-2">
                <span>10</span>
                <span>500</span>
                <span>1000</span>
              </div>
            </div>

            {/* Projection Cards */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-surface-darker rounded-xl p-5 border border-surface-border">
                <div className="flex items-center gap-2 mb-3">
                  <span className="material-symbols-outlined text-blue-400">today</span>
                  <span className="text-text-dim text-sm">Daily Cost</span>
                </div>
                <div className="text-3xl font-bold text-white">${projections.daily_cost.toFixed(2)}</div>
                <div className="text-xs text-text-dim mt-1">At {queriesPerDay} queries/day</div>
              </div>

              <div className="bg-surface-darker rounded-xl p-5 border border-surface-border">
                <div className="flex items-center gap-2 mb-3">
                  <span className="material-symbols-outlined text-emerald-400">calendar_month</span>
                  <span className="text-text-dim text-sm">Monthly Cost</span>
                </div>
                <div className="text-3xl font-bold text-white">${projections.monthly_cost.toFixed(2)}</div>
                <div className="text-xs text-text-dim mt-1">30-day projection</div>
              </div>

              <div className="bg-surface-darker rounded-xl p-5 border border-primary/30">
                <div className="flex items-center gap-2 mb-3">
                  <span className="material-symbols-outlined text-primary">event</span>
                  <span className="text-text-dim text-sm">Annual Projection</span>
                </div>
                <div className="text-3xl font-bold text-primary">${projections.projected_annual.toFixed(2)}</div>
                <div className="text-xs text-text-dim mt-1">12-month estimate</div>
              </div>
            </div>

            {/* Cost per Query Breakdown */}
            <div className="mt-6 p-4 bg-background-dark rounded-lg">
              <h4 className="text-sm font-semibold text-text-dim mb-3">Cost per Query Breakdown</h4>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-white text-sm">GPT-4o Input (per 1M tokens)</span>
                  <span className="text-text-dim font-mono">$2.50</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-white text-sm">GPT-4o Output (per 1M tokens)</span>
                  <span className="text-text-dim font-mono">$10.00</span>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-surface-border">
                  <span className="text-white text-sm font-medium">Estimated per-query cost</span>
                  <span className="text-primary font-mono font-bold">${usage.avg_cost_per_request.toFixed(4)}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
