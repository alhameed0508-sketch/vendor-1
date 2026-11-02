import { statusLabel } from './statusLabel';

test('statusLabel makes sentence case', () => {
  expect(statusLabel('UNDER_REVIEW')).toBe('Under review');
  expect(statusLabel('ALL')).toBe('All');
});

test('statusLabel keeps STR uppercase', () => {
  expect(statusLabel('STR_FILED')).toBe('STR filed');
});
