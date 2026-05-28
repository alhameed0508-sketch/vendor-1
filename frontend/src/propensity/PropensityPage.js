import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { apiFetch } from '../auth/api';
import { GlassCard } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { Search, TrendingUp } from 'lucide-react';

/* ── Helpers ── */

const WINDOW_LABELS = ['1h', '6h', '24h', '7d', '30d'];

function getScoreColor(score) {
  if (score > 0.8) return '#F43F5E';
  if (score > 0.6) return '#FB923C';
  if (score > 0.4) return '#FACC15';
  return 'var(--text-muted)';
}

function formatUpdatedAt(ts) {
  if (!ts) return '--';
  try {
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now - d;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDay = Math.floor(diffHr / 24);
    return `${diffDay}d ago`;
  } catch {
    return '--';
  }
}

/* ── Score Bar (reusable) ── */

function ScoreBar({ value, label, height = 6, showLabel = true, animate = true }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const color = getScoreColor(value);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%' }}>
      {showLabel && label && (
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: 'var(--text-muted)',
          minWidth: 32,
          textAlign: 'right',
          letterSpacing: '0.3px',
        }}>
          {label}
        </span>
      )}
      <div style={{
        flex: 1,
        height,
        background: 'rgba(255,255,255,0.05)',
        borderRadius: height / 2,
        overflow: 'hidden',
        position: 'relative',
      }}>
        <motion.div
          initial={animate ? { width: 0 } : false}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
          style={{
            height: '100%',
            background: `linear-gradient(90deg, ${color}, ${color}90)`,
            borderRadius: height / 2,
            boxShadow: `0 0 8px ${color}40`,
          }}
        />
      </div>
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        fontWeight: 600,
        color,
        minWidth: 42,
        textAlign: 'right',
      }}>
        {(value * 100).toFixed(1)}%
      </span>
    </div>
  );
}

/* ── Section 1: Top Risk Accounts ── */

