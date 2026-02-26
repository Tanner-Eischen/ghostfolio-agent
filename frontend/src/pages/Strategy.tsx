import { useEffect, useState } from 'react';
import { strategyApi } from '../api/client';
import type { StrategyConfig, StrategyRecommendation } from '../api/client';

const frameworks = [
  { name: 'LangChain', type: 'Standard Chains', reasoning: 'Linear', complexity: 40, ecosystem: 'Python/JS' },
  { name: 'LangGraph', type: 'Stateful Cyclic', reasoning: 'Cyclic Graph', complexity: 75, ecosystem: 'Python' },
  { name: 'CrewAI', type: 'Multi-Agent', reasoning: 'Role-Based', complexity: 60, ecosystem: 'Python' },
];

const contributionPaths = [
  { id: 'dataset', name: 'Release Dataset', description: 'Publish evaluation datasets to HuggingFace for community benchmarking.', icon: 'dataset', time: '2h' },
  { id: 'langchain', name: 'PR to LangChain', description: 'Contribute a new tool or fix directly to the LangChain repository.', icon: 'call_merge', time: '5-8h' },
  { id: 'deploy', name: 'Deploy Agent', description: 'Deploy directly to production infrastructure with monitoring.', icon: 'rocket_launch', time: '30m' },
];

const models = ['GPT-4o (OpenAI)', 'Claude 3.5 Sonnet (Anthropic)', 'Llama 3 70B (Meta)'];

