/* Shared helpers for the three ledger templates. */
(function () {
  const L = window.LEDGER, S = window.SPEC;
  const inr = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 0 });
  const inr0 = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });
  const H = {
    L, S,
    rupees: (v, frac = false) => (v == null ? '—' : (v < 0 ? '−₹' : '₹') + (frac ? inr : inr0).format(Math.abs(v))),
    lakh: (v) => (v == null ? '—' : v >= 1e7 ? `₹${(v / 1e7).toFixed(2)} Cr` : `₹${(v / 1e5).toFixed(2)} L`),
    int: (v) => inr0.format(v || 0),
    pct: (v, d = 1) => (v == null ? '—' : `${(v * 100).toFixed(d)}%`),
    score: (v) => (v ? v.toFixed(3) : '0.000'),
    short: (id) => (id.length > 12 ? id.slice(0, 10) + '…' : id),
    esc: (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])),
    fill: (t) => String(t)
      .replace('{rows}', H.int(L.batch.rows)).replace('{accounts}', H.int(L.batch.accounts))
      .replace('{negRows}', H.int(L.batch.negative_balance.rows)).replace('{links}', H.int(L.engine.internal_links))
      .replace('{normalized}', H.int(L.engine.normalized_transactions))
      .replace('{scoreRange}', L.engine.score_range ? L.engine.score_range.map((v) => v.toFixed(3)).join(' – ') : 'no rings')
      .replace('{complicit}', L.engine.classification_counts.COMPLICIT).replace('{exploited}', L.engine.classification_counts.EXPLOITED)
      .replace('{total}', H.rupees(L.batch.total_amount)),
    /* spec row for a scorer driver key */
    featureFor: (key) => S.features.find((f) => f.drivers.includes(key)),
    standardsFor: (acc) => {
      const ids = new Set();
      acc.drivers.forEach((d) => (H.featureFor(d.feature)?.standard || []).forEach((s) => ids.add(s)));
      return [...ids];
    },
    shell: (active) => `
      <aside class="side" aria-label="Main">
        <div class="side__brand"><span class="side__mark"></span>MuleCatch</div>
        ${['Command center', 'Assessment ledger', 'Detection modules', 'Investigations', 'Alert queue', 'Live stream', 'Risk engine', 'Data import', 'Compliance']
          .map((n) => `<div class="side__item${n === active ? ' side__item--on' : ''}">${n}</div>`).join('')}
      </aside>
      <header class="top"><span>Workspace</span><span>/</span><span class="top__crumb">${active}</span><span class="top__spacer"></span><span class="top__user">investigator</span></header>`,
    sourceChip: () => L.source.kind === 'sample'
      ? `<span class="chip chip--synthetic" title="sha256 ${L.source.sha256}">Synthetic sample · ${H.esc(L.source.filename)}</span>`
      : `<span class="chip" title="sha256 ${L.source.sha256}">Uploaded · ${H.esc(L.source.filename)}</span>`,
    genuineLine: () => L.genuine_check
      ? `${L.genuine_check.genuine_flagged} of ${L.genuine_check.genuine_accounts} genuine accounts flagged · ${L.genuine_check.ring_flagged}/${L.genuine_check.planted_ring} planted ring found (synthetic data)`
      : 'File has no mule / genuine labels: false-alert rate not measurable',
  };
  window.H = H;
})();
