import { parseSse } from './sseParse';

describe('parseSse', () => {
  it('parses complete frames and returns the unfinished remainder', () => {
    const { events, rest } = parseSse('data: {"a":1}\n\ndata: {"a":2}\n\ndata: {"a"');
    expect(events).toEqual([{ a: 1 }, { a: 2 }]);
    expect(rest).toBe('data: {"a"');
  });

  it('joins a frame split across chunks', () => {
    const first = parseSse('data: {"a":');
    expect(first.events).toEqual([]);
    const second = parseSse(`${first.rest}1}\n\n`);
    expect(second.events).toEqual([{ a: 1 }]);
    expect(second.rest).toBe('');
  });

  it('skips comments and malformed frames instead of throwing', () => {
    const { events } = parseSse(': keep-alive\n\ndata: not-json\n\ndata: {"ok":true}\n\n');
    expect(events).toEqual([{ ok: true }]);
  });
});
