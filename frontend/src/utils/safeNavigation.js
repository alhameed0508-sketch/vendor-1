export function alertPath(alertId) {
  return `/alert/${encodeURIComponent(String(alertId ?? ''))}`;
}

export function isSafeInternalPath(path) {
  return (
    typeof path === 'string'
    && path.startsWith('/')
    && !path.startsWith('//')
    && !path.includes('\\')
    && !path.includes('\0')
  );
}
