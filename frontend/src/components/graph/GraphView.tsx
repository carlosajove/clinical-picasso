import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d';
import { fetchGraphExport } from '@/api/graph';
import { DOC_TYPE_HEX, EDGE_COLORS, TRIAL_HEX, getDocHex } from '@/lib/colors';
import { Search, Zap, X } from 'lucide-react';

interface GraphNode {
  id: string;
  label: string;
  type: 'document' | 'trial';
  docType?: string;
  color: string;
  data: Record<string, unknown>;
  x?: number;
  y?: number;
}

interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  edgeType: string;
  color: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export default function GraphView() {
  const navigate = useNavigate();
  const fgRef = useRef<ForceGraphMethods<GraphNode, GraphLink> | undefined>();
  const containerRef = useRef<HTMLDivElement>(null);
  const { data: rawGraph, isLoading } = useQuery({ queryKey: ['graph'], queryFn: fetchGraphExport });

  const [search, setSearch] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);

  // Resize observer — must fire before we render ForceGraph2D
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) {
        setDimensions({ width, height });
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Build graph data
  const graphData: GraphData = useMemo(() => {
    if (!rawGraph) return { nodes: [], links: [] };

    const nodes: GraphNode[] = [];
    const links: GraphLink[] = [];
    const nodeIds = new Set<string>();

    for (const item of rawGraph) {
      if (!('edge' in item) && (item.type === 'Document' || item.type === 'Trial')) {
        const data = (item.data ?? {}) as Record<string, unknown>;
        const id = (data.doc_id ?? data.trial_key ?? data.protocol_id ?? data.id ?? '') as string;
        if (!id || nodeIds.has(id)) continue;
        nodeIds.add(id);

        const isTrial = item.type === 'Trial';
        const docType = (data.document_type as string) || '';

        nodes.push({
          id,
          label: isTrial
            ? (data.trial_key as string) || (data.protocol_id as string) || 'Trial'
            : (data.source_file as string) || docType || id,
          type: isTrial ? 'trial' : 'document',
          docType,
          color: isTrial ? TRIAL_HEX : getDocHex(docType),
          data,
        });
      }
    }

    for (const item of rawGraph) {
      if ('edge' in item) {
        const edgeLabel = item.edge as string;
        const from = item.from as string;
        const to = item.to as string;
        if (nodeIds.has(from) && nodeIds.has(to)) {
          links.push({
            source: from,
            target: to,
            edgeType: edgeLabel,
            color: EDGE_COLORS[edgeLabel] ?? '#94a3b8',
          });
        }
      }
    }

    return { nodes, links };
  }, [rawGraph]);

  // Search highlighting
  const searchMatches = useMemo(() => {
    if (!search) return new Set<string>();
    const q = search.toLowerCase();
    return new Set(
      graphData.nodes
        .filter(
          (n) =>
            n.id.toLowerCase().includes(q) ||
            n.label.toLowerCase().includes(q) ||
            (n.docType || '').toLowerCase().includes(q) ||
            ((n.data.protocol_id as string) || '').toLowerCase().includes(q)
        )
        .map((n) => n.id)
    );
  }, [graphData.nodes, search]);

  // Connected nodes for hover highlighting
  const getConnectedIds = useCallback(
    (nodeId: string) => {
      const ids = new Set<string>();
      ids.add(nodeId);
      for (const link of graphData.links) {
        const src = typeof link.source === 'string' ? link.source : link.source.id;
        const tgt = typeof link.target === 'string' ? link.target : link.target.id;
        if (src === nodeId) ids.add(tgt);
        if (tgt === nodeId) ids.add(src);
      }
      return ids;
    },
    [graphData.links]
  );

  const connectedIds = useMemo(
    () => (hoveredNode ? getConnectedIds(hoveredNode.id) : null),
    [hoveredNode, getConnectedIds]
  );

  // Node rendering
  const paintNode = useCallback(
    (node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const isTrial = node.type === 'trial';
      const baseRadius = isTrial ? 16 : 12;
      const isHovered = hoveredNode?.id === node.id;
      const isConnected = connectedIds?.has(node.id);
      const isSearchMatch = search && searchMatches.has(node.id);
      const isDimmed = (hoveredNode && !isConnected) || (search && !isSearchMatch);

      const radius = isHovered ? baseRadius * 1.6 : isSearchMatch ? baseRadius * 1.3 : baseRadius;

      // Glow effect
      if (isHovered || isSearchMatch) {
        ctx.beginPath();
        ctx.arc(x, y, radius + 5, 0, 2 * Math.PI);
        ctx.fillStyle = node.color + '20';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(x, y, radius + 2.5, 0, 2 * Math.PI);
        ctx.fillStyle = node.color + '35';
        ctx.fill();
      }

      // Main circle
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = isDimmed ? node.color + '30' : node.color;
      ctx.fill();

      // White border on trial nodes
      if (isTrial && !isDimmed) {
        ctx.strokeStyle = TRIAL_HEX + '80';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Labels
      const showLabel = globalScale > 0.6 || isHovered || isSearchMatch;
      if (showLabel) {
        const fontSize = Math.max(11 / globalScale, 2.5);
        ctx.font = `${isHovered || isSearchMatch ? '600 ' : '400 '}${fontSize}px Inter, system-ui, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        // Class label above the node
        if ((isHovered || globalScale > 1.2) && node.docType) {
          ctx.font = `400 ${fontSize * 0.75}px Inter, system-ui, sans-serif`;
          ctx.fillStyle = isDimmed ? '#94a3b840' : node.color;
          ctx.textBaseline = 'bottom';
          ctx.fillText(node.docType, x, y - radius - 3);
        }

        // Main label below the node
        ctx.textBaseline = 'top';
        const labelText = node.label.length > 28 ? node.label.slice(0, 26) + '…' : node.label;
        ctx.fillStyle = isDimmed ? '#94a3b850' : '#334155';
        ctx.fillText(labelText, x, y + radius + 2);
      }
    },
    [hoveredNode, connectedIds, search, searchMatches]
  );

  // Link rendering
  const paintLink = useCallback(
    (link: GraphLink, ctx: CanvasRenderingContext2D) => {
      const src = link.source as GraphNode;
      const tgt = link.target as GraphNode;
      if (src.x == null || tgt.x == null) return;

      const srcId = typeof link.source === 'string' ? link.source : (link.source as GraphNode).id;
      const tgtId = typeof link.target === 'string' ? link.target : (link.target as GraphNode).id;
      const isHighlighted = hoveredNode && connectedIds?.has(srcId) && connectedIds?.has(tgtId);

      ctx.beginPath();
      ctx.moveTo(src.x, src.y!);
      ctx.lineTo(tgt.x, tgt.y!);
      ctx.strokeStyle = hoveredNode
        ? isHighlighted
          ? link.color + 'bb'
          : '#e2e8f020'
        : link.color + '40';
      ctx.lineWidth = isHighlighted ? 1.8 : 0.6;
      ctx.stroke();
    },
    [hoveredNode, connectedIds]
  );

  // Configure forces (must re-run after ForceGraph2D mounts, which depends on dimensions)
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force('charge')?.strength(-150);
    fg.d3Force('link')?.distance((link: GraphLink) =>
      link.edgeType === 'BelongsToTrial' ? 90 : 55
    );
    fg.d3Force('center')?.strength(0.05);
  }, [graphData, dimensions]);

  // Zoom to fit on load and when container dimensions change
  useEffect(() => {
    if (graphData.nodes.length > 0 && fgRef.current) {
      setTimeout(() => fgRef.current?.zoomToFit(400, 60), 300);
    }
  }, [graphData.nodes.length, dimensions?.width, dimensions?.height]);

  const ready = !isLoading && dimensions;

  return (
    <div className="space-y-3">
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
              className="pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200 bg-white"
            />
          </div>
        </div>
      </div>

      <div
        ref={containerRef}
        className="bg-white rounded-xl border border-slate-200 overflow-hidden w-full"
        style={{ height: 'calc(100vh - 220px)', minWidth: 0 }}
      >
        {!ready && (
          <div className="flex items-center justify-center h-full">
            <div className="animate-pulse text-slate-400">Loading graph...</div>
          </div>
        )}
        {ready && <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="#ffffff"
          nodeCanvasObject={paintNode}
          nodePointerAreaPaint={(node: GraphNode, color, ctx) => {
            const r = node.type === 'trial' ? 20 : 16;
            ctx.beginPath();
            ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
          }}
          linkCanvasObject={paintLink}
          onNodeClick={(node: GraphNode) => setSelectedNode(node)}
          onNodeHover={(node: GraphNode | null) => setHoveredNode(node)}
          onBackgroundClick={() => setSelectedNode(null)}
          cooldownTicks={100}
          warmupTicks={50}
          enableNodeDrag={true}
          enableZoomInteraction={true}
          enablePanInteraction={true}
        />}
      </div>

      {/* Legend */}
      <div className="flex flex-col gap-2 text-xs text-slate-500">
        <div className="flex items-center gap-4 flex-wrap">
          <span className="font-medium">Nodes:</span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full" style={{ background: TRIAL_HEX }} />
            Trial
          </span>
          {Object.entries(DOC_TYPE_HEX).map(([label, color]) => (
            <span key={label} className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full" style={{ background: color }} />
              {label}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          <span className="font-medium">Edges:</span>
          {Object.entries(EDGE_COLORS).map(([label, color]) => (
            <span key={label} className="flex items-center gap-1">
              <span className="w-4 h-0.5 rounded" style={{ background: color }} />
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Selected node panel */}
      {selectedNode && (
        <div className="fixed right-0 top-14 w-80 bg-white border-l border-slate-200 shadow-lg p-5 h-[calc(100vh-56px)] overflow-y-auto z-40">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full"
                style={{ background: selectedNode.color }}
              />
              <h3 className="text-sm font-semibold text-slate-700">
                {selectedNode.type === 'trial' ? 'Trial' : selectedNode.docType || 'Document'}
              </h3>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-slate-400 hover:text-slate-600"
            >
              <X size={16} />
            </button>
          </div>

          <div className="space-y-3 text-sm">
            {Object.entries(selectedNode.data).map(([key, value]) => {
              if (key.startsWith('_') || value == null || value === '') return null;
              return (
                <div key={key}>
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">
                    {key}
                  </p>
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
