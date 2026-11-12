import React from 'react';

// A simple illustration per product, tinted by its id, so the catalogue does not read as a plain list.
function hueOf(seed) {
  let h = 0;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

export default function ProductArt({ category, seed }) {
  return (
    <div className="art" style={{ '--art': `hsl(${hueOf(seed)} 42% 46%)` }} aria-hidden="true">
      {category === 'headphones' ? (
        <svg viewBox="0 0 120 72">
          <path d="M34 46V38a26 26 0 0 1 52 0v8" />
          <rect className="fill" x="26" y="42" width="14" height="22" rx="6" />
          <rect className="fill" x="80" y="42" width="14" height="22" rx="6" />
        </svg>
      ) : (
        <svg viewBox="0 0 120 72">
          <rect x="30" y="10" width="60" height="40" rx="4" />
          <rect className="fill" x="35" y="15" width="50" height="30" rx="2" />
          <path d="M18 56h84l-6 7H24z" />
        </svg>
      )}
    </div>
  );
}
