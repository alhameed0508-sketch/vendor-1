import React from 'react';
import { statusLabel } from '../utils/statusLabel';

/**
 * One labelled group of filter buttons; the chosen one stays marked.
 * `activeClass` maps an option to the class that marks it when chosen, for options that carry a colour.
 */
export default function FilterGroup({ label, options, value, onChange, activeClass = {} }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      <span className="filter-label" aria-hidden="true">{label}</span>
      {options.map(option => (
        <button
          key={option}
          type="button"
          aria-pressed={value === option}
          className={`filter-tab ${value === option ? (activeClass[option] || 'active') : ''}`}
          onClick={() => onChange(option)}
        >
          {statusLabel(option)}
        </button>
      ))}
    </div>
  );
}
