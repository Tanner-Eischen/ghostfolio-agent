import { useState } from 'react';
import {
  repoApi,
  type RepoConnection,
  type RepoConnectionRequest,
  type RepoConnectionResponse,
} from '../api/client';

interface RepoConnectorProps {
  onConnected: (connection: RepoConnection) => void;
  onDisconnect: () => void;
  connectedRepo: RepoConnection | null;
}

// Predefined repos for quick connect
const QUICK_REPOS = [
  {
    name: 'Ghostfolio',
    source: 'https://github.com/ghostfolio/ghostfolio.git',
    description: 'Open source wealth management platform',
  },
  {
    name: 'FastAPI',
    source: 'https://github.com/tiangolo/fastapi.git',
    description: 'Modern async Python web framework',
  },
];

export function RepoConnector({ onConnected, onDisconnect, connectedRepo }: RepoConnectorProps) {
  const [source, setSource] = useState('');
  const [branch, setBranch] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConnect = async (overrideSource?: string, overrideName?: string) => {
    const sourceToUse = overrideSource || source.trim();
    if (!sourceToUse) {
      setError('Please enter a git URL or local path');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const request: RepoConnectionRequest = {
        source: sourceToUse,
        branch: branch.trim() || undefined,
        name: overrideName || name.trim() || undefined,
      };

      const response: RepoConnectionResponse = await repoApi.connect(request);

      if (response.success && response.connection) {
        onConnected(response.connection);
        setSource('');
        setBranch('');
        setName('');
      } else {
        const r = response as { error?: string; detail?: string; message?: string };
        const msg = (r.error ?? r.detail ?? r.message ?? '').trim();
        if (!msg) {
          console.error('Repo connect failed; no error message from server:', response);
        }
        setError(
          msg ||
          'Failed to connect. Check the repository URL, ensure Git is installed, and that the backend is running.'
        );
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Connection failed';
      const isNetwork =
        typeof message === 'string' &&
        (message === 'Failed to fetch' || message.includes('NetworkError') || message.includes('Load failed'));
      setError(
        isNetwork
          ? 'Could not reach the server. Check that the backend is running and the URL is correct.'
          : message
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!connectedRepo) return;

    try {
      await repoApi.disconnect(connectedRepo.id);
      onDisconnect();
    } catch (err) {
      console.error('Failed to disconnect:', err);
      // Still disconnect locally even if API fails
      onDisconnect();
    }
  };

  // If connected, show connection info
  if (connectedRepo) {
    return (
      <div className="bg-surface-dark border border-surface-border rounded-xl p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400">
              <span className="material-symbols-outlined text-xl">folder_open</span>
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">{connectedRepo.name}</h3>
              <p className="text-xs text-slate-400 mt-1 font-mono truncate max-w-md">
                {connectedRepo.source}
              </p>
              {connectedRepo.branch && (
                <p className="text-xs text-slate-500 mt-1">
                  Branch: <span className="text-primary">{connectedRepo.branch}</span>
                </p>
              )}
              <p className="text-xs text-slate-500 mt-1">
                {connectedRepo.is_local ? 'Local path' : 'Cloned repository'}
              </p>
            </div>
          </div>
          <button
            onClick={handleDisconnect}
            className="text-xs text-red-400 hover:text-red-300 border border-red-500/30 hover:border-red-500/50 rounded px-3 py-1.5 transition-colors flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-sm">link_off</span>
            Disconnect
          </button>
        </div>
      </div>
    );
  }

  // Connection form
  return (
    <div className="bg-surface-dark border border-surface-border rounded-xl p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-lg bg-primary/20 text-primary">
          <span className="material-symbols-outlined text-xl">cable</span>
        </div>
        <div>
          <h3 className="text-sm font-bold text-white">Connect to Repository</h3>
          <p className="text-xs text-slate-400">
            Enter a git URL or local path to analyze a target codebase
          </p>
        </div>
      </div>

      <div className="space-y-3">
        <div>
          <label className="block text-xs text-slate-400 mb-1">
            Git URL or Local Path
          </label>
          <input
            type="text"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="https://github.com/user/repo.git or /path/to/repo"
            className="w-full bg-surface-darker border border-surface-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-primary/50"
            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              Branch (optional)
            </label>
            <input
              type="text"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              placeholder="main"
              className="w-full bg-surface-darker border border-surface-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-primary/50"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              Display Name (optional)
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Repo"
              className="w-full bg-surface-darker border border-surface-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-primary/50"
            />
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            <span className="material-symbols-outlined text-sm">error</span>
            {error}
          </div>
        )}

        <button
          onClick={() => handleConnect()}
          disabled={loading || !source.trim()}
          className="w-full bg-primary hover:bg-cyan-400 disabled:bg-slate-600 disabled:cursor-not-allowed text-surface-darker font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <span className="material-symbols-outlined text-sm animate-spin">sync</span>
              Connecting...
            </>
          ) : (
            <>
              <span className="material-symbols-outlined text-sm">link</span>
              Connect Repository
            </>
          )}
        </button>
      </div>

      <div className="mt-4 pt-4 border-t border-surface-border">
        <p className="text-xs text-slate-400 mb-2">Quick Connect:</p>
        <div className="flex flex-wrap gap-2">
          {QUICK_REPOS.map((repo) => (
            <button
              key={repo.name}
              onClick={() => handleConnect(repo.source, repo.name)}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-darker border border-surface-border rounded-lg text-xs text-slate-300 hover:text-white hover:border-primary/50 transition-colors disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-sm text-primary">bolt</span>
              {repo.name}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-500 mt-3">
          <span className="text-slate-400">Supported:</span> HTTPS git URLs, local filesystem paths
        </p>
        <p className="text-xs text-slate-500 mt-1">
          <span className="text-amber-400">Note:</span> SSH URLs and embedded credentials are not supported
        </p>
      </div>
    </div>
  );
}
