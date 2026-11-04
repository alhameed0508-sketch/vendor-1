// Shapes the returns API sends, shared by the returns tests.
export const SIGNALS = (scores = {}) => ['exif', 'vlm', 'receipt', 'device', 'behavioral', 'graph'].map(name => ({
  name, score: scores[name] ?? 0, confidence: 1, available: true, reasons: [`${name} reason`], detail: {},
  source: `${name} source`, corroborated_by: [],
}));

export const claimView = (id, { claim, ...rest } = {}) => ({
  claim: {
    claim_id: id, customer_id: `C-${id}`, customer_name: `Person ${id}`, item: 'Smartphone', amount: 54000,
    delivered_at: '2027-02-10T12:00:00+05:30', returned_at: '2027-02-10T20:00:00+05:30',
    device_id: 'D1', address: 'A1', payment_fp: 'P1', carrier_events: [], chargebacks: [], ...claim,
  },
  signals: SIGNALS({ device: 100, graph: 90, receipt: 100, exif: 100 }),
  fusion: {
    tier: 'BLOCK', score: 100, raw_score: 100, capped_from: null, corroborating: 4, firewall: 'No single signal can block.',
    adjustments: [], contributions: { exif: 30, vlm: 0, receipt: 30, device: 25, behavioral: 0, graph: 15 },
  },
  narrative: { what_happened: 'Person returned a phone.', what_we_found: 'The device is shared.', what_we_recommend: 'Send to the fraud desk.' },
  dispute_category: { code: 'RING', label: 'Organised return-fraud ring', note: 'Indicative mapping.' },
  review: null,
  ...rest,
});

export const OVERVIEW = {
  as_of: '2027-03-01T10:00:00+05:30',
  summary: { total: 3, by_tier: { BLOCK: 1, CHALLENGE: 0, VERIFY: 1, APPROVE: 1 }, needs_review: 2, amount_in_question: 72500 },
  signal_coverage: Object.fromEntries(['exif', 'vlm', 'receipt', 'device', 'behavioral', 'graph'].map(n => [n, { ran: 3, fired: 1 }])),
  rings: [{ claims: ['RC-1', 'RC-2', 'RC-3'], customers: 3, amount: 54000 }],
  scenarios: [
    { scenario: 'legit', blurb: 'An ordinary return.', claim_id: 'RC-9', tier: 'APPROVE', score: 0.2 },
    { scenario: 'ring', blurb: 'Five customers share a device.', claim_id: 'RC-8', tier: 'BLOCK', score: 100 },
  ],
};

export const LIST = {
  claims: [
    { claim_id: 'RC-8', customer_name: 'Dev Ghosh', item: 'Smartphone', amount: 54000, tier: 'BLOCK', score: 100, reviewed: false },
    { claim_id: 'RC-2', customer_name: 'Vikram Shah', item: 'Dock', amount: 18500, tier: 'VERIFY', score: 64, reviewed: true },
    { claim_id: 'RC-9', customer_name: 'Anita Rao', item: 'Headphones', amount: 4200, tier: 'APPROVE', score: 0.2, reviewed: false },
  ],
};

export const ok = data => ({ ok: true, json: () => Promise.resolve({ success: true, data }) });
