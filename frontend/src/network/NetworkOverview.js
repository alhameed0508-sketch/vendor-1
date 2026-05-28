import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, Users, ArrowRightLeft, AlertTriangle, Share2 } from 'lucide-react';
import { apiFetch } from '../auth/api';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import NetworkGraph from '../graph_viz/NetworkGraph';
import TimelineSlider from '../graph_viz/TimelineSlider';

/* ── Stat Card ── */
function StatCard({ label, value, color, icon: Icon, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35, ease: 'easeOut' }}
      style={{
        background: 'rgba(15,20,33,0.70)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 10,
        padding: '16px 18px',
        position: 'relative',
        overflow: 'hidden',
        transition: 'border-color 0.2s, box-shadow 0.2s',
        cursor: 'default',
      }}
      whileHover={{
        borderColor: `${color}30`,
        boxShadow: `0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px ${color}18`,
        y: -1,
        transition: { duration: 0.2 },
      }}
    >
      {/* Glow behind value */}
      <div style={{
        position: 'absolute', top: -20, right: -20,
        width: 80, height: 80,
        background: `radial-gradient(circle, ${color}18 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />
      {/* Top accent */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 1,
        background: `linear-gradient(90deg, ${color}60, transparent)`,
      }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'var(--text-muted)',
          letterSpacing: '1.2px',
          textTransform: 'uppercase',
          fontWeight: 700,
        }}>{label}</div>
        {Icon && (
          <div style={{ color, opacity: 0.5 }}>
            <Icon size={13} />
          </div>
        )}
      </div>

      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: 28,
        fontWeight: 800,
        color,
        letterSpacing: '-1px',
        lineHeight: 1,
      }}>{value}</div>
    </motion.div>
  );
}

/* ── Aggregate helpers ── */

function aggregateGraphData(alerts) {
  const nodeMap = new Map();
  const edgeMap = new Map();

  for (const alert of alerts) {
    const nodes = alert.nodes || [];
    const edges = alert.edges || [];

    for (const node of nodes) {
      if (!node.account_id) continue;
      const existing = nodeMap.get(node.account_id);
      if (!existing) {
        nodeMap.set(node.account_id, { ...node });
      } else {
        // Keep the higher smurf_score and more severe role
        const rolePriority = { SOURCE: 4, AGGREGATOR: 3, MULE: 2, LEGITIMATE: 1, UNKNOWN: 0 };
        const existingPriority = rolePriority[existing.role] || 0;
        const newPriority = rolePriority[node.role] || 0;
        if (newPriority > existingPriority) {
          nodeMap.set(node.account_id, {
            ...existing,
            role: node.role,
            smurf_score: Math.max(existing.smurf_score || 0, node.smurf_score || 0),
            betweenness: Math.max(existing.betweenness || 0, node.betweenness || 0),
            pagerank: Math.max(existing.pagerank || 0, node.pagerank || 0),
          });
        } else {
          nodeMap.set(node.account_id, {
            ...existing,
            smurf_score: Math.max(existing.smurf_score || 0, node.smurf_score || 0),
            betweenness: Math.max(existing.betweenness || 0, node.betweenness || 0),
            pagerank: Math.max(existing.pagerank || 0, node.pagerank || 0),
          });
        }
      }
    }

    for (const edge of edges) {
      const key = `${edge.from_account}:${edge.to_account}`;
      const existing = edgeMap.get(key);
      if (!existing) {
        edgeMap.set(key, {
          ...edge,
          timestamps: [...(edge.timestamps || [])],
        });
      } else {
        // Merge: sum amounts and counts, concat timestamps
        edgeMap.set(key, {
          ...existing,
          total_amount: (existing.total_amount || 0) + (edge.total_amount || 0),
          txn_count: (existing.txn_count || 0) + (edge.txn_count || 0),
          timestamps: [...(existing.timestamps || []), ...(edge.timestamps || [])],
          // Keep the more suspicious pattern
          pattern: pickPattern(existing.pattern, edge.pattern),
        });
      }
    }
  }

  return {
    nodes: Array.from(nodeMap.values()),
    edges: Array.from(edgeMap.values()),
  };
}

function pickPattern(a, b) {
  const priority = { SMURFING: 3, CONSOLIDATION: 2, NORMAL: 1 };
  return (priority[a] || 0) >= (priority[b] || 0) ? a : b;
}

/* ── Main Component ── */

export default function NetworkOverview() {
  const [alerts, setAlerts] = useState([]);
  const [graphStats, setGraphStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState(null);

  const fetchData = useCallback(() => {
    setLoading(true);

    const alertsPromise = apiFetch('/api/v1/alerts?limit=100')
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        return data.alerts || [];
      })
      .catch(err => {
        console.error('[NetworkOverview] Failed to load alerts:', err);
        return [];
      });

    const statsPromise = apiFetch('/api/v1/graph/stats')
      .then(r => r.json())
      .then(body => body?.data || body)
      .catch(err => {
        console.error('[NetworkOverview] Failed to load graph stats:', err);
        return null;
      });

    Promise.all([alertsPromise, statsPromise]).then(([alertData, statsData]) => {
      setAlerts(alertData);
      setGraphStats(statsData);
      setLoading(false);
    });
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const { nodes, edges } = useMemo(() => aggregateGraphData(alerts), [alerts]);

  const stats = useMemo(() => ({
    totalAccounts: graphStats?.total_accounts ?? nodes.length,
    totalTransactions: graphStats?.total_transactions ?? edges.length,
    totalAlerts: graphStats?.total_alerts ?? alerts.length,
    clustersDetected: graphStats?.mule_clusters_detected ?? alerts.filter(
      a => a.severity === 'CRITICAL' || a.severity === 'HIGH'
    ).length,
  }), [graphStats, nodes.length, edges.length, alerts]);

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          letterSpacing: '1px',
          color: 'var(--text-muted)',
        }}>
          LOADING NETWORK TOPOLOGY...
        </span>
      </div>
    );
  }

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1440, margin: '0 auto' }}>

      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 24,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <h1 className="gradient-text" style={{
              fontFamily: 'var(--font-display)',
              fontSize: 26,
              fontWeight: 800,
              letterSpacing: '-0.5px',
              margin: 0,
            }}>
              Network Intelligence
            </h1>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              background: 'rgba(62,231,255,0.08)',
              border: '1px solid rgba(62,231,255,0.2)',
              borderRadius: 5,
              padding: '2px 8px',
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: 'var(--accent-cyan)',
                animation: 'emeraldPulse 2s ease-in-out infinite',
              }} />
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                color: 'var(--accent-cyan)',
                letterSpacing: '1px',
                textTransform: 'uppercase',
                fontWeight: 700,
              }}>Live</span>
            </div>
          </div>
          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--text-muted)',
            letterSpacing: '0.3px',
            margin: 0,
          }}>
            <span style={{ color: 'rgba(62,231,255,0.6)' }}>//</span>
            {' '}Transaction graph topology
            <span style={{ margin: '0 8px', color: 'var(--text-faint)' }}>·</span>
            Real-time cluster detection
          </p>
        </div>

        <button
          className="btn btn-ghost"
          onClick={fetchData}
          style={{ gap: 7, marginTop: 4 }}
        >
          <RefreshCw size={13} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.5px' }}>Refresh</span>
        </button>
      </motion.div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
        <StatCard
          label="Total Accounts"
          value={stats.totalAccounts}
          color="var(--accent-cyan)"
          icon={Users}
          index={0}
        />
        <StatCard
          label="Total Transactions"
          value={stats.totalTransactions.toLocaleString()}
          color="#FB923C"
          icon={ArrowRightLeft}
          index={1}
        />
        <StatCard
          label="Total Alerts"
          value={stats.totalAlerts}
          color="#F43F5E"
          icon={AlertTriangle}
          index={2}
        />
        <StatCard
          label="Clusters Detected"
          value={stats.clustersDetected}
          color="#10B981"
          icon={Share2}
          index={3}
        />
      </div>

      {/* Network Graph */}
      <AnimateIn delay={0.15}>
        <GlassCard
          padding={0}
          hover={false}
          style={{
            border: '1px solid var(--border)',
            borderRadius: 10,
            overflow: 'hidden',
            boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
          }}
        >
          {/* Graph header */}
          <div style={{
            padding: '12px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Share2 size={14} style={{ color: 'var(--accent-cyan)', opacity: 0.7 }} />
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-primary)',
                letterSpacing: '0.3px',
              }}>
                Combined Network Graph
              </span>
            </div>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-muted)',
              letterSpacing: '0.5px',
            }}>
              {nodes.length} nodes
              <span style={{ margin: '0 6px', color: 'var(--text-faint)' }}>·</span>
              {edges.length} edges
              <span style={{ margin: '0 6px', color: 'var(--text-faint)' }}>·</span>
              {alerts.length} alerts merged
            </span>
          </div>

          {/* Graph body */}
          {nodes.length === 0 ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '80px 40px',
              gap: 16,
              textAlign: 'center',
            }}>
              <div style={{
                width: 48, height: 48,
                borderRadius: '50%',
                background: 'rgba(62,231,255,0.08)',
                border: '1px solid rgba(62,231,255,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Share2 size={20} color="var(--accent-cyan)" />
              </div>
              <div>
                <p style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: 15,
                  fontWeight: 600,
                  color: 'var(--text-secondary)',
                  marginBottom: 4,
                }}>
                  No network data available
                </p>
                <p style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--text-muted)',
                  letterSpacing: '0.3px',
                }}>
                  // run detection pipeline to populate the graph
                </p>
              </div>
            </div>
          ) : (
            <>
              <NetworkGraph nodes={nodes} edges={edges} timeRange={timeRange} />
              <TimelineSlider edges={edges} onChange={setTimeRange} />
            </>
          )}
        </GlassCard>
      </AnimateIn>
    </div>
  );
}
