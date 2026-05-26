import '@testing-library/jest-dom';

// Polyfill ResizeObserver for jsdom (required by cmdk)
global.ResizeObserver = class ResizeObserver {
  constructor(cb) { this._cb = cb; }
  observe() {}
  unobserve() {}
  disconnect() {}
};
