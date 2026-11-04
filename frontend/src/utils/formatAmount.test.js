import { formatAmount, formatRupeesExact } from './formatAmount';

describe('formatAmount', () => {
  it.each([
    [17900000, '₹1.79Cr'],
    [18250000, '₹1.83Cr'],
    [1250000, '₹12.5L'],
    [125000, '₹1.3L'],
    [25000000, '₹2.5Cr'],
    [10000000, '₹1Cr'],
    [450000, '₹4.5L'],
    [500000, '₹5L'],
    [8000, '₹8K'],
    [950, '₹950'],
    [0, '₹0'],
  ])('%s -> %s', (amount, text) => expect(formatAmount(amount)).toBe(text));

  it.each([[9999999, '₹1Cr'], [99960, '₹1L'], [999.6, '₹1K']])(
    'moves up a unit when rounding reaches it: %s -> %s', (amount, text) => expect(formatAmount(amount)).toBe(text));

  it.each([[undefined], [null], [NaN], ['abc']])('shows ₹0 for a missing amount (%s)', amount =>
    expect(formatAmount(amount)).toBe('₹0'));
});

describe('formatRupeesExact', () => {
  it.each([[21250, '₹21,250'], [185000, '₹1,85,000'], [12345678, '₹1,23,45,678'], [950, '₹950'], [null, '₹0']])(
    '%s -> %s', (amount, text) => expect(formatRupeesExact(amount)).toBe(text));
});
