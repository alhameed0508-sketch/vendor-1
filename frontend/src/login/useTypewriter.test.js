import { renderHook, act } from '@testing-library/react';
import useTypewriter from './useTypewriter';

const LINES = ['abc', 'xy'];
const TYPE_MS = 70;
const ERASE_MS = 35;
const HOLD_MS = 2200;

const setReducedMotion = matches => {
  window.matchMedia = jest.fn(() => ({ matches }));
};

beforeEach(() => {
  jest.useFakeTimers();
  setReducedMotion(false);
});

afterEach(() => {
  jest.useRealTimers();
  delete window.matchMedia;
});

// One act() per step: the next timer is only scheduled once React has re-rendered.
const advance = (ms, steps = 1) => {
  for (let i = 0; i < steps; i += 1) act(() => { jest.advanceTimersByTime(ms); });
};

describe('useTypewriter', () => {
  it('starts empty and types the first line one character at a time', () => {
    const { result } = renderHook(() => useTypewriter(LINES));
    expect(result.current).toBe('');
    advance(TYPE_MS);
    expect(result.current).toBe('a');
    advance(TYPE_MS, 2);
    expect(result.current).toBe('abc');
  });

  it('holds the finished line, then erases it', () => {
    const { result } = renderHook(() => useTypewriter(LINES));
    advance(TYPE_MS, 3);
    advance(HOLD_MS - 1);
    expect(result.current).toBe('abc');
    advance(1);
    advance(ERASE_MS);
    expect(result.current).toBe('ab');
  });

  it('moves on to the next line and wraps back to the first', () => {
    const { result } = renderHook(() => useTypewriter(LINES));
    advance(TYPE_MS, 3);
    advance(HOLD_MS);
    advance(ERASE_MS, 3);
    expect(result.current).toBe('');
    advance(ERASE_MS);
    advance(TYPE_MS);
    expect(result.current).toBe('x');
    advance(TYPE_MS);
    advance(HOLD_MS);
    advance(ERASE_MS, 3);
    advance(TYPE_MS);
    expect(result.current).toBe('a');
  });

  it('shows the first line still, with no timers, when the visitor prefers reduced motion', () => {
    setReducedMotion(true);
    const { result } = renderHook(() => useTypewriter(LINES));
    expect(result.current).toBe('abc');
    expect(jest.getTimerCount()).toBe(0);
  });

  it('stops its timer when it unmounts', () => {
    const { unmount } = renderHook(() => useTypewriter(LINES));
    unmount();
    expect(jest.getTimerCount()).toBe(0);
  });
});
