import { BOARD_COLUMNS, groupByStatus, requiresApproval, requiresReason, canMove } from './boardModel';

describe('boardModel', () => {
  it('has the seven columns in order', () => {
    expect(BOARD_COLUMNS.map(c => c.status)).toEqual([
      'OPEN', 'UNDER_REVIEW', 'RESOLVED', 'FALSE_POSITIVE', 'NO_FURTHER_ACTION',
      'SUSPICION_CONFIRMED_ESCALATED', 'STR_FILED',
    ]);
  });

  it('groups empty input into every column', () => {
    const g = groupByStatus([]);
    BOARD_COLUMNS.forEach(c => expect(g[c.status]).toEqual([]));
    expect(g.OTHER).toEqual([]);
  });

  it('puts unknown legacy statuses under OTHER', () => {
    const a = { alert_id: 'A1', status: 'ESCALATED' };
    const b = { alert_id: 'A2', status: 'OPEN' };
    const g = groupByStatus([a, b]);
    expect(g.OTHER).toEqual([a]);
    expect(g.OPEN).toEqual([b]);
  });

  it('requires approval only for STR_FILED', () => {
    expect(requiresApproval('STR_FILED')).toBe(true);
    ['OPEN', 'UNDER_REVIEW', 'RESOLVED', 'FALSE_POSITIVE'].forEach(s =>
      expect(requiresApproval(s)).toBe(false));
  });

  it('asks for a reason on both disposition statuses only', () => {
    ['NO_FURTHER_ACTION', 'SUSPICION_CONFIRMED_ESCALATED'].forEach(s =>
      expect(requiresReason(s)).toBe(true));
    ['OPEN', 'RESOLVED', 'FALSE_POSITIVE', 'STR_FILED'].forEach(s =>
      expect(requiresReason(s)).toBe(false));
  });

  it('cannot move to the same status', () => {
    expect(canMove('OPEN', 'OPEN')).toBe(false);
    expect(canMove('OPEN', 'RESOLVED')).toBe(true);
  });
});
