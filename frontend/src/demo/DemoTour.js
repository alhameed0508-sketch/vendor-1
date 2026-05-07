import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import gsap from 'gsap';

const TOUR_STEPS = [
  {
    route: '/',
    target: '.data-table',
    duration: 4000,
    narration: 'MuleCatch monitors real-time UPI transactions and detects mule account networks using a 6-layer detection pipeline.',
  },
  {
    route: null,
    action: 'clickCriticalAlert',
    duration: 2000,
    narration: 'Each alert is a cluster of connected accounts. Severity is scored by Louvain community detection + smurf-weighting + centrality analysis.',
  },
  {
    route: null,
    target: '.network-graph-container',
    duration: 6000,
    narration: 'Animated money flow particles show fund movement in real-time. Node size reflects PageRank; betweenness centrality identifies network bottlenecks.',
  },
  {
    route: null,
    target: '.reason-codes-panel',
    duration: 4000,
    narration: "20 detection rules aligned with RBI MuleHunter.AI patterns. Every alert ships with explainable reason codes for auditable decisions.",
  },
  {
    route: null,
    target: '.investigator-workspace',
    duration: 3500,
    narration: 'Investigators can escalate to supervisors, annotate findings, and provide feedback that triggers active model retraining.',
  },
  {
    route: '/roi',
    target: '.kpi-grid',
    duration: 5000,
    narration: 'Quantified ROI: 75% faster investigations, 40% fewer false positives, real-time fraud prevention metrics with active learning loop.',
  },
  {
    route: '/compliance',
    target: null,
    duration: 4000,
    narration: 'One-click PDF STR export for FIU-IND filing. Full audit trail tracks every investigator action for RBI compliance.',
  },
  {
    route: '/',
    target: null,
    duration: 3000,
    narration: null,
    finale: true,
  },
];

const ARCHITECTURE_LAYERS = [
  { layer: 'Layer 6', name: 'Investigator Dashboard + Escalation Workflow', color: '#06b6d4' },
  { layer: 'Layer 5', name: 'Explainability + Narrative + PDF STR Export', color: '#a78bfa' },
  { layer: 'Layer 4', name: 'Active Learning + Feedback Retrain Loop', color: '#ec4899' },
  { layer: 'Layer 3', name: 'Graph Intelligence (Louvain + Centrality + GNN)', color: '#f59e0b' },
  { layer: 'Layer 2', name: 'Smurf-Weighting + Behavioral Baseline', color: '#3b82f6' },
  { layer: 'Layer 1', name: 'UPI Transaction Ingestion (Kafka-ready)', color: '#10b981' },
];

