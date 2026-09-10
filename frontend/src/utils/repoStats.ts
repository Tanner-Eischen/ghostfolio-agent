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
