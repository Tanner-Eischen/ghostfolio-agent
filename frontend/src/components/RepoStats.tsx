import type { FileNode } from '../api/client';

export interface FileStats {
  totalFiles: number;
  totalDirs: number;
  byExtension: Record<string, number>;
}

export function computeFileStats(root: FileNode): FileStats {
  const stats: FileStats = { totalFiles: 0, totalDirs: 0, byExtension: {} };

  function traverse(node: FileNode) {
    if (node.type === 'file') {
      stats.totalFiles++;
      const parts = node.name.split('.');
      const ext = parts.length > 1 ? parts.pop()!.toLowerCase() : 'unknown';
      stats.byExtension[ext] = (stats.byExtension[ext] || 0) + 1;
    } else if (node.children) {
      stats.totalDirs++;
      node.children.forEach(traverse);
    }
  }

  traverse(root);
  return stats;
}

// Map extensions to language names
const extensionToLanguage: Record<string, string> = {
  py: 'Python',
  ts: 'TypeScript',
  tsx: 'TypeScript',
  js: 'JavaScript',
  jsx: 'JavaScript',
  json: 'JSON',
  md: 'Markdown',
  yaml: 'YAML',
  yml: 'YAML',
  css: 'CSS',
  scss: 'SCSS',
  html: 'HTML',
  sql: 'SQL',
  sh: 'Shell',
  bash: 'Shell',
  toml: 'TOML',
  ini: 'INI',
  txt: 'Text',
};

// Get icon for extension
function getExtensionIcon(ext: string): string {
  const iconMap: Record<string, string> = {
    py: 'terminal',
    ts: 'javascript',
    tsx: 'javascript',
    js: 'javascript',
    jsx: 'javascript',
    json: 'data_object',
    md: 'description',
    yaml: 'settings',
    yml: 'settings',
    css: 'palette',
    scss: 'palette',
    html: 'code',
    sql: 'database',
    sh: 'terminal',
    bash: 'terminal',
  };
  return iconMap[ext] || 'description';
}

// Get color for extension
function getExtensionColor(ext: string): string {
  const colorMap: Record<string, string> = {
    py: 'text-blue-400',
    ts: 'text-blue-300',
    tsx: 'text-blue-300',
    js: 'text-yellow-400',
    jsx: 'text-yellow-400',
    json: 'text-amber-400',
    md: 'text-slate-400',
    yaml: 'text-pink-400',
    yml: 'text-pink-400',
    css: 'text-purple-400',
    scss: 'text-pink-400',
    html: 'text-orange-400',
    sql: 'text-cyan-400',
  };
  return colorMap[ext] || 'text-slate-400';
}

interface RepoStatsProps {
  fileTree: FileNode | null;
}

export function RepoStats({ fileTree }: RepoStatsProps) {
  if (!fileTree) {
    return null;
  }

  const stats = computeFileStats(fileTree);

  // Get top extensions by count
  const sortedExtensions = Object.entries(stats.byExtension)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return (
    <div className="border-t border-surface-border pt-3 mt-2">
      <div className="px-2 mb-2">
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
          Quick Stats
        </span>
      </div>

      <div className="px-2 space-y-3">
        {/* Totals */}
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-sm text-slate-500">description</span>
            <span className="text-slate-300">{stats.totalFiles}</span>
            <span className="text-slate-500">files</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-sm text-slate-500">folder</span>
            <span className="text-slate-300">{stats.totalDirs}</span>
            <span className="text-slate-500">dirs</span>
          </div>
        </div>

        {/* Language breakdown */}
        {sortedExtensions.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[10px] text-slate-500 uppercase tracking-wide">Tech Stack</div>
            <div className="space-y-1">
              {sortedExtensions.map(([ext, count]) => (
                <div key={ext} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5">
                    <span className={`material-symbols-outlined text-sm ${getExtensionColor(ext)}`}>
                      {getExtensionIcon(ext)}
                    </span>
                    <span className="text-slate-300">{extensionToLanguage[ext] || ext.toUpperCase()}</span>
                  </div>
                  <span className="text-slate-500 font-mono">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
