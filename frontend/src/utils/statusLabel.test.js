import { statusLabel } from './statusLabel';

test('statusLabel makes sentence case', () => {
  expect(statusLabel('UNDER_REVIEW')).toBe('Under review');
  expect(statusLabel('ALL')).toBe('All');
});

test('statusLabel keeps STR uppercase', () => {
  expect(statusLabel('STR_FILED')).toBe('STR filed');
});

test('statusLabel reads the disposition statuses as plain phrases', () => {
  expect(statusLabel('NO_FURTHER_ACTION')).toBe('No further action');
  expect(statusLabel('SUSPICION_CONFIRMED_ESCALATED')).toBe('Suspicion confirmed, escalated');
});
