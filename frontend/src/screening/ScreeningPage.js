import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Shield, Upload, RefreshCw, AlertTriangle, CheckCircle, XCircle, Database } from 'lucide-react';
import { toast } from 'sonner';
import { apiFetch } from '../auth/api';

const cardStyle = {
  background: 'rgba(12, 18, 32, 0.65)',
  backdropFilter: 'blur(20px)',
  WebkitBackdropFilter: 'blur(20px)',
  border: '1px solid rgba(255,255,255,0.07)',
  borderRadius: 12,
  padding: '22px 24px',
  position: 'relative',
  overflow: 'hidden',
  boxShadow: '0 4px 20px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
};

function StatCard({ label, value, color, icon: Icon, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35 }}
      style={cardStyle}
      whileHover={{
        borderColor: `${color}30`,
        boxShadow: `0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px ${color}18`,
        y: -2,
        transition: { duration: 0.2 },
      }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${color}, transparent)`, opacity: 0.7 }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700 }}>{label}</div>
        {Icon && <div style={{ color, opacity: 0.5 }}><Icon size={13} /></div>}
      </div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 800, color, letterSpacing: '-1px', lineHeight: 1 }}>{value}</div>
    </motion.div>
  );
}

function ScreenResult({ result, index }) {
  const isMatch = result.match_score > 0.7;
  const isMaybe = result.match_score > 0.4 && result.match_score <= 0.7;
  const statusColor = isMatch ? '#F43F5E' : isMaybe ? '#FB923C' : '#10B981';
  const statusLabel = isMatch ? 'HIT' : isMaybe ? 'POSSIBLE' : 'CLEAR';

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      style={{
        ...cardStyle,
        padding: '14px 18px',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
      }}
    >
      <div style={{
        width: 36, height: 36, borderRadius: 8,
        background: `${statusColor}15`,
        border: `1px solid ${statusColor}30`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        {isMatch ? <XCircle size={16} color={statusColor} /> : isMaybe ? <AlertTriangle size={16} color={statusColor} /> : <CheckCircle size={16} color={statusColor} />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>
          {result.name || result.account_id}
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
          {result.matched_list || 'No list match'} {result.match_type ? `// ${result.match_type}` : ''}
        </div>
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
        color: statusColor, letterSpacing: '1px',
        background: `${statusColor}12`,
        padding: '3px 10px', borderRadius: 4,
        border: `1px solid ${statusColor}25`,
      }}>
        {statusLabel}
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: statusColor, minWidth: 50, textAlign: 'right' }}>
        {(result.match_score * 100).toFixed(0)}%
      </div>
    </motion.div>
  );
}

