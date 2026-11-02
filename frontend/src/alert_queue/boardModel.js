export const BOARD_COLUMNS = [
  { status: 'OPEN', label: 'Open' },
  { status: 'UNDER_REVIEW', label: 'Under Review' },
  { status: 'RESOLVED', label: 'Resolved' },
  { status: 'FALSE_POSITIVE', label: 'False Positive' },
  { status: 'NO_FURTHER_ACTION', label: 'No further action' },
  { status: 'SUSPICION_CONFIRMED_ESCALATED', label: 'Suspicion confirmed, escalated' },
  { status: 'STR_FILED', label: 'STR Filed' },
];

const KNOWN = new Set(BOARD_COLUMNS.map(c => c.status));

export function groupByStatus(alerts) {
  const groups = { OTHER: [] };
  BOARD_COLUMNS.forEach(c => { groups[c.status] = []; });
  alerts.forEach(a => {
    groups[KNOWN.has(a.status) ? a.status : 'OTHER'].push(a);
  });
  return groups;
}

const REASON_STATUSES = new Set(['NO_FURTHER_ACTION', 'SUSPICION_CONFIRMED_ESCALATED']);

export const requiresReason = toStatus => REASON_STATUSES.has(toStatus);

export const requiresApproval = toStatus => toStatus === 'STR_FILED';

export const canMove = (fromStatus, toStatus) => fromStatus !== toStatus;
