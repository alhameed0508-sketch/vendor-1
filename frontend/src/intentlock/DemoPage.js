import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useConfig } from './IntentLockApp';
import { SCENARIOS } from './scenarios';
import Icon from './icons';

export default function Demo() {
  const config = useConfig();
  const navigate = useNavigate();
  const scenarios = SCENARIOS.filter((s) => !s.needsDemoTools || config.demo_tools);
  return (
    <div className="stack" style={{ maxWidth: 900 }}>
      <div className="page-head"><p className="lede" style={{ margin: 0 }}>Each scenario sets up the same laptop request and takes you to the review step. You confirm it yourself, and a banner on each page says what to press next. Payments use PayPal Sandbox; no real money moves.</p></div>
      <section className="panel" aria-label="Scenarios">
        <div className="scenarios">
          {scenarios.map((sc, i) => (
            <div className="scenario-row" key={sc.id}>
              <span className="n">{i + 1}</span>
              <div><h2>{sc.title}</h2><p className="small muted">{sc.blurb}</p></div>
              <button className="btn primary" onClick={() => navigate(`/new?demo=${sc.id}`)}>Start<Icon name="arrow" size={16} /></button>
            </div>
          ))}
          {config.featured_receipt_path && (
            <div className="scenario-row">
              <span className="n">{scenarios.length + 1}</span>
              <div><h2>A real receipt</h2><p className="small muted">A completed PayPal Sandbox purchase: the instruction, every rule check, the capture and the verified webhook. Read-only; no login.</p></div>
              <Link className="btn" to={config.featured_receipt_path}>Open<Icon name="arrow" size={16} /></Link>
            </div>
          )}
        </div>
      </section>
      <p className="small muted">The dashboard and ledger update as soon as a scenario posts its proposals.</p>
    </div>
  );
}
