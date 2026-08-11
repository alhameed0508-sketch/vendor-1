# MuleCatch — GitHub & Ecosystem Deep Research

Research date: 2026-07-26. Star counts and activity verified via `gh` API on that date.

---

## 1. Context: IOB Cybernova / PSBs Hackathon Series

**What it is.** Cybernova is Indian Overseas Bank's entry in the **PSBs Hackathon Series**, driven by the
Department of Financial Services (DFS), Ministry of Finance, and coordinated by the **Indian Banks'
Association (IBA)**. Each public sector bank hosts one edition with its own problem statement.

| Edition | Academic partner | Knowledge partner | Theme |
|---|---|---|---|
| Cybernova 2025 | B.S. Abdur Rahman Crescent Institute | Ernst & Young | "Authentication Solutions for Enhanced Security" |
| IOB PAN-India 2026 | RMK Group of Institutions | — | Financial Inclusion, Digital Banking, Banking for Specially Abled |

Notes that matter for positioning:

- The **2025 IOB theme was authentication**, not mule detection. Mule accounts are the problem statement
  of *other* banks in the series — Bank of India (with IIT Hyderabad) runs the "Cybersecurity, Fraud &
  AI" track (₹20 lakh pool), and the RBI "Zero Financial Frauds" HaRBInger hackathon has an explicit
  mule-account statement.
- The **2026 IOB edition** (RMK Group MoU) lists Financial Inclusion / Digital Banking / Specially Abled
  as its stated pillars, culminating May 2026, with winners showcased at **Global Fintech Festival 2026**.
- Confirmed by GitHub evidence: `jasvindar123/BOI-IITH-Hackathon` is literally titled "Mule Account
  Detection", and `Durgesh-18/Mule-Account-Detection-...` cites the **RBIH MuleHunter challenge at IIT
  Delhi Tryst 2026**.

**Implication.** If MuleCatch is being pitched into an IOB channel, the framing should lead with the
**RBI/RBIH MuleHunter.AI alignment and the DFS/IBA regulatory mandate**, not with a specific Cybernova
problem statement — the published IOB statements don't name mule detection. Positioning MuleCatch as the
bank-side implementation of MuleHunter.AI's 19 behavioural patterns is the stronger pitch.

**MuleHunter.AI baseline to benchmark against.** Built in-house by RBIH; 19 mule behaviour patterns
derived with partner banks; live at Canara Bank (~95% claimed detection accuracy), PNB, Bank of India,
Bank of Baroda, AU Small Finance Bank; Federal Bank in late-stage rollout; 15+ more banks in pipeline.
**It is not open source** — there is no RBIH MuleHunter repository on GitHub. Every "MuleHunter" repo on
GitHub is a student reimplementation.

---

## 2. Tier 1 — Production-grade repos worth actually adopting

These are the ones with real engineering behind them, active maintenance, and a usable license.

