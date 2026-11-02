import {
  roleLabel, isFlaggedEdge, hopRounds, summariseClusters, riskiestCluster,
  graphVerdict, whyFlagged, edgeKey, accountRows,
} from './graphModel';

const node = (account_id, role, smurf_score = 0, extra = {}) => ({ account_id, role, smurf_score, ...extra });
const edge = (from_account, to_account, pattern = 'OBSERVED', total_amount = 100000) =>
  ({ from_account, to_account, pattern, total_amount });
const byId = nodes => new Map(nodes.map(n => [n.account_id, n]));

const RING = [
  node('S1', 'SOURCE', 0.9), node('A1', 'AGGREGATOR', 0.8),
  node('M1', 'MULE', 0.7), node('M2', 'MULE', 0.66), node('L1', 'LEGITIMATE', 0.05),
];
const RING_EDGES = [
  edge('S1', 'A1', 'SMURFING', 500000), edge('A1', 'M1'), edge('A1', 'M2'), edge('M1', 'L1', 'NORMAL', 20000),
];

describe('roleLabel', () => {
  it.each([['SOURCE', 'Source'], ['AGGREGATOR', 'Aggregator'], ['MULE', 'Mule'], ['LEGITIMATE', 'Legitimate']])(
    '%s -> %s', (role, label) => expect(roleLabel(role)).toBe(label));
  it('falls back to Unknown', () => expect(roleLabel(undefined)).toBe('Unknown'));
});

describe('isFlaggedEdge', () => {
  const nodes = byId(RING);
  it('flags named laundering patterns', () => expect(isFlaggedEdge(edge('L1', 'L1', 'SMURFING'), nodes)).toBe(true));
  it('never flags NORMAL', () => expect(isFlaggedEdge(edge('S1', 'A1', 'NORMAL'), nodes)).toBe(false));
  it('flags OBSERVED between two suspicious accounts', () => expect(isFlaggedEdge(edge('A1', 'M1'), nodes)).toBe(true));
  it('does not flag OBSERVED into a low-risk legitimate account', () =>
    expect(isFlaggedEdge(edge('M1', 'L1'), nodes)).toBe(false));
  it('flags OBSERVED when both ends are high risk even if role is unknown', () => {
    const n = byId([node('U1', 'UNKNOWN', 0.7), node('U2', 'UNKNOWN', 0.6)]);
    expect(isFlaggedEdge(edge('U1', 'U2'), n)).toBe(true);
  });
});

describe('hopRounds', () => {
  it('orders flagged edges outward from the source, one round per hop', () => {
    const rounds = hopRounds(RING, RING_EDGES);
    expect(rounds.get(edgeKey(RING_EDGES[0]))).toBe(0);
    expect(rounds.get(edgeKey(RING_EDGES[1]))).toBe(1);
    expect(rounds.get(edgeKey(RING_EDGES[2]))).toBe(1);
  });
  it('leaves normal edges out of the replay', () =>
    expect(hopRounds(RING, RING_EDGES).has(edgeKey(RING_EDGES[3]))).toBe(false));
  it('starts from accounts with no flagged inflow when there is no source role', () => {
    const nodes = [node('X', 'MULE', 0.8), node('Y', 'MULE', 0.8), node('Z', 'MULE', 0.8)];
    const edges = [edge('X', 'Y'), edge('Y', 'Z')];
    const rounds = hopRounds(nodes, edges);
    expect([...rounds.values()]).toEqual([0, 1]);
  });
  it('still replays a pure cycle', () => {
    const nodes = [node('X', 'MULE', 0.8), node('Y', 'MULE', 0.8)];
    const rounds = hopRounds(nodes, [edge('X', 'Y'), edge('Y', 'X')]);
    expect(rounds.size).toBe(2);
  });
});

describe('summariseClusters and riskiestCluster', () => {
  const nodes = [...RING, node('Q1', 'UNKNOWN', 0.2), node('Q2', 'UNKNOWN', 0.3)];
  const edges = [...RING_EDGES, edge('Q1', 'Q2', 'NORMAL', 900000)];
  const clusters = summariseClusters(nodes, edges);

  it('finds connected groups, largest first', () => {
    expect(clusters.map(c => c.ids.length)).toEqual([5, 2]);
  });
  it('totals flagged money only', () => expect(clusters[0].flaggedAmount).toBe(700000));
  it('picks the cluster with the highest risk', () => expect(riskiestCluster(clusters).ids).toContain('S1'));
  it('returns null for no clusters', () => expect(riskiestCluster([])).toBeNull());
});

describe('graphVerdict', () => {
  it('calls a source-to-mules chain with high risk a likely mule ring', () =>
    expect(graphVerdict(RING, RING_EDGES).headline).toBe('Likely mule ring'));
  it('trusts the detector roles: a source feeding layered accounts is a ring even at moderate scores', () => {
    const nodes = [node('S1', 'SOURCE', 0.45), node('A1', 'AGGREGATOR', 0.48), node('M1', 'MULE', 0.47)];
    expect(graphVerdict(nodes, [edge('S1', 'A1'), edge('A1', 'M1')]).headline).toBe('Likely mule ring');
  });
  it('needs at least two layered accounts behind the source to call a ring', () => {
    const nodes = [node('S1', 'SOURCE', 0.9), node('M1', 'MULE', 0.9)];
    expect(graphVerdict(nodes, [edge('S1', 'M1')]).headline).toBe('Suspicious flow to review');
  });
  it('reports no suspicious flow when nothing is flagged', () => {
    const nodes = [node('L1', 'LEGITIMATE', 0.1), node('L2', 'LEGITIMATE', 0.1)];
    expect(graphVerdict(nodes, [edge('L1', 'L2', 'NORMAL')]).headline).toBe('No suspicious flow');
  });
  it('asks for review when flow is flagged but no ring shape exists', () => {
    const nodes = [node('U1', 'UNKNOWN', 0.6), node('U2', 'UNKNOWN', 0.6)];
    expect(graphVerdict(nodes, [edge('U1', 'U2')]).headline).toBe('Suspicious flow to review');
  });
  it('returns the figures shown under the headline', () => {
    const v = graphVerdict(RING, RING_EDGES);
    expect(v.figures).toEqual({ accounts: 5, flaggedAmount: 700000, flaggedTransfers: 3, highestRisk: 0.9 });
  });
});

describe('accountRows', () => {
  it('lists accounts riskiest first with money sent and received', () => {
    const rows = accountRows(RING, RING_EDGES);
    expect(rows.map(r => r.node.account_id)).toEqual(['S1', 'A1', 'M1', 'M2', 'L1']);
    expect(rows[1]).toMatchObject({ sent: 200000, received: 500000 });
  });
});

describe('whyFlagged', () => {
  it('explains a mule in plain words', () => {
    const reasons = whyFlagged(
      node('M1', 'MULE', 0.7, { account_age_days: 12, kyc_status: 'PENDING' }), RING_EDGES);
    expect(reasons).toEqual([
      'Receives money and moves it on quickly',
      'Received from 1 account, sent to 1 account',
      'Account opened 12 days ago',
      'KYC is pending',
    ]);
  });
  it('says nothing alarming about an old, verified, quiet account', () =>
    expect(whyFlagged(node('L1', 'LEGITIMATE', 0.05, { account_age_days: 900, kyc_status: 'COMPLETE' }), []))
      .toEqual([]));
});
