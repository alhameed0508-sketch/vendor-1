import { NAV_SECTIONS } from './navItems';

const paths = () => NAV_SECTIONS.flatMap(s => s.items).map(i => i.path);

test('platform pages come first in the navigation', () => {
  expect(NAV_SECTIONS[0].label).toBe('Platform');
  expect(NAV_SECTIONS[0].items.map(i => i.path)).toEqual(['/command-center', '/modules', '/investigations']);
});

test('the existing intelligence pages are still present', () => {
  expect(paths()).toEqual(expect.arrayContaining(['/', '/queue', '/network']));
});

test('every path appears once', () => {
  expect(new Set(paths()).size).toBe(paths().length);
});
