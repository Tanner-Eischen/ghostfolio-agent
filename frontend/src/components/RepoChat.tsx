import { useState, useRef, useEffect, useCallback } from 'react';
import { chatApi } from '../api/client';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  loading?: boolean;
}

interface RepoChatProps {
  repoId: string;
  repoName: string;
  initialInsight?: string | null;
}

// Context-aware suggestions that make it clear we're asking about code
const SUGGESTED_QUESTIONS = [
  "What are the main code entry points in this repo?",
  "Explain the data flow and module dependencies",
  "Where should I integrate an AI agent in this codebase?",
  "What architecture patterns does this project use?",
];

// Follow-up suggestions based on conversation
const FOLLOWUP_QUESTIONS = [
  "Show me the key files I should understand first",
  "What are the main API endpoints?",
  "How is error handling implemented?",
  "What external services does this connect to?",
];

export function RepoChat({ repoId, repoName, initialInsight }: RepoChatProps) {
  const [messages, setMessages] = useState<Message[]>(() => {
    if (initialInsight) {
      return [{
        id: 'initial',
        role: 'assistant' as const,
        content: initialInsight,
      }];
    }
    return [];
  });
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Scroll only the messages container to bottom (not the whole page)
  const scrollToBottom = useCallback(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const sendMessage = useCallback(async (messageText: string) => {
    if (!messageText.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageText.trim(),
    };

    const assistantMessage: Message = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      loading: true,
    };

    setMessages(prev => [...prev, userMessage, assistantMessage]);
    setInput('');
    setIsLoading(true);
    setError(null);

    // Cancel any previous request
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    try {
      const response = await chatApi.send(
        {
          message: messageText.trim(),
          repo_id: repoId,
        },
        abortControllerRef.current.signal
      );

      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? { ...msg, content: response.response, loading: false }
            : msg
        )
      );
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      const errorMessage = err instanceof Error ? err.message : 'Failed to get response';
      setError(errorMessage);
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? { ...msg, content: `Error: ${errorMessage}`, loading: false }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [repoId, isLoading]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const handleSuggestedQuestion = (question: string) => {
    sendMessage(question);
  };

  const handleCancel = () => {
    abortControllerRef.current?.abort();
    setIsLoading(false);
  };

  // Show different suggestions based on conversation state
  const suggestions = messages.length <= 1 ? SUGGESTED_QUESTIONS : FOLLOWUP_QUESTIONS;
  // Pick 3 random suggestions to keep it fresh
  const displaySuggestions = suggestions.sort(() => Math.random() - 0.5).slice(0, 3);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-surface-border shrink-0">
        <div className="p-1.5 rounded-lg bg-primary/20 text-primary">
          <span className="material-symbols-outlined text-lg">chat</span>
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-bold text-white truncate">Ask about {repoName}</h3>
          <p className="text-[10px] text-slate-500">Codebase-specific questions</p>
        </div>
      </div>

      {/* Messages - with its own scroll container */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0"
      >
        {messages.length === 0 && (
          <div className="text-center py-4">
            <span className="material-symbols-outlined text-3xl text-slate-600 mb-2">forum</span>
            <p className="text-xs text-slate-500">Ask questions about this codebase</p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            <div
              className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center ${
                msg.role === 'user'
                  ? 'bg-primary/20 text-primary'
                  : 'bg-slate-700 text-slate-300'
              }`}
            >
              <span className="material-symbols-outlined text-xs">
                {msg.role === 'user' ? 'person' : 'smart_toy'}
              </span>
            </div>
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-xs ${
                msg.role === 'user'
                  ? 'bg-primary/20 text-white'
                  : 'bg-surface-darker text-slate-300'
              }`}
            >
              {msg.loading ? (
                <div className="flex items-center gap-1.5 py-1">
                  <span className="size-1.5 rounded-full bg-slate-400 animate-pulse" />
                  <span className="size-1.5 rounded-full bg-slate-400 animate-pulse delay-75" />
                  <span className="size-1.5 rounded-full bg-slate-400 animate-pulse delay-150" />
                </div>
              ) : (
                <div className="whitespace-pre-wrap">{msg.content}</div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Suggested Questions - always visible */}
      <div className="px-3 py-2 border-t border-surface-border/50 shrink-0">
        <div className="flex flex-wrap gap-1">
          {displaySuggestions.map((q) => (
            <button
              key={q}
              onClick={() => handleSuggestedQuestion(q)}
              disabled={isLoading}
              className="px-2 py-1 text-[10px] rounded-full bg-surface-dark border border-surface-border text-slate-400 hover:text-white hover:border-primary/30 transition-colors disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="p-2 border-t border-surface-border shrink-0">
        {error && (
          <div className="mb-1.5 px-2 py-1 text-[10px] text-red-400 bg-red-500/10 rounded">
            {error}
          </div>
        )}
        <div className="flex gap-1.5">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the codebase..."
            disabled={isLoading}
            className="flex-1 min-w-0 bg-surface-dark border border-surface-border rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-primary/50 disabled:opacity-50"
          />
          {isLoading ? (
            <button
              onClick={handleCancel}
              className="px-2 py-1.5 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors shrink-0"
            >
              <span className="material-symbols-outlined text-base">close</span>
            </button>
          ) : (
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim()}
              className="px-2 py-1.5 rounded-lg bg-primary/20 text-primary hover:bg-primary/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
            >
              <span className="material-symbols-outlined text-base">send</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
