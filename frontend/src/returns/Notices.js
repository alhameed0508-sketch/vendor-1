import React from 'react';
import { formatClock } from './labels';

/** Shown when the service cannot be reached and the screen is drawn from the last good answer. */
export function StaleNotice({ at, onRetry }) {
  return (
    <p role="alert" className="rf-stale">
      We couldn't reach the signal service. Showing the last result from {formatClock(at)}.{' '}
      <button type="button" className="btn btn-ghost btn-sm" onClick={onRetry}>Retry</button>
    </p>
  );
}

/** Shown when there is nothing to fall back to. */
export function FailedNotice({ message, onRetry }) {
  return (
    <div role="alert" className="rf-empty">
      <p className="rf-error">{message}</p>
      <p>Nothing has been changed. Check that the service is running, then try again.</p>
      <button type="button" className="btn btn-ghost btn-sm" onClick={onRetry}>Retry</button>
    </div>
  );
}
