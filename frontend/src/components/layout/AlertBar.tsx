interface AlertBarProps {
  message?: string;
  onAction?: () => void;
  actionLabel?: string;
  onDismiss?: () => void;
}

export function AlertBar({
  message = 'Missing Critical API Keys: Ghostfolio API, OpenAI, Database Credentials',
  onAction,
  actionLabel = 'Setup Alert',
  onDismiss,
}: AlertBarProps) {
  return (
    <div className="bg-amber-500/10 border-b border-amber-500/20 text-amber-500 px-6 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center gap-3">
        <span className="material-symbols-outlined text-lg">warning</span>
        <span className="font-medium">{message}</span>
      </div>
      <div className="flex items-center gap-2">
        {onAction && (
          <button
            onClick={onAction}
            className="bg-amber-500 hover:bg-amber-600 text-black font-bold px-3 py-1 rounded text-xs transition-colors"
          >
            {actionLabel}
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="p-1 rounded hover:bg-amber-500/20 text-amber-500 transition-colors"
            aria-label="Dismiss warning"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        )}
      </div>
    </div>
  );
}
