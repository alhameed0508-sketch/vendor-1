const load = flag => {
  const prev = process.env.REACT_APP_EXTRA_PAGES;
  if (flag === undefined) delete process.env.REACT_APP_EXTRA_PAGES;
  else process.env.REACT_APP_EXTRA_PAGES = flag;
  let mod;
  jest.isolateModules(() => {
    jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));
    mod = { features: require('./features'), nav: require('../components/navItems') };
  });
  if (prev === undefined) delete process.env.REACT_APP_EXTRA_PAGES;
  else process.env.REACT_APP_EXTRA_PAGES = prev;
  return mod;
};

const paths = nav => nav.NAV_SECTIONS.flatMap(s => s.items.map(i => i.path));

describe('extra pages flag', () => {
  it('is off unless REACT_APP_EXTRA_PAGES is exactly "true"', () => {
    expect(load(undefined).features.EXTRA_PAGES_ENABLED).toBe(false);
    expect(load('1').features.EXTRA_PAGES_ENABLED).toBe(false);
    expect(load('true').features.EXTRA_PAGES_ENABLED).toBe(true);
  });

  it('shows only the core pages when off', () => {
    expect(paths(load(undefined).nav)).toEqual(['/', '/queue', '/network', '/live', '/benchmarks']);
  });

  it('shows every page when on', () => {
    expect(paths(load('true').nav)).toEqual([
      '/', '/queue', '/network', '/live', '/complaints', '/analytics', '/compliance',
      '/risk-operations', '/data-import', '/benchmarks',
    ]);
  });

  it('lists the hidden route prefixes only when off', () => {
    expect(load(undefined).features.isHiddenPath('/compliance')).toBe(true);
    expect(load(undefined).features.isHiddenPath('/complaints/C-1')).toBe(true);
    expect(load(undefined).features.isHiddenPath('/queue')).toBe(false);
    expect(load('true').features.isHiddenPath('/compliance')).toBe(false);
  });
});
