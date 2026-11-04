// Plain words for the codes the returns API sends. Colour always comes with a word, never alone.

export const TIER = {
  APPROVE: { label: 'Refund', action: 'Refund. Nothing needs a second look.', colour: 'var(--accent)' },
  VERIFY: { label: 'Ask for proof', action: 'Ask for one more proof before refunding.', colour: 'var(--medium)' },
  CHALLENGE: { label: 'Hold the refund', action: 'Hold the refund and ask for the original proof.', colour: 'var(--high)' },
  BLOCK: { label: 'Send to fraud desk', action: 'Send to the fraud desk before any refund.', colour: 'var(--critical)' },
};

export const SIGNAL = {
  exif: 'Photo details',
  vlm: 'Photo against the claim',
  receipt: 'Receipt file',
  device: 'Shared device',
  behavioral: 'Return habits',
  graph: 'Linked customers',
};

// One sentence each: what the check measures and why it matters. Shown as a tooltip wherever a check is named.
export const SIGNAL_HELP = {
  exif: 'Reads the photo\'s hidden details: when it was taken, by which phone, and whether another customer sent the same picture. A real damage photo is taken after delivery.',
  vlm: 'Compares what the photo shows with what the customer says is wrong. Simulated here: it reads labels, not pixels.',
  receipt: 'Reads the receipt file\'s own details: the program that saved it, when, how often, and whether it was used before.',
  device: 'Counts how many other customers return items from the same phone or computer.',
  behavioral: 'Looks at how often this customer returns, and how soon after delivery or an event.',
  graph: 'Links customers who share a device, an address or a card, and notes when their claims read almost the same.',
};

export const SIGNAL_ORDER = ['exif', 'vlm', 'receipt', 'device', 'behavioral', 'graph'];

export const SCENARIO = {
  legit: 'An ordinary return',
  receipt_manipulation: 'Edited receipt',
  exif_mismatch: 'Photo older than the delivery',
  ring: 'Five customers, one device',
  wardrobing: 'Worn once, then returned',
  friendly_fraud: 'Says it never arrived',
  inr_carrier_fault: 'Carrier damaged the parcel',
};

export const REVIEW_OUTCOME = {
  refund: 'Refund',
  request_proof: 'Ask for proof',
  reject: 'Reject the return',
  escalate: 'Send to fraud desk',
};

export const canReview = role => ['ADMIN', 'SUPERVISOR'].includes(role);
export const canFile = role => ['ADMIN', 'SUPERVISOR', 'INVESTIGATOR'].includes(role);

const WHEN = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata',
});
export const formatWhen = iso => (iso ? WHEN.format(new Date(iso)) : '—');

const CLOCK = new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' });
export const formatClock = iso => `${CLOCK.format(new Date(iso))} IST`;

/** The time a finding refers to, when the evidence carries one: the photo being taken, the receipt being saved. */
export const evidenceTime = signal => signal.detail?.taken_at || signal.detail?.modified_at || signal.detail?.created_at || null;

/** A signal that scored above this "fired": the same line the bank package uses. */
export const FIRED_ABOVE = 30;
/** A check must score above this, with enough confidence, to count as agreeing with the others. */
export const AGREES_ABOVE = 60;
