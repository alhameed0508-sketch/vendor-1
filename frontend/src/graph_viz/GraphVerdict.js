import React from 'react';
import { formatAmount } from '../utils/formatAmount';

/** Plain verdict for the graph, with the few figures that back it up. */
export default function GraphVerdict({ verdict }) {
  const { headline, figures } = verdict;
  const items = [
    ['Accounts', figures.accounts],
    ['Flagged flow', formatAmount(figures.flaggedAmount)],
    ['Flagged transfers', figures.flaggedTransfers],
    ['Riskiest account',`${Math.round(figures.highestRisk * 100)}%`],
  ];
  return (
    <div className="graph-verdict">
      <h2 className="graph-verdict-title">{headline}</h2>
      <dl className="graph-figures">
        {items.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
