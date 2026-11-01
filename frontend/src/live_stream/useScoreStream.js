import { useCallback, useEffect, useReducer, useRef } from 'react';
import { resolveUrl, getToken } from '../auth/api';
import { initialState, streamReducer } from './streamReducer';

const STREAM_PATH = '/api/v1/score/stream';

/**
 * Connects to the payment replay stream (demo mode only on the backend).
 * The server closes the stream when the replay ends; we do not auto-reconnect,
 * because a reconnect would restart the replay from the beginning.
 */
export default function useScoreStream({ limit = 300, rate = 5 } = {}) {
  const [state, dispatch] = useReducer(streamReducer, initialState);
  const sourceRef = useRef(null);

  const stop = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    stop();
    const params = new URLSearchParams({ limit: String(limit), rate: String(rate) });
    const token = getToken();
    if (token) params.set('token', token);
    const source = new EventSource(resolveUrl(`${STREAM_PATH}?${params}`));
    sourceRef.current = source;
    dispatch({ type: 'open' });
    source.onmessage = (message) => {
      try {
        dispatch({ type: 'event', event: JSON.parse(message.data) });
      } catch {
        /* ignore a malformed frame rather than crash the page */
      }
    };
    source.onerror = () => {
      source.close();
      sourceRef.current = null;
      dispatch({ type: 'closed' });
    };
  }, [limit, rate, stop]);

  useEffect(() => stop, [stop]);

  return { state, start, stop };
}
