import fs from 'fs';
import path from 'path';

const SRC = path.join(__dirname, '..');
// A raw hex or rgba() ignores the theme switch; these screens use App.css tokens instead.
const RAW_COLOUR = /#[0-9A-Fa-f]{3,8}\b|rgba?\(/;
const THEMED_FILES = [
  'benchmark/BenchmarkPage.js',
  'genai/InvestigationChat.js',
  'components/IndiaMap.js',
  'components/StatCard.js',
  'compliance_portal/CompliancePortal.js',
  'network/NetworkOverview.js',
  'network/RegionalStatsPanel.js',
  'roi_dashboard/ROIDashboard.js',
];

test('guard regex catches hex and rgba but not tokens', () => {
  expect(RAW_COLOUR.test("stroke: '#FB923C'")).toBe(true);
  expect(RAW_COLOUR.test("background: 'rgba(62,231,255,0.08)'")).toBe(true);
  expect(RAW_COLOUR.test("fill: 'var(--accent)'")).toBe(false);
  expect(RAW_COLOUR.test("fill: 'url(#prevGrad)'")).toBe(false);
});

test.each(THEMED_FILES)('%s takes every colour from theme tokens', file => {
  const lines = fs.readFileSync(path.join(SRC, file), 'utf8').split('\n');
  expect(lines.filter(line => RAW_COLOUR.test(line))).toEqual([]);
});
