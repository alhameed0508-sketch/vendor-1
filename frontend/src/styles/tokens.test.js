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

test('dark accent tokens match the emerald vault spec', () => {
  expect(token(darkBlock, '--accent')).toBe('#34C79A');
  expect(token(darkBlock, '--accent-hover')).toBe('#5ED6AF');
  expect(token(darkBlock, '--on-accent')).toBe('#06281D');
});

test('vault neutrals: green-biased base in both themes, no navy left over', () => {
  expect(token(darkBlock, '--bg-base')).toBe('#0B1311');
  expect(token(lightBlock, '--bg-base')).toBe('#F5F8F6');
  expect(darkBlock).not.toMatch(/rgba\(\s*17,\s*24,\s*39/);
  expect(token(darkBlock, '--chart-axis')).not.toBe('#1E2D45');
});

test('severity colours meet 4.5:1 as text in both themes', () => {
  ['--critical', '--high', '--medium'].forEach(t => {
    expect(contrastRatio(token(lightBlock, t), '#FFFFFF')).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(token(darkBlock, t), token(darkBlock, '--bg-base'))).toBeGreaterThanOrEqual(4.5);
  });
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
  const pairs = [[darkBlock, token(darkBlock, '--bg-base')], [lightBlock, token(lightBlock, '--bg-surface')], [lightBlock, token(lightBlock, '--bg-card')]];
  pairs.forEach(([b, bg]) => {
    ['--text-secondary', '--text-muted', '--text-faint'].forEach(t => {
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

test('fonts: IBM Plex Sans UI, Bodoni Moda display, IBM Plex Mono code', () => {
  expect(indexCss).toMatch(/IBM\+Plex\+Sans/);
  expect(indexCss).toMatch(/Bodoni\+Moda/);
  expect(indexCss).toMatch(/IBM\+Plex\+Mono/);
  expect(indexCss).not.toMatch(/family=Inter|JetBrains\+Mono/);
  expect(indexCss).toMatch(/display=swap/);
  expect(token(darkBlock, '--font-sans')).toMatch(/^'IBM Plex Sans'.*sans-serif$/);
  expect(token(darkBlock, '--font-display')).toMatch(/^'Bodoni Moda'.*serif$/);
  expect(token(darkBlock, '--font-mono')).toMatch(/^'IBM Plex Mono'.*monospace$/);
});

test('display serif is limited to page titles and headline numbers', () => {
  const headings = appCss.match(/^h1, h2, h3, h4 \{[^}]*\}/m)[0];
  expect(headings).toMatch(/var\(--font-sans\)/);
  expect(appCss).toMatch(/\.page-header h1[^{]*\{[^}]*var\(--font-display\)/);
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

const SURFACES = ['--bg-base', '--bg-surface', '--bg-elevated'];
const THEMES = [['dark', darkBlock], ['light', lightBlock]];

test.each(THEMES)('accent and muted text meet 4.5:1 on every %s surface', (_, b) => {
  const short = SURFACES.flatMap(bg => ['--accent', '--text-muted', '--critical', '--high', '--medium']
    .map(t => [t, bg, Number(contrastRatio(token(b, t), token(b, bg)).toFixed(2))]))
    .filter(([, , ratio]) => ratio < 4.5);
  expect(short).toEqual([]);
});

// Graph nodes and map markers carry meaning, so WCAG 1.4.11 asks 3:1 against the canvas.
test.each(THEMES)('graph role colours meet 3:1 on the %s canvas', (_, b) => {
  const short = ['--role-source', '--role-aggregator', '--role-mule', '--role-neutral']
    .map(t => [t, Number(contrastRatio(token(b, t), token(b, '--bg-base')).toFixed(2))])
    .filter(([, ratio]) => ratio < 3);
  expect(short).toEqual([]);
});
