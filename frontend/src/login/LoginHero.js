import React from 'react';
import { Activity, Clock, Link2, Shield } from 'lucide-react';
import HeroGraphic from './HeroGraphic';
import useTypewriter from './useTypewriter';

const TAGLINES = [
  'Linking accounts through the money they move',
  'Scoring every cluster, with the reasons',
  'Chaining evidence so any edit shows',
  'Counting down every complaint deadline',
];

const FEATURES = [
  { icon: Shield, label: 'Role-based access' },
  { icon: Link2, label: 'Hash-chained evidence' },
  { icon: Clock, label: 'RBI complaint deadlines' },
];

export function BrandMark() {
  return <div className="login-mark" aria-hidden="true">MC</div>;
}

/** The left panel: what MuleCatch does, shown before anyone signs in. Hidden on narrow screens. */
export default function LoginHero() {
  const typed = useTypewriter(TAGLINES);

  return (
    <section className="login-hero" aria-labelledby="login-hero-title">
      <div>
        <div className="login-brand">
          <BrandMark />
          <div>
            <div className="login-brand__name">MuleCatch</div>
            <div className="login-brand__tag">Fraud Intelligence Platform</div>
          </div>
        </div>

        <h1 id="login-hero-title" className="login-hero__title">
          Trace mule accounts. Close fraud complaints on time.
        </h1>
        <p className="login-hero__lead">
          MuleCatch links accounts through the money they move, scores each cluster with reasons an analyst
          can read, and keeps a tamper-evident evidence chain for every fraud complaint, timed to the RBI deadlines.
        </p>

        <p className="login-tagline">
          <Activity size={14} aria-hidden="true" />
          <span className="sr-only">{TAGLINES.join('. ')}</span>
          <span aria-hidden="true">
            {typed}
            <span className="login-cursor" />
          </span>
        </p>
      </div>

      <HeroGraphic />

      <ul className="login-features" aria-label="What MuleCatch gives you">
        {FEATURES.map(({ icon: Icon, label }) => (
          <li key={label}>
            <Icon size={13} aria-hidden="true" />
            {label}
          </li>
        ))}
      </ul>
    </section>
  );
}
