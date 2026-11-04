import { buildRing, timelineEvents, firedSignals } from './ringModel';

const row = (n, extra) => ({
  claim_id: `RC-${n}`, customer_id: `C${n}`, customer_name: `Person ${n}`, amount: 1000 * n,
  returned_at: `2027-02-1${n}T10:00:00+05:30`, device_id: 'D1', address: `A${n}`, payment_fp: `P${n}`, ...extra,
});

describe('buildRing', () => {
  it('puts every customer on the ring and keeps only identifiers two or more share', () => {
    const ring = buildRing([row(1), row(2), row(3, { address: 'A1' })]);
    expect(ring.customers).toHaveLength(3);
    expect(ring.hubs.map(h => [h.kind, h.members.length])).toEqual([['Device', 3], ['Address', 2]]);
    expect(ring.links).toHaveLength(5);
  });

  it('orders customers by when they returned, and folds repeat claims by one customer', () => {
    const ring = buildRing([row(3), row(1), row(2), row(1, { claim_id: 'RC-99' })]);
    expect(ring.customers.map(c => c.id)).toEqual(['C1', 'C2', 'C3']);
  });

  it('gives every node a position inside the drawing', () => {
    const ring = buildRing([row(1), row(2), row(3), row(4), row(5)]);
    [...ring.customers, ...ring.hubs].forEach(n => {
      expect(n.x).toBeGreaterThan(0);
      expect(n.x).toBeLessThan(ring.width);
      expect(n.y).toBeGreaterThan(0);
      expect(n.y).toBeLessThan(ring.height);
    });
  });

  it('has no hubs when nothing is shared', () => {
    const ring = buildRing([row(1, { device_id: 'x1' }), row(2, { device_id: 'x2' })]);
    expect(ring.hubs).toEqual([]);
  });
});

describe('timelineEvents', () => {
  const view = {
    claim: {
      delivered_at: '2027-02-10T12:00:00+05:30', returned_at: '2027-02-14T12:00:00+05:30',
      carrier_events: [{ type: 'damaged_in_transit', at: '2027-02-09T18:00:00+05:30' }],
      chargebacks: [{ status: 'opened', at: '2027-02-20T10:00:00+05:30' }],
    },
    signals: [
      { name: 'exif', available: true, score: 80, detail: { taken_at: '2027-02-01T10:00:00+05:30' } },
      { name: 'receipt', available: true, score: 60,
        detail: { created_at: '2027-02-10T10:00:00', modified_at: '2027-02-13T10:00:00' } },
    ],
  };

  it('lists every dated event oldest first, each tied to its signal', () => {
    const events = timelineEvents(view);
    expect(events.map(e => e.label)).toEqual([
      'Photo taken', 'Carrier: damaged in transit', 'Receipt file created', 'Parcel delivered',
      'Receipt file edited', 'Return requested', 'Chargeback opened',
    ]);
    expect(events.find(e => e.id === 'photo').signal).toBe('exif');
    expect(events.find(e => e.id === 'delivered').signal).toBeNull();
  });

  it('treats receipt dates without a zone as IST so the order is the same in every browser', () => {
    const edited = timelineEvents(view).find(e => e.id === 'receipt-edited');
    expect(edited.at).toBe('2027-02-13T10:00:00+05:30');
  });

  it('skips events a claim does not have', () => {
    const labels = timelineEvents({ claim: { delivered_at: view.claim.delivered_at, returned_at: view.claim.returned_at }, signals: [] })
      .map(e => e.label);
    expect(labels).toEqual(['Parcel delivered', 'Return requested']);
  });
});

test('firedSignals keeps only signals that ran and scored above the line', () => {
  const fired = firedSignals({ signals: [
    { name: 'a', available: true, score: 31 }, { name: 'b', available: true, score: 30 }, { name: 'c', available: false, score: 90 },
  ] });
  expect(fired.map(s => s.name)).toEqual(['a']);
});
