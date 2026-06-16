import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../auth/api';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { Search, FileText, Brain, Zap, ChevronRight, AlertTriangle } from 'lucide-react';

/* ── Shared style constants ── */
const SECTION_TITLE = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  letterSpacing: '1.5px',
  textTransform: 'uppercase',
  fontWeight: 700,
  color: 'var(--text-muted)',
  marginBottom: 12,
};

const MONO_XS = {
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  letterSpacing: '0.3px',
};

const TABLE_CELL = {
  padding: '10px 14px',
  borderBottom: '1px solid var(--border)',
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
  color: 'var(--text-primary)',
};

const TABLE_HEADER = {
  ...TABLE_CELL,
  fontSize: 9,
  letterSpacing: '1.2px',
  textTransform: 'uppercase',
  fontWeight: 700,
  color: 'var(--text-muted)',
  background: 'var(--bg-card)',
};

/* ── Priority score color ── */
function getPriorityColor(score) {
  if (score >= 0.8) return 'var(--critical)';
  if (score >= 0.6) return 'var(--high)';
  if (score >= 0.4) return 'var(--accent-amber)';
  return 'var(--text-muted)';
}

/* ── Priority score badge ── */
function PriorityBadge({ score }) {
  const color = getPriorityColor(score);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 40, height: 3,
        background: 'var(--border-subtle)',
        borderRadius: 2,
        overflow: 'hidden',
      }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score * 100}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          style={{ height: '100%', background: color, borderRadius: 2 }}
        />
      </div>
      <span style={{ ...MONO_XS, color, fontWeight: 600 }}>
        {(score * 100).toFixed(0)}
      </span>
    </div>
  );
}

