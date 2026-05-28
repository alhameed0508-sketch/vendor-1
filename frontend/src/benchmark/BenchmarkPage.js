import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend,
} from 'recharts';
import { Play, BarChart2, Zap, Shield, RefreshCw, CheckCircle, Target, Layers } from 'lucide-react';
import { toast } from 'sonner';
import { apiFetch } from '../auth/api';

const cardStyle = {
  background: 'rgba(12, 18, 32, 0.65)',
  border: '1px solid rgba(255,255,255,0.07)',
  borderRadius: 12,
  padding: '22px 24px',
  position: 'relative',
  overflow: 'hidden',
  boxShadow: '0 4px 20px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
};

const chartTooltipStyle = {
  background: 'rgba(8, 12, 20, 0.95)',
  border: '1px solid rgba(99,102,241,0.25)',
  borderRadius: 6,
  padding: '10px 14px',
  boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={chartTooltipStyle}>
      <p style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#4A5568', marginBottom: 6, letterSpacing: '1px', textTransform: 'uppercase' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: p.color, margin: 0, fontWeight: 600 }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(3) : p.value}
        </p>
      ))}
    </div>
  );
};

function MetricCard({ label, value, color, icon: Icon, sub, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35 }}
      style={cardStyle}
      whileHover={{ borderColor: `${color}30`, boxShadow: `0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px ${color}18`, y: -2, transition: { duration: 0.2 } }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${color}, transparent)`, opacity: 0.7 }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700 }}>{label}</div>
        {Icon && <div style={{ color, opacity: 0.5 }}><Icon size={13} /></div>}
      </div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 700, color, letterSpacing: '-0.5px', lineHeight: 1, marginBottom: sub ? 6 : 0 }}>{value}</div>
      {sub && <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.3px' }}>{sub}</div>}
    </motion.div>
  );
}

function ChartPanel({ title, children }) {
  return (
    <div style={cardStyle}>
      <p style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#4A5568', textTransform: 'uppercase', letterSpacing: '1.5px', fontWeight: 700, marginBottom: 18 }}>// {title}</p>
      {children}
    </div>
  );
}

export default function BenchmarkPage() {
  const [results, setResults] = useState(null);
  const [savedResults, setSavedResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(null);

  useEffect(() => {
    apiFetch('/api/v1/benchmark/results')
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setSavedResults(data?.results || []);
        if (data?.results?.length > 0) {
          setResults(data.results[data.results.length - 1]);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const runBenchmark = async (type) => {
    setRunning(type);
    try {
      let endpoint, method, bodyData;
      switch (type) {
        case 'synthetic':
          endpoint = '/api/v1/benchmark/synthetic';
          method = 'POST';
          bodyData = JSON.stringify({ num_clusters: 3, num_legit_accounts: 30 });
          break;
        case 'adversarial':
          endpoint = '/api/v1/benchmark/adversarial';
          method = 'POST';
          bodyData = JSON.stringify({ num_clusters: 3, num_legit: 30, num_adversarial: 20 });
          break;
        case 'cross-val':
          endpoint = '/api/v1/benchmark/cross-validation';
          method = 'POST';
          bodyData = JSON.stringify({ num_clusters: 3, num_legit: 30, num_folds: 5 });
          break;
        case 'full':
          endpoint = '/api/v1/benchmark/full-evaluation';
          method = 'GET';
          break;
        case 'comparison':
          endpoint = '/api/v1/benchmark/comparison';
          method = 'GET';
          break;
        default:
          return;
      }

      const opts = { method, headers: { 'Content-Type': 'application/json' } };
      if (bodyData) opts.body = bodyData;

      const res = await apiFetch(endpoint, opts);
      const body = await res.json();
      const data = body?.data || body;
      setResults(data);
      toast.success(`${type} benchmark completed`);
    } catch (err) {
      toast.error(`Benchmark failed: ${err.message || 'Unknown error'}`);
    } finally {
      setRunning(null);
    }
  };

  const precision = results?.precision ?? results?.metrics?.precision ?? 0;
  const recall = results?.recall ?? results?.metrics?.recall ?? 0;
  const f1 = results?.f1_score ?? results?.metrics?.f1_score ?? 0;
  const accuracy = results?.accuracy ?? results?.metrics?.accuracy ?? 0;

  const radarData = results ? [
    { metric: 'Precision', value: precision * 100 },
    { metric: 'Recall', value: recall * 100 },
    { metric: 'F1 Score', value: f1 * 100 },
    { metric: 'Accuracy', value: accuracy * 100 },
  ] : [];

  const comparisonData = results?.benchmarks ? results.benchmarks.map((b, i) => ({
    name: b.config || `Config ${i + 1}`,
    precision: (b.precision ?? b.metrics?.precision ?? 0) * 100,
    recall: (b.recall ?? b.metrics?.recall ?? 0) * 100,
    f1: (b.f1_score ?? b.metrics?.f1_score ?? 0) * 100,
  })) : [];

  if (loading) return (
    <div className="loading">
      <div className="spinner" />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, letterSpacing: '1px', color: '#4A5568' }}>LOADING BENCHMARKS...</span>
    </div>
  );

  return (
    <div style={{ padding: '32px 36px', maxWidth: 1440, margin: '0 auto' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
          <h1 className="gradient-text" style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.5px', margin: 0 }}>Model Benchmarks</h1>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 10, color: '#22D3EE', letterSpacing: '1.5px', textTransform: 'uppercase',
            background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.2)', padding: '2px 8px', borderRadius: 4,
          }}>EVALUATION</span>
        </div>
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4A5568', letterSpacing: '0.5px' }}>
          // detection pipeline benchmarks · precision/recall · adversarial testing · cross-validation
        </p>
      </motion.div>

      {/* Benchmark Action Buttons */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        {[
          { id: 'synthetic', label: 'Synthetic', icon: Play, color: '#6366F1' },
          { id: 'adversarial', label: 'Adversarial', icon: Zap, color: '#F43F5E' },
          { id: 'cross-val', label: 'Cross-Validation', icon: Layers, color: '#FB923C' },
          { id: 'comparison', label: 'Comparison', icon: BarChart2, color: '#22D3EE' },
          { id: 'full', label: 'Full Evaluation', icon: Target, color: '#10B981' },
        ].map(btn => (
          <motion.button
            key={btn.id}
            onClick={() => runBenchmark(btn.id)}
            disabled={running !== null}
            className="btn"
            style={{
              padding: '8px 16px', fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
              background: `${btn.color}15`, border: `1px solid ${btn.color}30`, color: btn.color, borderRadius: 8,
              cursor: running ? 'wait' : 'pointer', opacity: running && running !== btn.id ? 0.5 : 1,
            }}
            whileHover={!running ? { scale: 1.02 } : {}}
            whileTap={!running ? { scale: 0.98 } : {}}
          >
            {running === btn.id ? <RefreshCw size={12} className="spinning" /> : <btn.icon size={12} />}
            {running === btn.id ? 'Running...' : btn.label}
          </motion.button>
        ))}
      </div>

      {/* Results Metrics */}
      {results && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
            <MetricCard label="Precision" value={`${(precision * 100).toFixed(1)}%`} color="#6366F1" icon={Target} sub="true positive rate" index={0} />
            <MetricCard label="Recall" value={`${(recall * 100).toFixed(1)}%`} color="#22D3EE" icon={Zap} sub="detection coverage" index={1} />
            <MetricCard label="F1 Score" value={`${(f1 * 100).toFixed(1)}%`} color="#10B981" icon={CheckCircle} sub="harmonic mean" index={2} />
            <MetricCard label="Accuracy" value={`${(accuracy * 100).toFixed(1)}%`} color="#FB923C" icon={Shield} sub="overall correctness" index={3} />
          </div>

          {/* Charts */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            <ChartPanel title="Model Performance Radar">
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="rgba(255,255,255,0.08)" />
                  <PolarAngleAxis dataKey="metric" tick={{ fill: '#94A3B8', fontSize: 11, fontFamily: 'var(--font-mono)' }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#4A5568', fontSize: 10 }} />
                  <Radar name="Score" dataKey="value" stroke="#6366F1" fill="#6366F1" fillOpacity={0.2} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </ChartPanel>

            {comparisonData.length > 0 ? (
              <ChartPanel title="Configuration Comparison">
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={comparisonData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="name" tick={{ fill: '#4A5568', fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#4A5568', fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} domain={[0, 100]} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontFamily: 'var(--font-mono)', fontSize: 11 }} />
                    <Bar dataKey="precision" name="Precision" fill="#6366F1" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="recall" name="Recall" fill="#22D3EE" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="f1" name="F1" fill="#10B981" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartPanel>
            ) : (
              <ChartPanel title="Confusion Matrix">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  {[
                    { label: 'True Positives', value: results.true_positives ?? results.confusion_matrix?.tp ?? '—', color: '#10B981' },
                    { label: 'False Positives', value: results.false_positives ?? results.confusion_matrix?.fp ?? '—', color: '#FB923C' },
                    { label: 'False Negatives', value: results.false_negatives ?? results.confusion_matrix?.fn ?? '—', color: '#F43F5E' },
                    { label: 'True Negatives', value: results.true_negatives ?? results.confusion_matrix?.tn ?? '—', color: '#22D3EE' },
                  ].map(cell => (
                    <div key={cell.label} style={{
                      background: `${cell.color}08`, border: `1px solid ${cell.color}20`, borderRadius: 8, padding: '16px', textAlign: 'center',
                    }}>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 28, fontWeight: 700, color: cell.color, lineHeight: 1, marginBottom: 6 }}>{cell.value}</div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.5px' }}>{cell.label}</div>
                    </div>
                  ))}
                </div>
              </ChartPanel>
            )}
          </div>

          {/* Additional Details */}
          {(results.detection_time_ms || results.total_accounts || results.mules_detected) && (
            <div style={{ ...cardStyle, marginBottom: 16 }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 16, fontWeight: 700 }}>// Run Details</div>
              <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
                {[
                  { label: 'Detection Time', value: results.detection_time_ms ? `${results.detection_time_ms}ms` : null },
                  { label: 'Total Accounts', value: results.total_accounts },
                  { label: 'Mules Detected', value: results.mules_detected },
                  { label: 'Clusters Found', value: results.clusters_found ?? results.num_clusters },
                  { label: 'Dataset', value: results.dataset_type },
                ].filter(d => d.value != null).map(d => (
                  <div key={d.label}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.5px', marginBottom: 4 }}>{d.label}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>{d.value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* No Results */}
      {!results && (
        <div style={{ ...cardStyle, textAlign: 'center', padding: '60px 40px' }}>
          <BarChart2 size={40} color="#4A5568" style={{ marginBottom: 16 }} />
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: 'var(--text-muted)', marginBottom: 8 }}>No benchmark results yet</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4A5568' }}>Run a benchmark to evaluate the detection pipeline</div>
        </div>
      )}
    </div>
  );
}

