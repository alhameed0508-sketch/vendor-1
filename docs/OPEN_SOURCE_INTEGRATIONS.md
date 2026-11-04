# Open-source intelligence integrations

Validated on 2026-07-26. Only permissively licensed, maintained components are
linked directly into the runtime.

## Integrated

| Project | License | MuleCatch use | Guardrail |
|---|---|---|---|
| [PyOD](https://github.com/yzhao062/pyod) | BSD-2-Clause | ECOD peer-group anomaly scoring over 13 normalized account/graph/behavior features | Supporting signal only; maximum risk boost is 0.06 and it cannot create an alert alone |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | MIT | Hybrid entity resolution across name/address similarity and exact hashed identifiers | Exact phone/email values are SHA-256 hashed before persistence; only candidate IDs and evidence are returned |
| [FingerprintJS](https://github.com/fingerprintjs/fingerprintjs) compatible contract | MIT | `/api/v1/device/events` accepts a channel-generated fingerprint hash and emulator/root/bot flags | MuleCatch does not collect raw browser attributes; collection belongs in the bank's consented customer channel |
| [TopoJSON Client](https://github.com/topojson/topojson-client) | ISC | Converts the bundled India state topology for the D3 transaction-flow map | No remote map/CDN request; geography remains a bundled, version-controlled asset |

The device endpoint and the transaction pipeline use the same singleton
`DeviceProfiler`, so pre-transaction channel intelligence contributes to later
account risk. In a multi-pod production deployment, the bank channel should
also publish the same event to Kafka/Neo4j so history remains shared across
workers.

### Customer-channel example

This code belongs in internet/mobile banking, not in the investigator console:

```javascript
import FingerprintJS from '@fingerprintjs/fingerprintjs';

const agent = await FingerprintJS.load();
const { visitorId } = await agent.get();

await fetch('/api/v1/device/events', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${channelToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    account_id: customerAccountId,
    device_fingerprint_hash: visitorId,
    source_channel: 'WEB',
  }),
});
```

The open-source FingerprintJS identifier is spoofable. Treat it as corroborating
evidence, not authentication. A bank-grade deployment should add server-side
attestation, replay protection, VPN/proxy intelligence, and explicit privacy
notices.

## Already present in MuleCatch

- PyTorch Geometric GraphSAGE, directed edges, edge features, focal loss.
- LightGBM learned account scorer with a deterministic heuristic fallback;
  XGBoost remains optional rather than inflating the default production image.
- Neo4j relationship persistence, PageRank, betweenness, Louvain communities.
- Kafka transaction ingestion with manual commits and bounded deduplication.
- Device reuse, IP reuse, Markov lifecycle, behavioral baselines, transaction
  semantics, RBIH-aligned deterministic patterns, SHAP-style explanation.
- UNSC sanctions ingestion and fuzzy watchlist screening.
- Human review, feedback, alert prioritisation, STR workflow, audit hash chain.

## Deliberately not embedded

- GraphStorm, Flink, Feast, and federated learning require bank-scale
  infrastructure and operating ownership. They are deployment tracks, not safe
  library additions.
- OpenSanctions/Yente and commercial device/network intelligence require data
  licensing, privacy review, and external service credentials.
- MIDAS is a useful streaming-graph benchmark, but its research implementation
  is not inserted into settlement decisions without validation on bank traffic.
- LLMs remain investigator assistants. They do not approve onboarding, freeze
  accounts, or file STRs autonomously.

## Dependency-security decision

The frontend keeps React Router on the maintained React-18-compatible 6.30.4
release. On 2026-07-26 the npm advisory service reports two moderate issues in
that line, while the otherwise-compatible 7.18 line is affected by a
high-severity React Server Components advisory. MuleCatch does not use SSR/RSC,
does not accept untrusted navigation destinations, and CI blocks all
high/critical production dependency findings. Revisit the version after a
React-18-compatible fully patched release is available.

## Validation before adverse use

Back-test each new signal on time-split bank data, publish precision/recall and
false-positive results by customer segment, calibrate thresholds, run fairness
and drift checks, obtain model-risk approval, and preserve human review for all
high-impact outcomes.
