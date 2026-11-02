import {
  AMOUNT_NORMALIZATION_BASE,
  PRIORITY_WEIGHT_AMOUNT,
  PRIORITY_WEIGHT_CENTRALITY,
  PRIORITY_WEIGHT_EVIDENCE,
  PRIORITY_WEIGHT_RISK,
  PRIORITY_WEIGHT_TIME,
  SEVERITY_PRIORITY,
} from '../config';

// Risk as the queue ranks it: weighted by the evidence the ring's members carry themselves
// (backend rank_score), so a community that only looks suspicious by shape does not top the queue.
export function riskTerm(a) {
  return Math.min(1, a.rank_score ?? a.risk_score ?? 0);
}

export function scorePriority(a) {
  const risk   = riskTerm(a);
  const amt    = Math.min(1, Math.log1p(a.total_amount || 0) / Math.log1p(AMOUNT_NORMALIZATION_BASE));
  const nodes  = (a.nodes || []);
  const cent   = nodes.length ? Math.max(...nodes.map(n => n.betweenness_centrality || n.betweenness || 0)) : 0;
  const evid   = Math.min(1, (a.reason_codes || []).length / 10);
  const newAcc = nodes.filter(n => (n.account_age_days || 999) < 7).length;
  const time   = Math.min(1, 0.5 + 0.5 * (newAcc / Math.max(nodes.length, 1)));
  return PRIORITY_WEIGHT_RISK * risk + PRIORITY_WEIGHT_AMOUNT * amt + PRIORITY_WEIGHT_CENTRALITY * cent + PRIORITY_WEIGHT_EVIDENCE * evid + PRIORITY_WEIGHT_TIME * time;
}

export function sarProbability(a) {
  const base = SEVERITY_PRIORITY[a.severity?.toUpperCase()] || 0.1;
  return Math.min(1, base + Math.min((a.reason_codes || []).length * 0.02, 0.1));
}

export function complexity(a) {
  const score = (a.account_count || 0) + (a.txn_count || 0) / 10 + (a.reason_codes || []).length;
  return score > 15 ? 'HIGH' : score > 5 ? 'MEDIUM' : 'LOW';
}

export function breakdown(a) {
  const nodes = a.nodes || [];
  const cent  = nodes.length ? Math.max(...nodes.map(n => n.betweenness_centrality || n.betweenness || 0)) : 0;
  const newAcc = nodes.filter(n => (n.account_age_days || 999) < 7).length;
  return {
    risk_score:         riskTerm(a),
    amount_factor:      Math.min(1, Math.log1p(a.total_amount || 0) / Math.log1p(AMOUNT_NORMALIZATION_BASE)),
    network_centrality: cent,
    evidence_diversity: Math.min(1, (a.reason_codes || []).length / 10),
    time_sensitivity:   Math.min(1, 0.5 + 0.5 * (newAcc / Math.max(nodes.length, 1))),
  };
}
