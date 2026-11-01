import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, Users, ArrowRightLeft, AlertTriangle, Share2, X } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { apiFetch } from '../auth/api';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import IndiaMap from '../components/IndiaMap';
import RegionalStatsPanel from './RegionalStatsPanel';
import NetworkGraph from '../graph_viz/NetworkGraph';
import TimelineSlider from '../graph_viz/TimelineSlider';
import useAlertStream from '../hooks/useAlertStream';
import StatCard from '../components/StatCard';
import { CITY_COORDS, CITY_TO_STATE } from '../constants/cities';
import { API_ALERTS_LIMIT } from '../config';

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
        edgeMap.set(key, {
          ...existing,
          total_amount: (existing.total_amount || 0) + (edge.total_amount || 0),
          txn_count: (existing.txn_count || 0) + (edge.txn_count || 0),
          timestamps: [...(existing.timestamps || []), ...(edge.timestamps || [])],
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

/** Aggregate per-city alert/severity stats from alerts array */
function aggregateCityData(alerts) {
  const cities = {};

  for (const alert of alerts) {
    const nodes = alert.nodes || [];
    const severity = alert.severity || 'MEDIUM';
    const volume = (alert.edges || []).reduce((s, e) => s + (e.total_amount || 0), 0);

    // Track which accounts we've already counted for this alert
    const seenAccounts = new Set();

    for (const node of nodes) {
      const city = node.city;
      if (!city || !CITY_COORDS[city]) continue;

      if (!cities[city]) {
        cities[city] = {
          name: city,
          coords: CITY_COORDS[city],
          alertCount: 0,
          criticalCount: 0,
          highCount: 0,
          mediumCount: 0,
          accountCount: 0,
          totalVolume: 0,
          roles: new Set(),
          _alertIds: new Set(),
        };
      }

      const c = cities[city];

      // Count unique accounts
      if (!seenAccounts.has(node.account_id)) {
        seenAccounts.add(node.account_id);
        c.accountCount += 1;
      }
      c.roles.add(node.role);

      // Count this alert once per city
      const alertId = alert.alert_id || alert.id || JSON.stringify({ s: alert.severity, n: nodes.length });
      if (!c._alertIds.has(alertId)) {
        c._alertIds.add(alertId);
        c.alertCount += 1;
        if (severity === 'CRITICAL') c.criticalCount += 1;
        else if (severity === 'HIGH') c.highCount += 1;
        else c.mediumCount += 1;
        c.totalVolume += volume;
      }
    }
  }

  // Clean up internal tracking field and sort by alertCount desc
  return Object.values(cities)
    .map(({ _alertIds, ...rest }) => rest)
    .sort((a, b) => b.alertCount - a.alertCount);
}

/* ── Main Component ── */

export default function NetworkOverview() {
  const [alerts, setAlerts] = useState([]);
  const [graphStats, setGraphStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState(null);
  const [selectedCity, setSelectedCity] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(Date.now());

  const fetchData = useCallback(() => {
    setLoading(true);

    const alertsPromise = apiFetch(`/api/v1/alerts?limit=${API_ALERTS_LIMIT}`)
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
      setLastUpdated(Date.now());
    });
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // SSE live updates
  const { connected } = useAlertStream({
    enabled: true,
    onNewAlerts: useCallback(() => {
      setLastUpdated(Date.now());
      fetchData();
    }, [fetchData]),
  });

  const { nodes, edges } = useMemo(() => aggregateGraphData(alerts), [alerts]);

  const stats = useMemo(() => ({
    totalAccounts: graphStats?.total_accounts ?? nodes.length,
    totalTransactions: graphStats?.total_transactions ?? edges.length,
    totalAlerts: graphStats?.total_alerts ?? alerts.length,
    clustersDetected: graphStats?.mule_clusters_detected ?? alerts.filter(
      a => a.severity === 'CRITICAL' || a.severity === 'HIGH'
    ).length,
  }), [graphStats, nodes.length, edges.length, alerts]);

  // City-level aggregation for map + stats panel
  const cityData = useMemo(() => aggregateCityData(alerts), [alerts]);

  // State-level alert counts for heatmap coloring
  const stateAlertCounts = useMemo(() => {
    const counts = {};
    for (const city of cityData) {
      const state = CITY_TO_STATE[city.name];
      if (state) {
        counts[state] = (counts[state] || 0) + city.alertCount;
      }
    }
    return counts;
  }, [cityData]);

  // Filter nodes/edges when a city is selected
  const filteredData = useMemo(() => {
    if (!selectedCity) return { nodes, edges };

    const cityNodeIds = new Set(
      nodes.filter(n => n.city === selectedCity).map(n => n.account_id)
    );

    const filteredNodes = nodes.filter(n => cityNodeIds.has(n.account_id));
    const filteredEdges = edges.filter(
      e => cityNodeIds.has(e.from_account) || cityNodeIds.has(e.to_account)
    );

    return { nodes: filteredNodes, edges: filteredEdges };
  }, [selectedCity, nodes, edges]);

  // Handle city click — toggle selection
  const handleCityClick = useCallback((cityName) => {
    setSelectedCity(prev => prev === cityName ? null : cityName);
  }, []);

  // "Updated X ago" text
  const updatedAgo = useMemo(() => {
    try {
      return formatDistanceToNow(lastUpdated, { addSuffix: true });
    } catch {
      return '';
    }
  }, [lastUpdated]);

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        <span style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 12,
          color: 'var(--text-muted)',
        }}>
          LOADING NETWORK TOPOLOGY...
        </span>
      </div>
    );
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1440, margin: '0 auto' }}>

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
            <h1 className="text-page-title" style={{ fontSize: 26, margin: 0 }}>
              Network Intelligence
            </h1>

            {/* LIVE / OFFLINE badge */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              background: connected ? 'rgba(16,185,129,0.08)' : 'rgba(156,163,175,0.08)',
              border: `1px solid ${connected ? 'rgba(16,185,129,0.25)' : 'rgba(156,163,175,0.2)'}`,
              borderRadius: 5,
              padding: '2px 8px',
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: connected ? '#10B981' : '#9CA3AF',
                animation: connected ? 'emeraldPulse 2s ease-in-out infinite' : 'none',
              }} />
              <span style={{
                fontFamily: 'var(--font-sans)',
                fontSize: 12,
                color: connected ? '#10B981' : '#9CA3AF',
                fontWeight: 700,
              }}>{connected ? 'Live' : 'Offline'}</span>
            </div>
          </div>

          <p style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            color: 'var(--text-muted)',
            letterSpacing: '0.3px',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            
            Transaction graph topology
            <span style={{ color: 'var(--text-faint)' }}>·</span>
            Real-time cluster detection
            {updatedAgo && (
              <>
                <span style={{ color: 'var(--text-faint)' }}>·</span>
                <span style={{ color: 'var(--text-faint)' }}>Updated {updatedAgo}</span>
              </>
            )}
          </p>
        </div>

        <button
          className="btn btn-ghost"
          onClick={fetchData}
          style={{ gap: 7, marginTop: 4 }}
        >
          <RefreshCw size={13} />
          <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, }}>Refresh</span>
        </button>
      </motion.div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
        <StatCard label="Total Accounts"      value={stats.totalAccounts}                   color="var(--accent-cyan)" icon={Users} />
        <StatCard label="Total Transactions"  value={stats.totalTransactions.toLocaleString()} color="#FB923C"          icon={ArrowRightLeft} />
        <StatCard label="Total Alerts"        value={stats.totalAlerts}                     color="#F43F5E"            icon={AlertTriangle} />
        <StatCard label="Clusters Detected"   value={stats.clustersDetected}                color="#10B981"            icon={Share2} />
      </div>

      {/* Map + Regional Stats Row */}
      <AnimateIn delay={0.1}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 3fr) minmax(0, 2fr)',
          gap: 16,
          marginBottom: 24,
        }}
          className="network-map-grid"
        >
          <IndiaMap
            nodes={nodes}
            edges={edges}
            onCityClick={handleCityClick}
            selectedCity={selectedCity}
            stateAlertCounts={stateAlertCounts}
          />
          <RegionalStatsPanel
            cityData={cityData}
            selectedCity={selectedCity}
            onCityClick={handleCityClick}
          />
        </div>
      </AnimateIn>

      {/* Network Graph */}
      <AnimateIn delay={0.2}>
        <GlassCard
          padding={0}
          hover={false}
          style={{
            border: '1px solid var(--border)',
            borderRadius: 10,
            overflow: 'hidden',
            boxShadow: '0 4px 20px rgba(0,0,0,0.25)',
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
                fontFamily: 'var(--font-sans)',
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-primary)',
                letterSpacing: '0.3px',
              }}>
                {selectedCity ? `Network Graph — ${selectedCity}` : 'Combined Network Graph'}
              </span>
              {selectedCity && (
                <button
                  className="btn btn-ghost"
                  onClick={() => setSelectedCity(null)}
                  style={{ padding: '2px 8px', fontSize: 12, gap: 4 }}
                >
                  <X size={10} />
                  <span style={{ fontFamily: 'var(--font-sans)', }}>Clear Filter</span>
                </button>
              )}
            </div>
            <span style={{
              fontFamily: 'var(--font-sans)',
              fontSize: 12,
              color: 'var(--text-muted)',
              }}>
              {filteredData.nodes.length} nodes
              <span style={{ margin: '0 6px', color: 'var(--text-faint)' }}>·</span>
              {filteredData.edges.length} edges
              <span style={{ margin: '0 6px', color: 'var(--text-faint)' }}>·</span>
              {alerts.length} alerts merged
            </span>
          </div>

          {/* Graph body */}
          {filteredData.nodes.length === 0 ? (
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
                  {selectedCity
                    ? `No network data for ${selectedCity}`
                    : 'No network data available'}
                </p>
                <p style={{
                  fontFamily: 'var(--font-sans)',
                  fontSize: 12,
                  color: 'var(--text-muted)',
                  letterSpacing: '0.3px',
                }}>
                  {selectedCity
                    ? 'Try selecting a different city or clear the filter'
                    : 'Run detection pipeline to populate the graph'}
                </p>
              </div>
              {selectedCity && (
                <button
                  className="btn btn-ghost"
                  onClick={() => setSelectedCity(null)}
                  style={{ marginTop: 8 }}
                >
                  Clear Filter
                </button>
              )}
            </div>
          ) : (
            <>
              <NetworkGraph
                nodes={filteredData.nodes}
                edges={filteredData.edges}
                timeRange={timeRange}
              />
              <TimelineSlider edges={filteredData.edges} onChange={setTimeRange} />
            </>
          )}
        </GlassCard>
      </AnimateIn>

      {/* Responsive CSS */}
      <style>{`
        @media (max-width: 1024px) {
          .network-map-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
