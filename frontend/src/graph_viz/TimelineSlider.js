import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { Pause, Play } from 'lucide-react';

/**
 * TimelineSlider — lets investigators scrub through time to see
 * how the mule network evolved.  Filters edges by timestamp range.
 *
 * Props:
 *   edges       – array of edge objects with `timestamps` array
 *   onChange    – callback({start, end}) when range changes
 *   windowPct  – playback window size as % of total range (default 15)
 *   stepPct    – playback step size as % per tick (default 0.5)
 *   intervalMs – playback tick interval in ms (default 80)
 */

const DEFAULT_WINDOW_PCT = 15;
const DEFAULT_STEP_PCT = 0.5;
const DEFAULT_INTERVAL_MS = 80;

export default function TimelineSlider({
  edges = [],
  onChange,
  windowPct = DEFAULT_WINDOW_PCT,
  stepPct = DEFAULT_STEP_PCT,
  intervalMs = DEFAULT_INTERVAL_MS,
}) {
  const allTimestamps = useMemo(() => {
    const ts = [];
    for (const e of edges) {
      for (const t of (e.timestamps || [])) {
        ts.push(new Date(t).getTime());
      }
    }
    ts.sort((a, b) => a - b);
    return ts;
  }, [edges]);

  const minTime = allTimestamps[0] || 0;
  const maxTime = allTimestamps[allTimestamps.length - 1] || 1;
  const range = maxTime - minTime || 1;

  const [startPct, setStartPct] = useState(0);
  const [endPct, setEndPct] = useState(100);
  const [playing, setPlaying] = useState(false);
  const playRef = useRef(null);
  const playingRef = useRef(false);

  const startTime = minTime + (startPct / 100) * range;
  const endTime = minTime + (endPct / 100) * range;

  const emitRange = useCallback((sPct, ePct) => {
    const s = minTime + (sPct / 100) * range;
    const e = minTime + (ePct / 100) * range;
    onChange?.({ start: s, end: e });
  }, [minTime, range, onChange]);

  const handleStartChange = useCallback((e) => {
    const val = Math.min(Number(e.target.value), endPct - 2);
    setStartPct(val);
    emitRange(val, endPct);
  }, [endPct, emitRange]);

  const handleEndChange = useCallback((e) => {
    const val = Math.max(Number(e.target.value), startPct + 2);
    setEndPct(val);
    emitRange(startPct, val);
  }, [startPct, emitRange]);

  const handleReset = useCallback(() => {
    setStartPct(0);
    setEndPct(100);
    onChange?.({ start: minTime, end: maxTime });
  }, [minTime, maxTime, onChange]);

  const stopPlayback = useCallback(() => {
    clearInterval(playRef.current);
    playRef.current = null;
    playingRef.current = false;
    setPlaying(false);
  }, []);

  const togglePlay = useCallback(() => {
    if (playingRef.current) {
      stopPlayback();
      return;
    }

    playingRef.current = true;
    setPlaying(true);

    let currentStart = 0;
    let currentEnd = windowPct;
    setStartPct(currentStart);
    setEndPct(currentEnd);
    emitRange(currentStart, currentEnd);

    playRef.current = setInterval(() => {
      currentStart += stepPct;
      currentEnd += stepPct;

      if (currentEnd >= 100) {
        stopPlayback();
        setStartPct(0);
        setEndPct(100);
        onChange?.({ start: minTime, end: maxTime });
        return;
      }

      setStartPct(currentStart);
      setEndPct(currentEnd);
      emitRange(currentStart, currentEnd);
    }, intervalMs);
  }, [windowPct, stepPct, intervalMs, minTime, maxTime, onChange, emitRange, stopPlayback]);

  // Cleanup on unmount
  useEffect(() => () => clearInterval(playRef.current), []);

  const formatTime = (ms) => {
    const d = new Date(ms);
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
      + ' ' + d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
  };

  const activeEdges = useMemo(() => {
    return edges.filter(e =>
      (e.timestamps || []).some(t => {
        const ms = new Date(t).getTime();
        return ms >= startTime && ms <= endTime;
      })
    ).length;
  }, [edges, startTime, endTime]);

  if (allTimestamps.length < 2) return null;

  return (
    <div style={{
      padding: '10px 20px 6px',
      borderTop: '1px solid var(--border)',
      background: 'var(--surface)',
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            className="btn btn-ghost"
            style={{ padding: '2px 8px', fontSize: 11 }}
            onClick={togglePlay}
            aria-label={playing ? 'Pause timeline' : 'Play timeline'}
          >
            {playing ? <Pause size={12} /> : <Play size={12} />}
          </button>
          <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-muted)' }}>
            Timeline
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--accent)' }}>
            {activeEdges} of {edges.length} transfers
          </span>
          <button
            className="btn btn-ghost"
            style={{ padding: '2px 8px', fontSize: 12 }}
            onClick={handleReset}
          >
            Reset
          </button>
        </div>
      </div>

      {/* Dual-range slider area */}
      <div style={{ position: 'relative', height: 24, marginBottom: 4 }}>
        {/* Track background */}
        <div style={{
          position: 'absolute', top: 10, left: 0, right: 0, height: 4,
          background: 'var(--border)', borderRadius: 2,
        }} />
        {/* Active range highlight */}
        <div style={{
          position: 'absolute', top: 10, height: 4,
          left: `${startPct}%`, width: `${endPct - startPct}%`,
          background: 'var(--accent)', borderRadius: 2, opacity: 0.6,
        }} />
        {/* Start slider */}
        <input
          type="range" min={0} max={100} step={0.5} value={startPct}
          onChange={handleStartChange}
          style={{
            position: 'absolute', top: 0, left: 0, width: '100%',
            appearance: 'none', background: 'transparent', pointerEvents: 'none',
            height: 24, zIndex: 2,
          }}
          className="timeline-range"
        />
        {/* End slider */}
        <input
          type="range" min={0} max={100} step={0.5} value={endPct}
          onChange={handleEndChange}
          style={{
            position: 'absolute', top: 0, left: 0, width: '100%',
            appearance: 'none', background: 'transparent', pointerEvents: 'none',
            height: 24, zIndex: 3,
          }}
          className="timeline-range"
        />
      </div>

      {/* Time labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-muted)' }}>
          {formatTime(startTime)}
        </span>
        <span style={{ fontSize: 12, fontFamily: 'var(--font-sans)', color: 'var(--text-muted)' }}>
          {formatTime(endTime)}
        </span>
      </div>
    </div>
  );
}