export default function DemoTour({ onEnd }) {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(true);
  const [progress, setProgress] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();

  const endTour = useCallback(() => {
    sessionStorage.setItem('demoCompleted', 'true');
    setVisible(false);
    setTimeout(() => onEnd(), 300);
  }, [onEnd]);

  // Navigate to step route
  useEffect(() => {
    const current = TOUR_STEPS[step];
    if (!current) { endTour(); return; }

    if (current.action === 'clickCriticalAlert') {
      fetch('/api/v1/alerts?limit=10')
        .then(r => r.json())
        .then(body => {
          const data = body?.data || body;
          const critical = (data.alerts || []).find(a => a.severity === 'CRITICAL') || (data.alerts || [])[0];
          if (critical) navigate(`/alert/${critical.alert_id}`);
        })
        .catch(() => {});
    } else if (current.route && location.pathname !== current.route) {
      navigate(current.route);
    }
  }, [step]); // eslint-disable-line

  // Auto-advance timer
  useEffect(() => {
    const current = TOUR_STEPS[step];
    if (!current) return;

    const dur = current.duration;
    const startTime = Date.now();

    const progressInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      setProgress(Math.min((elapsed / dur) * 100, 100));
    }, 30);

    const timer = setTimeout(() => {
      if (step < TOUR_STEPS.length - 1) {
        setStep(s => s + 1);
        setProgress(0);
      } else {
        endTour();
      }
    }, dur);

    return () => {
      clearTimeout(timer);
      clearInterval(progressInterval);
    };
  }, [step, endTour]);

  if (!visible) return null;

  const current = TOUR_STEPS[step];

  // Finale overlay
  if (current?.finale) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
        style={{
          position: 'fixed', inset: 0, zIndex: 10000,
          background: 'rgba(10,12,16,0.95)',
          backdropFilter: 'blur(20px)',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
        }}
      >
        <motion.div
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 200, damping: 20 }}
          style={{ fontSize: 48, color: '#06b6d4', marginBottom: 16, textShadow: '0 0 40px rgba(6,182,212,0.4)' }}
        >
          ⬡
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          style={{
            fontSize: 28, fontWeight: 800, fontFamily: "'Syne', sans-serif",
            color: '#e8edf5', marginBottom: 12,
          }}
        >
          MuleCatch
        </motion.div>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: 14,
            color: '#8895b0', marginBottom: 24,
          }}
        >
          6-Layer Detection Engine  |  Built for IOB  |  RBI MuleHunter.AI Compliant
        </motion.div>

        {/* 4-layer architecture with GSAP stagger */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: 400 }}>
          {ARCHITECTURE_LAYERS.map((l, i) => (
            <motion.div
              key={l.layer}
              initial={{ opacity: 0, x: -40 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 + i * 0.12, type: 'spring', stiffness: 200, damping: 25 }}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 16px',
                border: `1px solid ${l.color}40`,
                borderLeft: `3px solid ${l.color}`,
                borderRadius: '0 6px 6px 0',
                background: `${l.color}08`,
                backdropFilter: 'blur(4px)',
              }}
            >
              <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: l.color }}>{l.layer}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#e8edf5' }}>{l.name}</span>
            </motion.div>
          ))}
        </div>

        <motion.button
          onClick={endTour}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.9 }}
          whileHover={{ scale: 1.05, boxShadow: '0 0 24px rgba(6,182,212,0.3)' }}
          whileTap={{ scale: 0.97 }}
          style={{
            marginTop: 32, padding: '10px 28px',
            background: '#06b6d4', color: '#000',
            border: 'none', borderRadius: 6,
            fontWeight: 700, fontSize: 14, cursor: 'pointer',
            fontFamily: "'Syne', sans-serif",
          }}
        >
          Explore Dashboard
        </motion.button>
      </motion.div>
    );
  }

  return (
    <>
      {/* Semi-transparent overlay */}
      <div style={{
        position: 'fixed', inset: 0, zIndex: 9998,
        background: 'rgba(10,12,16,0.3)',
        pointerEvents: 'none',
      }} />

      {/* Bottom narration bar */}
      <motion.div
        initial={{ y: 100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        style={{
          position: 'fixed', bottom: 0, left: 0, right: 0,
          zIndex: 10000,
          background: 'rgba(17,21,32,0.92)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderTop: '1px solid rgba(6,182,212,0.2)',
          padding: '16px 32px 20px',
        }}
      >
        {/* Progress bar */}
        <motion.div
          style={{
            position: 'absolute', top: 0, left: 0,
            height: 2,
            background: 'linear-gradient(90deg, #06b6d4, #08d0ef)',
          }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.1, ease: 'linear' }}
        />

        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          {/* Step indicator dots */}
          <div style={{ display: 'flex', gap: 6 }}>
            {TOUR_STEPS.map((_, i) => (
              <motion.div
                key={i}
                layoutId={i === step ? 'active-dot' : undefined}
                animate={{
                  width: i === step ? 20 : 8,
                  background: i === step ? '#06b6d4' : i < step ? 'rgba(6,182,212,0.5)' : '#2a3550',
                }}
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                style={{
                  height: 8,
                  borderRadius: 4,
                }}
              />
            ))}
          </div>

          {/* Narration text with crossfade */}
          <div style={{ flex: 1, position: 'relative', minHeight: 24 }}>
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                transition={{ duration: 0.2 }}
                style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: 13,
                  color: '#e8edf5',
                  lineHeight: 1.6,
                }}
              >
                {current?.narration || ''}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Step counter & skip */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 11,
              color: '#4a5568',
            }}>
              {step + 1}/{TOUR_STEPS.length}
            </span>
            <motion.button
              onClick={endTour}
              whileHover={{ borderColor: 'rgba(255,255,255,0.2)', color: '#e8edf5' }}
              whileTap={{ scale: 0.95 }}
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: '#8895b0',
                padding: '6px 14px',
                borderRadius: 4,
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: 11,
                cursor: 'pointer',
                backdropFilter: 'blur(4px)',
              }}
            >
              Skip Tour
            </motion.button>
          </div>
        </div>
      </motion.div>
    </>
  );
}
