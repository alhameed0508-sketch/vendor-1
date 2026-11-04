import React from 'react';

// A symbol as well as a colour, so the status reads without colour vision.
const STATUS = {
  IMPLEMENTED: { label: 'Implemented', symbol: '●' },
  PARTIAL: { label: 'Partial', symbol: '◐' },
  PLANNED: { label: 'Planned', symbol: '○' },
};

export default function StatusBadge({ status }) {
  const { label, symbol } = STATUS[status] || STATUS.PLANNED;
  return (
    <span className={`status-badge status-badge--${(STATUS[status] ? status : 'PLANNED').toLowerCase()}`}>
      <span aria-hidden="true">{symbol}</span> {label}
    </span>
  );
}
