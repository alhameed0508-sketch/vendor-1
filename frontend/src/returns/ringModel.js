import { FIRED_ABOVE } from './labels';

const WIDTH = 400;
const HEIGHT = 280;
const HUB_KINDS = [['device_id', 'Device'], ['address', 'Address'], ['payment_fp', 'Card']];

const place = (index, count, rx, ry) => {
  const angle = (index / count) * 2 * Math.PI - Math.PI / 2;
  return { x: WIDTH / 2 + rx * Math.cos(angle), y: HEIGHT / 2 + ry * Math.sin(angle) };
};

/**
 * Customers on an outer ring, and in the middle every device, address or card that two or more of them share.
 * `rows` are claim rows (one per customer is enough; extra claims by one customer are folded into it).
 */
export function buildRing(rows) {
  const byCustomer = new Map();
  rows.forEach(r => { if (!byCustomer.has(r.customer_id)) byCustomer.set(r.customer_id, r); });
  const people = [...byCustomer.values()].sort((a, b) => new Date(a.returned_at) - new Date(b.returned_at));
  const customers = people.map((r, i) => ({
    id: r.customer_id, name: r.customer_name, claimId: r.claim_id, returnedAt: r.returned_at, amount: r.amount,
    ...place(i, people.length, 150, 105),
  }));

  const hubs = [];
  HUB_KINDS.forEach(([field, kind]) => {
    const groups = new Map();
    people.forEach(r => { if (r[field]) groups.set(r[field], [...(groups.get(r[field]) || []), r.customer_id]); });
    groups.forEach((members, value) => { if (members.length >= 2) hubs.push({ id: `${field}:${value}`, kind, value, members }); });
  });
  const placedHubs = hubs.map((h, i) => ({ ...h, ...place(i, hubs.length, hubs.length > 1 ? 50 : 0, hubs.length > 1 ? 36 : 0) }));
  const links = placedHubs.flatMap(h => h.members.map(customer => ({ hub: h.id, customer })));
  return { width: WIDTH, height: HEIGHT, customers, hubs: placedHubs, links };
}

const asIst = naive => (naive && !/[zZ+]|-\d\d:\d\d$/.test(naive) ? `${naive}+05:30` : naive);
const CARRIER = {
  delivered: 'Carrier: delivered',
  in_transit: 'Carrier: in transit',
  lost_in_transit: 'Carrier: lost in transit',
  damaged_in_transit: 'Carrier: damaged in transit',
  returned_to_sender: 'Carrier: returned to sender',
};

/** Everything dated on a claim, oldest first, each tied to the signal it supports (or none). */
export function timelineEvents(view) {
  const c = view.claim;
  const signal = name => view.signals.find(s => s.name === name);
  const events = [
    { id: 'delivered', at: c.delivered_at, label: 'Parcel delivered', signal: null },
    { id: 'returned', at: c.returned_at, label: 'Return requested', signal: 'behavioral' },
  ];
  const taken = signal('exif')?.detail?.taken_at;
  if (taken) events.push({ id: 'photo', at: taken, label: 'Photo taken', signal: 'exif' });
  const receipt = signal('receipt')?.detail || {};
  if (receipt.created_at) events.push({ id: 'receipt-made', at: asIst(receipt.created_at), label: 'Receipt file created', signal: 'receipt' });
  if (receipt.modified_at && receipt.modified_at !== receipt.created_at) {
    events.push({ id: 'receipt-edited', at: asIst(receipt.modified_at), label: 'Receipt file edited', signal: 'receipt' });
  }
  (c.carrier_events || []).forEach((e, i) => events.push({ id: `carrier-${i}`, at: e.at, label: CARRIER[e.type] || e.type, signal: null }));
  (c.chargebacks || []).forEach((e, i) => events.push({ id: `chargeback-${i}`, at: e.at, label: `Chargeback ${e.status}`, signal: null }));
  return events.sort((a, b) => new Date(a.at) - new Date(b.at));
}

export const firedSignals = view => view.signals.filter(s => s.available && s.score > FIRED_ABOVE);
