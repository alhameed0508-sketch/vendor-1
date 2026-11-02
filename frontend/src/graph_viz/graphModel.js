/**
 * Pure graph logic for the money-flow view: which transfers are flagged,
 * the order money hops in, cluster summaries, the verdict and "why" reasons.
 * No d3 or DOM here, so every rule is unit-tested.
 */

const ROLE_LABELS = {
  SOURCE: 'Source', AGGREGATOR: 'Aggregator', MULE: 'Mule',
  LEGITIMATE: 'Legitimate', UNKNOWN: 'Unknown',
};

const SUSPICIOUS_ROLES = new Set(['SOURCE', 'AGGREGATOR', 'MULE']);
const NAMED_PATTERNS = new Set(['SMURFING', 'CONSOLIDATION', 'LAYERING', 'FAN_OUT', 'FAN_IN', 'ROUND_TRIP']);
const SUSPICIOUS_SCORE = 0.5;
// A source feeding this many layered accounts reads as a ring.
const RING_LAYERED = 2;
const NEW_ACCOUNT_DAYS = 90;

const ROLE_REASONS = {
  SOURCE: 'Sends money out to several accounts',
  AGGREGATOR: 'Collects money from several accounts and passes it on',
  MULE: 'Receives money and moves it on quickly',
};

export const roleLabel = role => ROLE_LABELS[role] || 'Unknown';

const fromOf = e => e.from_account ?? e.source;
const toOf = e => e.to_account ?? e.target;
export const edgeKey = e => `${fromOf(e)}->${toOf(e)}`;

const isSuspiciousNode = n =>
  Boolean(n) && (SUSPICIOUS_ROLES.has(n.role) || (n.smurf_score || 0) >= SUSPICIOUS_SCORE);

/** A transfer is flagged when its pattern is a known laundering shape, or both ends look suspicious. */
export function isFlaggedEdge(edge, nodeById) {
  if (edge.pattern === 'NORMAL') return false;
  if (NAMED_PATTERNS.has(edge.pattern)) return true;
  return isSuspiciousNode(nodeById.get(fromOf(edge))) && isSuspiciousNode(nodeById.get(toOf(edge)));
}

const indexNodes = nodes => new Map(nodes.map(n => [n.account_id, n]));

/** Replay order: flagged edges get the hop number of their sender, walking out from the sources. */
export function hopRounds(nodes, edges) {
  const nodeById = indexNodes(nodes);
  const flagged = edges.filter(e => isFlaggedEdge(e, nodeById));
  const outgoing = new Map();
  flagged.forEach(e => outgoing.set(fromOf(e), [...(outgoing.get(fromOf(e)) || []), e]));
  const hasInflow = new Set(flagged.map(toOf));

  const sources = [...outgoing.keys()].filter(id => nodeById.get(id)?.role === 'SOURCE');
  const roots = sources.length ? sources : [...outgoing.keys()].filter(id => !hasInflow.has(id));

  const rounds = new Map();
  const depth = new Map();
  const walk = seeds => {
    const queue = seeds.filter(id => !depth.has(id));
    queue.forEach(id => depth.set(id, 0));
    while (queue.length) {
      const id = queue.shift();
      (outgoing.get(id) || []).forEach(e => {
        if (!rounds.has(edgeKey(e))) rounds.set(edgeKey(e), depth.get(id));
        if (!depth.has(toOf(e))) {
          depth.set(toOf(e), depth.get(id) + 1);
          queue.push(toOf(e));
        }
      });
    }
  };

  walk(roots);
  // Cycles have no root; start each leftover loop at its first sender.
  let leftover = flagged.find(e => !rounds.has(edgeKey(e)));
  while (leftover) {
    walk([fromOf(leftover)]);
    leftover = flagged.find(e => !rounds.has(edgeKey(e)));
  }
  return rounds;
}

