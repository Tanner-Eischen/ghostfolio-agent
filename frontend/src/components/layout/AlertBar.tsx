interface AlertBarProps {
  message?: string;
  onAction?: () => void;
  actionLabel?: string;
}

export function AlertBar({
  message = 'Missing Critical API Keys: Ghostfolio API, OpenAI, Database Credentials',
  onAction,
  actionLabel = 'Setup Alert'
}: AlertBarProps) {
  return (
    <div className="bg-amber-500/10 border-b border-amber-500/20 text-amber-500 px-6 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center gap-3">
        <span className="material-symbols-outlined text-lg">warning</span>
        <span className="font-medium">{message}</span>
      </div>
      {onAction && (
        <button
          onClick={onAction}
          className="bg-amber-500 hover:bg-amber-600 text-black font-bold px-3 py-1 rounded text-xs transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
