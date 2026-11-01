import fs from 'fs';
import path from 'path';
import { contrastRatio } from './contrast';

const read = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');
const appCss = read('App.css');
const indexCss = read('index.css');

const darkBlock = appCss.slice(appCss.indexOf(':root,'), appCss.indexOf('html[data-theme="light"]'));
const lightBlock = appCss.slice(appCss.indexOf('html[data-theme="light"]'));
const token = (block, name) => {
  const m = block.match(new RegExp(`${name}:\\s*([^;]+);`));
  return m ? m[1].trim() : undefined;
};
const ruleBody = selector => {
  const m = appCss.match(new RegExp(`^${selector.replace(/[.:]/g, '\\$&')} \\{[^}]*\\}`, 'm'));
  return m ? m[0] : '';
};

test('contrastRatio black on white is 21', () => {
  expect(contrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 0);
});

test('dark accent tokens match spec', () => {
  expect(token(darkBlock, '--accent')).toBe('#10B981');
  expect(token(darkBlock, '--accent-hover')).toBe('#34D399');
  expect(token(darkBlock, '--on-accent')).toBe('#04261A');
});

test('light accent tokens match spec', () => {
  expect(token(lightBlock, '--accent')).toBe('#047857');
  expect(token(lightBlock, '--accent-hover')).toBe('#065F46');
  expect(token(lightBlock, '--on-accent')).toBe('#FFFFFF');
});

test('on-accent text meets 4.5:1 in both themes', () => {
  [darkBlock, lightBlock].forEach(b => {
    expect(contrastRatio(token(b, '--on-accent'), token(b, '--accent'))).toBeGreaterThanOrEqual(4.5);
  });
});

test('text tokens meet 4.5:1 on their theme backgrounds', () => {
  const pairs = [[darkBlock, '#0A0A0A'], [lightBlock, token(lightBlock, '--bg-surface')], [lightBlock, token(lightBlock, '--bg-card')]];
  pairs.forEach(([b, bg]) => {
    ['--text-secondary', '--text-muted'].forEach(t => {
      expect(contrastRatio(token(b, t), bg)).toBeGreaterThanOrEqual(4.5);
    });
  });
});

test('emerald aliases follow the accent', () => {
  [darkBlock, lightBlock].forEach(b => {
    expect(token(b, '--emerald')).toMatch(/var\(--accent\)|#10B981|#047857/);
    expect(b).not.toMatch(/--emerald[^:]*:\s*[^;]*(#2563EB|#3B82F6|37,\s*99,\s*235)/i);
  });
});

test('fonts: Inter + JetBrains Mono, no Space Grotesk', () => {
  expect(indexCss).toMatch(/Inter/);
  expect(indexCss).toMatch(/JetBrains\+Mono/);
  expect(indexCss).not.toMatch(/Space\+Grotesk/);
  expect(indexCss).toMatch(/display=swap/);
  expect(token(darkBlock, '--font-sans')).toMatch(/sans-serif$/);
  expect(token(darkBlock, '--font-mono')).toMatch(/monospace$/);
  expect(token(darkBlock, '--font-display')).not.toMatch(/Space Grotesk/);
});

test('focus ring uses accent token', () => {
  expect(ruleBody(':focus-visible')).toMatch(/var\(--focus-ring\)|var\(--accent\)/);
});

test('btn-primary uses accent and on-accent tokens', () => {
  const body = ruleBody('.btn-primary');
  expect(body).toMatch(/var\(--accent\)/);
  expect(body).toMatch(/var\(--on-accent\)/);
});

test('no brand-blue left in App.css outside the blue data tokens', () => {
  const stripped = appCss.replace(/--(accent-blue|cyan|cyan-dim|accent-cyan):[^;]+;/g, '');
  expect(stripped).not.toMatch(/#2563EB|rgba\(\s*37,\s*99,\s*235/i);
});

test('low and medium badges do not use the brand accent', () => {
  [/\.badge-low[^{]*\{[^}]*\}/i, /\.badge-MEDIUM[^{]*\{[^}]*\}/].forEach(re => {
    const m = appCss.match(re);
    expect(m).not.toBeNull();
    expect(m[0]).not.toMatch(/--accent-(primary|secondary|dim)|--emerald/);
  });
});

test('interactive classes set cursor pointer', () => {
  ['.btn', '.filter-tab', '.sidebar-link'].forEach(sel => {
    expect(ruleBody(sel)).toMatch(/cursor:\s*pointer/);
  });
});

test('reduced motion block exists', () => {
  expect(appCss).toMatch(/prefers-reduced-motion:\s*reduce/);
});
