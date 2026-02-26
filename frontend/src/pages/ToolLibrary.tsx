import { useEffect, useState } from 'react';
import { toolsApi, chatApi } from '../api/client';
import type { Tool, ChatResponse } from '../api/client';

const mockTools: Tool[] = [
  {
    id: '1',
    name: 'portfolio_analysis',
    description: 'Analyzes asset allocation and risk exposure across linked brokerage accounts.',
    parameters: { account_id: 'string', symbols: 'array<string>', benchmark: 'string?' },
    status: 'active',
  },
  {
    id: '2',
    name: 'transaction_categorize',
    description: 'Auto-categorizes transactions based on merchant codes and spending history.',
    parameters: { transaction_list: 'array<obj>', rules_id: 'string' },
    status: 'beta',
  },
  {
    id: '3',
    name: 'tax_estimate',
    description: 'Estimates short/long term capital gains tax based on current fiscal year rules.',
    parameters: { realized_gains: 'float', region_code: 'string', income_bracket: 'integer' },
    status: 'active',
  },
  {
    id: '4',
    name: 'compliance_check',
    description: 'Validates trades against wash-sale rules and restricted security lists.',
    parameters: { trade_intent: 'object', portfolio_history: 'ref_id' },
    status: 'active',
  },
  {
    id: '5',
    name: 'market_data',
    description: 'Fetches real-time price, volume, and depth for requested ticker symbols.',
    parameters: { tickers: 'array<string>', interval: 'string', source: 'string' },
    status: 'active',
  },
];

const iconColors = [
  'from-blue-600 to-indigo-900',
  'from-emerald-600 to-teal-900',
  'from-orange-600 to-red-900',
  'from-purple-600 to-fuchsia-900',
  'from-cyan-600 to-blue-800',
];

const iconMap: Record<string, string> = {
  portfolio_analysis: 'pie_chart',
  transaction_categorize: 'category',
  tax_estimate: 'receipt_long',
  compliance_check: 'gavel',
  market_data: 'candlestick_chart',
};

