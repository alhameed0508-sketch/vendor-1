import { useCallback, useEffect, useReducer, useRef } from 'react';
import { apiFetch } from '../auth/api';
import { initialState, streamReducer } from './streamReducer';
import { parseSse } from './sseParse';

const STREAM_PATH = '/api/v1/score/stream';

/**
 * Reads the stream (synthetic replay, real public payments with source 'live', or live stock-exchange
 * trades with source 'market') with fetch,
 * so the access token travels in the Authorization header and never in the URL.
 * No auto-reconnect: a reconnect would restart the replay from the beginning.
 */
export default function useScoreStream({ limit = 300, rate = 5, source = 'demo' } = {}) {
  const [state, dispatch] = useReducer(streamReducer, initialState);
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
      const params = new URLSearchParams({ limit: String(limit), rate: String(rate) });
      if (source !== 'demo') params.set('source', source);
      const res = await apiFetch(`${STREAM_PATH}?${params}`, {
        signal: controller.signal,
        headers: { Accept: 'text/event-stream' },
      });
      if (!res.ok || !res.body) throw new Error(`stream request failed (${res.status})`);
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
      dispatch({ type: 'failed', message: `Stream unavailable: ${err && err.message ? err.message : 'connection failed'}` });
      return;
    }
    if (controllerRef.current === controller) controllerRef.current = null;
    dispatch({ type: 'closed' });
  }, [limit, rate, source, abort]);

  useEffect(() => abort, [abort]);

  const review = useCallback((caseId, decision) => dispatch({ type: 'review', caseId, decision }), []);

  return { state, start, stop, review };
}
