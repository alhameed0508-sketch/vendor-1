// Plain words for the codes the complaint API returns. Colour always comes with a word, never alone.

export const CATEGORY = {
  BANK_NEGLIGENCE: 'Bank at fault',
  THIRD_PARTY_BREACH: 'Third-party fraud',
  CUSTOMER_NEGLIGENCE: 'Customer negligence',
  NOT_FRAUD: 'Customer made the payment',
  UNDETERMINED: 'Not clear yet',
};

export const OUTCOME = {
  ZERO_LIABILITY: { label: 'Customer pays nothing', colour: 'var(--accent)' },
  CUSTOMER_LIABLE: { label: 'Customer bears the loss', colour: 'var(--high)' },
  SHARED_LIABILITY: { label: 'Loss shared', colour: 'var(--medium)' },
  BANK_POLICY: { label: 'Bank policy decides', colour: 'var(--medium)' },
  NOT_FRAUD: { label: 'Not a fraud', colour: 'var(--critical)' },
  UNPROVEN: { label: 'Bank cannot prove it yet', colour: 'var(--text-muted)' },
};

export const DECISION_OUTCOMES = ['ZERO_LIABILITY', 'CUSTOMER_LIABLE', 'SHARED_LIABILITY', 'NOT_FRAUD'];

export const SOURCE = {
  CUSTOMER: 'Customer',
  BANK_CORE: 'Core banking',
  AUTH_LOG: 'Login records',
  SMS_GATEWAY: 'SMS gateway',
  TELECOM: 'Telecom',
  BANK_SECURITY: 'Bank security',
  MERCHANT: 'Merchant',
  COURIER: 'Courier',
  MULECATCH: 'MuleCatch',
};

export const FLAG = {
  MULE_BENEFICIARY: 'Money went to a known mule',
  RETURN_ABUSE: 'Returned item was swapped',
};

export const CHANNEL = {
  UPI: 'UPI', IMPS: 'IMPS', NEFT: 'NEFT', NETBANKING: 'Net banking',
  DEBIT_CARD: 'Debit card', CREDIT_CARD: 'Credit card', WALLET: 'Wallet',
};

// What a bank's partners send in. Each preset is one realistic message from one system.
export const EVIDENCE_PRESETS = [
  { key: 'delivered', source: 'COURIER', kind: 'delivery_confirmed', data: { address_matches: true, otp_verified: true },
    summary: 'Courier: delivered to the registered address; the delivery OTP was entered' },
  { key: 'device', source: 'MERCHANT', kind: 'device_history', data: { same_device: true, prior_orders: 6 },
    summary: 'Merchant: ordered from the same phone as 6 earlier undisputed orders' },
  { key: 'return', source: 'MERCHANT', kind: 'return_inspection', data: { item_matches: false },
    summary: 'Warehouse: the returned item is not the one that was shipped' },
  { key: 'sim', source: 'TELECOM', kind: 'sim_swap', data: {},
    summary: 'Telecom: the SIM was re-issued shortly before the payment' },
  { key: 'sms-ok', source: 'SMS_GATEWAY', kind: 'sms_alert', data: { delivered: true },
    summary: 'SMS gateway: the debit alert reached the registered mobile' },
  { key: 'sms-failed', source: 'SMS_GATEWAY', kind: 'sms_alert', data: { delivered: false },
    summary: 'SMS gateway: the debit alert was never delivered' },
  { key: 'known-device', source: 'AUTH_LOG', kind: 'login', data: { new_device: false, otp_verified: true },
    summary: "Login records: approved with the OTP on the customer's usual phone" },
  { key: 'new-device', source: 'AUTH_LOG', kind: 'login', data: { new_device: true },
    summary: 'Login records: a device never seen on this account' },
  { key: 'disclosed', source: 'CUSTOMER', kind: 'credential_disclosed', data: {},
    summary: "Customer's statement: they shared the OTP with a caller" },
  { key: 'breach', source: 'BANK_SECURITY', kind: 'bank_breach', data: {},
    summary: "Bank security: the customer's credentials leaked from the bank's side" },
  { key: 'ncrp', source: 'CUSTOMER', kind: 'ncrp_report', data: {},
    summary: 'Customer reported it on 1930 / NCRP' },
];

const WHEN = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', year: 'numeric',
  hour: '2-digit', minute: '2-digit', hour12: false,
});
const DAY = new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', year: 'numeric' });

export const formatWhen = iso => (iso ? WHEN.format(new Date(iso)) : '—');
export const formatDay = iso => (iso ? DAY.format(new Date(iso)) : '—');

/** "5 days left", "Due today", "3 days overdue" */
export function clockLabel({ days_left: daysLeft, overdue }) {
  if (overdue) return `${Math.max(-daysLeft, 1)} day${Math.max(-daysLeft, 1) === 1 ? '' : 's'} overdue`;
  if (daysLeft === 0) return 'Due today';
  return `${daysLeft} day${daysLeft === 1 ? '' : 's'} left`;
}

export const canDecide = role => ['ADMIN', 'SUPERVISOR'].includes(role);
export const canWrite = role => ['ADMIN', 'SUPERVISOR', 'INVESTIGATOR'].includes(role);
