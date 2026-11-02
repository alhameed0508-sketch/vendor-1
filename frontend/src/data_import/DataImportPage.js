import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Upload, FileText, AlertTriangle, CheckCircle, Database,
  BarChart2, Users, ArrowRight, RefreshCw, XCircle
} from 'lucide-react';
import { toast } from 'sonner';
import { apiFetch } from '../auth/api';
import { MAX_UPLOAD_SIZE_BYTES } from '../config';
import StatCard from '../components/StatCard';

const cardStyle = {
  borderTop: '1px solid var(--border)',
  padding: '20px 0',
  position: 'relative',
};

function SeverityBadge({ severity, count }) {
  const colorMap = {
    CRITICAL: 'var(--critical)',
    HIGH: 'var(--high)',
    MEDIUM: 'var(--medium)',
    LOW: 'var(--accent)',
  };
  const color = colorMap[severity] || 'var(--text-muted)';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '6px 12px', borderRadius: 6,
      background: `${color}12`, border: `1px solid ${color}25`,
    }}>
      <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, fontWeight: 700, color, }}>
        {severity}
      </span>
      <span style={{ fontFamily: 'var(--font-sans)', fontSize: 14, fontWeight: 700, color }}>
        {count}
      </span>
    </div>
  );
}

export default function DataImportPage() {
  const navigate = useNavigate();
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

  // Load existing preview on mount
  useEffect(() => {
    apiFetch('/api/v1/csv-upload/preview')
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        if (data?.loaded) {
          setUploadResult({
            accounts: data.accounts,
            transactions: data.transactions,
            alerts_generated: data.alerts,
            channels: data.channels,
            severity_counts: data.severity_counts,
            account_summaries: data.account_summaries || [],
          });
        }
      })
      .catch(() => {});
  }, []);

  const validateFile = useCallback((file) => {
    if (!file) return 'No file selected';
    if (!file.name.toLowerCase().endsWith('.csv')) return 'Only .csv files are accepted';
    if (file.size > MAX_UPLOAD_SIZE_BYTES) return 'File exceeds 50MB limit';
    return null;
  }, []);

  const handleUpload = useCallback(async (file) => {
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    setSelectedFile(file);
    setUploading(true);
    setError(null);
    setUploadResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await apiFetch('/api/v1/csv-upload/upload', {
        method: 'POST',
        body: formData,
      });

      const body = await res.json();

      if (!res.ok || !body.success) {
        const errMsg = body?.error?.message || 'Upload failed';
        setError(errMsg);
        toast.error(errMsg);
        return;
      }

      const data = body.data;
      setUploadResult(data);
      toast.success(`Processed ${data.transactions} transactions across ${data.accounts} accounts. ${data.alerts_generated} alerts generated.`);
    } catch (err) {
      const msg = err.message || 'Upload failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  }, [validateFile]);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) handleUpload(file);
  }, [handleUpload]);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  }, [handleUpload]);

  return (
    <div className="page">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        style={{ marginBottom: 28 }}
      >
        <h1 style={{
          fontFamily: 'var(--font-display)', fontStretch: 'var(--display-stretch)', fontSize: 22, fontWeight: 700,
          color: 'var(--text-primary)', letterSpacing: '-0.3px', marginBottom: 4,
        }}>
          Data Import
        </h1>
        <p style={{
          fontFamily: 'var(--font-sans)', fontSize: 12,
          color: 'var(--text-muted)', letterSpacing: '0.3px',
        }}>
          Upload CBS mule account data for detection pipeline analysis
        </p>
      </motion.div>

      {/* Section A: Upload Zone */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05, duration: 0.35 }}
        style={{ ...cardStyle, marginBottom: 24 }}
      >

        <div style={{
          fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)',
          fontWeight: 700, marginBottom: 16,
        }}>
          Upload File
        </div>

        {/* Drop zone */}
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          style={{
            border: `2px dashed ${dragActive ? 'var(--accent)' : 'var(--border)'}`,
            borderRadius: 10,
            padding: '40px 24px',
            textAlign: 'center',
            cursor: 'pointer',
            background: dragActive ? 'color-mix(in srgb, var(--accent) 4%, transparent)' : 'transparent',
            transition: 'all 0.2s ease',
          }}
          onClick={() => document.getElementById('csv-file-input')?.click()}
        >
          <input
            id="csv-file-input"
            type="file"
            accept=".csv"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          {uploading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              >
                <RefreshCw size={28} color="var(--accent)" />
              </motion.div>
              <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--accent)' }}>
                Processing {selectedFile?.name}...
              </span>
              <div style={{
                width: 200, height: 3, borderRadius: 2,
                background: 'var(--border)', overflow: 'hidden',
              }}>
                <motion.div
                  initial={{ width: '0%' }}
                  animate={{ width: '100%' }}
                  transition={{ duration: 8, ease: 'linear' }}
                  style={{ height: '100%', background: 'var(--accent)', borderRadius: 2 }}
                />
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
              <Upload size={28} color={dragActive ? 'var(--accent)' : 'var(--text-muted)'} />
              <div>
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--text-primary)' }}>
                  Drop CSV file here or{' '}
                </span>
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--accent)', fontWeight: 600 }}>
                  browse
                </span>
              </div>
              <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-faint)' }}>
                Pipe-delimited CBS format (.csv, max 50MB)
              </span>
            </div>
          )}
        </div>

        {/* Error display */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              style={{
                marginTop: 12, padding: '10px 14px', borderRadius: 6,
                background: 'color-mix(in srgb, var(--critical) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--critical) 20%, transparent)',
                display: 'flex', alignItems: 'center', gap: 8,
              }}
            >
              <XCircle size={14} color="var(--critical)" />
              <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--critical)' }}>
                {error}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Section B: Data Preview (shown after upload) */}
      <AnimatePresence>
        {uploadResult && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.4 }}
          >
            {/* Summary stat cards */}
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 14, marginBottom: 24,
            }}>
              <StatCard label="Accounts" value={uploadResult.accounts} icon={Users} index={0} />
              <StatCard label="Transactions" value={uploadResult.transactions} icon={Database} index={1} />
              <StatCard label="Alerts Generated" value={uploadResult.alerts_generated} icon={AlertTriangle} index={2} />
              <StatCard label="Channels" value={Object.keys(uploadResult.channels || {}).length} icon={BarChart2} index={3} />
            </div>

            {uploadResult.data_quality && (
              <div style={{ ...cardStyle, marginBottom: 24 }}>
                <div style={{
                  fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)',
                  fontWeight: 700, marginBottom: 14,
                }}>
                  Data Quality & Linkage
                </div>
                <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', marginBottom: 14 }}>
                  {[
                    ['Source rows', uploadResult.data_quality.source_rows],
                    ['Internal links', uploadResult.data_quality.internal_links],
                    ['Linkage', uploadResult.data_quality.linkage_strategy],
                    ['Confidence', uploadResult.data_quality.linkage_confidence],
                    ['Distinct times', uploadResult.data_quality.distinct_timestamps],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <div style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-faint)', }}>{label}</div>
                      <div style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-primary)', marginTop: 4 }}>{value}</div>
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {(uploadResult.data_quality.warnings || []).map(warning => (
                    <span key={warning} style={{
                      padding: '4px 8px', borderRadius: 4,
                      border: '1px solid color-mix(in srgb, var(--high) 25%, transparent)',
                      background: 'color-mix(in srgb, var(--high) 7%, transparent)',
                      color: 'var(--high)', fontFamily: 'var(--font-sans)', fontSize: 12,
                    }}>
                      {warning.replaceAll('_', ' ')}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Channel breakdown + date range */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 24 }}>
              {/* Channels */}
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                style={cardStyle}
              >
                <div style={{
                  fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)',
                  fontWeight: 700, marginBottom: 14,
                }}>
                  Channel Breakdown
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {Object.entries(uploadResult.channels || {}).map(([ch, count]) => (
                    <div key={ch} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-primary)' }}>{ch}</span>
                      <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>{count}</span>
                    </div>
                  ))}
                </div>
              </motion.div>

              {/* Anomaly flags or severity */}
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.35 }}
                style={cardStyle}
              >
                <div style={{
                  fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)',
                  fontWeight: 700, marginBottom: 14,
                }}>
                  Anomaly Flags
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {(uploadResult.anomaly_flags || []).length === 0 ? (
                    <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-faint)' }}>
                      No pre-processing anomalies detected
                    </span>
                  ) : (
                    (uploadResult.anomaly_flags || []).slice(0, 8).map((flag, i) => (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '4px 8px', borderRadius: 4,
                        background: 'color-mix(in srgb, var(--high) 6%, transparent)',
                      }}>
                        <AlertTriangle size={11} color="var(--high)" />
                        <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-primary)' }}>
                          {flag.flag}
                        </span>
                        <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-faint)', marginLeft: 'auto' }}>
                          {flag.account_id?.slice(0, 8)}...
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </motion.div>
            </div>

            {/* Account summary table */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              style={{ ...cardStyle, marginBottom: 24 }}
            >
              <div style={{
                fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)',
                fontWeight: 700, marginBottom: 14,
              }}>
                Account Summaries
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-sans)', fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      {['Account', 'CIF', 'Age (days)', 'Balance', 'Debits', 'Credits', 'Avg Txn', 'KYC'].map(h => (
                        <th key={h} style={{
                          textAlign: 'left', padding: '8px 10px',
                          color: 'var(--text-faint)', fontSize: 12, fontWeight: 700,
                          }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(uploadResult.account_summaries || []).slice(0, 20).map((acc, i) => (
                      <motion.tr
                        key={acc.account_id || i}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.45 + i * 0.02 }}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          cursor: 'default',
                        }}
                        whileHover={{ backgroundColor: 'color-mix(in srgb, var(--accent) 3%, transparent)' }}
                      >
                        <td style={{ padding: '8px 10px', color: 'var(--text-primary)' }}>
                          {(acc.account_id || '').slice(0, 12)}...
                        </td>
                        <td style={{ padding: '8px 10px', color: 'var(--text-muted)' }}>
                          {(acc.cif_id || '').slice(0, 10)}...
                        </td>
                        <td style={{ padding: '8px 10px', color: 'var(--text-primary)' }}>
                          {acc.account_age_days}
                        </td>
                        <td style={{
                          padding: '8px 10px',
                          color: (acc.balance || 0) < 0 ? 'var(--critical)' : 'var(--text-primary)',
                          fontWeight: (acc.balance || 0) < 0 ? 600 : 400,
                        }}>
                          {(acc.balance || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '8px 10px', color: 'var(--critical)' }}>
                          {acc.debit_count || 0}
                        </td>
                        <td style={{ padding: '8px 10px', color: 'var(--accent)' }}>
                          {acc.credit_count || 0}
                        </td>
                        <td style={{ padding: '8px 10px', color: 'var(--text-muted)' }}>
                          {(acc.avg_txn_amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </td>
                        <td style={{ padding: '8px 10px' }}>
                          <span style={{
                            fontSize: 12, fontWeight: 700, padding: '2px 6px', borderRadius: 3,
                            background: acc.kyc_status === 'VERIFIED' ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : 'color-mix(in srgb, var(--high) 10%, transparent)',
                            color: acc.kyc_status === 'VERIFIED' ? 'var(--accent)' : 'var(--high)',
                            border: `1px solid ${acc.kyc_status === 'VERIFIED' ? 'color-mix(in srgb, var(--accent) 20%, transparent)' : 'color-mix(in srgb, var(--high) 20%, transparent)'}`,
                          }}>
                            {acc.kyc_status}
                          </span>
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>

            {/* Transaction preview table */}
            {uploadResult.preview_rows && uploadResult.preview_rows.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                style={{ ...cardStyle, marginBottom: 24 }}
              >
                <div style={{
                  fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)',
                  fontWeight: 700, marginBottom: 14,
                }}>
                  Transaction Preview (first 50)
                </div>

                <div style={{ overflowX: 'auto', maxHeight: 400 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-sans)', fontSize: 12 }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)', position: 'sticky', top: 0, background: 'var(--bg-card)' }}>
                        {['Txn ID', 'From', 'To', 'Amount', 'Type', 'Channel', 'Time'].map(h => (
                          <th key={h} style={{
                            textAlign: 'left', padding: '8px 10px',
                            color: 'var(--text-faint)', fontSize: 12, fontWeight: 700,
                            }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {uploadResult.preview_rows.slice(0, 50).map((txn, i) => (
                        <tr key={txn.txn_id || i} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>{(txn.txn_id || '').slice(0, 10)}...</td>
                          <td style={{ padding: '6px 10px', color: 'var(--text-primary)' }}>{(txn.from_account || '').slice(0, 10)}...</td>
                          <td style={{ padding: '6px 10px', color: 'var(--text-primary)' }}>{(txn.to_account || '').slice(0, 10)}...</td>
                          <td style={{ padding: '6px 10px', color: 'var(--accent)', fontWeight: 600 }}>{txn.amount?.toLocaleString('en-IN')}</td>
                          <td style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>{txn.txn_type}</td>
                          <td style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>{txn.channel}</td>
                          <td style={{ padding: '6px 10px', color: 'var(--text-faint)', fontSize: 12 }}>{txn.timestamp?.replace('T', ' ')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* Section C: Detection Results */}
            {uploadResult.alerts_generated > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.55 }}
                style={{ ...cardStyle, marginBottom: 24 }}
              >
                <div style={{
                  fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)',
                  fontWeight: 700, marginBottom: 16,
                }}>
                  Detection Results
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
                  <CheckCircle size={20} color="var(--accent)" />
                  <span style={{ fontFamily: 'var(--font-sans)', fontSize: 14, color: 'var(--text-primary)' }}>
                    Pipeline generated <strong>{uploadResult.alerts_generated}</strong> alerts from uploaded data
                  </span>
                </div>

                {/* Severity breakdown */}
                {uploadResult.severity_counts && (
                  <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
                    {Object.entries(uploadResult.severity_counts)
                      .filter(([, count]) => count > 0)
                      .map(([sev, count]) => (
                        <SeverityBadge key={sev} severity={sev} count={count} />
                      ))}
                  </div>
                )}

                {/* Navigation links */}
                <div style={{ display: 'flex', gap: 12 }}>
                  <button className="btn btn-ghost" onClick={() => navigate('/')}
                    style={{ gap: 8, color: 'var(--accent)', borderColor: 'color-mix(in srgb, var(--accent) 25%, transparent)' }}
                  >
                    <BarChart2 size={14} />
                    View Dashboard
                    <ArrowRight size={12} />
                  </button>

                  <button className="btn btn-ghost" onClick={() => navigate('/queue')}
                    style={{ gap: 8, color: 'var(--critical)', borderColor: 'color-mix(in srgb, var(--critical) 25%, transparent)' }}
                  >
                    <FileText size={14} />
                    Triage
                    <ArrowRight size={12} />
                  </button>
                </div>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