| Repo | Stars | License | Why it matters to MuleCatch |
|---|---|---|---|
| [checkmarble/marble](https://github.com/checkmarble/marble) | 568★ | NOASSERTION (check before use) | **Closest thing to a real open-source competitor.** Real-time decision engine for fraud *and* AML — rule authoring UI, case management, decision API. Study its rule-DSL and case-management data model rather than reinventing them. |
| [jube-home/aml-fraud-transaction-monitoring](https://github.com/jube-home/aml-fraud-transaction-monitoring) | 90★ | **AGPL-3.0** | Real-time transaction monitoring with ML, C#. Commercially-backed (jube.io). AGPL — safe to read and learn from, **not** safe to vendor into a proprietary bank deployment. |
| [awslabs/graphstorm](https://github.com/awslabs/graphstorm) | 453★ | Apache-2.0 | Billion-scale graph ML framework. This is the answer to "how do we go from a demo graph to IOB's actual account volume." Directly relevant given your `torch-geometric` dependency. |
| [opensanctions/opensanctions](https://github.com/opensanctions/opensanctions) + [yente](https://github.com/opensanctions/yente) (162★) + [followthemoney](https://github.com/opensanctions/followthemoney) (85★) | 778★ | Various OSS | Sanctions/PEP database, matching API, and the **FollowTheMoney entity graph data model** used by dozens of fincrime tools. FtM is a genuinely good schema to borrow for your counterparty/entity layer. |
| [moov-io/watchman](https://github.com/moov-io/watchman) | 482★ | Apache-2.0 | AML/CTF/KYC/OFAC watchlist search service. Drop-in sanctions screening microservice. |
| [pyg-team/pytorch_geometric](https://github.com/pyg-team/pytorch_geometric) | 23.9k★ | MIT | Already your GNN dependency. |
| [feast-dev/feast](https://github.com/feast-dev/feast) | 7.2k★ | Apache-2.0 | Feature store. Solves the train/serve skew problem you will hit when your Kafka path and your batch path compute velocity features differently. |
| [fingerprintjs/fingerprintjs](https://github.com/fingerprintjs/fingerprintjs) | 27.9k★ | MIT | Device fingerprinting. Mule rings are frequently caught by *device reuse*, not transaction pattern. High-value, low-effort signal. |
| [tirrenotechnologies/tirreno](https://github.com/tirrenotechnologies/tirreno) | 1.5k★ | AGPL-3.0 | Event tracking + threat detection + risk scoring framework. Good reference for the risk-scoring surface. |

---

## 3. Tier 2 — Research & model repos (the detection core)

| Repo | Stars | License | Notes |
|---|---|---|---|
| [safe-graph/graph-fraud-detection-papers](https://github.com/safe-graph/graph-fraud-detection-papers) | 1,870★ | none | **Start here.** Curated graph/transformer fraud + anomaly detection papers with code links. Has a live paper dashboard. |
| [benedekrozemberczki/awesome-fraud-detection-papers](https://github.com/benedekrozemberczki/awesome-fraud-detection-papers) | 1,819★ | — | Broader data-mining fraud literature. |
| [AI4Risk/awesome-fraud-detection](https://github.com/AI4Risk/awesome-fraud-detection) | 48★ | — | Specifically graph-based financial fraud, papers **and** code. Smaller but better targeted. |
| [pygod-team/pygod](https://github.com/pygod-team/pygod) | 1,497★ | BSD-2 | Graph outlier detection library. Unsupervised — important, because you will not have labelled mule accounts on day one. Note: last push Nov 2024. |
| [yzhao062/pyod](https://github.com/yzhao062/pyod) | 9,929★ | BSD-2 | 60+ tabular anomaly detectors, actively maintained. The tabular complement to PyGOD. |
| [Stream-AD/MIDAS](https://github.com/Stream-AD/MIDAS) | 776★ | Apache-2.0 | **Real-time anomaly detection on dynamic/streaming graphs.** Constant-memory, microsecond-scale. Conceptually the right primitive for a Kafka-fed mule detector. |
| [safe-graph/DGFraud](https://github.com/safe-graph/DGFraud) (759★) / [DGFraud-TF2](https://github.com/safe-graph/DGFraud-TF2) (139★) | | Apache-2.0 | Graph fraud detection toolbox — implementations of the classic papers (CARE-GNN, Player2Vec, etc.). Archived-ish (2022) but the model implementations remain the reference. |
| [IBM/Multi-GNN](https://github.com/IBM/Multi-GNN) | 119★ | Apache-2.0 | **Multi-GNN architectures for AML** — the companion code to IBM's AMLworld work. Directly on-target. |
| [RongLiu-AML/EvoAML](https://github.com/RongLiu-AML/EvoAML) | 415★ | MIT | Graph networks + temporal evolution for AML, framed around BSA/AMLA 2020 compliance. Temporal evolution is exactly the mule "dormancy → burst" signature. |
| [issacchan26/AntiMoneyLaunderingDetectionWithGNN](https://github.com/issacchan26/AntiMoneyLaunderingDetectionWithGNN) | 70★ | none | Graph Attention Network for AML. Clean, readable reference implementation. |
| [Fraud-Detection-Handbook](https://github.com/Fraud-Detection-Handbook/fraud-detection-handbook) | 714★ | NOASSERTION | Reproducible ML for card fraud — free book + notebooks. **Best single resource for evaluation methodology under extreme class imbalance**, which is where most hackathon submissions fall apart. |
| [graphistry/pygraphistry](https://github.com/graphistry/pygraphistry) | 2,539★ | BSD-3 | GPU-accelerated large graph visualization. Relevant to your Network Intelligence page if the graph outgrows what the browser can render. |

---

## 4. Tier 3 — Datasets & synthetic data generators

Data is the binding constraint on this problem. There is no public Indian mule-account dataset.

| Repo / dataset | Stars | License | Notes |
|---|---|---|---|
| [IBM/AMLSim](https://github.com/IBM/AMLSim) | 379★ | Apache-2.0 | **The reference AML simulator.** Multi-agent simulation producing synthetic bank transactions with *known injected laundering typologies* (fan-in, fan-out, cycle, scatter-gather). This is how you generate labelled mule rings without real data. Last push Sep 2025. |
| [SantanderAI/gen-fraud-graph](https://github.com/SantanderAI/gen-fraud-graph) | 275★ | Apache-2.0 | Synthetic fraud **graph** generator for benchmarking graph fraud models — from a real bank's AI team, on PyPI, actively maintained (Jul 2026). Newer and more convenient than AMLSim. |
| IBM **AMLworld** (dataset, on Kaggle) | — | — | Large synthetic multi-bank AML dataset. Community repos: [hugocorreia123/tracer-aml-graph-intelligence](https://github.com/hugocorreia123/tracer-aml-graph-intelligence), [emzerbib/aml-detection](https://github.com/emzerbib/aml-detection), [daniikc/DeteccionFraudeGrafosHibrido](https://github.com/daniikc/DeteccionFraudeGrafosHibrido) (PNA + XGBoost hybrid, masters thesis). |
| **Elliptic** Bitcoin dataset | — | — | 200k labelled Bitcoin txs, licit/illicit. The standard GNN-AML benchmark. Best reference impls: [markasame/fraud-detection-gnn](https://github.com/markasame/fraud-detection-gnn) (GraphSAGE vs XGBoost baseline + GNNExplainer + FastAPI + Streamlit — a well-structured full stack), [advaitrane/GCN_Elliptic-Dataset](https://github.com/advaitrane/GCN_Elliptic-Dataset) (16★), [fmerizzi/GCN_detect_bitcoin_money_laundering](https://github.com/fmerizzi/GCN_detect_bitcoin_money_laundering) (19★). |
| **PaySim** (mobile money simulator) | — | — | Kaggle synthetic mobile-money dataset. Closest public proxy to UPI-style flows. |
| [ihmeuw/pseudopeople](https://github.com/ihmeuw/pseudopeople) | 25★ | — | Realistic simulated population data for testing entity resolution at scale — useful for your KYC/counterparty-linking layer. |

**Caveat worth stating in any pitch:** all of the above are synthetic or crypto. Performance on AMLSim or
Elliptic does **not** transfer to Indian CBS data. Frame benchmark numbers as methodology validation, not
as expected production accuracy.

---

## 5. Tier 4 — Competitive intelligence: peer mule-detection projects

These are other people building your exact thing, mostly for Indian hackathons. Low star counts, mostly
unlicensed — **read for feature ideas, do not copy code** (no license = all rights reserved).

| Repo | Stars | What's notable |
|---|---|---|
| [pranavpanchal1326/ARGUS-PRISM](https://github.com/pranavpanchal1326/ARGUS-PRISM) | 10★ | "Pre-crime intelligence — catches the warming phase 72 hours *before* illicit funds arrive." Strong differentiating narrative; iDEA 2.0 PS3. Live demo deployed. |
| [Rupali-2507/MULE_HUNTER](https://github.com/Rupali-2507/MULE_HUNTER) | 7★ | UPI-focused: GraphSAGE + **JA3 TLS fingerprinting** + Extended Isolation Forest. The JA3 network-layer signal is a genuinely clever angle most submissions miss. |
| [Durgesh-18/Mule-Account-Detection-Based-on-Transaction-Graph-Analytics-...](https://github.com/Durgesh-18/Mule-Account-Detection-Based-on-Transaction-Graph-Analytics-and-Temporal-Activity-Window-Detection) | 0★ | EDA for the **RBIH MuleHunter challenge, IIT Delhi Tryst 2026**. Focuses on velocity, fan-in/fan-out ratios, dormancy-to-activity shifts. Useful for feature parity. |
| [Atrangi-Coders/Financial-Forensics-Engine](https://github.com/Atrangi-Coders/Financial-Forensics-Engine) | 4★ | Graph analysis + statistical anomaly + interactive viz. Part of a whole cluster of **RIFT 2026 hackathon** money-muling repos. |
| [shauryagangrade/mule-account-detection-poc](https://github.com/shauryagangrade/mule-account-detection-poc) | 4★ | Straightforward transaction-pattern + behavioural-signal PoC. |
| [vaibhav-aiml/aml-gnn-upi](https://github.com/vaibhav-aiml/aml-gnn-upi) | 1★ | GNN for AML specifically in **UPI networks**. |
| [Parth0603/MuleAccountDetection](https://github.com/Parth0603/MuleAccountDetection) | 0★ | Risk scoring + explainability + compliance reporting + investigation workflows — same scope as MuleCatch. |
| [jasvindar123/BOI-IITH-Hackathon](https://github.com/jasvindar123/BOI-IITH-Hackathon) | 0★ | Confirms Bank of India / IIT-H is the mule-account track. |
| [Vandita-1011/AI-Driven-Suspicious-Activity-Detection](https://github.com/Vandita-1011/AI-Driven-Suspicious-Activity-Detection) | 0★ | Agentic AI framework for autonomous AML — the LLM-agent framing. |
| [luuisotorres/AML-MultiAgent-RAG](https://github.com/luuisotorres/AML-MultiAgent-RAG) | 15★ | Multi-agent RAG for AML/CFT compliance Q&A. Relevant to your `genai/` and `compliance/` modules. |

**Reading of the field:** the crowded, undifferentiated middle is "GNN + dashboard." The submissions that
stand out do one of: (a) a non-obvious signal layer (JA3/device fingerprint, temporal warming), (b) real
regulatory workflow depth (STR/FIU-IND filing, EWS timelines), or (c) demonstrated scale. MuleCatch's
existing `compliance/` and `explainability/` modules are the right bet — that is the moat versus 40 other
GraphSAGE demos.

---

## 6. Gaps in MuleCatch worth closing (from this research)

Reading your `backend/requirements.txt` against the field:

1. **Unsupervised path — closed.** PyOD ECOD now supplies a capped,
   explainable cold-start peer anomaly score over the shared 13-feature account
   vector.
2. **No streaming-graph anomaly primitive.** You have Kafka but the detection appears batch/graph-query
   based. **MIDAS** gives constant-memory microsecond anomaly scoring on edge streams — a strong "real-time"
   claim for a pitch.
3. **Device/session signal — partially closed.** Device reuse,
   emulator/root/bot flags, graph links, and a privacy-minimised channel
   ingestion endpoint are implemented. Server-side attestation remains a
   bank-channel integration.
4. **Sanctions screening — closed for UNSC.** MuleCatch imports the UNSC
   consolidated list and persists explainable matches. PEP/adverse-media data
   still requires a licensed bank source.
5. **Synthetic data generation isn't in-tree.** AMLSim or `gen-fraud-graph` in `backend/data/` would let
   you demo injected laundering typologies with ground truth — far more convincing than a static fixture.
6. **Entity resolution — closed for onboarding.** RapidFuzz hybrid matching
   combines fuzzy names/addresses with exact hashed phone, email, government-ID,
   and device identifiers, backed by PostgreSQL in production.
7. **Scale story.** `networkx` + `python-louvain` will not survive IOB-scale graphs. GraphStorm (or Neo4j
   GDS, which you already have the driver for) is the credible answer to the inevitable scale question.

---

## 7. Sources

- [IOB Cybernova 2025 hackathon concludes — UNI India](https://www.uniindia.com/iob-cybernova-2025-hackathon-concludes/south/news/3460201.html)
- [IOB Cybernova 2025 Grand Finale — India Education Diary](https://indiaeducationdiary.in/iob-cybernova-2025-hackathon-grand-finale-concludes-successfully-fostering-innovation-in-authentication-for-a-safer-digital-future/)
- [IOB signs MoU with B.S. Abdur Rahman Crescent Institute — APN News](https://www.apnnews.com/indian-overseas-bank-signs-mou-with-b-s-abdur-rahman-crescent-institute-to-launch-cybersecurity-hackathon/)
- [IOB partners RMK Group for PAN-India Cybersecurity Hackathon 2026 — Indian Masterminds](https://indianmasterminds.com/news/indian-overseas-bank-rmk-cybersecurity-hackathon-2026-186449/)
- [Cybernova Hackathon 2025 problem statement PDF — Dept. of Financial Services](https://www.financialservices.gov.in/beta/sites/default/files/2025-10/Indian-o-Bank.pdf)
- [PSBs Hackathon Series 2026 problem statements — MNNIT](https://www.mnnit.ac.in/hackathon2026/index.php?page=problem)
- [PSB's Cybersecurity, Fraud & AI Hackathon — Bank of India / IIT Hyderabad](https://bankofindia.bank.in/cybersecurity-hackathon)
- [MuleHunter — RBIH project page](https://rbihub.in/projects/mulehunter)
- [RBI pilots MuleHunter.AI — FinTech Futures](https://www.fintechfutures.com/ai-in-fintech/reserve-bank-of-india-pilots-new-mulehunter-ai-solution-to-help-identify-mule-accounts)
- [RBI Innovation Hub develops MuleHunter.AI — Business Standard](https://www.business-standard.com/finance/news/rbi-innovation-hub-develops-mulehunter-ai-to-combat-mule-account-frauds-124120601042_1.html)
