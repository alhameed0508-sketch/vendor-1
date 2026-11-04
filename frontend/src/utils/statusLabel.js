const LABELS = {
  STR_FILED: 'STR filed',
  SUSPICION_CONFIRMED_ESCALATED: 'Suspicion confirmed, escalated',
};

/** 'UNDER_REVIEW' -> 'Under review'; keeps 'STR filed' and 'ALL' readable. */
export const statusLabel = s =>
  LABELS[s] || s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, ' ');
