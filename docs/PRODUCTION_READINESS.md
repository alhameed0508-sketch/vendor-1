# Production readiness

## Status

MuleCatch is a production-engineered candidate. Repository controls can make a
deployment safe-by-default, but production effectiveness and regulatory
acceptance cannot be manufactured from source code alone.

## In-repository controls

| Control | Status |
|---|---|
| Authentication and RBAC | Implemented |
| Durable PostgreSQL/Neo4j production requirement | Enforced |
| Kafka manual commit after successful processing | Implemented |
| Bounded duplicate replay protection | Implemented |
| Production dependency readiness probe | Implemented |
| Onboarding and screening API/UI integration | Implemented |
| Configured-only UNSC refresh (SSRF protection) | Implemented |
| Tamper-evident audit hash chain | Implemented |
| Alert model/rule attribution | Implemented |
| Synthetic execution disabled in production | Implemented |
| Placeholder/weak secret rejection | Implemented |
| TLS enforcement for Kafka/Neo4j/Redis/PostgreSQL/LDAP | Implemented at startup |
| Non-root/read-only Kubernetes container | Implemented |
| Public internal-metrics ingress | Removed |
| Blocking dependency audits | Implemented |

## Mandatory external go-live gates

These gates remain **blocked until supplied by the bank or responsible
authority**:

1. Representative, de-identified historical transactions and confirmed
   investigator outcomes.
2. Time-based out-of-sample validation, segment analysis, calibration, and an
   approved alert-capacity threshold.
3. Independent model validation and Model Risk Management approval.
4. FIU-IND/FINGate schema, packaging, submission, rejection, and
   acknowledgement acceptance testing.
5. Production FRI or other government intelligence endpoint and credentials.
6. Bank IAM/LDAP integration, HSM/secret-manager keys, certificates, and
   network routes.
7. Penetration test, threat model, privacy impact assessment, data-retention
   approval, and disaster-recovery exercise.
8. Compliance, legal, operations, information-security, and change-management
   sign-off.
9. Human-review policy, false-positive remediation, customer grievance, and
   freeze/unfreeze procedures.

No document should label the system “production approved” until all gates have
named owners, dated evidence, and approval references.

The Kubernetes `base` includes single-node reference data stores for
development and smoke testing. It is deliberately rejected by the production
startup validator because those reference services use plaintext internal
transports. Production must use a bank-approved overlay or managed services
with TLS and high availability.

## Acceptance metrics

The bank must define values before validation:

- Recall at fixed daily investigation capacity
- Precision and false positives per 1,000 monitored accounts
- PR-AUC and calibration error
- Recall by customer/account/channel segment
- P95/P99 ingest-to-alert latency
- Duplicate and replay rate
- Investigator handling time and inter-reviewer agreement
- Data loss after broker, database, or worker failure
- Recovery time objective and recovery point objective

## Authoritative references

- [RBI KYC Amendment Directions, 2025](https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=12866)
- [RBI Fraud Risk Management Directions, 2024](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12702%281%29.html)
- [RBI Digital Payment Security Controls](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12032%283%29.html)
- [FIU-IND FINGate 2.0 reporting-format introduction](https://fiuindia.gov.in/pdfs/quicklinks/Reporting_Format.pdf)
- [FIU-IND FINGate reports manual](https://fiuindia.gov.in/pdfs/quicklinks/User_Manual_FINGate_Reports.pdf)

Regulatory interpretation must be confirmed by the reporting entity's legal
and compliance functions.
