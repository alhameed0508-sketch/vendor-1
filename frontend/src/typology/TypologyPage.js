import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../auth/api';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { StaggerContainer, StaggerItem } from '../components/motion/StaggerContainer';


/* ── Typology Definitions ─────────────────────────────────────────────── */

const TYPOLOGIES = [
  { key: 'DECEIVER',   color: '#FF5C7A', description: 'Expert fraudster, synthetic identity' },
  { key: 'PEDDLER',    color: '#FFB020', description: 'Legitimate then sells access' },
  { key: 'ACCOMPLICE', color: '#F59E0B', description: 'Willing participant, progressive structuring' },
  { key: 'CHUMP',      color: '#38BDF8', description: 'Unwitting mule, coerced/tricked' },
  { key: 'VICTIM',     color: '#10B981', description: 'Account takeover victim' },
];

const TYPOLOGY_COLOR_MAP = Object.fromEntries(
  TYPOLOGIES.map(t => [t.key, t.color]),
);


/* ── Typology Card ────────────────────────────────────────────────────── */

function TypologyCard({ typology, count, index }) {
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
        cursor: 'default',
      }}
      whileHover={{
        borderColor: `${typology.color}30`,
        boxShadow: `0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px ${typology.color}18`,
        y: -1,
        transition: { duration: 0.2 },
      }}
    >
      {/* Glow */}
      <div style={{
        position: 'absolute', top: -20, right: -20,
        width: 80, height: 80,
        background: `radial-gradient(circle, ${typology.color}18 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />
      {/* Top accent */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg, ${typology.color}80, transparent)`,
      }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: typology.color,
          letterSpacing: '1.2px',
          textTransform: 'uppercase',
          fontWeight: 700,
        }}>
          {typology.key}
        </div>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: typology.color,
          opacity: 0.6,
          boxShadow: `0 0 8px ${typology.color}60`,
        }} />
      </div>

      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: 28,
        fontWeight: 800,
        color: typology.color,
        letterSpacing: '-1px',
        lineHeight: 1,
        marginBottom: 6,
      }}>
        {count}
      </div>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        color: 'var(--text-muted)',
        letterSpacing: '0.3px',
        lineHeight: 1.4,
      }}>
        {typology.description}
      </div>
    </motion.div>
  );
}


/* ── Confidence Bar ───────────────────────────────────────────────────── */

function ConfidenceBar({ value, color }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 120 }}>
      <div style={{
        flex: 1, height: 4, borderRadius: 2,
        background: 'rgba(255,255,255,0.06)',
        overflow: 'hidden',
      }}>
        <motion.div
          style={{
            height: '100%', borderRadius: 2,
            background: color,
          }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color,
        fontWeight: 600,
        minWidth: 36,
        textAlign: 'right',
      }}>
        {pct}%
      </span>
    </div>
  );
}


/* ── Type Badge ───────────────────────────────────────────────────────── */

function TypeBadge({ type }) {
  const color = TYPOLOGY_COLOR_MAP[type] || 'var(--text-muted)';
  return (
    <span style={{
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '0.8px',
      textTransform: 'uppercase',
      color,
      background: `${color}14`,
      border: `1px solid ${color}30`,
      borderRadius: 4,
      padding: '2px 8px',
      whiteSpace: 'nowrap',
    }}>
      {type}
    </span>
  );
}


/* ── Account Detail Panel ─────────────────────────────────────────────── */

