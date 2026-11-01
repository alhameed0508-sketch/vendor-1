import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, ChevronDown } from 'lucide-react';
import { GlassCard } from '../components/ui/GlassCard';
import { apiFetch } from '../auth/api';

const STATUS_COLORS = {
  active: 'var(--accent-green)',
  fallback: 'var(--accent-amber)',
  offline: 'var(--text-muted)',
};

function StatusBadge({ status }) {
  const label = status?.enabled ? status.provider : 'Template Fallback';
  const color = status?.enabled ? STATUS_COLORS.active : STATUS_COLORS.fallback;
  return (
    <span style={{
      fontSize: 12, fontFamily: 'var(--font-sans)', 
      padding: '2px 8px', borderRadius: 10,
      background: `${color}18`, color, border: `1px solid ${color}30`,
      textTransform: 'uppercase',
    }}>
      {status?.enabled ? 'GenAI' : 'Template'} · {label}
    </span>
  );
}

function MessageBubble({ role, content }) {
  const isUser = role === 'user';
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 10,
      }}
    >
      <div style={{
        maxWidth: '85%',
        padding: '10px 14px',
        borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
        background: isUser ? 'rgba(62,231,255,0.10)' : 'var(--bg-elevated)',
        border: `1px solid ${isUser ? 'rgba(62,231,255,0.20)' : 'var(--border)'}`,
        fontSize: 12,
        fontFamily: 'var(--font-sans)',
        color: 'var(--text-primary)',
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {content}
      </div>
    </motion.div>
  );
}

export default function InvestigationChat({ alertId, alertData }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [collapsed, setCollapsed] = useState(false);
  const scrollRef = useRef(null);

  // Fetch GenAI status on mount
  useEffect(() => {
    apiFetch('/api/v1/genai/status')
      .then(r => r.json())
      .then(body => setStatus(body?.data || body))
      .catch(err => {
        console.error('[InvestigationChat] GenAI status check failed:', err);
        setStatus({ enabled: false, provider: 'offline', fallback_active: true });
      });
  }, []);

  // Load initial suggestions
  useEffect(() => {
    if (alertData) {
      const severity = alertData.severity || '';
      const codes = alertData.reason_codes || [];
      const base = [
        severity === 'CRITICAL'
          ? 'Why is this alert classified as CRITICAL?'
          : 'What does the risk score mean for this alert?',
        'Explain the mule network structure in this cluster.',
        'What RBI regulations apply to this suspicious activity?',
        'What should I do as the next investigation step?',
        'How confident is MuleCatch in this detection?',
      ];
      if (codes.length > 0) {
        const first = codes[0].split(':')[0];
        base[1] = `Explain rule ${first} — why did it trigger?`;
      }
      setSuggestions(base);
    }
  }, [alertData]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async (text) => {
    if (!text.trim()) return;

    const userMsg = { role: 'user', content: text.trim() };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput('');
    setLoading(true);

    try {
      const res = await apiFetch('/api/v1/genai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text.trim(),
          alert_id: alertId,
          conversation_history: updatedMessages.map(m => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });
      const body = await res.json();
      const data = body?.data || body;

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.message || 'No response received.',
      }]);

      if (data.suggested_questions) {
        setSuggestions(data.suggested_questions);
      }
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Failed to get response. Please try again.',
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <GlassCard padding={0} hover={false} style={{ overflow: 'hidden' }}>
      {/* Header */}
      <button
        type="button"
        aria-expanded={!collapsed}
        style={{
          padding: '12px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
          background: 'none',
          border: 'none',
          borderBottom: '1px solid var(--border)',
          width: '100%',
          color: 'inherit',
        }}
        onClick={() => setCollapsed(!collapsed)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)',
            letterSpacing: '2px', textTransform: 'uppercase',
          }}>
            Ask MuleCatch AI
          </span>
          <StatusBadge status={status} />
        </div>
        <motion.span
          animate={{ rotate: collapsed ? 0 : 180 }}
          style={{ color: 'var(--text-muted)', display: 'flex' }}
        >
          <ChevronDown size={14} />
        </motion.span>
      </button>

      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {/* Messages area */}
            <div
              ref={scrollRef}
              style={{
                height: 300,
                overflowY: 'auto',
                padding: '16px 20px',
              }}
            >
              {messages.length === 0 && (
                <div style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  justifyContent: 'center', height: '100%', gap: 16,
                }}>
                  <div style={{ opacity: 0.08 }}><MessageSquare size={24} /></div>
                  <p style={{
                    fontSize: 12, fontFamily: 'var(--font-sans)',
                    color: 'var(--text-muted)', textAlign: 'center',
                  }}>
                    Ask questions about this alert, mule patterns, or RBI regulations.
                  </p>
                </div>
              )}
              {messages.map((msg, i) => (
                <MessageBubble key={i} role={msg.role} content={msg.content} />
              ))}
              {loading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  style={{
                    fontSize: 12, fontFamily: 'var(--font-sans)',
                    color: 'var(--text-muted)', padding: '8px 14px',
                  }}
                >
                  Thinking...
                </motion.div>
              )}
            </div>

            {/* Suggestions */}
            {messages.length === 0 && suggestions.length > 0 && (
              <div style={{
                padding: '0 20px 12px',
                display: 'flex', flexWrap: 'wrap', gap: 6,
              }}>
                {suggestions.map((q, i) => (
                  <motion.button
                    key={i}
                    className="btn btn-ghost"
                    style={{
                      fontSize: 10, padding: '5px 10px',
                      borderColor: 'rgba(62,231,255,0.15)',
                      color: 'var(--text-secondary)',
                    }}
                    onClick={() => sendMessage(q)}
                    whileHover={{ scale: 1.02, borderColor: 'rgba(62,231,255,0.4)' }}
                    whileTap={{ scale: 0.97 }}
                  >
                    {q}
                  </motion.button>
                ))}
              </div>
            )}

            {/* Input */}
            <div style={{
              padding: '12px 20px',
              borderTop: '1px solid var(--border)',
              display: 'flex', gap: 8,
            }}>
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about this alert..."
                aria-label="Ask a question about this alert"
                disabled={loading}
                style={{
                  flex: 1,
                  padding: '8px 14px',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-sans)',
                  fontSize: 12,
                  outline: 'none',
                }}
                onFocus={e => e.target.style.borderColor = 'var(--accent-cyan)'}
                onBlur={e => e.target.style.borderColor = 'var(--border)'}
              />
              <motion.button
                className="btn btn-primary"
                onClick={() => sendMessage(input)}
                disabled={loading || !input.trim()}
                style={{ padding: '8px 16px', fontSize: 11 }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
              >
                {loading ? '...' : 'Send'}
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </GlassCard>
  );
}
