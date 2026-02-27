import { useEffect, useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { chatApi, repoApi, feedbackApi, toolsApi, toolSuggestionsApi } from '../api/client';
import type {
  ChatResponse,
  RepoConnection,
  Tool,
  ToolDetail,
  ToolSuggestion,
  ToolSuggestionsResponse,
  GeneratedToolResponse,
} from '../api/client';

interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result?: unknown;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  confidence?: number;
  verificationPassed?: boolean;
  feedbackGiven?: 'positive' | 'negative' | null;
}

interface Conversation {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  messages: Message[];
}

interface ToolInfo {
  name: string;
  description: string;
}

// Storage keys
const STORAGE_KEY = 'ghostfolio-agent-conversations';

type AgentChatTab = 'chat' | 'tools';

// Generate prebuilt questions based on available tools
function generatePrebuiltQuestions(tools: ToolInfo[]): Array<{ icon: string; label: string; query: string }> {
  const questions: Array<{ icon: string; label: string; query: string }> = [];

  // Check for specific tools and add relevant questions
  const hasPortfolio = tools.some(t => t.name.includes('portfolio') || t.name.includes('allocation'));
  const hasRisk = tools.some(t => t.name.includes('risk'));
  const hasMarket = tools.some(t => t.name.includes('market') || t.name.includes('price'));
  const hasTax = tools.some(t => t.name.includes('tax'));
  const hasCompliance = tools.some(t => t.name.includes('compliance') || t.name.includes('wash'));

  if (hasPortfolio) {
    questions.push({ icon: 'pie_chart', label: 'Analyze my portfolio allocation', query: 'What is my current portfolio allocation?' });
  }
  if (hasRisk) {
    questions.push({ icon: 'trending_up', label: "What's my risk level?", query: 'What is my current portfolio risk level?' });
  }
  if (hasMarket) {
    questions.push({ icon: 'candlestick_chart', label: 'Get market data for AAPL', query: 'Get the latest market data for AAPL' });
  }
  if (hasTax) {
    questions.push({ icon: 'receipt_long', label: 'Estimate tax impact', query: 'What would be the tax impact if I sold my winners?' });
  }
  if (hasCompliance) {
    questions.push({ icon: 'gavel', label: 'Check wash-sale compliance', query: 'Are there any wash-sale violations in my portfolio?' });
  }

  // Default questions if no specific tools found
  if (questions.length === 0) {
    questions.push(
      { icon: 'pie_chart', label: 'Analyze my portfolio', query: 'Tell me about my portfolio' },
      { icon: 'help', label: 'What can you do?', query: 'What tools and capabilities do you have?' },
      { icon: 'info', label: 'Get started', query: 'How can you help me with my investments?' }
    );
  }

  return questions;
}

