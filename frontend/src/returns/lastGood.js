// The last good answer for each screen, so a failed request can show it with its time.
// Held in memory only (nothing is written to browser storage) and keyed by the signed-in user, so one person's
// claims are never shown to the next person on the same tab, and a reload starts clean.
const store = new Map();

const slot = (user, key) => `${user || 'anonymous'}:${key}`;

export function remember(user, key, data) {
  store.set(slot(user, key), { at: new Date().toISOString(), data });
}

export function recall(user, key) {
  return store.get(slot(user, key)) || null;
}

export const clearLastGood = () => store.clear();

/** A refusal (403, 404, 422) is an answer, so it is shown as is. Only a dead network or a 5xx falls back to the last result. */
export const isOutage = err => !err.status || err.status >= 500;
