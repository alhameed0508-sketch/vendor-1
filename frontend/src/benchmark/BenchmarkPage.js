import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart2,
  CheckCircle,
  Database,
  Layers,
  Play,
  RefreshCw,
  Shield,
  Target,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiFetch } from '../auth/api';

const ACTIONS = [
  {
    id: 'synthetic',
    label: 'Synthetic',
    icon: Play,
    endpoint: '/api/v1/benchmark/synthetic',
    body: { num_clusters: 3, num_legit_accounts: 30 },
  },
  {
    id: 'adversarial',
    label: 'Adversarial',
    icon: Zap,
    endpoint: '/api/v1/benchmark/adversarial',
    body: { num_clusters: 3, num_legit: 30, num_adversarial: 20 },
  },
  {
    id: 'cross_validation',
    label: 'Cross-Validation',
    icon: Layers,
    endpoint: '/api/v1/benchmark/cross-validation',
    body: { num_clusters: 3, num_legit: 30, num_folds: 5 },
  },
  {
    id: 'comparison',
    label: 'Comparison',
    icon: BarChart2,
    endpoint: '/api/v1/benchmark/comparison',
    body: { cluster_counts: [3, 5, 8] },
  },
  {
    id: 'full_evaluation',
    label: 'Full Evaluation',
    icon: Target,
    endpoint: '/api/v1/benchmark/full-evaluation',
  },
];

const cardStyle = {
  borderTop: '1px solid var(--border)',
  padding: '20px 0',
};

async function readResponse(response) {
  const body = await response.json();
  if (!response.ok || body?.success === false) {
    throw new Error(
      body?.error?.message || body?.detail || `Request failed (${response.status})`
    );
  }
  return body?.data ?? body;
}

function unwrapSavedResult(record) {
  return record?.result ?? record;
}

export function summarizeBenchmark(result) {
  if (!result) return null;
  if (result.summary) return result.summary;

  if (result.benchmark_type === 'comparison' && result.benchmarks?.length) {
    const count = result.benchmarks.length;
    const average = key =>
      result.benchmarks.reduce((total, item) => total + (item[key] || 0), 0) / count;
    return {
      dataset_name: 'configuration comparison',
      precision: average('precision'),
      recall: average('recall'),
      f1_score: average('f1_score'),
      accuracy: average('accuracy'),
      total_accounts: result.benchmarks.reduce(
        (total, item) => total + (item.total_accounts || 0),
        0
      ),
      elapsed_seconds: result.benchmarks.reduce(
        (total, item) => total + (item.elapsed_seconds || 0),
        0
      ),
    };
  }

  if (result.num_folds) {
    return {
      dataset_name: result.dataset_name,
      precision: result.mean_precision,
      recall: result.mean_recall,
      f1_score: result.mean_f1,
      accuracy: result.mean_accuracy,
      elapsed_seconds: result.elapsed_seconds,
      total_accounts: result.fold_results?.reduce(
        (total, fold) => total + (fold.test_accounts || 0),
        0
      ),
    };
  }
  return result;
}