function TopRiskAccounts({ accounts, loading, total }) {
  if (loading) {
    return (
      <div className="loading" style={{ padding: '60px 0' }}>
        <div className="spinner" />
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          letterSpacing: '1px',
          color: 'var(--text-muted)',
        }}>
          LOADING TOP RISK ACCOUNTS...
        </span>
      </div>
    );
  }

  if (!accounts || accounts.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '60px 20px',
        gap: 12,
      }}>
        <TrendingUp size={24} color="var(--text-faint)" />
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          color: 'var(--text-muted)',
          letterSpacing: '0.3px',
        }}>
          No propensity data available
        </span>
      </div>
    );
  }

  return (
    <div>
      {/* Column headers */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '36px 1fr 2fr 80px',
        gap: 12,
        padding: '0 16px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        marginBottom: 4,
      }}>
        <span style={colHeaderStyle}>#</span>
        <span style={colHeaderStyle}>Account</span>
        <span style={colHeaderStyle}>Score</span>
        <span style={{ ...colHeaderStyle, textAlign: 'right' }}>Updated</span>
      </div>

      {/* Rows */}
      {accounts.map((acct, idx) => {
        const color = getScoreColor(acct.score);
        return (
          <motion.div
            key={acct.account_id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: Math.min(idx * 0.03, 0.6), duration: 0.3 }}
            style={{
              display: 'grid',
              gridTemplateColumns: '36px 1fr 2fr 80px',
              gap: 12,
              alignItems: 'center',
              padding: '10px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.03)',
              transition: 'background 0.15s',
              borderRadius: 4,
            }}
            whileHover={{
              background: 'rgba(255,255,255,0.03)',
            }}
          >
            {/* Rank */}
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: idx < 3 ? color : 'var(--text-faint)',
              fontWeight: idx < 3 ? 700 : 400,
            }}>
              {idx + 1}
            </span>

            {/* Account ID */}
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--accent-cyan)',
              letterSpacing: '0.3px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {acct.account_id}
            </span>

            {/* Score bar + number */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                flex: 1,
                height: 4,
                background: 'rgba(255,255,255,0.05)',
                borderRadius: 2,
                overflow: 'hidden',
              }}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${acct.score * 100}%` }}
                  transition={{ duration: 0.6, delay: Math.min(idx * 0.03, 0.6), ease: 'easeOut' }}
                  style={{
                    height: '100%',
                    background: `linear-gradient(90deg, ${color}, ${color}80)`,
                    borderRadius: 2,
                    boxShadow: `0 0 6px ${color}30`,
                  }}
                />
              </div>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                fontWeight: 600,
                color,
                minWidth: 42,
                textAlign: 'right',
              }}>
                {(acct.score * 100).toFixed(1)}%
              </span>
            </div>

            {/* Updated at */}
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-faint)',
              textAlign: 'right',
              letterSpacing: '0.3px',
            }}>
              {formatUpdatedAt(acct.updated_at)}
            </span>
          </motion.div>
        );
      })}

      {/* Footer */}
      {total > accounts.length && (
        <div style={{
          padding: '12px 16px 4px',
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'var(--text-faint)',
          letterSpacing: '0.5px',
          textAlign: 'center',
        }}>
          showing {accounts.length} of {total} accounts
        </div>
      )}
    </div>
  );
}

const colHeaderStyle = {
  fontFamily: 'var(--font-mono)',
  fontSize: 9,
  color: 'var(--text-muted)',
  letterSpacing: '1.2px',
  textTransform: 'uppercase',
  fontWeight: 700,
};

/* ── Section 2: Account Detail Lookup ── */

function AccountDetail({ detail, loading, error }) {
  if (loading) {
    return (
      <div className="loading" style={{ padding: '60px 0' }}>
        <div className="spinner" />
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          letterSpacing: '1px',
          color: 'var(--text-muted)',
        }}>
          FETCHING ACCOUNT DATA...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        padding: '40px 20px',
        textAlign: 'center',
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        color: '#F43F5E',
        letterSpacing: '0.3px',
      }}>
        {error}
      </div>
    );
  }

  if (!detail) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '60px 20px',
        gap: 12,
      }}>
        <Search size={24} color="var(--text-faint)" />
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          color: 'var(--text-muted)',
          letterSpacing: '0.3px',
        }}>
          Enter an account ID to view propensity details
        </span>
      </div>
    );
  }

  const overallColor = getScoreColor(detail.score);
  const windowScores = detail.window_scores || {};
  const signalBreakdown = detail.signal_breakdown || {};

  return (
    <AnimateIn direction="fade">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

        {/* Overall score header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 20,
          paddingBottom: 20,
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}>
          <div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: 'var(--text-muted)',
              letterSpacing: '1.5px',
              textTransform: 'uppercase',
              marginBottom: 6,
            }}>
              Overall Propensity
            </div>
            <div style={{
              fontFamily: 'var(--font-display)',
              fontSize: 48,
              fontWeight: 800,
              color: overallColor,
              letterSpacing: '-2px',
              lineHeight: 1,
            }}>
              {(detail.score * 100).toFixed(1)}%
            </div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--accent-cyan)',
              letterSpacing: '0.3px',
              marginBottom: 4,
            }}>
              {detail.account_id}
            </div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-faint)',
              letterSpacing: '0.3px',
            }}>
              Updated {formatUpdatedAt(detail.updated_at)}
            </div>
          </div>
        </div>

        {/* Time window scores */}
        <div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            color: 'var(--text-muted)',
            letterSpacing: '1.5px',
            textTransform: 'uppercase',
            marginBottom: 14,
            fontWeight: 700,
          }}>
            // Time Window Scores
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {WINDOW_LABELS.map((w) => {
              const val = windowScores[w];
              if (val === undefined || val === null) return null;
              return (
                <ScoreBar
                  key={w}
                  value={val}
                  label={w}
                  height={6}
                  animate
                />
              );
            })}
          </div>
        </div>

        {/* Signal breakdown */}
        {Object.keys(signalBreakdown).length > 0 && (
          <div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: 'var(--text-muted)',
              letterSpacing: '1.5px',
              textTransform: 'uppercase',
              marginBottom: 14,
              fontWeight: 700,
            }}>
              // Signal Breakdown
            </div>
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 0,
            }}>
              {Object.entries(signalBreakdown).map(([key, value]) => (
                <div
                  key={key}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '8px 0',
                    borderBottom: '1px solid rgba(255,255,255,0.03)',
                  }}
                >
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    color: 'var(--text-secondary)',
                    letterSpacing: '0.3px',
                  }}>
                    {key}
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 12,
                    fontWeight: 600,
                    color: typeof value === 'number'
                      ? getScoreColor(value)
                      : 'var(--text-primary)',
                  }}>
                    {typeof value === 'number' ? value.toFixed(3) : String(value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AnimateIn>
  );
}

/* ── Main Page ── */

export default function PropensityPage() {
  const [topAccounts, setTopAccounts] = useState([]);
  const [topTotal, setTopTotal] = useState(0);
  const [topLoading, setTopLoading] = useState(true);

  const [lookupId, setLookupId] = useState('');
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  /* Fetch top risk accounts on mount */
  useEffect(() => {
    setTopLoading(true);
    apiFetch('/api/v1/propensity/top-risk?limit=20')
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setTopAccounts(data.accounts || []);
        setTopTotal(data.total || 0);
      })
      .catch(err => {
        console.error('[Propensity] Failed to load top risk accounts:', err);
      })
      .finally(() => setTopLoading(false));
  }, []);

  /* Lookup a specific account */
  const handleLookup = () => {
    const trimmed = lookupId.trim();
    if (!trimmed) return;

    setDetailLoading(true);
    setDetailError(null);
    setDetail(null);

    apiFetch(`/api/v1/propensity/${encodeURIComponent(trimmed)}`)
      .then(r => {
        if (!r.ok) {
          throw new Error(r.status === 404
            ? `Account "${trimmed}" not found`
            : `Request failed (${r.status})`);
        }
        return r.json();
      })
      .then(body => {
        const data = body?.data || body;
        setDetail(data);
      })
      .catch(err => {
        console.error('[Propensity] Lookup failed:', err);
        setDetailError(err.message || 'Failed to fetch account data');
      })
      .finally(() => setDetailLoading(false));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleLookup();
    }
  };

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
            fontWeight: 800,
            letterSpacing: '-0.5px',
            margin: 0,
          }}>
            Mule Propensity
          </h1>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            background: 'rgba(251,146,60,0.08)',
            border: '1px solid rgba(251,146,60,0.2)',
            borderRadius: 5,
            padding: '2px 8px',
          }}>
            <TrendingUp size={11} color="#FB923C" />
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: '#FB923C',
              letterSpacing: '1px',
              textTransform: 'uppercase',
              fontWeight: 700,
            }}>Scores</span>
          </div>
        </div>
        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: 'var(--text-muted)',
          letterSpacing: '0.3px',
          margin: 0,
        }}>
          <span style={{ color: 'rgba(251,146,60,0.6)' }}>//</span>
          {' '}Rolling risk scores &middot; 5 time windows &middot; Signal decomposition
        </p>
      </motion.div>

      {/* ── Two-column layout ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 20,
        alignItems: 'start',
      }}>

        {/* ── Left: Top Risk Accounts ── */}
        <AnimateIn delay={0.05}>
          <GlassCard padding={0} hover={false} style={{
            background: 'rgba(12,18,32,0.65)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255,255,255,0.07)',
            borderRadius: 12,
            overflow: 'hidden',
            boxShadow: '0 4px 20px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
          }}>
            {/* Section header */}
            <div style={{
              padding: '16px 20px 14px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <TrendingUp size={14} color="#F43F5E" />
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  color: 'var(--text-muted)',
                  letterSpacing: '1.2px',
                  textTransform: 'uppercase',
                  fontWeight: 700,
                }}>
                  Top Risk Accounts
                </span>
              </div>
              {!topLoading && topTotal > 0 && (
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  color: 'var(--text-faint)',
                  letterSpacing: '0.5px',
                }}>
                  {topTotal} total
                </span>
              )}
            </div>

            {/* Account list */}
            <div style={{ padding: '8px 0' }}>
              <TopRiskAccounts
                accounts={topAccounts}
                loading={topLoading}
                total={topTotal}
              />
            </div>
          </GlassCard>
        </AnimateIn>

        {/* ── Right: Account Detail Lookup ── */}
        <AnimateIn delay={0.12}>
          <GlassCard padding={0} hover={false} style={{
            background: 'rgba(12,18,32,0.65)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255,255,255,0.07)',
            borderRadius: 12,
            overflow: 'hidden',
            boxShadow: '0 4px 20px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
          }}>
            {/* Section header */}
            <div style={{
              padding: '16px 20px 14px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Search size={14} color="var(--accent-cyan)" />
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  color: 'var(--text-muted)',
                  letterSpacing: '1.2px',
                  textTransform: 'uppercase',
                  fontWeight: 700,
                }}>
                  Account Detail Lookup
                </span>
              </div>

              {/* Search input + button */}
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{
                  flex: 1,
                  position: 'relative',
                  display: 'flex',
                  alignItems: 'center',
                }}>
                  <Search
                    size={13}
                    color="var(--text-faint)"
                    style={{
                      position: 'absolute',
                      left: 10,
                      pointerEvents: 'none',
                    }}
                  />
                  <input
                    type="text"
                    placeholder="Enter account ID..."
                    value={lookupId}
                    onChange={(e) => setLookupId(e.target.value)}
                    onKeyDown={handleKeyDown}
                    style={{
                      width: '100%',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 6,
                      padding: '8px 12px 8px 32px',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 12,
                      color: 'var(--text-primary)',
                      outline: 'none',
                      transition: 'border-color 0.2s, box-shadow 0.2s',
                      letterSpacing: '0.3px',
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = 'rgba(34,211,238,0.3)';
                      e.target.style.boxShadow = '0 0 0 2px rgba(34,211,238,0.08)';
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = 'rgba(255,255,255,0.08)';
                      e.target.style.boxShadow = 'none';
                    }}
                  />
                </div>
                <button
                  onClick={handleLookup}
                  disabled={detailLoading || !lookupId.trim()}
                  style={{
                    background: lookupId.trim()
                      ? 'linear-gradient(135deg, rgba(34,211,238,0.15), rgba(34,211,238,0.08))'
                      : 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(34,211,238,0.2)',
                    borderRadius: 6,
                    padding: '8px 16px',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    fontWeight: 700,
                    color: lookupId.trim() ? 'var(--accent-cyan)' : 'var(--text-faint)',
                    letterSpacing: '0.8px',
                    textTransform: 'uppercase',
                    cursor: lookupId.trim() ? 'pointer' : 'not-allowed',
                    transition: 'all 0.2s',
                    whiteSpace: 'nowrap',
                    opacity: detailLoading ? 0.6 : 1,
                  }}
                >
                  Lookup
                </button>
              </div>
            </div>

            {/* Detail content */}
            <div style={{ padding: 20 }}>
              <AccountDetail
                detail={detail}
                loading={detailLoading}
                error={detailError}
              />
            </div>
          </GlassCard>
        </AnimateIn>
      </div>
    </div>
  );
}
