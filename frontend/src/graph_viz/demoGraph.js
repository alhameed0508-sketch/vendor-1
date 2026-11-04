// Sample mule network shown when an alert has no graph data yet.
export const DEMO_GRAPH = {
  nodes: [
    // Cluster 1 — Chennai smurfing ring (ALT-0001)
    { account_id: 'AC001', role: 'SOURCE',     smurf_score: 0.93, betweenness: 0.62, pagerank: 0.18, bank: 'IOB',  city: 'Chennai',    account_age_days: 3,   kyc_status: 'PARTIAL'  },
    { account_id: 'AC002', role: 'AGGREGATOR', smurf_score: 0.88, betweenness: 0.78, pagerank: 0.21, bank: 'IOB',  city: 'Chennai',    account_age_days: 5,   kyc_status: 'PARTIAL'  },
    { account_id: 'AC003', role: 'MULE',       smurf_score: 0.76, betweenness: 0.31, pagerank: 0.09, bank: 'SBI',  city: 'Coimbatore', account_age_days: 12,  kyc_status: 'PENDING'  },
    { account_id: 'AC004', role: 'MULE',       smurf_score: 0.71, betweenness: 0.22, pagerank: 0.08, bank: 'SBI',  city: 'Madurai',    account_age_days: 8,   kyc_status: 'PENDING'  },
    { account_id: 'AC005', role: 'MULE',       smurf_score: 0.68, betweenness: 0.18, pagerank: 0.07, bank: 'BOI',  city: 'Trichy',     account_age_days: 6,   kyc_status: 'PENDING'  },
    { account_id: 'AC006', role: 'LEGITIMATE', smurf_score: 0.12, betweenness: 0.05, pagerank: 0.04, bank: 'IOB',  city: 'Chennai',    account_age_days: 420, kyc_status: 'COMPLETE' },
    // Cluster 2 — Bangalore consolidation ring (ALT-0002)
    { account_id: 'AC010', role: 'SOURCE',     smurf_score: 0.77, betweenness: 0.55, pagerank: 0.14, bank: 'IOB',  city: 'Bangalore',  account_age_days: 14,  kyc_status: 'PARTIAL'  },
    { account_id: 'AC011', role: 'MULE',       smurf_score: 0.65, betweenness: 0.33, pagerank: 0.10, bank: 'HDFC', city: 'Bangalore',  account_age_days: 21,  kyc_status: 'PENDING'  },
    { account_id: 'AC012', role: 'MULE',       smurf_score: 0.59, betweenness: 0.28, pagerank: 0.09, bank: 'HDFC', city: 'Mysore',     account_age_days: 18,  kyc_status: 'PENDING'  },
    { account_id: 'AC013', role: 'LEGITIMATE', smurf_score: 0.08, betweenness: 0.04, pagerank: 0.03, bank: 'IOB',  city: 'Bangalore',  account_age_days: 730, kyc_status: 'COMPLETE' },
    // Cluster 3 — Mumbai device-overlap pair (ALT-0003)
    { account_id: 'AC020', role: 'SOURCE',     smurf_score: 0.54, betweenness: 0.40, pagerank: 0.11, bank: 'IOB',  city: 'Mumbai',     account_age_days: 30,  kyc_status: 'COMPLETE' },
    { account_id: 'AC021', role: 'MULE',       smurf_score: 0.48, betweenness: 0.22, pagerank: 0.07, bank: 'PNB',  city: 'Pune',       account_age_days: 45,  kyc_status: 'PARTIAL'  },
    { account_id: 'AC022', role: 'MULE',       smurf_score: 0.44, betweenness: 0.18, pagerank: 0.06, bank: 'PNB',  city: 'Nagpur',     account_age_days: 60,  kyc_status: 'PARTIAL'  },
  ],
  edges: [
    // Cluster 1 edges
    { from_account: 'AC001', to_account: 'AC002', total_amount: 750000, txn_count: 8,  pattern: 'SMURFING',      timestamps: ['2025-05-01T02:14:00', '2025-05-01T02:38:00'] },
    { from_account: 'AC001', to_account: 'AC003', total_amount: 450000, txn_count: 5,  pattern: 'SMURFING',      timestamps: ['2025-05-01T03:10:00'] },
    { from_account: 'AC002', to_account: 'AC004', total_amount: 380000, txn_count: 6,  pattern: 'CONSOLIDATION', timestamps: ['2025-05-02T14:22:00'] },
    { from_account: 'AC002', to_account: 'AC005', total_amount: 270000, txn_count: 5,  pattern: 'SMURFING',      timestamps: ['2025-05-02T15:00:00'] },
    { from_account: 'AC003', to_account: 'AC006', total_amount: 120000, txn_count: 3,  pattern: 'NORMAL',        timestamps: ['2025-05-03T09:00:00'] },
    { from_account: 'AC004', to_account: 'AC006', total_amount:  80000, txn_count: 2,  pattern: 'NORMAL',        timestamps: ['2025-05-03T10:00:00'] },
    // Cluster 2 edges
    { from_account: 'AC010', to_account: 'AC011', total_amount: 320000, txn_count: 6,  pattern: 'SMURFING',      timestamps: ['2025-05-04T11:00:00'] },
    { from_account: 'AC010', to_account: 'AC012', total_amount: 300000, txn_count: 5,  pattern: 'SMURFING',      timestamps: ['2025-05-04T11:45:00'] },
    { from_account: 'AC011', to_account: 'AC013', total_amount: 180000, txn_count: 3,  pattern: 'NORMAL',        timestamps: ['2025-05-05T09:00:00'] },
    // Cluster 3 edges
    { from_account: 'AC020', to_account: 'AC021', total_amount: 120000, txn_count: 4,  pattern: 'CONSOLIDATION', timestamps: ['2025-05-06T16:00:00'] },
    { from_account: 'AC020', to_account: 'AC022', total_amount:  90000, txn_count: 3,  pattern: 'CONSOLIDATION', timestamps: ['2025-05-06T16:30:00'] },
  ],
};
