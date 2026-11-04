import { useCallback, useEffect, useReducer, useRef } from 'react';
import { apiFetch } from '../auth/api';
import { parseSse } from '../live_stream/sseParse';
import { RISK_BASE } from './riskApi';

const MAX_FEED = 200;

export const initialStreamState = { status: 'idle', decisions: [], error: null, provenance: null, counters: null };

export function riskStreamReducer(state, action) {
  switch (action.type) {
    case 'open':
      return { ...initialStreamState, status: 'connecting' };
    case 'event': {
      const { event } = action;
      if (event?.error) return { ...state, status: 'failed', error: event.error };
      if (!event?.decision) return state;
      const decisions = [{ ...event.decision, _source: event.source, _provenance: event.provenance },
        ...state.decisions].slice(0, MAX_FEED);
      return { ...state, status: 'streaming', decisions, provenance: event.provenance || state.provenance,
        counters: event.counters || state.counters };
    }
    case 'failed':
      return { ...state, status: 'failed', error: action.message };
    case 'closed':
      return { ...state, status: state.status === 'failed' ? 'failed' : 'ended' };
    case 'stopped':
      return { ...state, status: 'stopped' };
    default:
      return state;
  }
}

/**
 * Reads /risk/stream with fetch so the token travels in the Authorization header, never in the URL.
 * source 'demo' tails the shared engine's synthetic traffic; 'live' scores real public payments on a
 * private engine on the server.
 */
export default function useRiskStream({ source = 'demo', limit = 500 } = {}) {
  const [state, dispatch] = useReducer(riskStreamReducer, initialStreamState);
  const controllerRef = useRef(null);

  const abort = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    abort();
    dispatch({ type: 'stopped' });
  }, [abort]);

  const start = useCallback(async () => {
    abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    dispatch({ type: 'open' });
    try {
      const params = new URLSearchParams({ source, limit: String(limit) });
      const res = await apiFetch(`${RISK_BASE}/stream?${params}`, {
        signal: controller.signal,
        headers: { Accept: 'text/event-stream' },
      });
      if (!res.ok || !res.body) {
        let message = `stream request failed (${res.status})`;
        try {
          const body = await res.json();
          message = body?.error?.message || message;
        } catch { /* not JSON */ }
        throw new Error(message);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        // eslint-disable-next-line no-await-in-loop
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSse(buffer);
        buffer = parsed.rest;
        parsed.events.forEach((event) => dispatch({ type: 'event', event }));
      }
    } catch (err) {
      if (err && err.name === 'AbortError') return;
      if (controllerRef.current === controller) controllerRef.current = null;
      dispatch({ type: 'failed', message: err && err.message ? err.message : 'connection failed' });
      return;
    }
    if (controllerRef.current === controller) controllerRef.current = null;
    dispatch({ type: 'closed' });
  }, [source, limit, abort]);

  useEffect(() => abort, [abort]);

  return { state, start, stop };
}