export function Strategy() {
  const [config, setConfig] = useState<StrategyConfig | null>(null);
  const [_recommendations, setRecommendations] = useState<StrategyRecommendation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [configData, recsData] = await Promise.all([
          strategyApi.get().catch(() => ({
            framework: 'LangGraph',
            model: 'GPT-4o (OpenAI)',
            temperature: 0.0,
            json_mode: true,
            stream_responses: false,
            contribution_path: 'langchain',
          })),
          strategyApi.getRecommendations().catch(() => []),
        ]);
        setConfig(configData as StrategyConfig);
        setRecommendations(recsData);
      } catch (error) {
        console.error('Failed to fetch strategy data:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const handleSave = async () => {
    if (config) {
      try {
        await strategyApi.save(config);
        alert('Configuration saved!');
      } catch (error) {
        console.error('Failed to save:', error);
      }
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-dim">Loading...</div>
      </div>
    );
  }

  return (
    <main className="flex-1 px-6 md:px-10 py-8 overflow-y-auto">
      <div className="mx-auto max-w-[1200px]">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 mb-6 text-sm">
          <span className="text-text-dim hover:text-primary transition-colors cursor-pointer">Home</span>
          <span className="text-surface-border">/</span>
          <span className="text-white font-medium">Strategy & Architecture</span>
        </div>

        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div className="max-w-2xl">
            <h1 className="text-white text-3xl md:text-4xl font-black leading-tight mb-2">
              Agent Strategy & Architecture Hub
            </h1>
            <p className="text-text-dim text-lg">
              Define your AI agent's reasoning framework, select underlying models, and configure contribution pathways.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-text-dim bg-surface-dark border border-surface-border rounded-lg hover:text-white hover:border-text-dim transition-all">
              <span className="material-symbols-outlined text-lg">history</span>
              Load Preset
            </button>
            <button
              onClick={handleSave}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-background-dark bg-primary rounded-lg hover:bg-primary-hover shadow-lg transition-all"
            >
              <span className="material-symbols-outlined text-lg">save</span>
              Save Configuration
            </button>
          </div>
        </div>

        {/* Grid Layout */}
        <div className="grid grid-cols-12 gap-6">
          {/* Left Column */}
          <div className="col-span-12 lg:col-span-8 space-y-8">
            {/* Framework Selection */}
            <section className="rounded-xl border border-surface-border bg-surface-dark/50 overflow-hidden">
              <div className="px-6 py-4 border-b border-surface-border flex justify-between items-center bg-surface-dark">
                <h3 className="text-white text-lg font-bold flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">hub</span>
                  Framework Selection Matrix
                </h3>
                <span className="px-2 py-1 rounded bg-primary/10 text-primary text-xs font-medium border border-primary/20">
                  Recommended: LangGraph
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-surface-dark/50 text-xs uppercase text-text-dim font-semibold tracking-wider">
                      <th className="px-6 py-4 border-b border-surface-border">Framework</th>
                      <th className="px-6 py-4 border-b border-surface-border">Reasoning</th>
                      <th className="px-6 py-4 border-b border-surface-border">Complexity</th>
                      <th className="px-6 py-4 border-b border-surface-border">Ecosystem</th>
                      <th className="px-6 py-4 border-b border-surface-border text-center">Select</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {frameworks.map((fw) => (
                      <tr
                        key={fw.name}
                        className={`group hover:bg-surface-border/30 transition-colors ${
                          config?.framework === fw.name ? 'bg-primary/5 border-l-2 border-l-primary' : ''
                        }`}
                      >
                        <td className="px-6 py-4">
                          <div className="flex flex-col">
                            <span className="text-white font-medium">{fw.name}</span>
                            <span className={`text-xs ${config?.framework === fw.name ? 'text-primary' : 'text-text-dim'}`}>
                              {fw.type}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            config?.framework === fw.name
                              ? 'bg-primary/20 text-primary border border-primary/30'
                              : 'bg-slate-800 text-slate-300 border border-slate-700'
                          }`}>
                            {fw.reasoning}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-24 h-1.5 rounded-full bg-surface-border overflow-hidden">
                              <div
                                className={`h-full ${config?.framework === fw.name ? 'bg-primary' : 'bg-primary/60'}`}
                                style={{ width: `${fw.complexity}%` }}
                              />
                            </div>
                            <span className={`text-xs ${config?.framework === fw.name ? 'text-white' : 'text-text-dim'}`}>
                              {fw.complexity > 60 ? 'High' : fw.complexity > 40 ? 'Med' : 'Low'}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-text-dim">{fw.ecosystem}</td>
                        <td className="px-6 py-4 text-center">
                          <input
                            type="radio"
                            name="framework"
                            checked={config?.framework === fw.name}
                            onChange={() => setConfig(prev => prev ? { ...prev, framework: fw.name } : null)}
                            className="h-5 w-5 border-surface-border bg-transparent text-primary focus:ring-primary cursor-pointer"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Contribution Path */}
            <section>
              <h3 className="text-white text-lg font-bold mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">alt_route</span>
                Contribution Path
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {contributionPaths.map((path) => (
                  <label
                    key={path.id}
                    className={`relative flex flex-col p-5 rounded-xl cursor-pointer transition-all ${
                      config?.contribution_path === path.id
                        ? 'border-2 border-primary bg-primary/5 shadow-lg'
                        : 'border border-surface-border bg-surface-dark/50 hover:bg-surface-border/30 hover:shadow-lg'
                    }`}
                  >
                    <input
                      type="radio"
                      name="contribution"
                      checked={config?.contribution_path === path.id}
                      onChange={() => setConfig(prev => prev ? { ...prev, contribution_path: path.id } : null)}
                      className="peer sr-only"
                    />
                    {config?.contribution_path === path.id && (
                      <div className="absolute top-5 right-5 h-5 w-5 rounded-full bg-primary border border-primary flex items-center justify-center">
                        <span className="material-symbols-outlined text-background-dark text-sm font-bold">check</span>
                      </div>
                    )}
                    <div className={`mb-3 h-10 w-10 rounded-lg flex items-center justify-center ${
                      config?.contribution_path === path.id ? 'bg-primary/20 text-primary' : 'bg-indigo-500/20 text-indigo-400'
                    }`}>
                      <span className="material-symbols-outlined">{path.icon}</span>
                    </div>
                    <h4 className="text-white font-semibold mb-1">{path.name}</h4>
                    <p className="text-sm text-text-dim leading-relaxed">{path.description}</p>
                    <div className={`mt-4 pt-4 border-t flex items-center gap-2 text-xs ${
                      config?.contribution_path === path.id ? 'border-primary/20 text-primary' : 'border-surface-border text-text-dim'
                    }`}>
                      <span className="material-symbols-outlined text-base">schedule</span> Est. {path.time}
                    </div>
                  </label>
                ))}
              </div>
            </section>
          </div>

          {/* Right Column: Model Selector */}
          <div className="col-span-12 lg:col-span-4 space-y-6">
            <div className="rounded-xl border border-surface-border bg-surface-dark p-6 sticky top-24">
              <h3 className="text-white text-lg font-bold mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">psychology</span>
                Model Configuration
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-text-dim mb-2 uppercase tracking-wide">Base Model</label>
                  <select
                    value={config?.model}
                    onChange={(e) => setConfig(prev => prev ? { ...prev, model: e.target.value } : null)}
                    className="w-full appearance-none rounded-lg bg-background-dark border border-surface-border text-white px-4 py-3 pr-10 focus:ring-1 focus:ring-primary focus:border-primary focus:outline-none cursor-pointer hover:border-text-dim transition-colors"
                  >
                    {models.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>

                {/* Model Stats */}
                <div className="p-4 rounded-lg bg-background-dark border border-surface-border space-y-4">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-text-dim">Predicted Latency</span>
                      <span className="text-emerald-400 font-mono">240ms</span>
                    </div>
                    <div className="h-1.5 w-full bg-surface-dark rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded-full" style={{ width: '25%' }} />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-text-dim">Cost per 1k tokens</span>
                      <span className="text-amber-400 font-mono">$0.03</span>
                    </div>
                    <div className="h-1.5 w-full bg-surface-dark rounded-full overflow-hidden">
                      <div className="h-full bg-amber-500 rounded-full" style={{ width: '65%' }} />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-text-dim">Context Window</span>
                      <span className="text-primary font-mono">128k</span>
                    </div>
                    <div className="h-1.5 w-full bg-surface-dark rounded-full overflow-hidden">
                      <div className="h-full bg-primary rounded-full" style={{ width: '100%' }} />
                    </div>
                  </div>
                </div>

                {/* Toggles */}
                <div className="pt-4 border-t border-surface-border space-y-2">
                  <label className="flex items-center justify-between cursor-pointer group">
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-white group-hover:text-primary transition-colors">JSON Mode</span>
                      <span className="text-xs text-text-dim">Force structured output</span>
                    </div>
                    <div className="relative inline-flex h-6 w-11 items-center rounded-full bg-surface-border">
                      <input
                        type="checkbox"
                        checked={config?.json_mode}
                        onChange={(e) => setConfig(prev => prev ? { ...prev, json_mode: e.target.checked } : null)}
                        className="peer sr-only"
                      />
                      <span className={`h-4 w-4 transform rounded-full bg-white transition-transform ${config?.json_mode ? 'translate-x-6' : 'translate-x-1'}`} />
                    </div>
                  </label>
                  <label className="flex items-center justify-between cursor-pointer group">
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-white group-hover:text-primary transition-colors">Stream Responses</span>
                      <span className="text-xs text-text-dim">Real-time token delivery</span>
                    </div>
                    <div className="relative inline-flex h-6 w-11 items-center rounded-full bg-surface-border">
                      <input
                        type="checkbox"
                        checked={config?.stream_responses}
                        onChange={(e) => setConfig(prev => prev ? { ...prev, stream_responses: e.target.checked } : null)}
                        className="peer sr-only"
                      />
                      <span className={`h-4 w-4 transform rounded-full bg-white transition-transform ${config?.stream_responses ? 'translate-x-6' : 'translate-x-1'}`} />
                    </div>
                  </label>
                </div>
              </div>

              <button className="mt-6 w-full py-2.5 rounded-lg border border-primary/30 bg-primary/10 text-primary font-medium text-sm hover:bg-primary hover:text-background-dark transition-all">
                Run Benchmark
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
