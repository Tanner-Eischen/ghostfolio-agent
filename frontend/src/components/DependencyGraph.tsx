import { useEffect, useState } from 'react';
import {
  ReactFlow,
  Background,
  useReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
  type NodeProps,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import type { DependencyNode, DependencyEdge } from '../api/client';

const COLORS: Record<string, string> = {
  primary: '#06b6d4',
  indigo: '#818cf8',
  emerald: '#10b981',
  slate: '#64748b',
};

function layoutWithDagre(nodes: Node[], edges: Edge[]): Node[] {
  if (nodes.length === 0) return [];

  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 80, marginx: 40, marginy: 40 });
  g.setDefaultEdgeLabel(() => ({}));

  nodes.forEach(n => g.setNode(n.id, { width: 120, height: 40 }));
  edges.forEach(e => g.setEdge(e.source, e.target));
  dagre.layout(g);

  return nodes.map(n => {
    const pos = g.node(n.id);
    return {
      ...n,
      position: { x: (pos?.x ?? 0) - 60, y: (pos?.y ?? 0) - 20 },
    };
  });
}

function SimpleNode({ data }: NodeProps) {
  const d = data as unknown as DependencyNode;
  const color = COLORS[d.color] || COLORS.slate;

  return (
    <div
      className="rounded-lg border-2 px-3 py-2 bg-surface-dark"
      style={{ borderColor: color, minWidth: 100 }}
    >
      <div className="flex items-center gap-1.5">
        <span className="material-symbols-outlined text-sm" style={{ color }}>
          {d.icon || 'extension'}
        </span>
        <span className="text-xs font-medium text-white">{d.name}</span>
      </div>
    </div>
  );
}

const nodeTypes = { simple: SimpleNode };

export type DependencyGraphLayout = 'hierarchical' | 'horizontal' | 'radial';

interface Props {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  layout?: DependencyGraphLayout;
  onNodeSelect?: (node: DependencyNode | null) => void;
  selectedNodeId?: string | null;
  searchTerm?: string;
  className?: string;
}

export function DependencyGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}

function Inner({ nodes: apiNodes, edges: apiEdges, searchTerm = '', className = '' }: Props) {
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  useEffect(() => {
    // Deduplicate by id (React Flow keeps one node per id; duplicates would hide nodes)
    const seenIds = new Set<string>();
    const uniqueNodes: DependencyNode[] = [];
    for (const n of apiNodes) {
      if (seenIds.has(n.id)) {
        console.warn('DependencyGraph: duplicate node id dropped:', n.id, n.name);
        continue;
      }
      seenIds.add(n.id);
      uniqueNodes.push(n);
    }
    if (uniqueNodes.length !== apiNodes.length) {
      console.log('DependencyGraph: deduplicated nodes', apiNodes.length, '->', uniqueNodes.length);
    }

    // Optional filter by search term (case-insensitive name substring)
    const term = searchTerm.trim().toLowerCase();
    const nodesToRender = term
      ? uniqueNodes.filter(n => n.name.toLowerCase().includes(term))
      : uniqueNodes;

    console.log('API nodes:', apiNodes.length, 'unique:', uniqueNodes.length, 'visible:', nodesToRender.length, term ? `(filter: "${searchTerm}")` : '');

    if (nodesToRender.length === 0) {
      setNodes([]);
      setEdges([]);
      return;
    }

    // Create a set of valid node IDs for validation
    const nodeIds = new Set(nodesToRender.map(n => n.id));

    // Convert to ReactFlow format
    const flowNodes: Node[] = nodesToRender.map(n => ({
      id: n.id,
      type: 'simple',
      data: n as unknown as Record<string, unknown>,
      position: { x: 0, y: 0 },
    }));

    // Filter edges: valid refs and (when search active) both endpoints visible
    const validEdges = apiEdges.filter(e => {
      if (!e.source || !e.target) {
        console.warn('Edge with null source/target:', e);
        return false;
      }
      if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) {
        if (!term) console.warn('Edge references non-existent node:', e.source, '->', e.target);
        return false;
      }
      return true;
    });

    const flowEdges: Edge[] = validEdges.map((e, i) => ({
      id: `e${i}`,
      source: e.source,
      target: e.target,
      type: 'smoothstep',
      style: { stroke: '#475569', strokeWidth: 1.5 },
    }));

    console.log('Flow nodes:', flowNodes.length, 'Flow edges:', flowEdges.length, '(filtered from', apiEdges.length, ')');

    const layouted = layoutWithDagre(flowNodes, flowEdges);
    setNodes(layouted);
    setEdges(flowEdges);

    setTimeout(() => fitView({ padding: 0.3 }), 100);
  }, [apiNodes, apiEdges, searchTerm, fitView]);

  const uniqueNodeCount = new Set(apiNodes.map(n => n.id)).size;
  const visibleCount = searchTerm.trim()
    ? (() => {
        const term = searchTerm.trim().toLowerCase();
        const visible = apiNodes.filter(n => n.name.toLowerCase().includes(term));
        const visibleIds = new Set<string>();
        const visibleUniq = visible.filter(n => { if (visibleIds.has(n.id)) return false; visibleIds.add(n.id); return true; });
        return { visible: visibleUniq.length, total: uniqueNodeCount };
      })()
    : null;

  if (apiNodes.length === 0) {
    return (
      <div className={`flex items-center justify-center ${className}`}>
        <p className="text-slate-500">No modules detected</p>
      </div>
    );
  }

  return (
    <div className={className}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        panOnScroll={false}
        zoomOnScroll
      >
        <Background color="#334155" />
        <Panel position="bottom-right" className="flex gap-1">
          <button onClick={() => fitView({ padding: 0.3 })} className="px-2 py-1 text-xs bg-surface-dark text-white border border-slate-600 rounded">Fit</button>
          <button onClick={() => zoomIn()} className="px-2 py-1 text-sm bg-surface-dark text-white border border-slate-600 rounded">+</button>
          <button onClick={() => zoomOut()} className="px-2 py-1 text-sm bg-surface-dark text-white border border-slate-600 rounded">−</button>
        </Panel>
        <Panel position="top-left">
          <span className="text-xs text-slate-400 bg-surface-dark px-2 py-1 rounded">
            {visibleCount
              ? `${visibleCount.visible} of ${visibleCount.total} nodes`
              : `${uniqueNodeCount} nodes`} · {edges.length} edges
          </span>
        </Panel>
      </ReactFlow>
    </div>
  );
}
