import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import NodeDetailPanel from './NodeDetailPanel';
import GraphVerdict from './GraphVerdict';
import GraphLegend from './GraphLegend';
import AccountList from './AccountList';
import { DEMO_GRAPH } from './demoGraph';
import { drawGraph } from './drawGraph';
import { graphVerdict, summariseClusters, whyFlagged } from './graphModel';

const VIEWS = [['graph', 'Graph'], ['list', 'List']];

export default function NetworkGraph({
  nodes: propNodes,
  edges: propEdges,
  timeRange = null,
  useDemoData = false,
}) {
  // Fall back to DEMO_GRAPH when no data is provided
  const rawNodes = (!propNodes || propNodes.length === 0 || useDemoData) ? DEMO_GRAPH.nodes : propNodes;
  const rawEdges = (!propEdges || propEdges.length === 0 || useDemoData) ? DEMO_GRAPH.edges : propEdges;

  // Normalise field names (backend may send betweenness_centrality, demo uses betweenness).
  // Memoised so selecting a node (state change) does not rebuild the d3 graph.
  const { nodes, edges } = useMemo(() => ({
    nodes: rawNodes.map(n => ({
      ...n,
      betweenness: n.betweenness ?? n.betweenness_centrality ?? 0,
    })),
    edges: rawEdges.map(e => ({
      ...e,
      from_account: e.from_account ?? e.source,
      to_account:   e.to_account   ?? e.target,
    })),
  }), [rawNodes, rawEdges]);

  const [view, setView] = useState('graph');
  const [selectedNode, setSelectedNode] = useState(null);
  const [hop, setHop] = useState(null);
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const graphRef = useRef(null);
  const timeRangeRef = useRef(timeRange);
  timeRangeRef.current = timeRange;

  const verdict = useMemo(() => graphVerdict(nodes, edges), [nodes, edges]);
  const hasClusters = useMemo(() => summariseClusters(nodes, edges).length > 1, [nodes, edges]);
  const reasons = useMemo(() => (selectedNode ? whyFlagged(selectedNode, edges) : []), [selectedNode, edges]);
  const closePanel = useCallback(() => setSelectedNode(null), []);

  useEffect(() => {
    if (!nodes.length) return undefined;
    const graph = drawGraph({
      svgEl: svgRef.current,
      container: containerRef.current,
      nodes,
      edges,
      onSelect: setSelectedNode,
      onHop: setHop,
    });
    graph.setTimeRange(timeRangeRef.current);
    graphRef.current = graph;
    return () => {
      graph.destroy();
      graphRef.current = null;
    };
  }, [nodes, edges]);

  useEffect(() => { graphRef.current?.setTimeRange(timeRange); }, [timeRange]);

  const canReplay = verdict.figures.flaggedTransfers > 0;

  return (
    <div className="graph-shell">
      <div className="graph-head">
        <GraphVerdict verdict={verdict} />
        <div className="graph-tools">
          <div className="view-toggle" role="group" aria-label="Graph view">
            {VIEWS.map(([key, label]) => (
              <button key={key} type="button" aria-pressed={view === key}
                      className={`filter-tab ${view === key ? 'active' : ''}`}
                      onClick={() => setView(key)}>
                {label}
              </button>
            ))}
          </div>
          {view === 'graph' && canReplay && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => graphRef.current?.replay()}>
              Replay money flow
            </button>
          )}
        </div>
      </div>

      <div className="graph-body">
        <div ref={containerRef} className="graph-stage" hidden={view !== 'graph'}>
          <svg ref={svgRef} role="img"
               aria-label="Money-flow graph of the accounts in this case. The list view shows the same accounts as a table." />
          <p className="graph-hop" aria-live="polite">{hop ? `Hop ${hop.current} of ${hop.total}` : ''}</p>
          <div className="graph-zoom">
            <button type="button" className="btn btn-ghost btn-sm" aria-label="Zoom in"
                    onClick={() => graphRef.current?.zoomBy(1.3)}>+</button>
            <button type="button" className="btn btn-ghost btn-sm" aria-label="Zoom out"
                    onClick={() => graphRef.current?.zoomBy(0.75)}>−</button>
            {hasClusters && (
              <button type="button" className="btn btn-ghost btn-sm"
                      onClick={() => graphRef.current?.focusRiskiest()}>Riskiest cluster</button>
            )}
            <button type="button" className="btn btn-ghost btn-sm"
                    onClick={() => graphRef.current?.showAll()}>Show all</button>
          </div>
        </div>
        {view === 'list' && <AccountList nodes={nodes} edges={edges} onSelect={setSelectedNode} />}
        <NodeDetailPanel node={selectedNode} reasons={reasons} onClose={closePanel} />
      </div>

      <GraphLegend />
    </div>
  );
}
