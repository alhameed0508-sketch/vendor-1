import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

const ROLE_COLORS = {
  SOURCE:      '#EF4444',
  AGGREGATOR:  '#ff7c3b',
  MULE:        '#f59e0b',
  LEGITIMATE:  '#3b82f6',
  UNKNOWN:     '#86868B',
};

const ROLE_RADIUS = {
  SOURCE: 18,
  AGGREGATOR: 16,
  MULE: 12,
  LEGITIMATE: 10,
  UNKNOWN: 10,
};

export default function NetworkGraph({ nodes = [], edges = [], timeRange = null }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const zoomRef = useRef(null);
  const linkSelRef = useRef(null);   // stores D3 link selection for time filtering
  const flowSelRef = useRef(null);   // stores flow particle group

  useEffect(() => {
    if (!nodes.length) return;

    const container = containerRef.current;
    const width = container.clientWidth || 600;
    const height = 420;

    // Clear previous render
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    // Zoom + pan container
    const g = svg.append('g');
    const zoom = d3.zoom()
      .scaleExtent([0.3, 4])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);
    zoomRef.current = { zoom, svg };

    // Defs
    const defs = svg.append('defs');

    // Arrowhead marker
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', 'var(--border-bright)');

    // Glow filter for high-risk nodes
    const glowFilter = defs.append('filter')
      .attr('id', 'glow')
      .attr('x', '-50%').attr('y', '-50%')
      .attr('width', '200%').attr('height', '200%');
    glowFilter.append('feGaussianBlur')
      .attr('stdDeviation', '3')
      .attr('result', 'coloredBlur');
    const feMerge = glowFilter.append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Particle glow filter — softer, wider blur for money flow dots
    const particleGlow = defs.append('filter')
      .attr('id', 'particleGlow')
      .attr('x', '-100%').attr('y', '-100%')
      .attr('width', '300%').attr('height', '300%');
    particleGlow.append('feGaussianBlur')
      .attr('stdDeviation', '4')
      .attr('result', 'glow');
    const pMerge = particleGlow.append('feMerge');
    pMerge.append('feMergeNode').attr('in', 'glow');
    pMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Build node map
    const nodeMap = {};
    nodes.forEach(n => { nodeMap[n.account_id] = n; });

    // Build D3 nodes & links — start all nodes at center for spawn effect
    const graphNodes = nodes.map(n => ({ ...n, id: n.account_id, x: width / 2, y: height / 2 }));
    const graphLinks = edges.map(e => ({
      source: e.from_account,
      target: e.to_account,
      amount: e.total_amount,
      count: e.txn_count,
      pattern: e.pattern,
      timestamps: e.timestamps || [],
    })).filter(e => nodeMap[e.source] && nodeMap[e.target]);

    // Force simulation — start with high alpha for dramatic spawn
    const simulation = d3.forceSimulation(graphNodes)
      .force('link', d3.forceLink(graphLinks).id(d => d.id).distance(90).strength(0.4))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => ROLE_RADIUS[d.role] + 14))
      .alpha(1.5)
      .alphaDecay(0.02);

    // Edge width scale
    const maxAmount = Math.max(...graphLinks.map(l => l.amount), 1);
    const edgeWidth = d3.scaleLinear().domain([0, maxAmount]).range([1, 4]);

    // Draw edges with dash animation (draw-in effect)
    const link = g.append('g').selectAll('line')
      .data(graphLinks).enter().append('line')
      .attr('stroke', l => l.pattern === 'SMURFING' ? 'rgba(255,59,92,0.4)' :
                            l.pattern === 'CONSOLIDATION' ? 'rgba(245,158,11,0.4)' : 'rgba(42,53,80,0.8)')
      .attr('stroke-width', l => edgeWidth(l.amount))
      .attr('marker-end', 'url(#arrowhead)')
      .attr('stroke-dasharray', '1000')
      .attr('stroke-dashoffset', '1000');

    linkSelRef.current = link;

    // Animate edges drawing in with stagger
    link.transition()
      .delay((d, i) => 300 + i * 80)
      .duration(600)
      .ease(d3.easeCubicOut)
      .attr('stroke-dashoffset', '0');

    // Edge amount labels
    const linkLabel = g.append('g').selectAll('text')
      .data(graphLinks.filter(l => l.amount > 10000)).enter().append('text')
      .attr('fill', 'var(--text-muted)')
      .attr('font-size', 9)
      .attr('font-family', 'var(--font-mono)')
      .attr('text-anchor', 'middle')
      .attr('opacity', 0);

    // Fade in labels after edges draw
    linkLabel.transition()
      .delay(800)
      .duration(400)
      .attr('opacity', 1);

    // Draw nodes — start invisible, stagger appear
    const nodeGroup = g.append('g').selectAll('g')
      .data(graphNodes).enter().append('g')
      .style('cursor', 'pointer')
      .attr('opacity', 0)
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      );

    // Stagger node appearance with spring-like scale
    nodeGroup.transition()
      .delay((d, i) => 100 + i * 100)
      .duration(500)
      .ease(d3.easeBackOut.overshoot(1.5))
      .attr('opacity', 1)
      .attrTween('transform', function(d) {
        const scaleInterp = d3.interpolate(0.3, 1);
        return function(t) {
          return `translate(${d.x},${d.y}) scale(${scaleInterp(t)})`;
        };
      });

    // Node glow ring for high-risk — with pulsing animation
    nodeGroup.filter(d => d.role === 'SOURCE' || d.role === 'AGGREGATOR')
      .append('circle')
      .attr('r', d => ROLE_RADIUS[d.role] + 6)
      .attr('fill', 'none')
      .attr('stroke', d => ROLE_COLORS[d.role])
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '3,3')
      .attr('opacity', 0.5)
      .attr('filter', 'url(#glow)');

    // Main circle
    nodeGroup.append('circle')
      .attr('r', d => ROLE_RADIUS[d.role])
      .attr('fill', d => ROLE_COLORS[d.role] + '22')
      .attr('stroke', d => ROLE_COLORS[d.role])
      .attr('stroke-width', 2);

    // Score indicator ring
    nodeGroup.append('circle')
      .attr('r', d => ROLE_RADIUS[d.role])
      .attr('fill', 'none')
      .attr('stroke', d => ROLE_COLORS[d.role])
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', d => {
        const circumference = 2 * Math.PI * ROLE_RADIUS[d.role];
        return `${circumference * d.smurf_score} ${circumference}`;
      })
      .attr('opacity', 0.8);

    // Role abbreviation label
    nodeGroup.append('text')
      .text(d => d.role.substring(0, 2))
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('fill', d => ROLE_COLORS[d.role])
      .attr('font-size', d => ROLE_RADIUS[d.role] > 12 ? 9 : 7)
      .attr('font-family', 'var(--font-mono)')
      .attr('font-weight', '500');

    // Account ID label below
    nodeGroup.append('text')
      .text(d => d.account_id)
      .attr('text-anchor', 'middle')
      .attr('dy', d => ROLE_RADIUS[d.role] + 12)
      .attr('fill', 'var(--text-secondary)')
      .attr('font-size', 9)
      .attr('font-family', 'var(--font-mono)');

    // ── Multi-particle money flow system ────────────────────────────────────
    // Particles per edge scale with txn count; size/speed scale with amount.
    const flowGroup = g.append('g').attr('class', 'flow-particles');
    flowSelRef.current = flowGroup;

    const PATTERN_COLOR = {
      SMURFING:      '#EF4444',
      CONSOLIDATION: '#f59e0b',
      NORMAL:        '#06b6d4',
    };

    const maxAmountFlow = Math.max(...graphLinks.map(l => l.amount), 1);
    const particleRadius = d3.scaleLinear().domain([0, maxAmountFlow]).range([1.5, 4]).clamp(true);
    const particleSpeed  = d3.scaleLinear().domain([0, maxAmountFlow]).range([2400, 1400]).clamp(true);
    const particleCount  = d3.scaleLinear().domain([1, 10]).range([2, 6]).clamp(true);

    const resolveNode = (ref) =>
      typeof ref === 'object' ? ref : graphNodes.find(n => n.id === ref);

    const activeTimers = [];

    graphLinks.forEach((linkData, i) => {
      const color = PATTERN_COLOR[linkData.pattern] || PATTERN_COLOR.NORMAL;
      const count = Math.round(particleCount(linkData.count || 1));
      const r     = particleRadius(linkData.amount);
      const dur   = particleSpeed(linkData.amount);

      for (let p = 0; p < count; p++) {
        // Trail circle — larger, dimmer, follows behind the main dot
        const trail = flowGroup.append('circle')
          .attr('r', r * 2.2)
          .attr('fill', color)
          .attr('opacity', 0)
          .attr('filter', 'url(#particleGlow)');

        // Main particle
        const dot = flowGroup.append('circle')
          .attr('r', r)
          .attr('fill', color)
          .attr('opacity', 0);

        const stagger = (p / count) * dur;

        const animateParticle = () => {
          const src = resolveNode(linkData.source);
          const tgt = resolveNode(linkData.target);
          if (!src || !tgt) return;

          // Position at source
          dot.attr('cx', src.x).attr('cy', src.y).attr('opacity', 0.85);
          trail.attr('cx', src.x).attr('cy', src.y).attr('opacity', 0.25);

          // Animate main dot
          dot.transition()
            .duration(dur)
            .ease(d3.easeLinear)
            .attrTween('cx', () => t => src.x + (tgt.x - src.x) * t)
            .attrTween('cy', () => t => src.y + (tgt.y - src.y) * t)
            .attrTween('opacity', () => t => {
              if (t < 0.1) return t / 0.1 * 0.85;
              if (t > 0.85) return (1 - t) / 0.15 * 0.85;
              return 0.85;
            })
            .on('end', animateParticle);

          // Animate trail — slightly delayed for a trailing effect
          trail.transition()
            .duration(dur)
            .ease(d3.easeLinear)
            .attrTween('cx', () => t => {
              const lag = Math.max(0, t - 0.08);
              return src.x + (tgt.x - src.x) * lag;
            })
            .attrTween('cy', () => t => {
              const lag = Math.max(0, t - 0.08);
              return src.y + (tgt.y - src.y) * lag;
            })
            .attrTween('opacity', () => t => {
              if (t < 0.12) return t / 0.12 * 0.25;
              if (t > 0.8) return (1 - t) / 0.2 * 0.25;
              return 0.25;
            });
        };

        // Stagger start after initial edge draw-in animation
        const timerId = setTimeout(animateParticle, 1400 + i * 120 + stagger);
        activeTimers.push(timerId);
      }
    });

    // Hover: highlight connected edges
    nodeGroup
      .on('mouseover', (event, d) => {
        // Dim all edges
        link.attr('opacity', 0.15);
        // Highlight connected edges
        link.filter(l => l.source.id === d.id || l.target.id === d.id)
          .attr('opacity', 1)
          .attr('stroke-width', l => edgeWidth(l.amount) + 1);
        // Dim non-connected nodes
        nodeGroup.attr('opacity', n => {
          if (n.id === d.id) return 1;
          const connected = graphLinks.some(l =>
            (l.source.id === d.id && l.target.id === n.id) ||
            (l.target.id === d.id && l.source.id === n.id)
          );
          return connected ? 1 : 0.3;
        });

        // Show tooltip
        tooltip.transition().duration(100).style('opacity', 1);
        tooltip.html(`
          <div style="color:${ROLE_COLORS[d.role]};font-weight:600;margin-bottom:4px">${d.role}</div>
          <div>${d.account_id}</div>
          <div style="color:var(--tooltip-muted);margin-top:4px">${d.bank} · ${d.city}</div>
          <div style="color:var(--tooltip-muted)">Age: ${d.account_age_days}d · KYC: ${d.kyc_status}</div>
          <div style="margin-top:4px">Smurf score: <span style="color:var(--accent-amber)">${(d.smurf_score*100).toFixed(0)}%</span></div>
          ${d.betweenness > 0.01 ? `<div>Betweenness: <span style="color:var(--accent-cyan)">${(d.betweenness*100).toFixed(1)}%</span></div>` : ''}
          ${d.pagerank > 0.01 ? `<div>PageRank: <span style="color:var(--accent-cyan)">${(d.pagerank*100).toFixed(1)}%</span></div>` : ''}
        `);
      })
      .on('mousemove', (event) => {
        const rect = container.getBoundingClientRect();
        tooltip
          .style('left', (event.clientX - rect.left + 12) + 'px')
          .style('top', (event.clientY - rect.top - 20) + 'px');
      })
      .on('mouseout', () => {
        // Restore all
        link.attr('opacity', 1).attr('stroke-width', l => edgeWidth(l.amount));
        nodeGroup.attr('opacity', 1);
        tooltip.transition().duration(200).style('opacity', 0);
      });

    // Tooltip
    const tooltip = d3.select(container).append('div')
      .style('position', 'absolute')
      .style('background', 'var(--tooltip-bg)')
      .style('border', '1px solid var(--tooltip-border)')
      .style('border-radius', 'var(--radius)')
      .style('padding', '10px 14px')
      .style('font-family', 'var(--font-mono)')
      .style('font-size', '11px')
      .style('color', 'var(--tooltip-text)')
      .style('pointer-events', 'none')
      .style('opacity', 0)
      .style('z-index', 10)
      .style('max-width', '200px')
      .style('backdrop-filter', 'blur(8px)');

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      linkLabel
        .attr('x', d => (d.source.x + d.target.x) / 2)
        .attr('y', d => (d.source.y + d.target.y) / 2)
        .text(d => `₹${(d.amount / 1000).toFixed(0)}k`);

      nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    return () => {
      activeTimers.forEach(clearTimeout);
      simulation.stop();
      d3.select(container).selectAll('div').remove();
    };
  }, [nodes, edges]);

  // Time filtering: when timeRange changes, dim out-of-range edges
  useEffect(() => {
    const linkSel = linkSelRef.current;
    if (!linkSel || !timeRange) return;

    linkSel.attr('opacity', d => {
      const timestamps = d.timestamps || [];
      const inRange = timestamps.some(t => {
        const ms = new Date(t).getTime();
        return ms >= timeRange.start && ms <= timeRange.end;
      });
      return inRange ? 1 : 0.06;
    });
  }, [timeRange]);

  // Legend
  const legendItems = [
    { role: 'SOURCE', label: 'Source' },
    { role: 'AGGREGATOR', label: 'Aggregator' },
    { role: 'MULE', label: 'Mule' },
    { role: 'LEGITIMATE', label: 'Legitimate' },
  ];

  const handleZoom = (factor) => {
    if (!zoomRef.current) return;
    const { zoom: z, svg: s } = zoomRef.current;
    s.transition().duration(300).call(z.scaleBy, factor);
  };
  const handleReset = () => {
    if (!zoomRef.current) return;
    const { zoom: z, svg: s } = zoomRef.current;
    s.transition().duration(500).call(z.transform, d3.zoomIdentity);
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <svg ref={svgRef} style={{ display: 'block', background: 'transparent' }} />
      {/* Zoom controls */}
      <div style={{ position: 'absolute', top: 8, right: 8, display: 'flex', gap: 4 }}>
        <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 14, lineHeight: 1 }} onClick={() => handleZoom(1.3)} title="Zoom in">+</button>
        <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 14, lineHeight: 1 }} onClick={() => handleZoom(0.7)} title="Zoom out">-</button>
        <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 11, lineHeight: 1 }} onClick={handleReset} title="Reset view">Fit</button>
      </div>
      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, padding: '8px 20px 12px', borderTop: '1px solid var(--border)', flexWrap: 'wrap' }}>
        {legendItems.map(item => (
          <div key={item.role} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: ROLE_COLORS[item.role] + '33', border: `2px solid ${ROLE_COLORS[item.role]}` }} />
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{item.label}</span>
          </div>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 2, background: 'rgba(255,59,92,0.5)' }} />
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Smurfing</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 2, background: 'rgba(245,158,11,0.5)' }} />
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Consolidation</span>
          </div>
          {/* Flow indicator — shows animated particle trail */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#06b6d4', boxShadow: '0 0 6px #06b6d4' }} />
              <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#06b6d4', opacity: 0.4 }} />
              <div style={{ width: 3, height: 3, borderRadius: '50%', background: '#06b6d4', opacity: 0.2 }} />
            </div>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Money Flow</span>
          </div>
        </div>
      </div>
    </div>
  );
}
