import '@testing-library/jest-dom';

// Polyfill ResizeObserver for jsdom (required by cmdk)
global.ResizeObserver = class ResizeObserver {
  constructor(cb) { this._cb = cb; }
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Polyfill IntersectionObserver for jsdom (required by framer-motion useInView in AnimatedCounter)
global.IntersectionObserver = class IntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