// Tool call dropdown component
function ToolCallDropdown({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setExpanded(!expanded);
    }
  };

  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        onKeyDown={handleKeyDown}
        aria-expanded={expanded}
        aria-controls={`tool-details-${toolCall.name}`}
        className="flex items-center gap-2 text-xs text-text-dim hover:text-white transition-colors w-full text-left focus:outline-none focus:ring-2 focus:ring-primary focus:ring-opacity-50 rounded px-1"
      >
        <span className="material-symbols-outlined text-sm text-primary" aria-hidden="true">
          {expanded ? 'expand_more' : 'chevron_right'}
        </span>
        <span className="material-symbols-outlined text-sm text-primary" aria-hidden="true">call_made</span>
        <span className="font-mono">{toolCall.name}</span>
        <span className="text-emerald-400 ml-auto">executed</span>
      </button>

      {expanded && (
        <div
          id={`tool-details-${toolCall.name}`}
          role="region"
          aria-label={`Details for ${toolCall.name}`}
          className="mt-2 ml-6 p-3 bg-surface-darker rounded-lg border border-surface-border space-y-2"
        >
          {/* Arguments */}
          {toolCall.args && typeof toolCall.args === 'object' && Object.keys(toolCall.args).length > 0 && (
            <div>
              <span className="text-[10px] text-text-dim uppercase tracking-wider">Arguments</span>
              <pre className="mt-1 p-2 bg-background-dark rounded text-[10px] text-slate-300 overflow-x-auto">
                {JSON.stringify(toolCall.args, null, 2)}
              </pre>
            </div>
          )}

          {/* Result */}
          {toolCall.result !== undefined && (
            <div>
              <span className="text-[10px] text-text-dim uppercase tracking-wider">Result</span>
              <pre className="mt-1 p-2 bg-background-dark rounded text-[10px] text-emerald-300 overflow-x-auto max-h-40">
                {typeof toolCall.result === 'string'
                  ? toolCall.result
                  : JSON.stringify(toolCall.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Constants
const MAX_MESSAGE_LENGTH = 10000;
const MAX_CONVERSATIONS = 50;
const MAX_MESSAGES_PER_CONVERSATION = 100;

// Toast notification type
interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'warning';
}

export function AgentChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true); // Loading state for initial data fetch
  const [sessionId, setSessionId] = useState<string>('');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [connections, setConnections] = useState<RepoConnection[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);
  const [availableTools, setAvailableTools] = useState<ToolInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Tools / Schema tab state
  const [activeTab, setActiveTab] = useState<AgentChatTab>('chat');
  const [registeredTools, setRegisteredTools] = useState<Tool[]>([]);
  const [toolDetails, setToolDetails] = useState<Record<string, ToolDetail>>({});
  const [suggestions, setSuggestions] = useState<ToolSuggestion[]>([]);
  const [suggestionsSummary, setSuggestionsSummary] = useState<string>('');
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [generatedTool, setGeneratedTool] = useState<GeneratedToolResponse | null>(null);
  const [generatingToolId, setGeneratingToolId] = useState<string | null>(null);
  const [selectedToolIds, setSelectedToolIds] = useState<Set<string>>(new Set());
  const [toolsLoading, setToolsLoading] = useState(false);

  // Helper to show toast notifications
  const showToast = (message: string, type: Toast['type'] = 'success') => {
    const id = `toast-${Date.now()}`;
    setToasts(prev => [...prev, { id, message, type }]);
    // Auto-dismiss after 3 seconds
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3000);
  };

  // Generate prebuilt questions based on tools
  const prebuiltQuestions = generatePrebuiltQuestions(availableTools);

  // Load conversations from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Conversation[];
        // Convert timestamp strings back to Date objects
        const conversationsWithDates = parsed.map(c => ({
          ...c,
          timestamp: new Date(c.timestamp),
          messages: c.messages.map(m => ({ ...m, timestamp: new Date(m.timestamp) }))
        }));
        // Enforce max conversations limit on load
        const limitedConversations = conversationsWithDates.slice(0, MAX_CONVERSATIONS);
        setConversations(limitedConversations);
      }
    } catch (e) {
      console.error('Failed to load conversations from localStorage:', e);
      showToast('Failed to load conversation history', 'warning');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save conversations to localStorage with limits
  useEffect(() => {
    if (conversations.length > 0) {
      try {
        // Enforce limits before saving: max conversations and max messages per conversation
        const limitedConversations = conversations
          .slice(0, MAX_CONVERSATIONS)
          .map(conv => ({
            ...conv,
            messages: conv.messages.slice(-MAX_MESSAGES_PER_CONVERSATION)
          }));
        localStorage.setItem(STORAGE_KEY, JSON.stringify(limitedConversations));
      } catch (e) {
        console.error('Failed to save conversations to localStorage:', e);
        showToast('Failed to save conversation. Storage may be full.', 'warning');
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversations]);

  // Load repo connections and tools together, track initial loading
  useEffect(() => {
    let mounted = true;

    async function fetchInitialData() {
      try {
        // Fetch connections and tools in parallel
        const [connectionsData, toolsData] = await Promise.all([
          repoApi.listConnections(),
          chatApi.getTools(),
        ]);

        if (!mounted) return;

        setConnections(connectionsData.connections);
        if (connectionsData.connections.length > 0) {
          setSelectedRepoId(connectionsData.connections[0].id);
        }
        setAvailableTools(toolsData);
      } catch (err) {
        if (!mounted) return;
        console.error('Failed to fetch initial data:', err);
        // Use default tools if fetch fails
        setAvailableTools([
          { name: 'portfolio_analysis', description: 'Analyze portfolio allocation' },
          { name: 'risk_assessment', description: 'Assess portfolio risk' },
          { name: 'market_data', description: 'Get market data' },
        ]);
      } finally {
        if (mounted) {
          setInitialLoading(false);
        }
      }
    }
    fetchInitialData();

    return () => { mounted = false; };
  }, []);

  // Generate session ID on mount (using cryptographically secure random UUID)
  useEffect(() => {
    // Use crypto.randomUUID() for secure session ID generation
    const secureId = crypto.randomUUID();
    setSessionId(`session-${Date.now()}-${secureId.split('-')[0]}`);
  }, []);

  // Auto-scroll to bottom with debouncing to prevent UI lag during rapid updates
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100); // 100ms debounce
    return () => clearTimeout(timeoutId);
  }, [messages]);

  // Clear error after 5 seconds
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  // Cleanup: abort pending requests on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // Load registered tools when Tools tab is active
  useEffect(() => {
    if (activeTab !== 'tools') return;
    let mounted = true;
    setToolsLoading(true);
    toolsApi
      .list()
      .then((list) => {
        if (!mounted) return;
        setRegisteredTools(list);
        setSelectedToolIds((prev) => {
          const next = new Set(prev);
          list.forEach((t) => next.add(t.id));
          return next;
        });
        return Promise.all(list.map((t) => toolsApi.get(t.name).catch(() => null)));
      })
      .then((details) => {
        if (!mounted || !details) return;
        const map: Record<string, ToolDetail> = {};
        details.forEach((d) => {
          if (d) map[d.name] = d;
        });
        setToolDetails(map);
      })
      .catch(() => {
        if (mounted) setRegisteredTools([]);
      })
      .finally(() => {
        if (mounted) setToolsLoading(false);
      });
    return () => { mounted = false; };
  }, [activeTab]);

  // Load tool suggestions from repo analysis when Tools tab is active and a repo is selected
  useEffect(() => {
    if (activeTab !== 'tools' || !selectedRepoId) {
      setSuggestions([]);
      setSuggestionsSummary('');
      return;
    }
    let mounted = true;
    setSuggestionsLoading(true);
    toolSuggestionsApi
      .getForRepo(selectedRepoId)
      .then((res: ToolSuggestionsResponse) => {
        if (!mounted) return;
        setSuggestions(res.suggestions);
        setSuggestionsSummary(res.analysis_summary);
      })
      .catch(() => {
        if (mounted) {
          setSuggestions([]);
          setSuggestionsSummary('');
        }
      })
      .finally(() => {
        if (mounted) setSuggestionsLoading(false);
      });
    return () => { mounted = false; };
  }, [activeTab, selectedRepoId]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    // Input validation: max length check
    if (input.length > MAX_MESSAGE_LENGTH) {
      setError(`Message too long. Maximum ${MAX_MESSAGE_LENGTH.toLocaleString()} characters allowed.`);
      return;
    }

    // Abort any previous pending request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const response: ChatResponse = await chatApi.send({
        message: input,
        session_id: sessionId,
        repo_id: selectedRepoId || undefined,
      }, abortControllerRef.current.signal);

      const assistantMessage: Message = {
        id: `msg-${Date.now()}-response`,
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        // Attach tool outputs to tool calls by index
        toolCalls: response.tool_calls.map((tc, idx) => ({
          ...tc,
          result: response.tool_outputs?.[idx],
        })),
        confidence: response.confidence,
        verificationPassed: response.verification_passed,
      };

      setMessages(prev => [...prev, assistantMessage]);

      // Update conversations list (using functional update to avoid stale closure)
      setConversations(prev => {
        const existing = prev.find(c => c.id === sessionId);
        // For existing conversation, append to its messages; for new, use just the new messages
        const allMessages = existing
          ? [...existing.messages, userMessage, assistantMessage]
          : [userMessage, assistantMessage];

        if (existing) {
          return prev.map(c => c.id === sessionId ? {
            ...c,
            lastMessage: response.response.substring(0, 50) + '...',
            timestamp: new Date(),
            messages: allMessages,
          } : c);
        }
        return [{
          id: sessionId,
          title: userMessage.content.substring(0, 30) + '...',
          lastMessage: response.response.substring(0, 50) + '...',
          timestamp: new Date(),
          messages: allMessages,
        }, ...prev];
      });
    } catch (err) {
      // Don't show error if request was aborted (user navigated away or sent new message)
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      console.error('Chat error:', err);
      setError('Failed to get response. Please try again.');
      const errorMessage: Message = {
        id: `msg-${Date.now()}-error`,
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handlePrebuiltClick = (query: string) => {
    setInput(query);
  };

  const handleNewConversation = () => {
    setMessages([]);
    // Use cryptographically secure random UUID for new session
    const secureId = crypto.randomUUID();
    setSessionId(`session-${Date.now()}-${secureId.split('-')[0]}`);
    showToast('New chat started', 'success');
  };

  const handleSelectConversation = (conv: Conversation) => {
    setSessionId(conv.id);
    setMessages(conv.messages);
  };

  const handleDeleteConversation = (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    setConversations(prev => prev.filter(c => c.id !== convId));
    if (sessionId === convId) {
      handleNewConversation();
    }
  };

  const getConfidenceColor = (confidence?: number) => {
    if (!confidence) return 'text-text-dim';
    if (confidence >= 80) return 'text-emerald-400';
    if (confidence >= 60) return 'text-amber-400';
    return 'text-red-400';
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast('Copied to clipboard', 'success');
    } catch {
      showToast('Failed to copy', 'error');
    }
  };

  const handleFeedback = async (messageId: string, rating: -1 | 1) => {
    try {
      await feedbackApi.send({
        message_id: messageId,
        session_id: sessionId,
        rating,
      });
      // Update message to show feedback was given
      setMessages(prev => prev.map(msg =>
        msg.id === messageId
          ? { ...msg, feedbackGiven: rating === 1 ? 'positive' : 'negative' }
          : msg
      ));
    } catch (err) {
      console.error('Failed to submit feedback:', err);
      showToast('Failed to submit feedback. Please try again.', 'error');
    }
  };

  return (
    <div className="flex h-full">
      {/* Conversation History Sidebar */}
      <aside className="w-64 bg-surface-darker border-r border-surface-border flex flex-col h-full" aria-label="Conversation history">
        <div className="p-4 border-b border-surface-border">
          <button
            onClick={handleNewConversation}
            aria-label="Start a new chat conversation"
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary hover:bg-primary-hover text-surface-darker font-medium rounded-lg transition-colors"
          >
            <span className="material-symbols-outlined text-lg" aria-hidden="true">add</span>
            New Chat
          </button>
        </div>

        {/* Repo Selector */}
        {connections.length > 0 && (
          <div className="px-4 py-3 border-b border-surface-border">
            <label htmlFor="repo-selector" className="text-text-dim text-xs font-medium uppercase tracking-wider mb-2 block">Repository</label>
            <select
              id="repo-selector"
              value={selectedRepoId || ''}
              onChange={(e) => setSelectedRepoId(e.target.value)}
              aria-label="Select repository context"
              className="w-full bg-surface-dark border border-surface-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-primary"
            >
              {connections.map((conn) => (
                <option key={conn.id} value={conn.id}>{conn.name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto p-2" role="list" aria-label="Recent conversations">
          <div className="text-xs text-text-dim uppercase tracking-wider px-2 mb-2">Recent Chats</div>
          {conversations.length === 0 ? (
            <div className="text-slate-500 text-sm px-2 py-4 text-center">
              No conversations yet. Start a new chat!
            </div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                role="listitem"
                onClick={() => handleSelectConversation(conv)}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleSelectConversation(conv)}
                tabIndex={0}
                aria-label={`Conversation: ${conv.title}. ${conv.lastMessage}`}
                className={`group relative w-full text-left p-3 rounded-lg mb-1 cursor-pointer transition-colors ${
                  sessionId === conv.id
                    ? 'bg-primary/10 border border-primary/20'
                    : 'hover:bg-surface-dark'
                }`}
              >
                <div className="text-white text-sm font-medium truncate pr-6">{conv.title}</div>
                <div className="text-text-dim text-xs truncate mt-1">{conv.lastMessage}</div>
                <button
                  onClick={(e) => handleDeleteConversation(e, conv.id)}
                  aria-label={`Delete conversation: ${conv.title}`}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-surface-border transition-all"
                >
                  <span className="material-symbols-outlined text-sm text-text-dim hover:text-red-400" aria-hidden="true">delete</span>
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col h-full bg-background-dark">
        {/* Header: tabs (Agent Chat | Tools / Schema) + utilities; subheading only for active tab */}
        <header className="sticky top-0 z-10 bg-background-dark/95 backdrop-blur-sm border-b border-surface-border px-6 py-4">
          <div className="flex justify-between items-center">
            <div className="flex gap-1" role="tablist" aria-label="Chat or Tools view">
              <button
                role="tab"
                aria-selected={activeTab === 'chat'}
                onClick={() => setActiveTab('chat')}
                className={`px-4 py-2.5 text-sm font-semibold rounded-t-lg transition-colors ${
                  activeTab === 'chat'
                    ? 'text-white bg-surface-dark border-b-2 border-primary -mb-px'
                    : 'text-text-dim hover:text-white'
                }`}
              >
                Agent Chat
              </button>
              <button
                role="tab"
                aria-selected={activeTab === 'tools'}
                onClick={() => setActiveTab('tools')}
                className={`px-4 py-2.5 text-sm font-semibold rounded-t-lg transition-colors ${
                  activeTab === 'tools'
                    ? 'text-white bg-surface-dark border-b-2 border-primary -mb-px'
                    : 'text-text-dim hover:text-white'
                }`}
              >
                Tools / Schema
              </button>
            </div>
            <div className="flex items-center gap-3">
              {selectedRepoId && (
                <span className="flex items-center gap-1 px-2 py-1 bg-surface-dark border border-surface-border rounded text-xs text-text-dim">
                  <span className="material-symbols-outlined text-sm">fork_right</span>
                  {connections.find(c => c.id === selectedRepoId)?.name || 'Unknown'}
                </span>
              )}
              <button
                onClick={() => copyToClipboard(sessionId)}
                className="flex items-center gap-1 px-2 py-1 bg-surface-dark border border-surface-border rounded text-xs text-text-dim hover:text-white transition-colors"
                title="Copy session ID"
              >
                <span className="material-symbols-outlined text-sm">content_copy</span>
                {sessionId.substring(0, 8)}...
              </button>
            </div>
          </div>
          {activeTab === 'chat' && (
            <p className="text-text-dim text-sm mt-2" role="status">
              Ask questions about your portfolio and investments
            </p>
          )}
          {activeTab === 'tools' && (
            <p className="text-text-dim text-sm mt-2" role="status">
              View and manage tool schemas; get suggestions from repo analysis
            </p>
          )}
        </header>

        {/* Error Toast */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2 text-red-400 text-sm">
            <span className="material-symbols-outlined">error</span>
            {error}
          </div>
        )}

        {/* Toast Notifications */}
        <div className="fixed bottom-20 right-6 z-50 flex flex-col gap-2">
          {toasts.map(toast => (
            <div
              key={toast.id}
              className={`px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 text-sm animate-slide-in ${
                toast.type === 'success' ? 'bg-emerald-500/90 text-white' :
                toast.type === 'error' ? 'bg-red-500/90 text-white' :
                'bg-amber-500/90 text-white'
              }`}
            >
              <span className="material-symbols-outlined text-sm">
                {toast.type === 'success' ? 'check_circle' : toast.type === 'error' ? 'error' : 'warning'}
              </span>
              {toast.message}
            </div>
          ))}
        </div>

        {activeTab === 'chat' && (
          <>
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {initialLoading ? (
            <div className="h-full flex flex-col items-center justify-center">
              <div className="animate-spin mb-4">
                <span className="material-symbols-outlined text-4xl text-primary">progress_activity</span>
              </div>
              <p className="text-text-dim">Loading...</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center">
              <div className="p-4 rounded-2xl bg-primary/10 mb-6">
                <span className="material-symbols-outlined text-5xl text-primary">smart_toy</span>
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">How can I help you today?</h2>
              <p className="text-text-dim text-center max-w-md mb-8">
                Ask me about your portfolio, market data, or investment strategies.
              </p>

              {/* Prebuilt Questions */}
              <div className="flex flex-wrap gap-2 justify-center max-w-2xl">
                {prebuiltQuestions.map((pq, i) => (
                  <button
                    key={i}
                    onClick={() => handlePrebuiltClick(pq.query)}
                    className="flex items-center gap-2 px-4 py-2 bg-surface-dark border border-surface-border rounded-full text-sm text-slate-300 hover:text-white hover:border-primary/50 transition-colors"
                  >
                    <span className="material-symbols-outlined text-primary text-lg">{pq.icon}</span>
                    {pq.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                      <span className="material-symbols-outlined text-primary text-lg">smart_toy</span>
                    </div>
                  )}
                  <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-first' : ''}`}>
                    <div
                      className={`rounded-2xl px-4 py-3 ${
                        msg.role === 'user'
                          ? 'bg-primary text-surface-darker'
                          : 'bg-surface-dark border border-surface-border'
                      }`}
                    >
                      {msg.role === 'user' ? (
                        <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                      ) : (
                        <div className="text-sm prose prose-invert prose-sm max-w-none">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      )}
                    </div>

                    {/* Tool Calls with Dropdown */}
                    {msg.toolCalls && msg.toolCalls.length > 0 && (
                      <div className="mt-2 p-3 bg-surface-darker/50 rounded-lg border border-surface-border">
                        <div className="text-xs text-text-dim uppercase tracking-wider mb-2 flex items-center gap-1">
                          <span className="material-symbols-outlined text-sm">build</span>
                          Tool Calls ({msg.toolCalls.length})
                        </div>
                        {msg.toolCalls.map((tc, i) => (
                          <ToolCallDropdown key={i} toolCall={tc} />
                        ))}
                      </div>
                    )}

                    {/* Confidence & Verification */}
                    {msg.role === 'assistant' && (msg.confidence !== undefined || msg.verificationPassed !== undefined) && (
                      <div className="flex items-center gap-3 mt-2 text-xs">
                        {msg.confidence !== undefined && (
                          <span className={`flex items-center gap-1 ${getConfidenceColor(msg.confidence)}`}>
                            <span className="material-symbols-outlined text-sm">speed</span>
                            {msg.confidence}% confidence
                          </span>
                        )}
                        {msg.verificationPassed !== undefined && (
                          <span className={`flex items-center gap-1 ${msg.verificationPassed ? 'text-emerald-400' : 'text-amber-400'}`}>
                            <span className="material-symbols-outlined text-sm">
                              {msg.verificationPassed ? 'verified' : 'warning'}
                            </span>
                            {msg.verificationPassed ? 'Verified' : 'Needs Review'}
                          </span>
                        )}
                        <button
                          onClick={() => copyToClipboard(msg.content)}
                          className="flex items-center gap-1 text-text-dim hover:text-white transition-colors"
                          title="Copy message"
                        >
                          <span className="material-symbols-outlined text-sm" aria-hidden="true">content_copy</span>
                        </button>
                        {/* Feedback buttons */}
                        {msg.feedbackGiven ? (
                          <span className="flex items-center gap-1 text-text-dim ml-auto" role="status">
                            <span className="material-symbols-outlined text-sm" aria-hidden="true">
                              {msg.feedbackGiven === 'positive' ? 'thumb_up' : 'thumb_down'}
                            </span>
                            Thanks for feedback!
                          </span>
                        ) : (
                          <div className="flex items-center gap-1 ml-auto" role="group" aria-label="Rate this response">
                            <button
                              onClick={() => handleFeedback(msg.id, 1)}
                              className="flex items-center gap-1 text-text-dim hover:text-emerald-400 transition-colors"
                              aria-label="Mark as helpful"
                            >
                              <span className="material-symbols-outlined text-sm" aria-hidden="true">thumb_up</span>
                            </button>
                            <button
                              onClick={() => handleFeedback(msg.id, -1)}
                              className="flex items-center gap-1 text-text-dim hover:text-red-400 transition-colors"
                              aria-label="Mark as not helpful"
                            >
                              <span className="material-symbols-outlined text-sm" aria-hidden="true">thumb_down</span>
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="sticky bottom-0 bg-background-dark/95 backdrop-blur-sm border-t border-surface-border px-6 py-4">
          {/* Quick Actions */}
          {messages.length > 0 && (
            <div className="flex gap-2 mb-3 overflow-x-auto pb-2">
              {prebuiltQuestions.slice(0, 3).map((pq, i) => (
                <button
                  key={i}
                  onClick={() => handlePrebuiltClick(pq.query)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-dark border border-surface-border rounded-full text-xs text-text-dim hover:text-white hover:border-primary/50 whitespace-nowrap transition-colors"
                >
                  <span className="material-symbols-outlined text-primary text-sm">{pq.icon}</span>
                  {pq.label}
                </button>
              ))}
            </div>
          )}

          {/* Input Box */}
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                placeholder="Ask about your portfolio..."
                aria-label="Type your message"
                maxLength={MAX_MESSAGE_LENGTH}
                className="w-full bg-surface-dark border border-surface-border rounded-xl px-4 py-3 pr-12 text-white placeholder-text-dim focus:outline-none focus:border-primary transition-colors"
                disabled={loading}
              />
              <button
                onClick={handleSend}
                aria-label={loading ? 'Sending message' : 'Send message'}
                disabled={loading || !input.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-primary text-surface-darker hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <span className="material-symbols-outlined">
                  {loading ? 'hourglass_empty' : 'send'}
                </span>
              </button>
            </div>
          </div>
        </div>
          </>
        )}

        {activeTab === 'tools' && (
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
            {/* Current tools schema */}
            <section className="rounded-xl bg-surface-dark border border-surface-border overflow-hidden">
              <h2 className="px-4 py-3 border-b border-surface-border text-white font-semibold flex items-center gap-2">
                <span className="material-symbols-outlined">build</span>
                Registered tools
              </h2>
              <p className="px-4 pt-2 text-xs text-text-dim">
                All listed tools are available to the agent. Checkbox toggles visibility in this list.
              </p>
              <div className="p-4">
                {toolsLoading ? (
                  <div className="flex items-center gap-2 text-text-dim">
                    <span className="material-symbols-outlined animate-spin">progress_activity</span>
                    Loading tools…
                  </div>
                ) : registeredTools.length === 0 ? (
                  <p className="text-text-dim text-sm">No tools registered.</p>
                ) : (
                  <ul className="space-y-3">
                    {registeredTools.map((t) => {
                      const detail = toolDetails[t.name];
                      const isSelected = selectedToolIds.has(t.id);
                      return (
                        <li
                          key={t.id}
                          className="rounded-lg border border-surface-border bg-surface-darker/50 overflow-hidden"
                        >
                          <div className="flex items-center gap-3 p-3">
                            <input
                              type="checkbox"
                              id={`tool-${t.id}`}
                              checked={isSelected}
                              onChange={() => {
                                setSelectedToolIds((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(t.id)) next.delete(t.id);
                                  else next.add(t.id);
                                  return next;
                                });
                              }}
                              className="rounded border-surface-border text-primary focus:ring-primary"
                              title="Show or hide in this list; all registered tools are available to the agent"
                              aria-label={`Show in list: ${t.name}`}
                            />
                            <label htmlFor={`tool-${t.id}`} className="flex-1 cursor-pointer">
                              <span className="font-medium text-white">{t.name}</span>
                              {t.description && (
                                <span className="text-text-dim text-sm block mt-0.5">{t.description}</span>
                              )}
                            </label>
                          </div>
                          {detail && (Object.keys(detail.parameters || {}).length > 0 || detail.args_schema) && (
                            <div className="px-3 pb-3 pt-0">
                              <details className="text-sm">
                                <summary className="cursor-pointer text-text-dim hover:text-white py-1">
                                  Schema / parameters
                                </summary>
                                <div className="mt-2 pl-2 border-l-2 border-surface-border space-y-1 text-text-dim">
                                  {detail.parameters && Object.keys(detail.parameters).length > 0 && (
                                    <pre className="text-xs overflow-x-auto bg-background-dark p-2 rounded">
                                      {JSON.stringify(detail.parameters, null, 2)}
                                    </pre>
                                  )}
                                  {detail.args_schema && (
                                    <pre className="mt-2 text-xs overflow-x-auto bg-background-dark p-2 rounded">
                                      {typeof detail.args_schema === 'string'
                                        ? detail.args_schema
                                        : JSON.stringify(detail.args_schema, null, 2)}
                                    </pre>
                                  )}
                                </div>
                              </details>
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </section>

            {/* Tool schema suggestor (from repo analysis) */}
            <section className="rounded-xl bg-surface-dark border border-surface-border overflow-hidden">
              <h2 className="px-4 py-3 border-b border-surface-border text-white font-semibold flex items-center gap-2">
                <span className="material-symbols-outlined">lightbulb</span>
                Suggested tools from repo
              </h2>
              <div className="p-4">
                {!selectedRepoId ? (
                  <p className="text-text-dim text-sm">
                    Connect a repo on the Repo Analysis page and select it in the sidebar to see suggestions based on your codebase.
                  </p>
                ) : suggestionsLoading ? (
                  <div className="flex items-center gap-2 text-text-dim">
                    <span className="material-symbols-outlined animate-spin">progress_activity</span>
                    Loading suggestions…
                  </div>
                ) : (
                  <>
                    {suggestionsSummary && (
                      <p className="text-text-dim text-sm mb-4 pb-3 border-b border-surface-border">
                        {suggestionsSummary}
                      </p>
                    )}
                    {suggestions.length === 0 ? (
                      <p className="text-text-dim text-sm">No tool suggestions for this repo yet.</p>
                    ) : (
                      <ul className="space-y-3">
                        {suggestions.map((s) => (
                          <li
                            key={s.id}
                            className="rounded-lg border border-surface-border bg-surface-darker/50 p-3"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <span className="font-medium text-white">{s.name}</span>
                                {s.source_type && (
                                  <span className="ml-2 text-xs text-text-dim">{s.source_type}</span>
                                )}
                                {s.description && (
                                  <p className="text-text-dim text-sm mt-1">{s.description}</p>
                                )}
                                {s.reasoning && (
                                  <p className="text-text-dim text-xs mt-1 italic">{s.reasoning}</p>
                                )}
                                {s.parameters?.length ? (
                                  <div className="mt-2 text-xs text-text-dim">
                                    Parameters: {s.parameters.map((p) => p.name).join(', ')}
                                  </div>
                                ) : null}
                              </div>
                              <button
                                type="button"
                                disabled={generatingToolId !== null}
                                onClick={() => {
                                  setGeneratingToolId(s.id);
                                  toolSuggestionsApi
                                    .generateTool(selectedRepoId!, { suggestion_id: s.id })
                                    .then((res) => {
                                      setGeneratedTool(res);
                                      showToast('Tool generated', 'success');
                                    })
                                    .catch(() => {
                                      setGeneratedTool(null);
                                      showToast('Failed to generate tool', 'error');
                                    })
                                    .finally(() => setGeneratingToolId(null));
                                }}
                                className="flex-shrink-0 px-3 py-1.5 bg-primary text-surface-darker text-sm font-medium rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 min-w-[88px] justify-center"
                              >
                                {generatingToolId === s.id ? (
                                  <>
                                    <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                                    Generating…
                                  </>
                                ) : (
                                  'Generate'
                                )}
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            </section>

            {/* Generated tool modal / block */}
            {generatedTool && (
              <section className="rounded-xl bg-surface-dark border border-primary/30 overflow-hidden">
                <div className="px-4 py-3 border-b border-surface-border flex items-center justify-between">
                  <h3 className="text-white font-semibold">Generated tool</h3>
                  <button
                    type="button"
                    onClick={() => setGeneratedTool(null)}
                    className="text-text-dim hover:text-white p-1 rounded"
                    aria-label="Close"
                  >
                    <span className="material-symbols-outlined">close</span>
                  </button>
                </div>
                <div className="p-4">
                  {generatedTool.generated_code && (
                    <pre className="text-xs overflow-x-auto bg-background-dark p-4 rounded border border-surface-border text-slate-300 whitespace-pre-wrap">
                      {generatedTool.generated_code}
                    </pre>
                  )}
                  {generatedTool.name && (
                    <p className="text-text-dim text-sm mt-2">Tool: {generatedTool.name} — {generatedTool.description}</p>
                  )}
                </div>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
