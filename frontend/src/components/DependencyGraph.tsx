import { useCallback, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeProps,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import type { DependencyNode, DependencyEdge } from '../api/client';

const COLOR_MAP: Record<string, { bg: string; border: string; text: string }> = {
  primary: { bg: 'rgba(6, 182, 212, 0.15)', border: '#06b6d4', text: '#06b6d4' },
  indigo: { bg: 'rgba(129, 140, 248, 0.15)', border: '#818cf8', text: '#818cf8' },
  emerald: { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981', text: '#10b981' },
  slate: { bg: 'rgba(100, 116, 139, 0.15)', border: '#64748b', text: '#f1f5f9' },
};

const NODE_WIDTH = 140;
const NODE_HEIGHT = 72;

type LayoutDirection = 'TB' | 'LR' | 'BT' | 'RL';

function getLayoutedElements(
  nodes: Node<Record<string, unknown>>[],
  edges: Edge[],
  direction: LayoutDirection = 'TB'
): { nodes: Node<Record<string, unknown>>[]; edges: Edge[] } {
  const dagreGraph = new dagre.graphlib.Graph({ compound: true });
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, nodesep: 60, ranksep: 80 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const isHorizontal = direction === 'LR' || direction === 'RL';
  const sourcePos = isHorizontal ? (direction === 'LR' ? 'right' : 'left') : 'bottom';
  const targetPos = isHorizontal ? (direction === 'LR' ? 'left' : 'right') : 'top';
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
      sourcePosition: sourcePos,
      targetPosition: targetPos,
    } as Node<Record<string, unknown>>;
  });

  return { nodes: layoutedNodes, edges };
}

export type DependencyGraphLayout = 'hierarchical' | 'horizontal' | 'radial';

interface DependencyGraphProps {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  layout?: DependencyGraphLayout;
  onNodeSelect?: (node: DependencyNode | null) => void;
  selectedNodeId?: string | null;
  searchTerm?: string;
  className?: string;
}

function ModuleNode({ data, selected }: NodeProps) {
  const d = data as unknown as DependencyNode;
  const colors = COLOR_MAP[d.color] || COLOR_MAP.slate;
  const hasCircular = d.has_circular;
  const fileCount = d.file_count ?? 0;
  const lineCount = d.line_count ?? 0;

  return (
    <div
      className={`rounded-xl border-2 px-3 py-2 shadow-md transition-all ${
        selected ? 'ring-2 ring-primary ring-offset-2 ring-offset-surface-darker' : ''
      } ${hasCircular ? 'ring-1 ring-amber-400' : ''}`}
      style={{
        backgroundColor: colors.bg,
        borderColor: colors.border,
        minWidth: NODE_WIDTH,
        minHeight: NODE_HEIGHT,
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="material-symbols-outlined text-xl"
          style={{ color: colors.text }}
        >
          {d.icon || 'extension'}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold text-sm" style={{ color: colors.text }}>
            {d.name}
          </div>
          {(fileCount > 0 || lineCount > 0) && (
            <div className="text-[10px] text-slate-500">
              {fileCount} files · {lineCount.toLocaleString()} LOC
            </div>
          )}
          {hasCircular && (
            <div className="text-[10px] text-amber-400">Circular dep</div>
          )}
        </div>
      </div>
    </div>
  );
}

const nodeTypes = { module: ModuleNode };

function toFlowNodes(apiNodes: DependencyNode[]): Node<Record<string, unknown>>[] {
  return apiNodes.map((n) => ({
    id: n.id,
    type: 'module',
    data: n as unknown as Record<string, unknown>,
    position: { x: 0, y: 0 },
  }));
}

function toFlowEdges(apiEdges: DependencyEdge[]): Edge[] {
  return apiEdges.map((e, i) => ({
    id: `e-${e.source}-${e.target}-${i}`,
    source: e.source,
    target: e.target,
    label: e.weight && e.weight > 1 ? String(e.weight) : undefined,
    style: { strokeWidth: Math.min(4, 1 + (e.weight ?? 1) * 0.3) },
    animated: (e.weight ?? 1) >= 3,
  }));
}

export function DependencyGraph({
  nodes: apiNodes,
  edges: apiEdges,
  layout = 'hierarchical',
  onNodeSelect,
  selectedNodeId,
  searchTerm = '',
  className = '',
}: DependencyGraphProps) {
  const direction: LayoutDirection =
    layout === 'horizontal' ? 'LR' : layout === 'radial' ? 'TB' : 'TB';

  const initialNodes = toFlowNodes(apiNodes);
  const initialEdges = toFlowEdges(apiEdges);
  const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
    initialNodes,
    initialEdges,
    direction
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes as Node[]);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  useEffect(() => {
    const { nodes: nextNodes, edges: nextEdges } = getLayoutedElements(
      toFlowNodes(apiNodes),
      toFlowEdges(apiEdges),
      direction
    );
    setNodes(nextNodes);
    setEdges(nextEdges);
  }, [apiNodes, apiEdges, direction, setNodes, setEdges]);

  const filteredNodeIds = searchTerm
    ? new Set(
        apiNodes
          .filter((n) =>
            n.name.toLowerCase().includes(searchTerm.toLowerCase())
          )
          .map((n) => n.id)
      )
    : null;

  const visibleNodes = nodes.map((n) => {
    let className = '';
    if (filteredNodeIds !== null && !filteredNodeIds.has(n.id)) className = 'opacity-30';
    return {
      ...n,
      className,
      selected: selectedNodeId === n.id,
    };
  });

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const apiNode = apiNodes.find((n) => n.id === node.id) ?? null;
      onNodeSelect?.(apiNode);
    },
    [apiNodes, onNodeSelect]
  );

  return (
    <div className={`h-full w-full ${className}`}>
      <ReactFlow
        nodes={visibleNodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={() => onNodeSelect?.(null)}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        defaultEdgeOptions={{ type: 'smoothstep', markerEnd: { type: 'arrowclosed' } }}
        minZoom={0.2}
        maxZoom={1.5}
      >
        <Background gap={16} size={1} color="rgba(100,116,139,0.2)" />
        <Controls className="!bottom-2 !top-auto !z-50" />
        <MiniMap
          nodeColor={(n) => {
            const d = n.data as unknown as DependencyNode;
            return COLOR_MAP[d.color]?.border ?? '#64748b';
          }}
          maskColor="rgba(15,23,42,0.8)"
          className="!bottom-2 !left-2 !bg-surface-darker"
        />
        <Panel position="top-left" className="text-xs text-slate-500">
          Layout: {layout} · {apiNodes.length} modules
        </Panel>
      </ReactFlow>
    </div>
  );
}
