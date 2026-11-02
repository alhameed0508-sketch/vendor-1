import { useEffect, useState } from 'react';

const TYPE_MS = 70;
const ERASE_MS = 35;
const HOLD_MS = 2200;

const START = { line: 0, chars: 0, erasing: false };

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches);

/** The delay before the next step, and the state that step leads to. */
function nextStep(lines, { line, chars, erasing }) {
  if (!erasing && chars < lines[line].length) return [TYPE_MS, { line, chars: chars + 1, erasing }];
  if (!erasing) return [HOLD_MS, { line, chars, erasing: true }];
  if (chars > 0) return [ERASE_MS, { line, chars: chars - 1, erasing }];
  return [ERASE_MS, { line: (line + 1) % lines.length, chars: 0, erasing: false }];
}

/**
 * Types each line in turn, holds it, erases it, then moves to the next and wraps.
 * A visitor who prefers reduced motion gets the first line, still.
 * `lines` must keep the same identity between renders, so define it outside the component.
 */
export default function useTypewriter(lines) {
  const [still] = useState(prefersReducedMotion);
  const [state, setState] = useState(START);

  useEffect(() => {
    if (still) return undefined;
    const [delay, next] = nextStep(lines, state);
    const timer = setTimeout(() => setState(next), delay);
    return () => clearTimeout(timer);
  }, [state, lines, still]);

  return still ? lines[0] : lines[state.line].slice(0, state.chars);
}
