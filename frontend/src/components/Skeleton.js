import React from 'react';

export function Skeleton({ width, height, borderRadius = 4, style = {}, className = '' }) {
  return (
    <div
      className={`shimmer-bg ${className}`}
      style={{
        width: width || '100%',
        height: height || 16,
        borderRadius,
        background: 'linear-gradient(90deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.03) 100%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 2s linear infinite',
        ...style,
      }}
    />
  );
}

export function SkeletonCard({ style = {} }) {
  return (
    <div className="glass-card" style={{ textAlign: 'center', padding: 20, ...style }}>
      <Skeleton width={60} height={32} style={{ margin: '0 auto 8px' }} borderRadius={4} />
      <Skeleton width={80} height={10} style={{ margin: '0 auto' }} />
    </div>
  );
}

export function SkeletonTableRow({ columns = 9 }) {
  return (
    <tr>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} style={{ padding: '14px' }}>
          <Skeleton width={i === 0 ? 100 : i === 2 ? '80%' : 60} height={14} />
        </td>
      ))}
    </tr>
  );
}

export function SkeletonTable({ rows = 6, columns = 9 }) {
  return (
    <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
      <table className="data-table">
        <thead>
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i}><Skeleton width={60} height={10} /></th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <SkeletonTableRow key={i} columns={columns} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SkeletonGraph() {
  return (
    <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between' }}>
        <Skeleton width={200} height={14} />
        <Skeleton width={100} height={10} />
      </div>
      <div style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: 200, height: 200, borderRadius: '50%',
          background: 'linear-gradient(90deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0.06) 50%, rgba(255,255,255,0.02) 100%)',
          backgroundSize: '200% 100%',
          animation: 'shimmer 2s linear infinite',
        }} />
      </div>
    </div>
  );
}
