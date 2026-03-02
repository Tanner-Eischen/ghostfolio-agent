import { useState, useEffect, useCallback, useRef } from 'react';
import {
  healthApi,
  chatApi,
  toolsApi,
  feedbackApi,
  sessionsApi,
  type HealthResponse,
  type Tool,
  type ChatResponse,
  type SessionSummary,
} from '../api/client';

import { useAppMode } from '../contexts/AppModeContext';

// Tab types
type MainTab = 'chat' | 'tools' | 'traces';

function formatHistoryDate(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
  } catch {
    return '';
  }
}

// Simple markdown renderer
function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="bg-surface-darker px-1 rounded text-primary">$1</code>')
    .replace(/\n/g, '<br/>');
}

// Toast notification component
function Toast({ message, type, onDismiss }: { message: string; type: 'success' | 'error'; onDismiss: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 3000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div className={`fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg z-50 ${
      type === 'success' ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white'
    }`}>
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-sm">
          {type === 'success' ? 'check_circle' : 'error'}
        </span>
        <span className="text-sm">{message}</span>
        <button onClick={onDismiss} className="ml-2 hover:opacity-70">
          <span className="material-symbols-outlined text-sm">close</span>
        </button>
      </div>
    </div>
  );
}

// Chat message component
function ChatMessage({
  role,
  content,
  toolCalls,
  runId,
  sessionId,
  onFeedback,
}: {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: Array<{ name: string; args: Record<string, unknown>; result?: unknown }>;
  runId?: string;
  sessionId?: string;
  onFeedback?: (rating: number) => void;
}) {
  const [feedbackGiven, setFeedbackGiven] = useState<number | null>(null);

  return (
    <div className={`flex ${role === 'user' ? 'justify-end' : 'justify-start'} mb-3 sm:mb-4`}>
      <div className={`max-w-[95%] sm:max-w-[85%] ${role === 'user' ? 'order-2' : 'order-1'}`}>
        <div className={`rounded-lg px-3 py-2.5 sm:px-4 sm:py-3 ${
          role === 'user'
            ? 'bg-primary text-white'
            : 'bg-surface-dark border border-surface-border text-slate-200'
        }`}>
          <div
            className="text-sm leading-relaxed"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
          />

          {/* Tool calls - collapsible sections with JSON args and results */}
          {toolCalls && toolCalls.length > 0 && (
            <div className="mt-3 pt-3 border-t border-surface-border">
              <div className="text-xs text-slate-400 mb-2">Tools used ({toolCalls.length}):</div>
              <div className="space-y-1">
                {toolCalls.map((tc, i) => (
                  <details key={i} className="bg-surface-darker rounded border border-surface-border">
                    <summary className="px-3 py-2 text-xs font-mono text-primary cursor-pointer hover:bg-surface-dark">
                      {tc.name}
                    </summary>
                    <div className="px-3 py-2 border-t border-surface-border">
                      <div className="text-[10px] text-slate-500 mb-1">Arguments</div>
                      <pre className="text-xs text-slate-300 font-mono overflow-x-auto">
                        {JSON.stringify(tc.args, null, 2)}
                      </pre>
                      {tc.result !== undefined && (
                        <>
                          <div className="text-[10px] text-slate-500 mb-1 mt-2">Result</div>
                          <pre className="text-xs text-slate-300 font-mono overflow-x-auto max-h-48">
                            {JSON.stringify(tc.result, null, 2)}
                          </pre>
                        </>
                      )}
                    </div>
                  </details>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Feedback buttons for assistant messages */}
        {role === 'assistant' && onFeedback && (
          <div className="flex items-center gap-2 mt-1 px-1">
            <button
              onClick={() => {
                if (runId && sessionId && feedbackGiven === null) {
                  onFeedback(1);
                  setFeedbackGiven(1);
                }
              }}
              className={`text-xs flex items-center gap-1 ${
                feedbackGiven === 1 ? 'text-emerald-400' : 'text-slate-500 hover:text-emerald-400'
              }`}
              disabled={feedbackGiven !== null}
            >
              <span className="material-symbols-outlined text-sm">thumb_up</span>
            </button>
            <button
              onClick={() => {
                if (runId && sessionId && feedbackGiven === null) {
                  onFeedback(-1);
                  setFeedbackGiven(-1);
                }
              }}
              className={`text-xs flex items-center gap-1 ${
                feedbackGiven === -1 ? 'text-red-400' : 'text-slate-500 hover:text-red-400'
              }`}
              disabled={feedbackGiven !== null}
            >
              <span className="material-symbols-outlined text-sm">thumb_down</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function AgentWorkspace() {
  const { appMode } = useAppMode();

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // Chat state
  const [messages, setMessages] = useState<Array<{
    role: 'user' | 'assistant';
    content: string;
    toolCalls?: Array<{ name: string; args: Record<string, unknown>; result?: unknown }>;
    runId?: string;
  }>>([]);
  const [input, setInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => `session-${Date.now()}`);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Chat history (sidebar on md+, drawer on small screens)
  const [sessionsList, setSessionsList] = useState<SessionSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [conversationsOpen, setConversationsOpen] = useState(false);

  const refreshSessions = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const { sessions } = await sessionsApi.list();
      setSessionsList(sessions);
    } catch (e) {
      console.error('Failed to load sessions:', e);
      setSessionsList([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  // Tools state
  const [tools, setTools] = useState<Tool[]>([]);
  const [toolsLoading, setToolsLoading] = useState(false);

  // UI state
  const [activeTab, setActiveTab] = useState<MainTab>('chat');
  const [toasts, setToasts] = useState<Array<{ id: string; message: string; type: 'success' | 'error' }>>([]);

  // Helper to show toast
  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    const id = `toast-${Date.now()}`;
    setToasts(prev => [...prev, { id, message, type }]);
  };

  // Load tools
  const loadTools = useCallback(async () => {
    setToolsLoading(true);
    try {
      const toolsData = await toolsApi.list();
      setTools(toolsData);
    } catch (e) {
      console.error('Failed to load tools:', e);
    } finally {
      setToolsLoading(false);
    }
  }, []);

  // Initialize on mount
  useEffect(() => {
    async function init() {
      try {
        const healthData = await healthApi.check();
        setHealth(healthData);
      } catch (error) {
        console.error('Failed to load health:', error);
      } finally {
        setLoading(false);
      }
      loadTools();
    }
    init();
  }, [loadTools]);

  // Auto-scroll chat
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim() || chatLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setChatLoading(true);

    try {
      const response: ChatResponse = await chatApi.send({
        message: userMessage,
        session_id: sessionId,
      });

      // Normalize tool calls: API sends { tool, input } and optionally tool_invocations; UI expects { name, args, result }
      const rawInvocations = response.tool_invocations ?? [];
      const rawCalls = response.tool_calls ?? [];
      const rawOutputs = response.tool_outputs ?? [];
      const toolCalls = rawInvocations.length > 0
        ? rawInvocations.map((inv: { call?: { tool?: string; input?: Record<string, unknown> }; output?: unknown }) => ({
            name: inv.call?.tool ?? 'unknown',
            args: inv.call?.input ?? {},
            result: inv.output,
          }))
        : rawCalls.map((tc: { tool?: string; name?: string; input?: Record<string, unknown>; args?: Record<string, unknown> }, idx: number) => ({
            name: tc.tool ?? tc.name ?? 'unknown',
            args: tc.input ?? tc.args ?? {},
            result: rawOutputs[idx],
          }));

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.response,
        toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
        runId: response.run_id || undefined,
      }]);
      refreshSessions();
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : 'Failed to send message';
      const errorMessage = rawMessage.startsWith('Error:') ? rawMessage : `Error: ${rawMessage}`;
      setMessages(prev => [...prev, { role: 'assistant', content: errorMessage }]);
      showToast(rawMessage.length > 60 ? 'Request failed — see message above' : rawMessage, 'error');
    } finally {
      setChatLoading(false);
    }
  };

  const handleFeedback = async (runId: string, rating: number) => {
    try {
      await feedbackApi.send({
        message_id: runId,
        session_id: sessionId,
        rating: rating as -1 | 1,
      });
      showToast('Feedback recorded', 'success');
    } catch (e) {
      console.error('Failed to send feedback:', e);
    }
  };

  // Load sessions list on mount and keep sidebar visible
  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  const loadSession = useCallback(async (id: string) => {
    try {
      const data = await sessionsApi.get(id);
      setSessionId(id);
      setMessages(
        data.messages.map((m) => ({
          role: m.role,
          content: m.content,
        }))
      );
      setConversationsOpen(false);
      refreshSessions();
    } catch (e) {
      console.error('Failed to load session:', e);
      showToast('Failed to load conversation', 'error');
    }
  }, [refreshSessions]);

  const startNewChat = useCallback(() => {
    setSessionId(`session-${Date.now()}`);
    setMessages([]);
    setConversationsOpen(false);
    refreshSessions();
  }, [refreshSessions]);

  // Suggested questions based on mode
  const suggestedQuestions = appMode === 'developer' ? [
    'What are the main entry points in this codebase?',
    'What tools would be useful for this repository?',
    'Explain the architecture of this project',
    'What are the key dependencies?',
  ] : [
    'What is my current portfolio value?',
    'How are my investments performing?',
    'What is my asset allocation?',
    'Any suggestions for my portfolio?',
  ];

  // Welcome message based on mode
  const welcomeTitle = appMode === 'developer'
    ? 'Developer'
    : 'Ask About Your Portfolio';

  const welcomeSubtitle = appMode === 'developer'
    ? 'Chat, inspect tools, and view traces'
    : 'I can help you understand your investments and financial data';

  // Tabs to show based on mode
  const visibleTabs: MainTab[] = appMode === 'developer'
    ? ['chat', 'tools', 'traces']
    : ['chat'];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-slate-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Slim bar: connection/status + mobile Conversations button */}
      <div className="shrink-0 flex items-center justify-between gap-2 sm:gap-4 px-3 py-2 sm:px-4 border-b border-surface-border bg-surface-darker/50 flex-wrap">
        <div className="flex items-center gap-2 sm:gap-3 text-xs text-slate-400 min-w-0">
          {health?.agent_ready && (
            <span className="flex items-center gap-1 text-emerald-400 shrink-0">
              <span className="size-1.5 rounded-full bg-emerald-400" />
              Agent Ready
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {/* Mobile: Conversations toggle (hidden on md+ where sidebar is visible) */}
          <button
            type="button"
            onClick={() => setConversationsOpen(true)}
            className="md:hidden flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-surface-dark text-xs font-medium"
            aria-label="Open conversations"
          >
            <span className="material-symbols-outlined text-lg">history</span>
            <span>Conversations</span>
          </button>
        </div>
      </div>

      {/* Main content: center | history sidebar (md+) or drawer (mobile) */}
      <div className="flex flex-1 min-h-0">
        {/* Center: Chat with tabs */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Tab bar (developer: Chat / Tools / Traces; user: Chat only) */}
          {visibleTabs.length > 1 && (
            <div className="flex items-center gap-1 px-3 sm:px-4 py-2 border-b border-surface-border bg-surface-darker shrink-0 flex-wrap">
              {visibleTabs.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm rounded-lg transition-colors capitalize ${
                    activeTab === tab
                      ? 'bg-primary/20 text-primary'
                      : 'text-slate-400 hover:text-white hover:bg-surface-dark'
                  }`}
                >
                  {tab}
                  {tab === 'tools' && tools.length > 0 && (
                    <span className="ml-1.5 text-xs text-slate-500">({tools.length})</span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Tab content */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {activeTab === 'chat' && (
              <div className="flex flex-col h-full">
                {/* Chat messages */}
                <div
                  ref={chatContainerRef}
                  className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-3 sm:space-y-4"
                >
                  {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center px-2">
                      <div className={`p-3 sm:p-4 rounded-full mb-3 sm:mb-4 ${
                        appMode === 'developer' ? 'bg-primary/10 text-primary' : 'bg-emerald-500/10 text-emerald-400'
                      }`}>
                        <span className="material-symbols-outlined text-3xl sm:text-4xl">
                          {appMode === 'developer' ? 'code' : 'account_balance_wallet'}
                        </span>
                      </div>
                      <h2 className="text-base sm:text-lg font-medium text-white mb-2">{welcomeTitle}</h2>
                      <p className="text-xs sm:text-sm text-slate-400 mb-4 max-w-md">{welcomeSubtitle}</p>
                    </div>
                  ) : (
                    messages.map((msg, i) => (
                      <ChatMessage
                        key={i}
                        role={msg.role}
                        content={msg.content}
                        toolCalls={msg.toolCalls}
                        runId={msg.runId}
                        sessionId={sessionId}
                        onFeedback={msg.runId ? (rating) => handleFeedback(msg.runId!, rating) : undefined}
                      />
                    ))
                  )}
                  {chatLoading && (
                    <div className="flex justify-start mb-4">
                      <div className="bg-surface-dark border border-surface-border rounded-lg px-4 py-3">
                        <div className="flex items-center gap-2 text-slate-400">
                          <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                          <span className="text-sm">Thinking...</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Suggested questions */}
                {messages.length === 0 && (
                  <div className="px-3 sm:px-4 pb-4">
                    <div className="flex flex-wrap gap-2 sm:gap-3 justify-center sm:justify-start">
                      {suggestedQuestions.slice(0, 3).map((q, i) => (
                        <button
                          key={i}
                          onClick={() => setInput(q)}
                          className={`px-3 py-2.5 sm:px-4 sm:py-3 text-xs sm:text-sm rounded-lg transition-colors ${
                            appMode === 'developer'
                              ? 'text-slate-400 bg-surface-dark border border-surface-border hover:border-primary/30 hover:text-slate-200'
                              : 'text-slate-400 bg-surface-dark border border-surface-border hover:border-emerald-500/30 hover:text-slate-200'
                          }`}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Input area */}
                <div className="p-3 sm:p-4 border-t border-surface-border bg-surface-dark shrink-0">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                      placeholder={
                        appMode === 'developer'
                          ? 'Type a message...'
                          : 'Ask about your portfolio...'
                      }
                      className="flex-1 min-w-0 bg-surface-darker border border-surface-border rounded-lg px-3 py-2.5 sm:px-4 text-sm sm:text-base text-white placeholder-slate-500 focus:outline-none focus:border-primary/50"
                      disabled={chatLoading}
                    />
                    <button
                      onClick={handleSendMessage}
                      disabled={!input.trim() || chatLoading}
                      className={`px-3 py-2.5 sm:px-4 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0 touch-manipulation ${
                        appMode === 'developer'
                          ? 'bg-primary hover:bg-primary/90'
                          : 'bg-emerald-500 hover:bg-emerald-600'
                      }`}
                      aria-label="Send message"
                    >
                      <span className="material-symbols-outlined text-xl sm:text-2xl">send</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'tools' && appMode === 'developer' && (
              <div className="h-full overflow-y-auto p-3 sm:p-4">
                {toolsLoading ? (
                  <div className="text-center text-slate-500 py-8">Loading tools...</div>
                ) : tools.length === 0 ? (
                  <div className="text-center text-slate-500 py-8">No tools available</div>
                ) : (
                  <div className="space-y-2">
                    {tools.map((tool) => (
                      <div
                        key={tool.id}
                        className="bg-surface-dark border border-surface-border rounded-lg p-4"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary">build</span>
                            <span className="font-medium text-white">{tool.name}</span>
                          </div>
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            tool.status === 'active'
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : tool.status === 'beta'
                              ? 'bg-amber-500/20 text-amber-400'
                              : 'bg-slate-500/20 text-slate-400'
                          }`}>
                            {tool.status}
                          </span>
                        </div>
                        <p className="text-sm text-slate-400">{tool.description}</p>
                        {tool.source && (
                          <div className="mt-2 text-xs text-slate-500">
                            Source: <span className="text-slate-400">{tool.source}</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'traces' && appMode === 'developer' && (
              <div className="h-full flex items-center justify-center text-slate-500">
                <div className="text-center">
                  <span className="material-symbols-outlined text-4xl mb-2">history</span>
                  <p>Trace history coming soon</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right sidebar: Chat history (visible from md up) */}
        <div className="hidden md:flex w-64 lg:w-72 flex-shrink-0 border-l border-surface-border bg-surface-darker/50 flex-col overflow-hidden">
          <div className="shrink-0 px-3 py-3 border-b border-surface-border">
            <h2 className="text-sm font-medium text-white">Conversations</h2>
          </div>
          <button
            type="button"
            onClick={startNewChat}
            className="mx-2 mt-2 flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/20 text-primary text-sm font-medium hover:bg-primary/30 transition-colors shrink-0"
          >
            <span className="material-symbols-outlined text-lg">add</span>
            New chat
          </button>
          <div className="flex-1 overflow-y-auto min-h-0 p-2">
            {historyLoading ? (
              <div className="text-slate-400 text-sm py-4 text-center">Loading...</div>
            ) : sessionsList.length === 0 ? (
              <div className="text-slate-500 text-sm py-4 text-center">No conversations yet</div>
            ) : (
              <ul className="space-y-1">
                {sessionsList.map((s) => (
                  <li key={s.session_id}>
                    <button
                      type="button"
                      onClick={() => loadSession(s.session_id)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                        s.session_id === sessionId
                          ? 'bg-primary/20 text-primary'
                          : 'text-slate-300 hover:bg-surface-dark hover:text-white'
                      }`}
                    >
                      <span className="block truncate font-mono text-xs text-slate-500 mb-0.5">
                        {s.session_id.slice(0, 16)}...
                      </span>
                      <span className="block text-slate-400 text-xs">
                        {s.message_count} message{s.message_count !== 1 ? 's' : ''}
                        {s.last_accessed ? ` · ${formatHistoryDate(s.last_accessed)}` : ''}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* Mobile conversations drawer (below md) */}
      {conversationsOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex" role="dialog" aria-label="Conversations">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setConversationsOpen(false)}
            aria-hidden
          />
          <div className="relative w-[85vw] max-w-sm bg-surface-darker border-l border-surface-border flex flex-col shadow-xl">
            <div className="flex items-center justify-between px-3 py-3 border-b border-surface-border shrink-0">
              <h2 className="text-sm font-medium text-white">Conversations</h2>
              <button
                type="button"
                onClick={() => setConversationsOpen(false)}
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-surface-dark touch-manipulation"
                aria-label="Close"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            </div>
            <button
              type="button"
              onClick={startNewChat}
              className="mx-2 mt-2 flex items-center gap-2 px-3 py-2.5 rounded-lg bg-primary/20 text-primary text-sm font-medium hover:bg-primary/30 transition-colors shrink-0 touch-manipulation"
            >
              <span className="material-symbols-outlined text-lg">add</span>
              New chat
            </button>
            <div className="flex-1 overflow-y-auto min-h-0 p-2">
              {historyLoading ? (
                <div className="text-slate-400 text-sm py-4 text-center">Loading...</div>
              ) : sessionsList.length === 0 ? (
                <div className="text-slate-500 text-sm py-4 text-center">No conversations yet</div>
              ) : (
                <ul className="space-y-1">
                  {sessionsList.map((s) => (
                    <li key={s.session_id}>
                      <button
                        type="button"
                        onClick={() => loadSession(s.session_id)}
                        className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors touch-manipulation ${
                          s.session_id === sessionId
                            ? 'bg-primary/20 text-primary'
                            : 'text-slate-300 hover:bg-surface-dark hover:text-white'
                        }`}
                      >
                        <span className="block truncate font-mono text-xs text-slate-500 mb-0.5">
                          {s.session_id.slice(0, 16)}...
                        </span>
                        <span className="block text-slate-400 text-xs">
                          {s.message_count} message{s.message_count !== 1 ? 's' : ''}
                          {s.last_accessed ? ` · ${formatHistoryDate(s.last_accessed)}` : ''}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Toasts */}
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToasts(prev => prev.filter(t => t.id !== toast.id))}
        />
      ))}
    </div>
  );
}