/* ── Status badge ── */
function StatusBadge({ status }) {
  const colorMap = {
    OPEN: 'var(--accent-amber)',
    UNDER_REVIEW: 'var(--accent-cyan)',
    RESOLVED: 'var(--accent-green, #10B981)',
    FALSE_POSITIVE: 'var(--text-muted)',
  };
  const color = colorMap[status] || 'var(--text-muted)';
  return (
    <span style={{
      fontSize: 9,
      fontFamily: 'var(--font-mono)',
      letterSpacing: '0.5px',
      padding: '2px 8px',
      borderRadius: 10,
      background: `${color}18`,
      color,
      border: `1px solid ${color}30`,
      textTransform: 'uppercase',
    }}>
      {(status || 'UNKNOWN').replace('_', ' ')}
    </span>
  );
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Section 1: Priority Queue
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function PriorityQueueSection({ alerts, priorityQueue, loadingQueue, onRefresh }) {
  return (
    <AnimateIn delay={0.1}>
      <GlassCard padding={0} hover={false} style={{ overflow: 'hidden' }}>
        {/* Section header */}
        <div style={{
          padding: '14px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Zap size={14} color="var(--accent-amber)" />
            <span style={SECTION_TITLE}>Priority Queue</span>
            <span style={{
              ...MONO_XS,
              fontSize: 10,
              color: 'var(--text-muted)',
              marginLeft: 4,
            }}>
              {priorityQueue.length} items
            </span>
          </div>
          <motion.button
            className="btn btn-ghost"
            onClick={onRefresh}
            style={{ fontSize: 10, padding: '4px 10px', gap: 5 }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
          >
            <Search size={11} />
            Re-rank
          </motion.button>
        </div>

        {/* Table */}
        {loadingQueue ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '48px 0', gap: 10,
          }}>
            <div className="spinner" />
            <span style={{ ...MONO_XS, color: 'var(--text-muted)' }}>
              Computing priority scores...
            </span>
          </div>
        ) : priorityQueue.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', padding: '60px 40px', gap: 12,
          }}>
            <AlertTriangle size={20} color="var(--text-muted)" style={{ opacity: 0.3 }} />
            <span style={{ ...MONO_XS, color: 'var(--text-muted)' }}>
              No alerts to prioritize
            </span>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Rank', 'Alert ID', 'SAR Probability', 'Complexity', 'Priority Score', 'Amount', 'Status'].map(h => (
                    <th key={h} style={TABLE_HEADER}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <AnimatePresence>
                  {priorityQueue.map((item, idx) => (
                    <motion.tr
                      key={item.alert_id || idx}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: Math.min(idx * 0.03, 0.4) }}
                      style={{
                        cursor: 'default',
                        transition: 'background 0.15s',
                      }}
                      whileHover={{
                        backgroundColor: 'rgba(62,231,255,0.03)',
                      }}
                    >
                      <td style={{ ...TABLE_CELL, color: 'var(--text-faint)', width: 50, textAlign: 'center' }}>
                        {idx + 1}
                      </td>
                      <td style={TABLE_CELL}>
                        <span style={{ color: 'var(--accent-cyan)', letterSpacing: '0.3px' }}>
                          {item.alert_id}
                        </span>
                      </td>
                      <td style={TABLE_CELL}>
                        <span style={{
                          color: (item.sar_probability || 0) >= 0.7 ? 'var(--critical)' : 'var(--text-primary)',
                          fontWeight: 600,
                        }}>
                          {((item.sar_probability || 0) * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td style={TABLE_CELL}>
                        <span style={{ color: 'var(--text-secondary)' }}>
                          {item.investigation_complexity || item.complexity || 'N/A'}
                        </span>
                      </td>
                      <td style={TABLE_CELL}>
                        <PriorityBadge score={item.priority_score || 0} />
                      </td>
                      <td style={TABLE_CELL}>
                        <span style={{ color: 'var(--high)', fontWeight: 600 }}>
                          {item.amount != null
                            ? `₹${Number(item.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
                            : '—'}
                        </span>
                      </td>
                      <td style={TABLE_CELL}>
                        <StatusBadge status={item.status} />
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </AnimateIn>
  );
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Section 2: Case Assembly
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function CaseAssemblySection({ alerts, loading: globalLoading }) {
  const [selectedAlertId, setSelectedAlertId] = useState('');
  const [assembling, setAssembling] = useState(false);
  const [caseFile, setCaseFile] = useState(null);
  const [error, setError] = useState(null);

  const selectedAlert = alerts.find(a => a.alert_id === selectedAlertId) || null;

  const handleAssemble = async () => {
    if (!selectedAlertId || !selectedAlert) return;
    setAssembling(true);
    setError(null);
    setCaseFile(null);

    try {
      const res = await apiFetch(`/api/v1/investigation/assemble/${selectedAlertId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_data: selectedAlert }),
      });
      const body = await res.json();
      const data = body?.data || body;
      setCaseFile(data);
    } catch (err) {
      console.error('[Investigation] Case assembly failed:', err);
      setError('Failed to assemble case. Please try again.');
    } finally {
      setAssembling(false);
    }
  };

  return (
    <AnimateIn delay={0.2}>
      <GlassCard padding={0} hover={false} style={{ overflow: 'hidden' }}>
        {/* Section header */}
        <div style={{
          padding: '14px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <FileText size={14} color="var(--accent-cyan)" />
          <span style={SECTION_TITLE}>Case Assembly</span>
        </div>

        <div style={{ padding: 20 }}>
          {/* Alert selector + assemble button */}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16 }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <select
                value={selectedAlertId}
                onChange={e => {
                  setSelectedAlertId(e.target.value);
                  setCaseFile(null);
                  setError(null);
                }}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: selectedAlertId ? 'var(--text-primary)' : 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  outline: 'none',
                  cursor: 'pointer',
                  appearance: 'none',
                  WebkitAppearance: 'none',
                }}
              >
                <option value="">Select Alert...</option>
                {alerts.map(a => (
                  <option key={a.alert_id} value={a.alert_id}>
                    {a.alert_id} — {a.severity} — Risk {(a.risk_score * 100).toFixed(0)}%
                  </option>
                ))}
              </select>
              <ChevronRight
                size={13}
                color="var(--text-muted)"
                style={{
                  position: 'absolute',
                  right: 12,
                  top: '50%',
                  transform: 'translateY(-50%) rotate(90deg)',
                  pointerEvents: 'none',
                }}
              />
            </div>
            <motion.button
              className="btn btn-primary"
              onClick={handleAssemble}
              disabled={!selectedAlertId || assembling}
              style={{
                padding: '10px 20px',
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.5px',
                gap: 6,
                whiteSpace: 'nowrap',
              }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
            >
              <FileText size={12} />
              {assembling ? 'Assembling...' : 'Assemble Case'}
            </motion.button>
          </div>

          {/* Error message */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                style={{
                  padding: '10px 14px',
                  background: 'rgba(239,68,68,0.08)',
                  border: '1px solid rgba(239,68,68,0.2)',
                  borderRadius: 8,
                  marginBottom: 16,
                  ...MONO_XS,
                  color: 'var(--critical)',
                }}
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Assembling spinner */}
          {assembling && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: '40px 0', gap: 10,
            }}>
              <div className="spinner" />
              <span style={{ ...MONO_XS, color: 'var(--text-muted)' }}>
                Assembling evidence...
              </span>
            </div>
          )}

          {/* Case file display */}
          <AnimatePresence>
            {caseFile && !assembling && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 12 }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              >
                {/* Case strength header */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  marginBottom: 16,
                  padding: '12px 16px',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                }}>
                  <div>
                    <div style={SECTION_TITLE}>Case Strength</div>
                    <div style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 24,
                      fontWeight: 700,
                      color: getPriorityColor(caseFile.case_strength || 0),
                      letterSpacing: '-0.5px',
                      lineHeight: 1,
                    }}>
                      {caseFile.case_strength != null
                        ? `${(caseFile.case_strength * 100).toFixed(0)}%`
                        : 'N/A'}
                    </div>
                  </div>
                  {caseFile.typology && (
                    <div style={{ textAlign: 'right' }}>
                      <div style={SECTION_TITLE}>Typology</div>
                      <span style={{
                        fontSize: 11,
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--accent-amber)',
                        padding: '3px 10px',
                        background: 'rgba(245,158,11,0.08)',
                        border: '1px solid rgba(245,158,11,0.2)',
                        borderRadius: 6,
                      }}>
                        {caseFile.typology}
                      </span>
                    </div>
                  )}
                </div>

                {/* Info grid: Account IDs + Timeline */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                  {/* Account IDs */}
                  <div style={{
                    padding: '12px 16px',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                  }}>
                    <div style={SECTION_TITLE}>Account IDs</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {(caseFile.account_ids || []).length > 0 ? (
                        caseFile.account_ids.map((id, i) => (
                          <span key={i} style={{
                            fontSize: 10,
                            fontFamily: 'var(--font-mono)',
                            color: 'var(--accent-cyan)',
                            padding: '2px 8px',
                            background: 'rgba(62,231,255,0.06)',
                            border: '1px solid rgba(62,231,255,0.15)',
                            borderRadius: 4,
                          }}>
                            {id}
                          </span>
                        ))
                      ) : (
                        <span style={{ ...MONO_XS, color: 'var(--text-muted)' }}>None identified</span>
                      )}
                    </div>
                  </div>

                  {/* Timeline */}
                  <div style={{
                    padding: '12px 16px',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                  }}>
                    <div style={SECTION_TITLE}>Timeline</div>
                    {(caseFile.timeline || []).length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {caseFile.timeline.slice(0, 5).map((entry, i) => (
                          <div key={i} style={{
                            display: 'flex', alignItems: 'flex-start', gap: 8,
                            paddingLeft: 8,
                            borderLeft: '2px solid var(--accent-cyan)',
                          }}>
                            <span style={{
                              fontSize: 10, fontFamily: 'var(--font-mono)',
                              color: 'var(--text-muted)', whiteSpace: 'nowrap',
                            }}>
                              {entry.time || entry.timestamp || `Step ${i + 1}`}
                            </span>
                            <span style={{
                              fontSize: 11, fontFamily: 'var(--font-mono)',
                              color: 'var(--text-secondary)',
                            }}>
                              {entry.event || entry.description || String(entry)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span style={{ ...MONO_XS, color: 'var(--text-muted)' }}>No timeline data</span>
                    )}
                  </div>
                </div>

                {/* Evidence items */}
                <div style={{
                  padding: '12px 16px',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                }}>
                  <div style={SECTION_TITLE}>Evidence Items</div>
                  {(caseFile.evidence_items || caseFile.evidence || []).length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {(caseFile.evidence_items || caseFile.evidence || []).map((ev, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.05 }}
                          style={{
                            display: 'flex', alignItems: 'flex-start', gap: 10,
                            padding: '8px 12px',
                            background: i % 2 === 0 ? 'var(--bg-card)' : 'transparent',
                            borderRadius: 6,
                            borderLeft: '2px solid var(--accent-amber)',
                          }}
                        >
                          <ChevronRight size={11} color="var(--accent-amber)" style={{ marginTop: 2, flexShrink: 0 }} />
                          <div>
                            <div style={{
                              fontSize: 11,
                              fontFamily: 'var(--font-mono)',
                              color: 'var(--text-primary)',
                              lineHeight: 1.5,
                            }}>
                              {ev.description || ev.title || ev.type || String(ev)}
                            </div>
                            {ev.source && (
                              <div style={{
                                fontSize: 9,
                                fontFamily: 'var(--font-mono)',
                                color: 'var(--text-muted)',
                                marginTop: 2,
                                letterSpacing: '0.3px',
                              }}>
                                Source: {ev.source}
                              </div>
                            )}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  ) : (
                    <span style={{ ...MONO_XS, color: 'var(--text-muted)' }}>No evidence collected</span>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Empty state when no alert selected */}
          {!selectedAlertId && !caseFile && !assembling && (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', padding: '40px 0', gap: 10,
            }}>
              <FileText size={20} color="var(--text-muted)" style={{ opacity: 0.2 }} />
              <span style={{ ...MONO_XS, color: 'var(--text-muted)' }}>
                Select an alert to assemble a case file
              </span>
            </div>
          )}
        </div>
      </GlassCard>
    </AnimateIn>
  );
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Section 3: Investigation Copilot
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function CopilotSection({ alerts }) {
  const [selectedAlertId, setSelectedAlertId] = useState('');
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [caseContext, setCaseContext] = useState(null);
  const scrollRef = useRef(null);

  const selectedAlert = alerts.find(a => a.alert_id === selectedAlertId) || null;

  // Scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendQuestion = async (text) => {
    const q = text || question;
    if (!q.trim() || !selectedAlertId) return;

    const userMsg = { role: 'user', content: q.trim() };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setQuestion('');
    setLoading(true);

    try {
      const res = await apiFetch('/api/v1/investigation/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          alert_id: selectedAlertId,
          question: q.trim(),
          case_context: caseContext || { alert: selectedAlert },
        }),
      });
      const body = await res.json();
      const data = body?.data || body;

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response || data.message || data.answer || 'No response received.',
      }]);

      // Preserve any context returned by the copilot
      if (data.updated_context) {
        setCaseContext(data.updated_context);
      }
    } catch (err) {
      console.error('[Investigation] Copilot request failed:', err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Copilot unavailable. Please try again.',
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendQuestion();
    }
  };

  const quickActions = [
    { label: 'Summarize risk', icon: AlertTriangle },
    { label: 'Suggest next steps', icon: ChevronRight },
    { label: 'Check connections', icon: Search },
  ];

  return (
    <AnimateIn delay={0.3}>
      <GlassCard padding={0} hover={false} style={{ overflow: 'hidden' }}>
        {/* Section header */}
        <div style={{
          padding: '14px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <Brain size={14} color="var(--accent-cyan)" />
          <span style={SECTION_TITLE}>Investigation Copilot</span>
          <span style={{
            fontSize: 9,
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.5px',
            padding: '2px 8px',
            borderRadius: 10,
            background: 'rgba(62,231,255,0.08)',
            color: 'var(--accent-cyan)',
            border: '1px solid rgba(62,231,255,0.2)',
            textTransform: 'uppercase',
          }}>
            AI
          </span>
        </div>

        <div style={{ padding: 20 }}>
          {/* Alert selector for copilot context */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ position: 'relative' }}>
              <select
                value={selectedAlertId}
                onChange={e => {
                  setSelectedAlertId(e.target.value);
                  setMessages([]);
                  setCaseContext(null);
                }}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: selectedAlertId ? 'var(--text-primary)' : 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  outline: 'none',
                  cursor: 'pointer',
                  appearance: 'none',
                  WebkitAppearance: 'none',
                }}
              >
                <option value="">Select Alert for context...</option>
                {alerts.map(a => (
                  <option key={a.alert_id} value={a.alert_id}>
                    {a.alert_id} — {a.severity}
                  </option>
                ))}
              </select>
              <ChevronRight
                size={13}
                color="var(--text-muted)"
                style={{
                  position: 'absolute',
                  right: 12,
                  top: '50%',
                  transform: 'translateY(-50%) rotate(90deg)',
                  pointerEvents: 'none',
                }}
              />
            </div>
          </div>

          {/* Chat messages */}
          <div
            ref={scrollRef}
            style={{
              height: 280,
              overflowY: 'auto',
              marginBottom: 12,
              padding: '12px 4px',
              borderRadius: 8,
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
            }}
          >
            {messages.length === 0 && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                justifyContent: 'center', height: '100%', gap: 12,
              }}>
                <Brain size={24} color="var(--text-muted)" style={{ opacity: 0.1 }} />
                <span style={{
                  ...MONO_XS,
                  fontSize: 11,
                  color: 'var(--text-muted)',
                  textAlign: 'center',
                  lineHeight: 1.5,
                }}>
                  {selectedAlertId
                    ? 'Ask a question about this alert or use the quick actions below.'
                    : 'Select an alert to start an investigation conversation.'}
                </span>
              </div>
            )}
            {messages.map((msg, i) => {
              const isUser = msg.role === 'user';
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  style={{
                    display: 'flex',
                    justifyContent: isUser ? 'flex-end' : 'flex-start',
                    marginBottom: 10,
                    padding: '0 12px',
                  }}
                >
                  <div style={{
                    maxWidth: '85%',
                    padding: '10px 14px',
                    borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                    background: isUser ? 'rgba(62,231,255,0.10)' : 'var(--bg-elevated)',
                    border: `1px solid ${isUser ? 'rgba(62,231,255,0.20)' : 'var(--border)'}`,
                    fontSize: 12,
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-primary)',
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}>
                    {msg.content}
                  </div>
                </motion.div>
              );
            })}
            {loading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                style={{
                  padding: '8px 16px',
                  fontSize: 11,
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                }}
              >
                Thinking...
              </motion.div>
            )}
          </div>

          {/* Quick action buttons */}
          <div style={{
            display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap',
          }}>
            {quickActions.map(({ label, icon: Icon }) => (
              <motion.button
                key={label}
                className="btn btn-ghost"
                style={{
                  fontSize: 10,
                  padding: '5px 12px',
                  gap: 5,
                  borderColor: 'rgba(62,231,255,0.15)',
                  color: 'var(--text-secondary)',
                }}
                onClick={() => sendQuestion(label)}
                disabled={!selectedAlertId || loading}
                whileHover={{ scale: 1.02, borderColor: 'rgba(62,231,255,0.4)' }}
                whileTap={{ scale: 0.97 }}
              >
                <Icon size={10} />
                {label}
              </motion.button>
            ))}
          </div>

          {/* Text input */}
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedAlertId ? 'Ask the copilot...' : 'Select an alert first...'}
              disabled={!selectedAlertId || loading}
              aria-label="Ask a question to the investigation copilot"
              style={{
                flex: 1,
                padding: '10px 14px',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                outline: 'none',
              }}
              onFocus={e => { e.target.style.borderColor = 'var(--accent-cyan)'; }}
              onBlur={e => { e.target.style.borderColor = 'var(--border)'; }}
            />
            <motion.button
              className="btn btn-primary"
              onClick={() => sendQuestion()}
              disabled={!selectedAlertId || loading || !question.trim()}
              style={{ padding: '10px 18px', fontSize: 11, gap: 5 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
            >
              <Zap size={11} />
              {loading ? '...' : 'Ask'}
            </motion.button>
          </div>
        </div>
      </GlassCard>
    </AnimateIn>
  );
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Main Page
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
export default function InvestigationPage() {
  const [alerts, setAlerts] = useState([]);
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [priorityQueue, setPriorityQueue] = useState([]);
  const [loadingQueue, setLoadingQueue] = useState(false);

  const fetchAlerts = async () => {
    setLoadingAlerts(true);
    try {
      const res = await apiFetch('/api/v1/alerts?limit=100');
      const body = await res.json();
      const data = body?.data || body;
      const alertList = data.alerts || [];
      setAlerts(alertList);
      setLoadingAlerts(false);

      // Auto-fetch priority queue once alerts are loaded
      if (alertList.length > 0) {
        fetchPriorityQueue(alertList);
      }
    } catch (err) {
      console.error('[Investigation] Failed to load alerts:', err);
      setLoadingAlerts(false);
    }
  };

  const fetchPriorityQueue = async (alertList) => {
    const source = alertList || alerts;
    if (source.length === 0) return;

    setLoadingQueue(true);
    try {
      const res = await apiFetch('/api/v1/investigation/priority-queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alerts: source }),
      });
      const body = await res.json();
      const data = body?.data || body;
      setPriorityQueue(data.priority_queue || data.queue || data.items || []);
    } catch (err) {
      console.error('[Investigation] Priority queue fetch failed:', err);
    } finally {
      setLoadingQueue(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1440, margin: '0 auto' }}>
      {/* ── Page Header ── */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        style={{ marginBottom: 28 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <h1 className="gradient-text" style={{
            fontFamily: 'var(--font-display)',
            fontSize: 26,
            fontWeight: 700,
            letterSpacing: '-0.5px',
            margin: 0,
          }}>
            Investigation Hub
          </h1>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5,
            background: 'rgba(62,231,255,0.08)',
            border: '1px solid rgba(62,231,255,0.2)',
            borderRadius: 5,
            padding: '2px 8px',
          }}>
            <Brain size={10} color="var(--accent-cyan)" />
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: 'var(--accent-cyan)',
              letterSpacing: '1px',
              textTransform: 'uppercase',
              fontWeight: 700,
            }}>Agentic</span>
          </div>
        </div>
        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: 'var(--text-muted)',
          letterSpacing: '0.3px',
        }}>
          <span style={{ color: 'rgba(62,231,255,0.6)' }}>//</span>
          {' '}Agentic AI case assembly
          <span style={{ margin: '0 8px', color: 'var(--text-faint)' }}>·</span>
          Priority queue
          <span style={{ margin: '0 8px', color: 'var(--text-faint)' }}>·</span>
          Copilot
        </p>
      </motion.div>

      {/* Loading state for initial alert fetch */}
      {loadingAlerts ? (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '80px 0', gap: 10,
        }}>
          <div className="spinner" />
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--text-muted)',
          }}>
            Loading investigation data...
          </span>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Section 1: Priority Queue */}
          <PriorityQueueSection
            alerts={alerts}
            priorityQueue={priorityQueue}
            loadingQueue={loadingQueue}
            onRefresh={() => fetchPriorityQueue(alerts)}
          />

          {/* Sections 2 + 3 side by side */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Section 2: Case Assembly */}
            <CaseAssemblySection alerts={alerts} loading={loadingAlerts} />

            {/* Section 3: Investigation Copilot */}
            <CopilotSection alerts={alerts} />
          </div>
        </div>
      )}
    </div>
  );
}