function AccountDetailPanel({ accountId, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    apiFetch(`/api/v1/typology/${accountId}`)
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setDetail(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('[TypologyPage] Failed to load account detail:', err);
        setError('Failed to load account details.');
        setLoading(false);
      });
  }, [accountId]);

  if (loading) {
    return (
      <GlassCard hover={false} style={{ marginTop: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="spinner" />
          <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Loading classification for {accountId}...
          </span>
        </div>
      </GlassCard>
    );
  }

  if (error) {
    return (
      <GlassCard hover={false} style={{ marginTop: 12, borderLeft: '3px solid var(--critical)' }}>
        <p style={{ fontSize: 12, color: 'var(--critical)', fontFamily: 'var(--font-mono)' }}>
          {error}
        </p>
      </GlassCard>
    );
  }

  if (!detail) return null;

  const behavioralSignals = detail.behavioral_signals || [];
  const reasonCodes = detail.reason_codes || [];
  const responseActions = detail.response_actions || [];
  const typeColor = TYPOLOGY_COLOR_MAP[detail.predicted_type] || 'var(--text-muted)';

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{ overflow: 'hidden' }}
    >
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12,
        padding: '16px 0 4px',
        borderTop: `1px solid ${typeColor}20`,
      }}>

        {/* Close / header row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 11,
              color: 'var(--accent-cyan)', letterSpacing: '0.3px',
            }}>
              {accountId}
            </span>
            <TypeBadge type={detail.predicted_type} />
          </div>
          <motion.button
            className="btn btn-ghost"
            style={{ fontSize: 10, padding: '3px 10px' }}
            onClick={onClose}
            whileTap={{ scale: 0.95 }}
          >
            Close
          </motion.button>
        </div>

        {/* Behavioral Signals */}
        {behavioralSignals.length > 0 && (
          <GlassCard hover={false} padding={14}>
            <p style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)',
              letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700,
              marginBottom: 10,
            }}>
              Behavioral Signals
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {behavioralSignals.map((signal, i) => (
                <motion.div
                  key={i}
                  style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <span style={{
                    color: typeColor, fontSize: 10, flexShrink: 0, marginTop: 2,
                    fontFamily: 'var(--font-mono)', fontWeight: 700,
                  }}>
                    &rsaquo;
                  </span>
                  <span style={{
                    fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5,
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {typeof signal === 'string' ? signal : signal.description || JSON.stringify(signal)}
                  </span>
                </motion.div>
              ))}
            </div>
          </GlassCard>
        )}

        {/* Reason Codes */}
        {reasonCodes.length > 0 && (
          <GlassCard hover={false} padding={14}>
            <p style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)',
              letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700,
              marginBottom: 10,
            }}>
              Reason Codes
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {reasonCodes.map((code, i) => (
                <motion.span
                  key={i}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.03 }}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    color: 'var(--text-secondary)',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 4,
                    padding: '3px 8px',
                    letterSpacing: '0.3px',
                  }}
                >
                  {typeof code === 'string' ? code : code.code || JSON.stringify(code)}
                </motion.span>
              ))}
            </div>
          </GlassCard>
        )}

        {/* Response Actions */}
        {responseActions.length > 0 && (
          <GlassCard hover={false} padding={14}>
            <p style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)',
              letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700,
              marginBottom: 10,
            }}>
              Response Actions
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {responseActions.map((action, i) => (
                <ResponseActionCard key={i} action={action} index={i} />
              ))}
            </div>
          </GlassCard>
        )}
      </div>
    </motion.div>
  );
}


/* ── Response Action Card ─────────────────────────────────────────────── */

