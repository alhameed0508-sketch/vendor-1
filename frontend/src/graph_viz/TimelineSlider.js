import React, { useState, useMemo, useCallback } from 'react';
import { Pause, Play } from 'lucide-react';

/**
 * TimelineSlider — lets investigators scrub through time to see
 * how the mule network evolved.  Filters edges by timestamp range.
 *
 * Props:
 *   edges       – array of edge objects with `timestamps` array
 *   onChange    – callback({start, end}) when range changes
 */
export default function TimelineSlider({ edges = [], onChange }) {
  // Extract all timestamps and build a sorted unique list
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
  const playRef = React.useRef(null);

  const startTime = minTime + (startPct / 100) * range;
  const endTime = minTime + (endPct / 100) * range;

  const handleStartChange = useCallback((e) => {
    const val = Math.min(Number(e.target.value), endPct - 2);
    setStartPct(val);
    const s = minTime + (val / 100) * range;
    onChange?.({ start: s, end: endTime });
  }, [endPct, minTime, range, endTime, onChange]);

  const handleEndChange = useCallback((e) => {
    const val = Math.max(Number(e.target.value), startPct + 2);
    setEndPct(val);
    const en = minTime + (val / 100) * range;
    onChange?.({ start: startTime, end: en });
  }, [startPct, minTime, range, startTime, onChange]);

  const handleReset = useCallback(() => {
    setStartPct(0);
    setEndPct(100);
    onChange?.({ start: minTime, end: maxTime });
  }, [minTime, maxTime, onChange]);

  // Playback: animate the window sliding forward
  const togglePlay = useCallback(() => {
    if (playing) {
      clearInterval(playRef.current);
      setPlaying(false);
      return;
    }
    setPlaying(true);
    setStartPct(0);
    setEndPct(15);
    const step = 0.5;
    playRef.current = setInterval(() => {
      setEndPct(prev => {
        const next = prev + step;
        if (next >= 100) {
          clearInterval(playRef.current);
          setPlaying(false);
          setEndPct(100);
          onChange?.({ start: minTime, end: maxTime });
          return 100;
        }
        const en = minTime + (next / 100) * range;
        onChange?.({ start: minTime, end: en });
        return next;
      });
    }, 80);
  }, [playing, minTime, maxTime, range, onChange]);

  // Cleanup on unmount
  React.useEffect(() => () => clearInterval(playRef.current), []);

  const formatTime = (ms) => {
    const d = new Date(ms);
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
      + ' ' + d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
  };

  // Count active edges in the current window
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
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Timeline
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
            {activeEdges}/{edges.length} edges
          </span>
          <button
            className="btn btn-ghost"
            style={{ padding: '2px 8px', fontSize: 10 }}
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
          background: 'var(--accent-cyan)', borderRadius: 2, opacity: 0.6,
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
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          {formatTime(startTime)}
        </span>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          {formatTime(endTime)}
        </span>
      </div>
    </div>
  );
}
