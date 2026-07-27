import { alertPath, isSafeInternalPath } from './safeNavigation';

describe('safe navigation', () => {
  test('encodes untrusted alert identifiers into a single route segment', () => {
    expect(alertPath('ALT\\//evil.example')).toBe('/alert/ALT%5C%2F%2Fevil.example');
  });

  test('accepts only local absolute paths without backslashes', () => {
    expect(isSafeInternalPath('/queue')).toBe(true);
    expect(isSafeInternalPath('//evil.example')).toBe(false);
    expect(isSafeInternalPath('/\\evil.example')).toBe(false);
    expect(isSafeInternalPath('https://evil.example')).toBe(false);
  });
});
