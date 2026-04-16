import dagre from '@dagrejs/dagre';
import type { Node, Edge } from '@xyflow/react';

const NODE_WIDTH = 200;
const NODE_HEIGHT = 70;
const TRIAL_WIDTH = 180;
const TRIAL_HEIGHT = 50;

export function layoutGraph(nodes: Node[], edges: Edge[]): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', ranksep: 80, nodesep: 40, marginx: 20, marginy: 20 });

  nodes.forEach((node) => {
    const isTrial = node.type === 'trial';
    g.setNode(node.id, {
      width: isTrial ? TRIAL_WIDTH : NODE_WIDTH,
      height: isTrial ? TRIAL_HEIGHT : NODE_HEIGHT,
    });
  });

  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    const isTrial = node.type === 'trial';
    return {
      ...node,
      position: {
        x: pos.x - (isTrial ? TRIAL_WIDTH : NODE_WIDTH) / 2,
        y: pos.y - (isTrial ? TRIAL_HEIGHT : NODE_HEIGHT) / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}
