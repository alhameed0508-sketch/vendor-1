/**
 * One rupee format for every screen: crores to 2 decimals, lakhs to 1, thousands whole,
 * trailing zeros dropped. The unit is picked after rounding, so 99.96K reads ₹1L, not ₹100K.
 */
const CRORE = 10000000;
const LAKH = 100000;
const THOUSAND = 1000;

// Divide by the smallest shown step first, so ₹1.825Cr rounds on an exact 182.5 rather than 1.8249999.
const inUnits = (value, unit, digits) => Math.round(value / (unit / 10 ** digits)) / 10 ** digits;

export function formatAmount(amount) {
  const value = Number(amount) || 0;
  const lakhs = inUnits(value, LAKH, 1);
  if (lakhs >= 100) return `₹${inUnits(value, CRORE, 2)}Cr`;
  const thousands = Math.round(value / THOUSAND);
  if (thousands >= 100) return `₹${lakhs}L`;
  if (Math.round(value) >= THOUSAND) return `₹${thousands}K`;
  return `₹${Math.round(value)}`;
}

/**
 * Exact rupees with Indian digit grouping (₹1,85,000), for what someone owes or is paid:
 * a liability or a compensation figure rounded to ₹21K would misstate the amount.
 */
export function formatRupeesExact(amount) {
  return `₹${Math.round(Number(amount) || 0).toLocaleString('en-IN')}`;
}
