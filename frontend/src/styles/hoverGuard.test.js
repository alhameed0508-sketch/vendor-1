import fs from 'fs';
import path from 'path';

const CSS = fs.readFileSync(path.join(__dirname, '..', 'App.css'), 'utf8');

// On touch screens a tap leaves :hover stuck on, so hover styles only apply where a pointer can hover.
// Scrollbar thumbs are skipped: touch screens never show them.
function unguardedHoverSelectors(css) {
  const found = [];
  let guardDepth = null;
  let depth = 0;
  let selector = '';
  for (const char of css.replace(/\/\*[\s\S]*?\*\//g, '')) {
    if (char === '{') {
      if (guardDepth === null && /@media[^{]*\(hover:\s*hover\)/.test(selector)) guardDepth = depth;
      if (guardDepth === null && selector.includes(':hover') && !selector.includes('scrollbar')) found.push(selector.trim());
      depth += 1;
      selector = '';
    } else if (char === '}') {
      depth -= 1;
      if (guardDepth === depth) guardDepth = null;
      selector = '';
    } else if (char === ';') {
      selector = '';
    } else {
      selector += char;
    }
  }
  return found;
}

test('the scanner flags bare hover rules and accepts guarded ones', () => {
  expect(unguardedHoverSelectors('.a:hover { color: red; }')).toEqual(['.a:hover']);
  expect(unguardedHoverSelectors('@media (hover: hover) { .a:hover { color: red; } } .b { color: red; }')).toEqual([]);
});

test('every hover style in App.css is behind @media (hover: hover)', () => {
  expect(unguardedHoverSelectors(CSS)).toEqual([]);
});