export function ToolLibrary() {
  const [tools, setTools] = useState<Tool[]>(mockTools);
  const [_selectedTool, setSelectedTool] = useState<Tool | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function fetchTools() {
      try {
        const data = await toolsApi.list();
        if (data.length > 0) setTools(data);
      } catch (error) {
        console.error('Failed to fetch tools:', error);
      }
    }
    fetchTools();
  }, []);

  const handleChat = async () => {
    if (!chatInput.trim()) return;

    const userMessage = chatInput;
    setChatInput('');
    setChatHistory(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const response: ChatResponse = await chatApi.send({ message: userMessage });
      setChatHistory(prev => [...prev, { role: 'assistant', content: response.response }]);
    } catch (error) {
      setChatHistory(prev => [...prev, { role: 'assistant', content: 'Error: Failed to get response.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full">
      {/* Side Navigation */}
      <aside className="flex w-64 flex-col bg-surface-darker border-r border-surface-border flex-shrink-0 h-full">
        <div className="flex flex-col h-full justify-between p-4">
          <div className="flex flex-col gap-6">
            {/* Brand */}
            <div className="flex items-center gap-3 px-2">
              <div className="bg-primary/20 flex items-center justify-center rounded-lg size-10">
                <span className="material-symbols-outlined text-primary">ssid_chart</span>
              </div>
              <div className="flex flex-col">
                <h1 className="text-white text-base font-bold leading-tight">Ghostfolio AI</h1>
                <p className="text-text-dim text-xs">Finance Ecosystem</p>
              </div>
            </div>

            {/* Navigation */}
            <nav className="flex flex-col gap-1">
              <a href="/" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-text-dim hover:bg-surface-border hover:text-white transition-colors">
                <span className="material-symbols-outlined text-xl">dashboard</span>
                <span className="text-sm font-medium">Dashboard</span>
              </a>
              <a href="/tools" className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-surface-border text-white">
                <span className="material-symbols-outlined text-xl text-primary fill-1">handyman</span>
                <span className="text-sm font-medium">Tool Library</span>
              </a>
              <a href="/strategy" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-text-dim hover:bg-surface-border hover:text-white transition-colors">
                <span className="material-symbols-outlined text-xl">smart_toy</span>
                <span className="text-sm font-medium">Strategy</span>
              </a>
            </nav>
          </div>

          {/* Create Tool Button */}
          <button className="flex w-full items-center justify-center gap-2 rounded-lg h-10 px-4 bg-primary hover:bg-primary/90 text-surface-darker text-sm font-bold transition-colors">
            <span className="material-symbols-outlined text-lg">add</span>
            <span>New Tool</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex flex-col flex-1 h-full overflow-hidden relative">
        {/* Header */}
        <header className="flex flex-col gap-6 px-8 pt-8 pb-4 flex-shrink-0">
          <div className="flex flex-wrap justify-between items-end gap-4">
            <div className="flex flex-col gap-2 max-w-2xl">
              <h2 className="text-white text-3xl font-bold tracking-tight">Financial Tool Library</h2>
              <p className="text-text-dim text-base">
                Manage and configure the core financial analysis functions available to your AI agents. All tools are sandboxed and monitored.
              </p>
            </div>
            <div className="flex gap-3">
              <button className="flex items-center gap-2 px-4 h-10 rounded-lg bg-surface-dark border border-surface-border text-white hover:bg-surface-border transition-colors text-sm font-medium">
                <span className="material-symbols-outlined text-lg">upload</span>
                Import Schema
              </button>
              <button className="flex items-center gap-2 px-4 h-10 rounded-lg bg-surface-dark border border-surface-border text-white hover:bg-surface-border transition-colors text-sm font-medium">
                <span className="material-symbols-outlined text-lg">terminal</span>
                View Logs
              </button>
            </div>
          </div>

          {/* Filter Chips */}
          <div className="flex gap-3 overflow-x-auto pb-2 border-b border-surface-border/30">
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/20 text-primary border border-primary/30 text-sm font-medium whitespace-nowrap">
              <span className="material-symbols-outlined text-lg">grid_view</span>
              All Tools
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-dark text-text-dim hover:border-surface-border hover:text-white text-sm font-medium whitespace-nowrap transition-colors">
              <span className="material-symbols-outlined text-lg">monitoring</span>
              Analysis
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-dark text-text-dim hover:border-surface-border hover:text-white text-sm font-medium whitespace-nowrap transition-colors">
              <span className="material-symbols-outlined text-lg">verified_user</span>
              Compliance
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-dark text-text-dim hover:border-surface-border hover:text-white text-sm font-medium whitespace-nowrap transition-colors">
              <span className="material-symbols-outlined text-lg">database</span>
              Data Feeds
            </button>
          </div>
        </header>

        {/* Tool Cards */}
        <div className="flex-1 overflow-y-auto px-8 pb-32">
          <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-6">
            {tools.map((tool, index) => (
              <div
                key={tool.id}
                className="group bg-surface-dark rounded-xl border border-surface-border hover:border-primary/50 transition-all p-5 flex flex-col gap-4 shadow-lg cursor-pointer"
                onClick={() => setSelectedTool(tool)}
              >
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-3">
                    <div className={`bg-gradient-to-br ${iconColors[index % iconColors.length]} rounded-lg p-2.5`}>
                      <span className="material-symbols-outlined text-white">
                        {iconMap[tool.name] || 'extension'}
                      </span>
                    </div>
                    <div>
                      <h3 className="text-white font-bold text-lg">{tool.name}</h3>
                      <span className={`flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full w-fit mt-1 ${
                        tool.status === 'active' ? 'text-emerald-400 bg-emerald-400/10' :
                        tool.status === 'beta' ? 'text-amber-400 bg-amber-400/10' :
                        'text-slate-400 bg-slate-400/10'
                      }`}>
                        <span className="material-symbols-outlined text-sm">
                          {tool.status === 'active' ? 'check_circle' : tool.status === 'beta' ? 'science' : 'block'}
                        </span>
                        {tool.status === 'active' ? 'Fact-Check Enabled' : tool.status === 'beta' ? 'Beta' : 'Disabled'}
                      </span>
                    </div>
                  </div>
                  <button className="text-text-dim hover:text-white transition-colors">
                    <span className="material-symbols-outlined">more_vert</span>
                  </button>
                </div>
                <p className="text-text-dim text-sm">{tool.description}</p>
                <div className="bg-surface-darker rounded-lg p-3 border border-white/5 font-mono text-xs text-text-dim">
                  <div className="flex justify-between items-center mb-2 border-b border-white/5 pb-1">
                    <span className="text-primary font-semibold">PARAMETERS</span>
                    <span className="text-[10px] opacity-50">JSON</span>
                  </div>
                  {Object.entries(tool.parameters).map(([key, value]) => (
                    <p key={key}>
                      <span className="text-purple-400">{key}</span>: <span className="text-orange-300">{String(value)}</span>
                    </p>
                  ))}
                </div>
                <div className="mt-auto pt-2 flex justify-end">
                  <button className="text-sm font-medium text-primary hover:text-white transition-colors flex items-center gap-1">
                    Configure <span className="material-symbols-outlined text-base">arrow_forward</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Test Console */}
        <div className="absolute bottom-0 left-0 right-0 border-t border-surface-border bg-surface-darker/95 backdrop-blur-md shadow-lg z-10">
          <div className="flex flex-col">
            <div className="flex items-center justify-between px-6 py-2 border-b border-surface-border/30 cursor-pointer hover:bg-white/5">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-sm">terminal</span>
                <span className="text-sm font-bold text-white uppercase tracking-wider">Test Console</span>
                <span className="text-xs text-text-dim ml-2 font-mono">{loading ? 'Processing...' : 'Idle - Ready for input'}</span>
              </div>
            </div>
            <div className="flex h-32">
              <div className="flex-1 p-4 border-r border-surface-border/30 font-mono text-sm">
                <div className="flex gap-2">
                  <span className="text-green-400 select-none">{'>'}</span>
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleChat()}
                    className="bg-transparent border-none outline-none text-white w-full placeholder-slate-600 focus:ring-0 p-0"
                    placeholder="Ask about your portfolio..."
                  />
                </div>
              </div>
              <div className="w-1/3 bg-surface-darker p-4 overflow-y-auto font-mono text-xs">
                {chatHistory.length === 0 ? (
                  <div className="text-slate-500">// Output Log</div>
                ) : (
                  chatHistory.map((msg, i) => (
                    <div key={i} className={msg.role === 'user' ? 'text-blue-400' : 'text-green-400'}>
                      {msg.role === 'user' ? '> ' : ''}{msg.content}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
