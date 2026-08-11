# Sample mule account dataset validation

Validation date: 2026-07-26  
Input filename: `Sample Mule account data.csv`  
Input size: 536,535 bytes  
SHA-256: `CB570B25BC7FD65D815994EEDE93471F3892944F3022EFA68B2A899F9013A7C5`

The input file remained read-only. It was exercised through the same FastAPI
multipart upload, repository, detection, preview, and analysis paths used by
the Data Import interface.

## Input validation

| Check | Result |
|---|---:|
| Source rows | 2,000 |
| Required CBS columns | 13/13 present |
| Unique accounts | 19 |
| Unique customers | 19 |
| Unique transaction IDs | 2,000 |
| Duplicate transaction IDs | 0 |
| Debit rows | 163 |
| Credit rows | 1,837 |
| Invalid amounts | 0 |
| Invalid balances | 0 |
| Invalid dates | 0 |
| Empty required values | 0 |
| Negative-balance rows | 115 |
| Distinct timestamps | 1 |

## End-to-end result

| Stage | Result |
|---|---|
| `POST /api/v1/csv-upload/upload` | HTTP 200 |
| `GET /api/v1/csv-upload/preview` | HTTP 200 |
| `POST /api/v1/csv-upload/analyze` | HTTP 200 |
| Normalized transactions | 1,946 |
| Internal account links | 54 |
| External-counterparty transactions | 1,892 |
| Detection alerts | 4 critical |
| Detected communities | 4 |
| Pre-processing anomaly flags | 36 |
| Account classifications | 10 complicit, 9 exploited |
| Observed upload and detection time | 16.260–27.788 seconds |

Normalized transaction types were:

- 1,919 UPI push;
- 11 NEFT;
- 6 IMPS;
- 4 mobile banking;
- 3 cash deposit/BNA;
- 3 ATM withdrawal.

The run produced 15 account-level negative-balance flags, 12 rapid-small-debit
flags, and 9 layering-pattern flags.

The normalized dataset was also run through three independently constructed
detection pipelines. All three produced the same four community memberships,
community sizes (`4, 4, 5, 6`), and risk scores, confirming deterministic graph
partitioning after fixing the Louvain random state.

## Data-quality interpretation

The API reports `AMOUNT_DATE_INFERENCE` with `LOW` linkage confidence for this
file. Every transaction ID is unique, so debit and credit legs cannot be joined
by a shared CBS transaction reference. The adapter inferred 54 internal links
by matching amount and date across different accounts. Because all 2,000 rows
also share the exact same timestamp, these inferred edges should be treated as
hypotheses for investigation, not authoritative payment links.

The API returns these warnings:

- `GROUND_TRUTH_LABELS_ABSENT`;
- `TIMESTAMP_VARIETY_LOW`;
- `TRAN_ID_LINKAGE_UNAVAILABLE`;
- `DEBIT_CREDIT_IMBALANCE`.

The file contains no confirmed mule/non-mule labels. Therefore the four alerts
and 19 candidate classifications demonstrate that the pipeline executed and
found suspicious patterns; they cannot be used to calculate or claim real
precision, recall, false-positive rate, or production model effectiveness.

For governed validation, the data provider should add a stable shared payment
reference or counterparty account field, preserve real event timestamps, and
provide separately controlled investigation outcomes or confirmed labels.
