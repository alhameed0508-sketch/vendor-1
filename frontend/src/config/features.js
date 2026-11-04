// Build-time switch. Core pages are always on; the rest ship only with REACT_APP_EXTRA_PAGES=true.
export const EXTRA_PAGES_ENABLED = process.env.REACT_APP_EXTRA_PAGES === 'true';

export const EXTRA_PATHS = ['/complaints', '/returns', '/analytics', '/compliance', '/risk-operations', '/data-import'];

export const isHiddenPath = pathname =>
  !EXTRA_PAGES_ENABLED && EXTRA_PATHS.some(p => pathname === p || pathname.startsWith(`${p}/`));
