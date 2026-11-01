import fs from 'fs';
import path from 'path';

const SRC = path.join(__dirname, '..');
const BRAND_BLUE = /#(2563EB|3B82F6|1D4ED8|1E40AF)\b|rgba\(\s*(37,\s*99,\s*235|59,\s*130,\s*246)/i;

const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => {
  const p = path.join(dir, e.name);
  return e.isDirectory() ? walk(p) : [p];
});
const SCREEN_FILES = walk(SRC)
  .filter(f => f.endsWith('.js') && !f.endsWith('.test.js'))
  .map(f => path.relative(SRC, f));

test('guard regex matches the old brand blue', () => {
  expect(BRAND_BLUE.test('color: #2563EB')).toBe(true);
  expect(BRAND_BLUE.test('rgba(37,99,235,0.2)')).toBe(true);
  expect(BRAND_BLUE.test('var(--accent)')).toBe(false);
});

test.each(SCREEN_FILES)('%s has no brand-blue hex', file => {
  expect(fs.readFileSync(path.join(SRC, file), 'utf8')).not.toMatch(BRAND_BLUE);
});