export default function ScreeningPage() {
  const [stats, setStats] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [screenResults, setScreenResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchName, setSearchName] = useState('');
  const [searchAccountId, setSearchAccountId] = useState('');
  const [screening, setScreening] = useState(false);
  const [activeTab, setActiveTab] = useState('screen');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/v1/screening/stats').then(r => r.json()).then(b => b?.data || b).catch(() => null),
      apiFetch('/api/v1/screening/watchlist?limit=50').then(r => r.json()).then(b => b?.data || b).catch(() => null),
    ]).then(([statsData, wlData]) => {
      setStats(statsData);
      if (wlData?.entries) setWatchlist(wlData.entries);
      setLoading(false);
    });
  }, []);

  const handleScreen = async () => {
    if (!searchName.trim() && !searchAccountId.trim()) return;
    setScreening(true);
    try {
      const accountId = searchAccountId.trim() || `ACC_${Date.now()}`;
      const res = await apiFetch(`/api/v1/screening/account/${encodeURIComponent(accountId)}?name=${encodeURIComponent(searchName.trim())}`);
      const body = await res.json();
      const data = body?.data || body;
      setScreenResults(Array.isArray(data) ? data : data?.matches || [data]);
      toast.success('Screening complete');
    } catch (err) {
      toast.error('Screening failed: ' + (err.message || 'Unknown error'));
    } finally {
      setScreening(false);
    }
  };

  const handleRefreshUNSC = async () => {
    setRefreshing(true);
    try {
      const res = await apiFetch('/api/v1/screening/watchlist/refresh-unsc', { method: 'POST' });
      const body = await res.json();
      toast.success(`UNSC list refreshed: ${body?.data?.entries_added || 0} entries added`);
    } catch (err) {
      toast.error('UNSC refresh failed');
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) return (
    <div className="loading">
      <div className="spinner" />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, letterSpacing: '1px', color: '#4A5568' }}>LOADING SCREENING...</span>
    </div>
  );

  return (
    <div style={{ padding: '32px 36px', maxWidth: 1440, margin: '0 auto' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
          <h1 style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.5px', color: '#EDF2F7', margin: 0 }}>Screening</h1>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 10, color: '#818CF8', letterSpacing: '1.5px', textTransform: 'uppercase',
            background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', padding: '2px 8px', borderRadius: 4,
          }}>PEP / SANCTIONS</span>
        </div>
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#4A5568', letterSpacing: '0.5px' }}>
          // watchlist screening · pep checks · unsc sanctions · ofac
        </p>
      </motion.div>

      {/* Stats Row */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
          <StatCard label="Watchlist Entries" value={stats.total_entries || 0} color="#6366F1" icon={Database} index={0} />
          <StatCard label="Screens Today" value={stats.screens_today || 0} color="#22D3EE" icon={Search} index={1} />
          <StatCard label="Hits Found" value={stats.hits_today || 0} color="#F43F5E" icon={AlertTriangle} index={2} />
          <StatCard label="Sources" value={stats.source_count || 0} color="#A78BFA" icon={Shield} index={3} />
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 20 }}>
        {[
          { id: 'screen', label: 'Screen Account', icon: Search },
          { id: 'watchlist', label: 'Watchlist', icon: Database },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.5px', textTransform: 'uppercase',
              padding: '8px 16px', borderRadius: 6, border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
              background: activeTab === tab.id ? 'rgba(99,102,241,0.12)' : 'transparent',
              color: activeTab === tab.id ? '#818CF8' : 'var(--text-muted)',
              transition: 'all 0.2s',
            }}
          >
            <tab.icon size={12} />
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'screen' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          {/* Search Form */}
          <div style={{ ...cardStyle, marginBottom: 20 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 16, fontWeight: 700 }}>
              // Screen Against Watchlists
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-secondary)', marginBottom: 6, letterSpacing: '0.5px', textTransform: 'uppercase' }}>Name</label>
                <input
                  type="text" value={searchName} onChange={e => setSearchName(e.target.value)}
                  placeholder="Enter name to screen..."
                  style={{
                    width: '100%', padding: '10px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                    borderRadius: 8, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: 13, outline: 'none', boxSizing: 'border-box',
                  }}
                  onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                  onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  onKeyDown={e => e.key === 'Enter' && handleScreen()}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-secondary)', marginBottom: 6, letterSpacing: '0.5px', textTransform: 'uppercase' }}>Account ID</label>
                <input
                  type="text" value={searchAccountId} onChange={e => setSearchAccountId(e.target.value)}
                  placeholder="Account ID (optional)"
                  style={{
                    width: '100%', padding: '10px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                    borderRadius: 8, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: 13, outline: 'none', boxSizing: 'border-box',
                  }}
                  onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                  onBlur={e => e.target.style.borderColor = 'var(--border)'}
                />
              </div>
              <motion.button
                onClick={handleScreen}
                disabled={screening || (!searchName.trim() && !searchAccountId.trim())}
                className="btn btn-primary"
                style={{ padding: '10px 20px', fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                {screening ? <RefreshCw size={13} className="spinning" /> : <Search size={13} />}
                {screening ? 'Screening...' : 'Screen'}
              </motion.button>
            </div>
          </div>

          {/* Results */}
          <AnimatePresence>
            {screenResults.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.5px', textTransform: 'uppercase', marginBottom: 12, fontWeight: 700 }}>
                  // {screenResults.length} Result{screenResults.length !== 1 ? 's' : ''}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {screenResults.map((r, i) => <ScreenResult key={i} result={r} index={i} />)}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}

      {activeTab === 'watchlist' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          {/* Controls */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
            <motion.button
              onClick={handleRefreshUNSC}
              disabled={refreshing}
              className="btn btn-primary"
              style={{ padding: '8px 16px', fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <RefreshCw size={12} className={refreshing ? 'spinning' : ''} />
              {refreshing ? 'Refreshing...' : 'Refresh UNSC List'}
            </motion.button>
          </div>

          {/* Watchlist Table */}
          <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.5px', textTransform: 'uppercase', fontWeight: 700 }}>
                // Watchlist Entries ({watchlist.length})
              </span>
            </div>
            {/* Header */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', padding: '10px 20px', borderBottom: '1px solid rgba(255,255,255,0.04)', background: 'rgba(255,255,255,0.02)' }}>
              {['Name', 'Source', 'Type', 'Added'].map(h => (
                <div key={h} style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '1.2px', textTransform: 'uppercase', fontWeight: 700 }}>{h}</div>
              ))}
            </div>
            {/* Rows */}
            {watchlist.length === 0 ? (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>No watchlist entries loaded</div>
            ) : (
              watchlist.slice(0, 50).map((entry, i) => (
                <div key={i} style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', padding: '10px 20px', borderBottom: '1px solid rgba(255,255,255,0.03)', transition: 'background 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.04)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{entry.name || entry.entity_name || '—'}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{entry.source || '—'}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{entry.entity_type || entry.type || '—'}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{entry.added_at ? new Date(entry.added_at).toLocaleDateString() : '—'}</div>
                </div>
              ))
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}