/** Connected groups of accounts, largest first, with the figures the graph labels need. */
export function summariseClusters(nodes, edges) {
  const nodeById = indexNodes(nodes);
  const neighbours = new Map(nodes.map(n => [n.account_id, []]));
  edges.forEach(e => {
    if (!neighbours.has(fromOf(e)) || !neighbours.has(toOf(e))) return;
    neighbours.get(fromOf(e)).push(toOf(e));
    neighbours.get(toOf(e)).push(fromOf(e));
  });

  const seen = new Set();
  const groups = [];
  nodes.forEach(({ account_id }) => {
    if (seen.has(account_id)) return;
    const ids = [];
    const queue = [account_id];
    seen.add(account_id);
    while (queue.length) {
      const id = queue.shift();
      ids.push(id);
      neighbours.get(id).forEach(nb => {
        if (!seen.has(nb)) { seen.add(nb); queue.push(nb); }
      });
    }
    groups.push(ids);
  });

  return groups
    .sort((a, b) => b.length - a.length)
    .map((ids, index) => {
      const members = new Set(ids);
      const flagged = edges.filter(e =>
        members.has(fromOf(e)) && members.has(toOf(e)) && isFlaggedEdge(e, nodeById));
      return {
        index,
        ids,
        flaggedAmount: flagged.reduce((sum, e) => sum + (e.total_amount || 0), 0),
        flaggedCount: flagged.length,
        maxRisk: Math.max(0, ...ids.map(id => nodeById.get(id)?.smurf_score || 0)),
      };
    });
}

export function riskiestCluster(clusters) {
  if (!clusters.length) return null;
  return clusters.reduce((best, c) =>
    c.maxRisk > best.maxRisk || (c.maxRisk === best.maxRisk && c.flaggedAmount > best.flaggedAmount) ? c : best);
}

/** One plain-language verdict for the whole graph, plus the figures shown under it. */
export function graphVerdict(nodes, edges) {
  const nodeById = indexNodes(nodes);
  const flagged = edges.filter(e => isFlaggedEdge(e, nodeById));
  const figures = {
    accounts: nodes.length,
    flaggedAmount: flagged.reduce((sum, e) => sum + (e.total_amount || 0), 0),
    flaggedTransfers: flagged.length,
    highestRisk: Math.max(0, ...nodes.map(n => n.smurf_score || 0)),
  };

  // Roles come from the detector, so the verdict trusts them rather than node scores.
  const layered = nodes.filter(n => n.role === 'MULE' || n.role === 'AGGREGATOR').length;
  const hasSource = nodes.some(n => n.role === 'SOURCE');
  let headline = 'Suspicious flow to review';
  if (!flagged.length) headline = 'No suspicious flow';
  else if (hasSource && layered >= RING_LAYERED) headline = 'Likely mule ring';

  return { headline, figures };
}

/** Rows for the list view: every account, riskiest first, with money sent and received. */
export function accountRows(nodes, edges) {
  const totals = id => edges.reduce((acc, e) => ({
    sent: acc.sent + (fromOf(e) === id ? e.total_amount || 0 : 0),
    received: acc.received + (toOf(e) === id ? e.total_amount || 0 : 0),
  }), { sent: 0, received: 0 });
  return [...nodes]
    .sort((a, b) => (b.smurf_score || 0) - (a.smurf_score || 0))
    .map(node => ({ node, ...totals(node.account_id) }));
}

const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`;
const capitalise = text => text.charAt(0).toUpperCase() + text.slice(1);

/** Plain reasons an investigator can read in the account panel. */
export function whyFlagged(node, edges) {
  const reasons = [];
  if (ROLE_REASONS[node.role]) reasons.push(ROLE_REASONS[node.role]);

  if (isSuspiciousNode(node)) {
    const senders = new Set(edges.filter(e => toOf(e) === node.account_id).map(fromOf));
    const receivers = new Set(edges.filter(e => fromOf(e) === node.account_id).map(toOf));
    const parts = [];
    if (senders.size) parts.push(`received from ${plural(senders.size, 'account')}`);
    if (receivers.size) parts.push(`sent to ${plural(receivers.size, 'account')}`);
    if (parts.length) reasons.push(capitalise(parts.join(', ')));
  }

  const age = node.account_age_days;
  if (Number.isFinite(age) && age < NEW_ACCOUNT_DAYS) reasons.push(`Account opened ${plural(age, 'day')} ago`);
  if (node.kyc_status && node.kyc_status !== 'COMPLETE') reasons.push(`KYC is ${node.kyc_status.toLowerCase()}`);
  return reasons;
}
