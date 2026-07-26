import { useEffect, useRef, useState } from 'react';
import { resolveUrl, getToken } from '../auth/api';
import { SSE_INITIAL_RECONNECT_MS, SSE_MAX_RECONNECT_MS, SSE_BACKOFF_MULTIPLIER } from '../config';

const INITIAL_RECONNECT_DELAY = SSE_INITIAL_RECONNECT_MS;
const MAX_RECONNECT_DELAY = SSE_MAX_RECONNECT_MS;

/**
 * SSE hook that connects to GET /api/v1/ingest/stream.
 * Calls `onNewAlerts(event)` when new-alert events arrive.
 * Auto-reconnects on disconnect with exponential backoff (5s → 60s max).
 *
 * @param {Object} options
 * @param {function} options.onNewAlerts - Called with the parsed SSE event data
 * @param {boolean}  [options.enabled=true] - Set to false to disable the stream
 * @returns {{ connected: boolean }}
 */
export default function useAlertStream({ onNewAlerts, enabled = true }) {
  const [connected, setConnected] = useState(false);
  const esRef = useRef(null);
  const reconnectTimer = useRef(null);
  const reconnectDelay = useRef(INITIAL_RECONNECT_DELAY);
  const onNewAlertsRef = useRef(onNewAlerts);
  const enabledRef = useRef(enabled);

  // Keep refs current without re-triggering effect
  useEffect(() => { onNewAlertsRef.current = onNewAlerts; }, [onNewAlerts]);
  useEffect(() => { enabledRef.current = enabled; }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      // Tear down everything when disabled
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      setConnected(false);
      reconnectDelay.current = INITIAL_RECONNECT_DELAY;
      return;
    }

    function connect() {
      if (esRef.current) {
        esRef.current.close();
      }

      const token = getToken();
      const baseUrl = resolveUrl('/api/v1/ingest/stream');
      const url = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;

      const es = new EventSource(url);
      esRef.current = es;

      es.onopen = () => {
        setConnected(true);
        // Reset backoff on successful connection
        reconnectDelay.current = INITIAL_RECONNECT_DELAY;
      };

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'new_alerts' && onNewAlertsRef.current) {
            onNewAlertsRef.current(data);
          }
        } catch {
          // Ignore non-JSON messages (keepalives, SSE comments)
          if (process.env.NODE_ENV === 'development' && event.data && event.data.trim()) {
            console.debug('[SSE] Skipped non-JSON message:', event.data);
          }
        }
      };

      es.onerror = () => {
        setConnected(false);
        es.close();
        esRef.current = null;

        const delay = reconnectDelay.current;
        // Exponential backoff: double delay each failure, cap at MAX
        reconnectDelay.current = Math.min(delay * SSE_BACKOFF_MULTIPLIER, MAX_RECONNECT_DELAY);

        reconnectTimer.current = setTimeout(() => {
          reconnectTimer.current = null;
          if (enabledRef.current) {
            connect();
          }
        }, delay);
      };
    }

    connect();

    return () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      setConnected(false);
      reconnectDelay.current = INITIAL_RECONNECT_DELAY;
    };
  }, [enabled]);

  return { connected };
}