function MetricCard({ label, value, icon: Icon, detail }) {
  return (
    <div style={{ ...cardStyle, position: 'relative', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="eyebrow">{label}</span>
        <Icon size={14} color="var(--text-muted)" />
      </div>
      <div
        style={{
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-display)', fontStretch: 'var(--display-stretch)',
          fontSize: 28,
          fontWeight: 600,
          marginTop: 10,
        }}
      >
        {value}
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>
        {detail}
      </div>
    </div>
  );
}

function ResultsTable({ result }) {
  let rows = [];
  if (result?.benchmarks) {
    rows = result.benchmarks.map(item => ({
      name: item.config || item.dataset_name,
      ...item,
    }));
  } else if (result?.fold_results) {
    rows = result.fold_results.map(item => ({
      name: `Fold ${item.fold}`,
      ...item,
    }));
  } else if (result?.standard) {
    rows = [
      { name: 'Standard', ...result.standard },
      { name: 'Adversarial', ...result.adversarial },
      {
        name: 'Cross-validation mean',
        precision: result.cross_validation?.mean_precision,
        recall: result.cross_validation?.mean_recall,
        f1_score: result.cross_validation?.mean_f1,
        accuracy: result.cross_validation?.mean_accuracy,
      },
    ];
  }
  if (!rows.length) return null;

  return (
    <div style={{ ...cardStyle, overflowX: 'auto' }}>
      <div className="eyebrow" style={{ marginBottom: 14 }}>
        Run breakdown
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>
            {['Evaluation', 'Precision', 'Recall', 'F1', 'Accuracy'].map(label => (
              <th
                key={label}
                style={{
                  textAlign: label === 'Evaluation' ? 'left' : 'right',
                  color: 'var(--text-muted)',
                  padding: '8px 10px',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.name}>
              <td style={{ padding: 10, color: 'var(--text-primary)' }}>{row.name}</td>
              {[row.precision, row.recall, row.f1_score, row.accuracy].map(
                (value, index) => (
                  <td
                    key={index}
                    style={{
                      padding: 10,
                      textAlign: 'right',
                      color: 'var(--text-secondary)',
                      fontFamily: 'var(--font-sans)',
                    }}
                  >
                    {Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—'}
                  </td>
                )
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BenchmarkPage() {
  const [capabilities, setCapabilities] = useState(null);
  const [savedResults, setSavedResults] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(null);

  const loadState = async () => {
    const [capabilityData, historyData] = await Promise.all([
      apiFetch('/api/v1/benchmark/capabilities').then(readResponse),
      apiFetch('/api/v1/benchmark/results').then(readResponse),
    ]);
    const history = historyData?.results || [];
    setCapabilities(capabilityData);
    setSavedResults(history);
    if (!results && history.length) {
      setResults(unwrapSavedResult(history[history.length - 1]));
    }
  };

  useEffect(() => {
    loadState()
      .catch(error => toast.error(`Could not load benchmarks: ${error.message}`))
      .finally(() => setLoading(false));
  }, []);

  const summary = useMemo(() => summarizeBenchmark(results), [results]);

  const runBenchmark = async action => {
    setRunning(action.id);
    try {
      const options = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      };
      if (action.body) options.body = JSON.stringify(action.body);
      const data = await apiFetch(action.endpoint, options).then(readResponse);
      setResults(data);
      const history = await apiFetch('/api/v1/benchmark/results').then(readResponse);
      setSavedResults(history?.results || []);
      toast.success(`${action.label} benchmark completed`);
    } catch (error) {
      toast.error(`Benchmark failed: ${error.message}`);
    } finally {
      setRunning(null);
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        <span>Loading benchmarks…</span>
      </div>
    );
  }

  const executionEnabled = capabilities?.execution_enabled === true;
  const percentage = value =>
    Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—';

  return (
    <div className="page">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ marginBottom: 28 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h1 className="text-page-title" style={{ margin: 0 }}>
            Model Benchmarks
          </h1>
          <span className="status-badge">Evaluation</span>
        </div>
        <p style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-sans)' }}>
          Run detection benchmarks: precision and recall, adversarial tests and
          repeatable cross-validation.
        </p>
      </motion.div>

      {!executionEnabled && (
        <div
          role="alert"
          style={{
            ...cardStyle,
            borderColor: 'var(--high)',
            color: 'var(--text-secondary)',
            marginBottom: 18,
          }}
        >
          <Shield size={15} color="var(--high)" style={{ marginRight: 8 }} />
          {capabilities?.restriction ||
            'Synthetic benchmarks are unavailable in this environment.'}
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        {ACTIONS.map(action => {
          const Icon = action.icon;
          const isRunning = running === action.id;
          return (
            <button
              key={action.id}
              type="button"
              onClick={() => runBenchmark(action)}
              disabled={!executionEnabled || running !== null}
              aria-label={`Run ${action.label} benchmark`}
              style={{
                padding: '9px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'transparent',
                color: 'var(--text-primary)',
                cursor: executionEnabled && !running ? 'pointer' : 'not-allowed',
                opacity: executionEnabled && (!running || isRunning) ? 1 : 0.5,
              }}
            >
              {isRunning ? <RefreshCw size={13} className="spinning" /> : <Icon size={13} />}
              {isRunning ? 'Running…' : action.label}
            </button>
          );
        })}
      </div>

      {summary ? (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 14,
              marginBottom: 18,
            }}
          >
            <MetricCard
              label="Precision"
              value={percentage(summary.precision)}
              icon={Target}
              detail="flagged accounts confirmed by labels"
            />
            <MetricCard
              label="Recall"
              value={percentage(summary.recall)}
              icon={Zap}
              detail="labelled mule accounts detected"
            />
            <MetricCard
              label="F1 score"
              value={percentage(summary.f1_score)}
              icon={CheckCircle}
              detail="precision/recall balance"
            />
            <MetricCard
              label="Accuracy"
              value={percentage(summary.accuracy)}
              icon={Shield}
              detail="overall account classification"
            />
          </div>

          <ResultsTable result={results} />

          <div style={{ ...cardStyle, marginTop: 18 }}>
            <div className="eyebrow" style={{ marginBottom: 12 }}>
              Execution evidence
            </div>
            <div style={{ display: 'flex', gap: 30, flexWrap: 'wrap' }}>
              {[
                ['Dataset', summary.dataset_name],
                ['Accounts', summary.total_accounts],
                ['Transactions', summary.total_transactions],
                ['Alerts', summary.alerts_generated],
                [
                  'Elapsed',
                  Number.isFinite(summary.elapsed_seconds)
                    ? `${summary.elapsed_seconds.toFixed(3)}s`
                    : null,
                ],
                ['Saved runs', savedResults.length],
              ]
                .filter(([, value]) => value !== undefined && value !== null)
                .map(([label, value]) => (
                  <div key={label}>
                    <div className="eyebrow">{label}</div>
                    <div
                      style={{
                        color: 'var(--text-primary)',
                        marginTop: 5,
                        fontFamily: 'var(--font-sans)',
                      }}
                    >
                      {value}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </>
      ) : (
        <div style={{ ...cardStyle, textAlign: 'center', padding: 56 }}>
          <Database size={38} color="var(--text-muted)" />
          <p style={{ color: 'var(--text-secondary)' }}>No benchmark result selected.</p>
          <small style={{ color: 'var(--text-muted)' }}>
            Run one of the enabled evaluation programs above.
          </small>
        </div>
      )}

      <p
        style={{
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-sans)',
          fontSize: 12,
          marginTop: 16,
        }}
      >
        Synthetic results validate software behaviour; they are not evidence of
        production model effectiveness on bank customer data.
      </p>
    </div>
  );
}
