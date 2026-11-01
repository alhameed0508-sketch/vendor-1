/* Minimal SSE parser for `data: <json>` frames separated by a blank line. */

export function parseSse(buffer) {
  const frames = buffer.split('\n\n');
  const rest = frames.pop();
  const events = [];
  frames.forEach((frame) => {
    const data = frame
      .split('\n')
      .filter((line) => line.startsWith('data: '))
      .map((line) => line.slice(6))
      .join('\n');
    if (!data) return;
    try {
      events.push(JSON.parse(data));
    } catch {
      /* skip a malformed frame rather than crash the stream */
    }
  });
  return { events, rest };
}
