/** 'UNDER_REVIEW' -> 'Under review'; keeps 'STR filed' and 'ALL' readable. */
export const statusLabel = s =>
  s === 'STR_FILED' ? 'STR filed' : s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, ' ');
