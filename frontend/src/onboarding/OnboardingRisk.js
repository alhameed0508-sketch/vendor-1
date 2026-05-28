import React, { useState, useEffect } from 'react';
import { GlassCardMetric } from '../components/ui/GlassCard';
import { AnimateIn } from '../components/motion/AnimateIn';
import { StaggerContainer, StaggerItem } from '../components/motion/StaggerContainer';
import { apiFetch } from '../auth/api';
import { DEFAULT_FORM } from './AssessmentForm';
import AssessmentForm from './AssessmentForm';
import AssessmentResult from './AssessmentResult';
import AssessmentTable from './AssessmentTable';

export default function OnboardingRisk() {
  const [form, setForm] = useState({ ...DEFAULT_FORM });
  const [result, setResult] = useState(null);
  const [assessments, setAssessments] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [aiExplanation, setAiExplanation] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);

  // Load stats and recent assessments
  useEffect(() => {
    apiFetch('/api/v1/onboarding/stats')
      .then(r => r.json())
      .then(body => setStats(body?.data || body))
      .catch(err => console.error('[Onboarding] Stats fetch failed:', err));

    apiFetch('/api/v1/onboarding/assessments?limit=10')
      .then(r => r.json())
      .then(body => {
        const data = body?.data || body;
        setAssessments(data.assessments || []);
      })
      .catch(err => console.error('[Onboarding] Assessments fetch failed:', err));
  }, []);

  const handleFormChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/onboarding/assess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const body = await res.json();
      const data = body?.data || body;
      setResult(data);
      // Refresh assessments & stats
      setAssessments(prev => [data, ...prev].slice(0, 10));
      apiFetch('/api/v1/onboarding/stats')
        .then(r => r.json())
        .then(body2 => setStats(body2?.data || body2))
        .catch(err => console.error('[Onboarding] Stats refresh failed:', err));
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleExplainWithAI = async () => {
    if (!result || result.error) return;
    setAiLoading(true);
    setAiExplanation(null);
    try {
      const res = await apiFetch('/api/v1/genai/explain-onboarding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assessment_data: result }),
      });
      const body = await res.json();
      const data = body?.data || body;
      setAiExplanation(data.message || data);
    } catch {
      setAiExplanation('Failed to generate AI explanation. Please try again.');
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div style={{ padding: '32px 32px 48px', maxWidth: 1400, margin: '0 auto' }}>

      {/* Page Header */}
      <AnimateIn>
        <div style={{ marginBottom: 28 }}>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--accent-cyan)',
            letterSpacing: '3px', textTransform: 'uppercase', marginBottom: 8, opacity: 0.8,
          }}>
            IOB &middot; Onboarding Risk Assessment
          </div>
          <h1 className="gradient-text" style={{
            fontFamily: 'var(--font-sans)', fontSize: 28, fontWeight: 700,
            letterSpacing: '-0.5px', margin: 0,
          }}>
            Onboarding Risk Scorer
          </h1>
          <p style={{
            fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)',
            marginTop: 6, letterSpacing: '0.3px',
          }}>
            // Assess mule risk at point of account onboarding &mdash; 14-signal scoring engine
          </p>
        </div>
      </AnimateIn>

      {/* Stats Cards */}
      <StaggerContainer style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        <StaggerItem>
          <GlassCardMetric label="Total Assessed" value={stats?.total_assessed || 0} color="var(--accent-cyan)" />
        </StaggerItem>
        <StaggerItem>
          <GlassCardMetric label="High-Risk Flagged" value={stats?.high_risk_flagged || 0} color="var(--critical)" />
        </StaggerItem>
        <StaggerItem>
          <GlassCardMetric label="Auto-Blocked" value={stats?.auto_blocked || 0} color="var(--accent-amber)" />
        </StaggerItem>
        <StaggerItem>
          <GlassCardMetric label="Pass Rate" value={`${((stats?.pass_rate || 1) * 100).toFixed(0)}%`} color="var(--accent-green)" />
        </StaggerItem>
      </StaggerContainer>

      {/* Main Grid: Form + Result */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        <AssessmentForm
          form={form}
          onFormChange={handleFormChange}
          onSubmit={handleSubmit}
          loading={loading}
        />
        <AssessmentResult
          result={result}
          aiExplanation={aiExplanation}
          aiLoading={aiLoading}
          onExplainWithAI={handleExplainWithAI}
        />
      </div>

      {/* Recent Assessments Table */}
      <AssessmentTable assessments={assessments} />
    </div>
  );
}