function ResponseActionCard({ action, index }) {
  const urgencyColor = (action.urgency || '').toUpperCase() === 'HIGH'
    ? 'var(--critical)'
    : (action.urgency || '').toUpperCase() === 'MEDIUM'
      ? 'var(--high)'
      : 'var(--text-muted)';

  const priorityColor = (action.investigation_priority || '').toUpperCase() === 'HIGH'
    ? 'var(--critical)'
    : (action.investigation_priority || '').toUpperCase() === 'MEDIUM'
      ? 'var(--high)'
      : 'var(--accent-cyan)';

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06 }}
      style={{
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 8,
        padding: 12,
      }}
    >
      {/* Header row: action type + urgency */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
          color: 'var(--text-primary)', letterSpacing: '0.3px',
        }}>
          {action.action_type || 'Unknown Action'}
        </span>
        <div style={{ display: 'flex', gap: 6 }}>
          {action.urgency && (
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
              color: urgencyColor,
              background: `${urgencyColor}12`,
              border: `1px solid ${urgencyColor}30`,
              borderRadius: 3, padding: '1px 6px',
              letterSpacing: '0.5px', textTransform: 'uppercase',
            }}>
              {action.urgency}
            </span>
          )}
          {action.investigation_priority && (
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
              color: priorityColor,
              background: `${priorityColor}12`,
              border: `1px solid ${priorityColor}30`,
              borderRadius: 3, padding: '1px 6px',
              letterSpacing: '0.5px', textTransform: 'uppercase',
            }}>
              P:{action.investigation_priority}
            </span>
          )}
        </div>
      </div>

      {/* Description */}
      {action.description && (
        <p style={{
          fontFamily: 'var(--font-mono)', fontSize: 11,
          color: 'var(--text-secondary)', lineHeight: 1.5,
          marginBottom: action.notification_targets ? 6 : 0,
        }}>
          {action.description}
        </p>
      )}

      {/* Notification Targets */}
      {action.notification_targets && action.notification_targets.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 9,
            color: 'var(--text-muted)', letterSpacing: '0.5px',
          }}>
            NOTIFY:
          </span>
          {action.notification_targets.map((target, j) => (
            <span key={j} style={{
              fontFamily: 'var(--font-mono)', fontSize: 10,
              color: 'var(--accent-cyan)',
              background: 'rgba(90,200,250,0.08)',
              borderRadius: 3, padding: '1px 6px',
            }}>
              {target}
            </span>
          ))}
        </div>
      )}
    </motion.div>
  );
}


/* ── Main Page ────────────────────────────────────────────────────────── */

