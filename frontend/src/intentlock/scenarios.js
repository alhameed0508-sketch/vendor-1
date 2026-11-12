import React, { useState } from 'react';

// Guided demo: one click sets up a known mandate, then a banner on each page says what to press next.
export const DEMO_REQUEST = 'Buy me a new laptop with at least 16GB RAM and 512GB storage, under $1,000 including shipping and tax.';
export const DEMO_TERMS = {
  category: 'laptop', condition: 'new', quantity: '1', model: '', budget: '1000.00', includeShipping: true, includeTax: true,
  sellerMode: 'allowlist', substitution: false,
  requirements: [{ key: 'ram_gb_min', name: '', value: '16' }, { key: 'storage_gb_min', name: '', value: '512' }],
};

export const SCENARIOS = [
  {
    id: 'valid', title: 'A purchase that goes through',
    blurb: 'The product fits your limits. PayPal captures the payment and you get a receipt.',
    steps: {
      review: 'Check the terms, then press "Confirm and lock this mandate".',
      discovery: 'Press "Select this product" on Aster Book 14, then "Continue to PayPal".',
      monitor: 'Pay with a PayPal Sandbox buyer account. The server fetches the approved order again, checks it, then captures.',
    },
  },
  {
    id: 'agent', title: 'An agent talked into overspending',
    blurb: 'A product description tells the AI to ignore your budget. The rules refuse it, and the assistant tries again.',
    steps: {
      review: 'Check the terms, then press "Confirm and lock this mandate".',
      discovery: 'Press "Simulate a manipulated agent" in the left panel and watch what the rules do with its pick.',
      monitor: 'This checkout came from the assistant\'s second, allowed proposal. You can pay it or stop here.',
    },
  },
  {
    id: 'tamper', title: 'An order changed after you approve', needsDemoTools: true,
    blurb: 'The PayPal order is altered behind the checkout. The final check refuses to capture.',
    steps: {
      review: 'Check the terms, then press "Confirm and lock this mandate".',
      discovery: 'Press "Select this product" on Aster Book 14, then "Continue to PayPal".',
      monitor: 'Press "Demo: change the PayPal order behind the checkout", then approve in PayPal. The capture is refused on the amount rule.',
    },
  },
];

const KEY = 'il_demo';
const read = () => { try { return window.sessionStorage.getItem(KEY); } catch (e) { return null; } };
export function startDemo(id) { try { window.sessionStorage.setItem(KEY, id); } catch (e) { /* private mode */ } }
export function endDemo() { try { window.sessionStorage.removeItem(KEY); } catch (e) { /* private mode */ } }

export function Guide({ page }) {
  const [id, setId] = useState(read);
  const scenario = SCENARIOS.find((s) => s.id === id);
  if (!scenario || !scenario.steps[page]) return null;
  return (
    <div className="guide" role="note">
      <div><span className="eyebrow">Guided demo · {scenario.title}</span><p>{scenario.steps[page]}</p></div>
      <button className="btn small" onClick={() => { endDemo(); setId(null); }}>End guide</button>
    </div>
  );
}
