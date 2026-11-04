import React, { useEffect, useState } from 'react';
import { getNarrative } from './complaintsApi';

/** The case in plain English; every sentence links to the evidence it rests on. */
export default function Narrative({ complaintId, chainHead }) {
  const [narrative, setNarrative] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    getNarrative(complaintId)
      .then(n => { if (live) { setNarrative(n); setError(''); } })
      .catch(err => { if (live) setError(err.message); });
    return () => { live = false; };
  }, [complaintId, chainHead]);

  const source = narrative?.source === 'template'
    ? 'Built from the evidence.'
    : `Drafted by ${narrative?.source}; every sentence checked against the evidence.`;

  return (
    <section className="glass-card fc-card" aria-labelledby="fc-narrative-title">
      <h2 id="fc-narrative-title" className="section-title">Narrative</h2>
      {error && <p role="alert" className="fc-error">{error}</p>}
      {!narrative && !error && <p className="page-meta">Writing…</p>}
      {narrative && (
        <>
          <p className="page-meta">
            {source}
            {narrative.dropped > 0 && ` ${narrative.dropped} uncited sentence${narrative.dropped === 1 ? '' : 's'} removed.`}
          </p>
          <div className="fc-narrative">
            {narrative.sentences.map((s, i) => (
              <p key={i}>
                {s.text}{' '}
                {s.evidence.map(id => <a key={id} href={`#ev-${id}`} className="fc-chip fc-cite">{id}</a>)}
              </p>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