export default function TypologyPage() {
  const [distribution, setDistribution] = useState({});
  const [totalFlagged, setTotalFlagged] = useState(0);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedAccountId, setSelectedAccountId] = useState(null);

  useEffect(() => {
    apiFetch('/api/v1/typology/distribution')
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setDistribution(data.distribution || {});
        setTotalFlagged(data.total_flagged || 0);
        setAccounts(data.accounts || []);
        setLoading(false);
      })
      .catch(err => {
        console.error('[TypologyPage] Failed to load distribution:', err);
        setError('Failed to load typology distribution.');
        setLoading(false);
      });
  }, []);

  const handleRowClick = (accountId) => {
    setSelectedAccountId(prev => prev === accountId ? null : accountId);
  };

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1440, margin: '0 auto' }}>

      {/* ── Page Header ── */}
      <AnimateIn>
        <div style={{ marginBottom: 28 }}>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontSize: 26,
            fontWeight: 800,
            letterSpacing: '-0.5px',
            color: 'var(--text-primary)',
            margin: 0,
            marginBottom: 4,
          }}>
            Mule Typology
          </h1>
          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--text-muted)',
            letterSpacing: '0.3px',
          }}>
            <span style={{ color: 'rgba(16,185,129,0.6)' }}>//</span>
            {' '}5-class behavioral classification
            <span style={{ margin: '0 8px', color: 'var(--text-faint)' }}>&middot;</span>
            Response orchestration
          </p>
        </div>
      </AnimateIn>

      {/* ── Section 1: Typology Distribution Cards ── */}
      {loading ? (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: 10, padding: '60px 0',
        }}>
          <div className="spinner" />
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)',
          }}>
            Loading typology distribution...
          </span>
        </div>
      ) : error ? (
        <GlassCard hover={false} style={{ marginBottom: 24, borderLeft: '3px solid var(--critical)' }}>
          <p style={{ fontSize: 12, color: 'var(--critical)', fontFamily: 'var(--font-mono)' }}>
            {error}
          </p>
        </GlassCard>
      ) : (
        <>
          {/* Distribution header */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            marginBottom: 14,
          }}>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)',
              letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700,
            }}>
              Distribution Overview
            </span>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 10,
              color: 'var(--accent-cyan)',
              background: 'rgba(90,200,250,0.08)',
              border: '1px solid rgba(90,200,250,0.15)',
              borderRadius: 4, padding: '2px 8px',
            }}>
              {totalFlagged} flagged
            </span>
          </div>

          {/* Cards Grid */}
          <StaggerContainer style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(5, 1fr)',
            gap: 12,
            marginBottom: 32,
          }}>
            {TYPOLOGIES.map((typology, i) => (
              <StaggerItem key={typology.key}>
                <TypologyCard
                  typology={typology}
                  count={distribution[typology.key] || 0}
                  index={i}
                />
              </StaggerItem>
            ))}
          </StaggerContainer>


          {/* ── Section 2: Account Classifications Table ── */}
          <AnimateIn delay={0.2}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              marginBottom: 14,
            }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)',
                letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700,
              }}>
                Account Classifications
              </span>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 10,
                color: 'var(--text-muted)',
              }}>
                {accounts.length} accounts
              </span>
            </div>
          </AnimateIn>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, delay: 0.25 }}
          >
            <div style={{
              background: 'rgba(15,20,33,0.60)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid var(--border)',
              borderRadius: 10,
              overflow: 'hidden',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
            }}>
              {accounts.length === 0 ? (
                <div style={{
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                  padding: '60px 40px', gap: 12, textAlign: 'center',
                }}>
                  <p style={{
                    fontFamily: 'var(--font-display)', fontSize: 15,
                    fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4,
                  }}>
                    No classified accounts
                  </p>
                  <p style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11,
                    color: 'var(--text-muted)', letterSpacing: '0.3px',
                  }}>
                    // classification pipeline has not flagged any accounts yet
                  </p>
                </div>
              ) : (
                <div className="table-container">
                  <table className="data-table" role="grid" aria-label="Typology classifications">
                    <thead>
                      <tr>
                        <th style={{ width: 40, paddingLeft: 16 }}>#</th>
                        <th>Account ID</th>
                        <th>Predicted Type</th>
                        <th style={{ minWidth: 180 }}>Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      <AnimatePresence>
                        {accounts.map((acct, idx) => {
                          const acctId = acct.account_id;
                          const isSelected = selectedAccountId === acctId;
                          const typeColor = TYPOLOGY_COLOR_MAP[acct.predicted_type] || 'var(--text-muted)';

                          return (
                            <React.Fragment key={acctId}>
                              <motion.tr
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: Math.min(idx * 0.02, 0.3) }}
                                className={`clickable ${isSelected ? 'selected' : ''}`}
                                onClick={() => handleRowClick(acctId)}
                                tabIndex={0}
                                role="row"
                                onKeyDown={e => { if (e.key === 'Enter') handleRowClick(acctId); }}
                                style={{ cursor: 'pointer' }}
                              >
                                <td style={{
                                  color: 'var(--text-faint)', fontSize: 11,
                                  fontFamily: 'var(--font-mono)', paddingLeft: 16,
                                }}>
                                  {idx + 1}
                                </td>
                                <td>
                                  <span style={{
                                    fontFamily: 'var(--font-mono)', fontSize: 12,
                                    color: 'var(--accent-cyan)', letterSpacing: '0.3px',
                                  }}>
                                    {acctId}
                                  </span>
                                </td>
                                <td>
                                  <TypeBadge type={acct.predicted_type} />
                                </td>
                                <td>
                                  <ConfidenceBar value={acct.confidence} color={typeColor} />
                                </td>
                              </motion.tr>

                              {/* ── Section 3: Expanded Detail Row ── */}
                              {isSelected && (
                                <tr>
                                  <td colSpan={4} style={{ padding: '0 16px 16px' }}>
                                    <AnimatePresence>
                                      <AccountDetailPanel
                                        accountId={acctId}
                                        onClose={() => setSelectedAccountId(null)}
                                      />
                                    </AnimatePresence>
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })}
                      </AnimatePresence>
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Keyboard hint */}
            <div style={{
              marginTop: 10,
              display: 'flex', gap: 16,
              fontFamily: 'var(--font-mono)', fontSize: 10,
              color: 'var(--text-faint)', letterSpacing: '0.5px',
            }}>
              {[['click row', 'expand detail'], ['Esc / close', 'collapse']].map(([k, v]) => (
                <span key={k}>
                  <span style={{
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid var(--border)',
                    borderRadius: 3, padding: '1px 5px',
                    marginRight: 5, fontWeight: 700,
                  }}>
                    {k}
                  </span>
                  {v}
                </span>
              ))}
            </div>
          </motion.div>
        </>
      )}
    </div>
  );
}
