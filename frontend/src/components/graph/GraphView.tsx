import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { fetchGraphExport } from '@/api/graph';
import { layoutGraph } from '@/lib/graph-layout';
import { EDGE_COLORS, getDocHex } from '@/lib/colors';
import DocumentNode from './DocumentNode';
import TrialNode from './TrialNode';
import { Search, Zap } from 'lucide-react';

const nodeTypes = { document: DocumentNode, trial: TrialNode };

export default function GraphView() {
  const navigate = useNavigate();
  const { data: rawGraph, isLoading } = useQuery({ queryKey: ['graph'], queryFn: fetchGraphExport });
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [search, setSearch] = useState('');
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  useEffect(() => {
    if (!rawGraph) return;

    const rfNodes: Node[] = [];
    const rfEdges: Edge[] = [];

    for (const item of rawGraph) {
      // OmniGraph export: nodes have "type" = "Document"|"Trial", edges have "edge" = "BelongsToTrial"|etc.
      if ('edge' in item) {
        // Edge entry
        const edgeLabel = item.edge as string;
        const from = item.from as string;
        const to = item.to as string;
        rfEdges.push({
          id: `${from}-${edgeLabel}-${to}`,
          source: from,
          target: to,
          label: edgeLabel,
          style: { stroke: EDGE_COLORS[edgeLabel] ?? '#cbd5e1', strokeWidth: edgeLabel === 'BelongsToTrial' ? 1 : 2 },
          animated: edgeLabel === 'Supersedes',
          labelStyle: { fontSize: 9, fill: '#94a3b8' },
          type: 'smoothstep',
        });
      } else if (item.type === 'Document' || item.type === 'Trial') {
        // Node entry
        const nodeLabel = item.type as string;
        const data = (item.data ?? {}) as Record<string, unknown>;
        const id = (data.doc_id ?? data.protocol_id ?? '') as string;

        if (!id) continue;

        rfNodes.push({
          id,
          type: nodeLabel === 'Trial' ? 'trial' : 'document',
          position: { x: 0, y: 0 },
          data: { ...data, _label: nodeLabel },
        });
      }
    }

    const { nodes: layouted, edges: layoutedEdges } = layoutGraph(rfNodes, rfEdges);
    setNodes(layouted);
    setEdges(layoutedEdges);
  }, [rawGraph, setNodes, setEdges]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const filteredNodes = useMemo(() => {
    if (!search) return nodes;
    const q = search.toLowerCase();
    return nodes.map((n) => ({
      ...n,
      hidden: !(
        (n.id ?? '').toLowerCase().includes(q) ||
        ((n.data as Record<string, unknown>).source_file as string ?? '').toLowerCase().includes(q) ||
        ((n.data as Record<string, unknown>).document_type as string ?? '').toLowerCase().includes(q) ||
        ((n.data as Record<string, unknown>).protocol_id as string ?? '').toLowerCase().includes(q)
      ),
    }));
  }, [nodes, search]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-pulse text-slate-400">Loading graph...</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-primary">Knowledge Graph</h2>
          <p className="text-sm text-slate-500">Document relationships and trial linkages</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search nodes..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden" style={{ height: 'calc(100vh - 220px)' }}>
        <ReactFlow
          nodes={filteredNodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.1}
          maxZoom={2}
          defaultEdgeOptions={{ type: 'smoothstep' }}
        >
          <Background color="#e2e8f0" gap={20} />
          <Controls className="!bg-white !border-slate-200 !shadow-sm" />
          <MiniMap
            nodeColor={(n) => {
              const d = n.data as Record<string, unknown>;
              if (n.type === 'trial') return '#1e3a5f';
              return getDocHex((d.document_type as string) || '');
            }}
            className="!bg-white !border-slate-200"
          />
        </ReactFlow>
      </div>

      {/* Edge legend */}
      <div className="flex items-center gap-4 text-xs text-slate-500">
        <span className="font-medium">Edges:</span>
        {Object.entries(EDGE_COLORS).map(([label, color]) => (
          <span key={label} className="flex items-center gap-1">
            <span className="w-4 h-0.5 rounded" style={{ background: color }} />
            {label}
          </span>
        ))}
      </div>

      {/* Selected node panel */}
      {selectedNode && (
        <div className="fixed right-0 top-14 w-80 bg-white border-l border-slate-200 shadow-lg p-5 h-[calc(100vh-56px)] overflow-y-auto z-40">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-700">Node Details</h3>
            <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-slate-600 text-xs">Close</button>
          </div>

          <div className="space-y-3 text-sm">
            {Object.entries(selectedNode.data as Record<string, unknown>).map(([key, value]) => {
              if (key.startsWith('_') || value == null || value === '') return null;
              return (
                <div key={key}>
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">{key}</p>
                  <p className="text-slate-700 break-all">{String(value)}</p>
                </div>
              );
            })}
          </div>

          {selectedNode.type === 'document' && (
            <button
              onClick={() => navigate(`/cascade/${selectedNode.id}`)}
              className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-light transition-colors"
            >
              <Zap size={14} />
              Run Cascade Analysis
            </button>
          )}
        </div>
      )}
    </div>
  );
}
