import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchEntity } from './shellApi';
import './shell.css';

const CONFIDENCE = { VERIFIED: 'Verified', PROBABLE: 'Probable', POSSIBLE: 'Possible' };

function ModulePanel({ module }) {
  const { module_id: id, score, evidence } = module;
  return (
    <section className="premium-card entity-module">
      <header className="entity-module__head">
        <h2 className="entity-module__name">{id}</h2>
        <span className="data-value">{score == null ? 'no score' : score.toFixed(2)}</span>
      </header>
      <ul>{evidence.map(e => <li key={e}>{e}</li>)}</ul>
    </section>
  );
}

function LinkRow({ link }) {
  const { other, basis, confidence } = link;
  return (
    <li className="entity-link">
      <span className={`entity-link__confidence entity-link__confidence--${confidence.toLowerCase()}`}>
        {CONFIDENCE[confidence] || confidence}
      </span>
      <Link to={`/entities/${encodeURIComponent(other.entity_id)}`}>{other.entity_id}</Link>
      <span className="entity-link__basis">{basis}</span>
    </li>
  );
}

/** One account across modules: each module's own score and evidence, and how it links to other accounts. */
export default function EntityView() {
  const { entityId } = useParams();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setData(null);
    setFailed(false);
    fetchEntity(entityId).then(setData).catch(() => setFailed(true));
  }, [entityId]);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Account {entityId}</h1>
        <div className="page-meta">Each module reports on its own, with its own score.</div>
      </div>
      {failed && <div role="alert" className="shell-error">Could not load this account. It may not exist, or the API is down.</div>}
      {data && data.modules.length === 0 && <p>No module has flagged this account.</p>}
      {data && data.modules.map(m => <ModulePanel key={m.module_id} module={m} />)}
      {data && data.links.length > 0 && (
        <>
          <h2>Linked accounts</h2>
          <p className="page-meta">A possible link is a lead to check. It does not mean the accounts belong to one party.</p>
          <ul className="entity-links">{data.links.map(l => <LinkRow key={`${l.other.entity_id}${l.basis}`} link={l} />)}</ul>
        </>
      )}
    </div>
  );
}
