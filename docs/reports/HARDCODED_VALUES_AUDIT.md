# Hardcoded Values Audit Report

**Date:** August 11, 2026
**Auditor:** Automated codebase scan
**Scope:** Backend detection, models, and services directories

> **Update:** rules R07, R08, R09, R10, R11, R16 and R19 were removed in `rules-2026.2` after they fired more on genuine accounts than on mules (`docs/buildx/05-evaluation.md` §7.6f). Their constants no longer need externalising. Externalise only the surviving rules' thresholds.

---

## Executive Summary

**Status:** ⚠️ **SIGNIFICANT HARDCODED VALUES FOUND**

| Severity | Count | Files Affected |
|----------|-------|----------------|
| **HIGH** | 34 | 3 files |
| **MEDIUM** | 12 | 3 files |
| **LOW** | 4 | 2 files |
| **TOTAL** | **50** | **3 files** |

### Key Findings

- ✅ **v2.0 risk scoring is clean** - `detection/risk_scorer.py` uses config correctly
- ✅ **Core config structure is good** - `core/config.py` has proper Pydantic setup
- ❌ **Detection pipeline has 16 hardcoded thresholds** - Should be in config
- ❌ **Mule classifier has 34 hardcoded constants** - Major refactoring needed
- ❌ **Entity resolution has 6 hardcoded weights** - Should be configurable

---

## Detailed Findings

### File 1: `backend/detection/pipeline.py`

**Impact:** HIGH - These thresholds affect rule-based detection

| Line | Constant | Value | Severity | Recommendation |
|------|----------|-------|----------|----------------|
| 45 | `STRUCTURED_RATIO_THRESHOLD` | 0.7 | HIGH | Move to config as `RULE_STRUCTURED_RATIO_THRESHOLD` |
| 56 | `SPLIT_TXN_TOTAL_THRESHOLD` | 100000 | HIGH | Move to config as `RULE_SPLIT_TXN_TOTAL` |
| 59 | `UPI_DIGIT_RATIO_THRESHOLD` | 0.6 | HIGH | Move to config as `RULE_UPI_DIGIT_RATIO` |
| 64 | `FUND_SWEEP_RATIO_THRESHOLD` | 0.90 | HIGH | Move to config as `RULE_FUND_SWEEP_RATIO` |
| 476 | `DEFAULT_LOUVAIN_WEIGHT` | 0.50 | MEDIUM | Move to config as `SCORE_LOUVAIN_WEIGHT` |
| 477 | `DEFAULT_SMURF_WEIGHT` | 0.30 | MEDIUM | Move to config as `SCORE_SMURF_WEIGHT` |
| 478 | `DEFAULT_GNN_WEIGHT` | 0.20 | MEDIUM | Move to config as `SCORE_GNN_WEIGHT` |
| 481 | `FALLBACK_LOUVAIN_WEIGHT` | 0.60 | MEDIUM | Move to config as `SCORE_LOUVAIN_WEIGHT_FALLBACK` |
| 482 | `FALLBACK_SMURF_WEIGHT` | 0.40 | MEDIUM | Move to config as `SCORE_SMURF_WEIGHT_FALLBACK` |
| 485 | `SEVERITY_CRITICAL_THRESHOLD` | 0.80 | HIGH | Move to config as `ALERT_SEVERITY_CRITICAL` |
| 486 | `SEVERITY_HIGH_THRESHOLD` | 0.60 | HIGH | Move to config as `ALERT_SEVERITY_HIGH` |
| 496 | `AGG_MAX_WEIGHT` | 0.6 | LOW | Move to config as `SCORE_AGG_MAX_WEIGHT` |
| 497 | `AGG_MEAN_WEIGHT` | 0.4 | LOW | Move to config as `SCORE_AGG_MEAN_WEIGHT` |

**Code Context:**
```python
# Lines 42-70: Rule engine thresholds
STRUCTURED_AMOUNT_LOWER = 40000  # lower bound of "near ₹50k ceiling" band
STRUCTURED_AMOUNT_UPPER = 50000  # upper bound (the ₹50k reporting threshold)
STRUCTURED_MIN_TXNS = 3  # minimum outgoing txns to evaluate
STRUCTURED_RATIO_THRESHOLD = 0.7  # fraction of txns near ceiling to flag
```

---

### File 2: `backend/detection/mule_classifier.py`

**Impact:** HIGH - These weights/thresholds affect mule type classification (COMPLICIT vs EXPLOITED)

#### Classification Weights (34 hardcoded values)

| Line | Constant | Value | Severity | Recommendation |
|------|----------|-------|----------|----------------|
| 27 | `WEIGHT_AGE_VERY_NEW` | 0.20 | HIGH | Move to config as `MULE_WEIGHT_AGE_VERY_NEW` |
| 28 | `WEIGHT_AGE_NEW` | 0.10 | HIGH | Move to config as `MULE_WEIGHT_AGE_NEW` |
| 29 | `WEIGHT_AGE_ESTABLISHED` | 0.15 | HIGH | Move to config as `MULE_WEIGHT_AGE_ESTABLISHED` |
| 32 | `WEIGHT_KYC_PENDING` | 0.10 | HIGH | Move to config as `MULE_WEIGHT_KYC_PENDING` |
| 33 | `WEIGHT_KYC_VERIFIED` | 0.05 | HIGH | Move to config as `MULE_WEIGHT_KYC_VERIFIED` |
| 36 | `WEIGHT_DEVICE_SHARED` | 0.25 | HIGH | Move to config as `MULE_WEIGHT_DEVICE_SHARED` |
| 39 | `WEIGHT_PASSTHROUGH_HIGH` | 0.15 | HIGH | Move to config as `MULE_WEIGHT_PASSTHROUGH_HIGH` |
| 40 | `WEIGHT_PASSTHROUGH_MED` | 0.08 | HIGH | Move to config as `MULE_WEIGHT_PASSTHROUGH_MED` |
| 43 | `WEIGHT_NIGHT_ACTIVITY` | 0.10 | HIGH | Move to config as `MULE_WEIGHT_NIGHT_ACTIVITY` |
| 46 | `WEIGHT_VELOCITY_BURST` | 0.20 | HIGH | Move to config as `MULE_WEIGHT_VELOCITY_BURST` |
| 47 | `WEIGHT_DORMANT_REACTIVATION` | 0.20 | HIGH | Move to config as `MULE_WEIGHT_DORMANT_REACTIVATION` |
| 50 | `WEIGHT_ROLE_SOURCE` | 0.10 | HIGH | Move to config as `MULE_WEIGHT_ROLE_SOURCE` |
| 51 | `WEIGHT_ROLE_AGGREGATOR` | 0.15 | HIGH | Move to config as `MULE_WEIGHT_ROLE_AGGREGATOR` |
| 70 | `WEIGHT_CBS_PASSTHROUGH` | 0.15 | HIGH | Move to config as `MULE_WEIGHT_CBS_PASSTHROUGH` |
| 71 | `WEIGHT_NEG_BALANCE_HIGH` | 0.15 | HIGH | Move to config as `MULE_WEIGHT_NEG_BALANCE_HIGH` |
| 72 | `WEIGHT_NEG_BALANCE_MED` | 0.08 | HIGH | Move to config as `MULE_WEIGHT_NEG_BALANCE_MED` |
| 73 | `WEIGHT_DC_RATIO_MATCH` | 0.10 | HIGH | Move to config as `MULE_WEIGHT_DC_RATIO_MATCH` |
| 74 | `WEIGHT_CREDIT_HUB` | 0.15 | HIGH | Move to config as `MULE_WEIGHT_CREDIT_HUB` |
| 75 | `WEIGHT_CREDIT_FUNNEL` | 0.10 | HIGH | Move to config as `MULE_WEIGHT_CREDIT_FUNNEL` |

#### Classification Thresholds

| Line | Constant | Value | Severity | Recommendation |
|------|----------|-------|----------|----------------|
| 54 | `THRESHOLD_PASSTHROUGH_HIGH` | 0.90 | HIGH | ⚠️ DUPLICATE of config.passthrough_threshold_high |
| 55 | `THRESHOLD_PASSTHROUGH_MED` | 0.70 | HIGH | ⚠️ DUPLICATE of config.passthrough_threshold_medium |
| 56 | `THRESHOLD_AGE_VERY_NEW` | 7 | HIGH | Move to config as `MULE_THRESHOLD_AGE_VERY_NEW` |
| 57 | `THRESHOLD_AGE_NEW` | 30 | HIGH | Move to config as `MULE_THRESHOLD_AGE_NEW` |
| 58 | `THRESHOLD_AGE_ESTABLISHED` | 365 | HIGH | Move to config as `MULE_THRESHOLD_AGE_ESTABLISHED` |
| 59 | `THRESHOLD_NIGHT_TXN_COUNT` | 3 | MEDIUM | Move to config as `MULE_THRESHOLD_NIGHT_TXN_COUNT` |
| 60 | `THRESHOLD_VELOCITY_BURST_DAYS` | 3 | MEDIUM | Move to config as `MULE_THRESHOLD_VELOCITY_BURST_DAYS` |
| 61 | `THRESHOLD_VELOCITY_BURST_TXN` | 5 | MEDIUM | Move to config as `MULE_THRESHOLD_VELOCITY_BURST_TXN` |
| 62 | `THRESHOLD_DORMANT_DAYS` | 180 | MEDIUM | Move to config as `MULE_THRESHOLD_DORMANT_DAYS` |
| 63 | `THRESHOLD_DORMANT_REACTIVATION_TXN` | 10 | MEDIUM | Move to config as `MULE_THRESHOLD_DORMANT_REACTIVATION_TXN` |
| 66 | `THRESHOLD_MIN_TOTAL_SCORE` | 0.15 | HIGH | Move to config as `MULE_THRESHOLD_MIN_TOTAL_SCORE` |
| 67 | `THRESHOLD_CLASSIFICATION_RATIO` | 1.3 | HIGH | Move to config as `MULE_THRESHOLD_CLASSIFICATION_RATIO` |
| 78 | `THRESHOLD_CBS_PASSTHROUGH` | 0.90 | HIGH | ⚠️ DUPLICATE (3rd occurrence!) |
| 79 | `THRESHOLD_DC_RATIO_LOW` | 0.85 | HIGH | Move to config as `MULE_THRESHOLD_DC_RATIO_LOW` |
| 80 | `THRESHOLD_DC_RATIO_HIGH` | 1.15 | HIGH | Move to config as `MULE_THRESHOLD_DC_RATIO_HIGH` |
| 81 | `THRESHOLD_NEG_BALANCE_HIGH` | 10 | MEDIUM | Move to config as `MULE_THRESHOLD_NEG_BALANCE_HIGH` |
| 82 | `THRESHOLD_NEG_BALANCE_MED` | 3 | MEDIUM | Move to config as `MULE_THRESHOLD_NEG_BALANCE_MED` |
| 83 | `THRESHOLD_CREDIT_HUB` | 50 | MEDIUM | Move to config as `MULE_THRESHOLD_CREDIT_HUB` |
| 84 | `THRESHOLD_CREDIT_FUNNEL` | 20 | MEDIUM | Move to config as `MULE_THRESHOLD_CREDIT_FUNNEL` |

**Code Context:**
```python
# Lines 25-90: Mule classification weights and thresholds
# ── Scoring weights (tunable constants) ────────────────────────────────────
# Account age signals
WEIGHT_AGE_VERY_NEW = 0.20  # < 7 days → complicit
WEIGHT_AGE_NEW = 0.10  # < 30 days → complicit
...
```

**CRITICAL ISSUE:** Lines 54-55 duplicate `passthrough_threshold_high/medium` already in config.py!

---

### File 3: `backend/services/entity_resolution_service.py`

**Impact:** MEDIUM - These thresholds affect duplicate account/synthetic identity detection

| Line | Item | Value | Severity | Recommendation |
|------|------|-------|----------|----------------|
| 24 | Class constant `MATCH_THRESHOLD` | 0.55 | MEDIUM | Move to config as `ENTITY_MATCH_THRESHOLD` |
| 46 | `weights["government_id_hash"]` | 0.75 | MEDIUM | Move to config as `ENTITY_WEIGHT_GOV_ID` |
| 47 | `weights["phone_hash"]` | 0.55 | MEDIUM | Move to config as `ENTITY_WEIGHT_PHONE` |
| 48 | `weights["email_hash"]` | 0.45 | MEDIUM | Move to config as `ENTITY_WEIGHT_EMAIL` |
| 49 | `weights["device_fingerprint"]` | 0.45 | MEDIUM | Move to config as `ENTITY_WEIGHT_DEVICE` |
| 70 | Name similarity threshold | 0.85 | MEDIUM | Move to config as `ENTITY_NAME_SIMILARITY_THRESHOLD` |
| 71 | Name similarity weight | 0.25 | LOW | Move to config as `ENTITY_WEIGHT_NAME` |
| 73 | Address similarity threshold | 0.80 | MEDIUM | Move to config as `ENTITY_ADDR_SIMILARITY_THRESHOLD` |
| 74 | Address similarity weight | 0.15 | LOW | Move to config as `ENTITY_WEIGHT_ADDRESS` |

**Code Context:**
```python
# Lines 42-83: Entity matching with hardcoded weights
weights = {
    "government_id_hash": 0.75,
    "phone_hash": 0.55,
    "email_hash": 0.45,
    "device_fingerprint": 0.45,
}
...
if name_similarity >= 0.85:
    score += 0.25 * name_similarity
```

---

## Verification of v2.0 Improvements

### ✅ Correctly Implemented (v2.0)

**File:** `backend/detection/risk_scorer.py`

```python
# GOOD: Uses configurable thresholds from settings
settings = get_settings()

if passthrough_ratio > settings.passthrough_threshold_high:
    signals.append('high_passthrough')

if round_amt_share > settings.round_amount_threshold:
    signals.append('round_amounts')
```

✅ All 16 v2.0 thresholds properly use `settings = get_settings()`
✅ No hardcoded business logic in risk_scorer.py
✅ Clean separation of concerns

### ❌ Issues Found with v2.0

**DUPLICATE THRESHOLDS:**
- `THRESHOLD_PASSTHROUGH_HIGH = 0.90` appears in `mule_classifier.py:54`
- Should use `settings.passthrough_threshold_high` instead
- Same for `THRESHOLD_PASSTHROUGH_MED` (line 55)

---

## Recommended Config Additions

Add these to `backend/core/config.py`:

```python
# Rule engine thresholds (detection/pipeline.py)
rule_structured_ratio: float = Field(0.7, alias="RULE_STRUCTURED_RATIO")
rule_split_txn_total: int = Field(100000, alias="RULE_SPLIT_TXN_TOTAL")
rule_upi_digit_ratio: float = Field(0.6, alias="RULE_UPI_DIGIT_RATIO")
rule_fund_sweep_ratio: float = Field(0.90, alias="RULE_FUND_SWEEP_RATIO")

# Alert severity thresholds
alert_severity_critical: float = Field(0.80, alias="ALERT_SEVERITY_CRITICAL")
alert_severity_high: float = Field(0.60, alias="ALERT_SEVERITY_HIGH")

# Score aggregation weights
score_louvain_weight: float = Field(0.50, alias="SCORE_LOUVAIN_WEIGHT")
score_smurf_weight: float = Field(0.30, alias="SCORE_SMURF_WEIGHT")
score_gnn_weight: float = Field(0.20, alias="SCORE_GNN_WEIGHT")
score_louvain_weight_fallback: float = Field(0.60, alias="SCORE_LOUVAIN_WEIGHT_FALLBACK")
score_smurf_weight_fallback: float = Field(0.40, alias="SCORE_SMURF_WEIGHT_FALLBACK")

# Mule classifier weights (19 weights)
mule_weight_age_very_new: float = Field(0.20, alias="MULE_WEIGHT_AGE_VERY_NEW")
mule_weight_age_new: float = Field(0.10, alias="MULE_WEIGHT_AGE_NEW")
mule_weight_age_established: float = Field(0.15, alias="MULE_WEIGHT_AGE_ESTABLISHED")
mule_weight_kyc_pending: float = Field(0.10, alias="MULE_WEIGHT_KYC_PENDING")
mule_weight_kyc_verified: float = Field(0.05, alias="MULE_WEIGHT_KYC_VERIFIED")
mule_weight_device_shared: float = Field(0.25, alias="MULE_WEIGHT_DEVICE_SHARED")
mule_weight_passthrough_high: float = Field(0.15, alias="MULE_WEIGHT_PASSTHROUGH_HIGH")
mule_weight_passthrough_med: float = Field(0.08, alias="MULE_WEIGHT_PASSTHROUGH_MED")
mule_weight_night_activity: float = Field(0.10, alias="MULE_WEIGHT_NIGHT_ACTIVITY")
mule_weight_velocity_burst: float = Field(0.20, alias="MULE_WEIGHT_VELOCITY_BURST")
mule_weight_dormant_reactivation: float = Field(0.20, alias="MULE_WEIGHT_DORMANT_REACTIVATION")
mule_weight_role_source: float = Field(0.10, alias="MULE_WEIGHT_ROLE_SOURCE")
mule_weight_role_aggregator: float = Field(0.15, alias="MULE_WEIGHT_ROLE_AGGREGATOR")
mule_weight_cbs_passthrough: float = Field(0.15, alias="MULE_WEIGHT_CBS_PASSTHROUGH")
mule_weight_neg_balance_high: float = Field(0.15, alias="MULE_WEIGHT_NEG_BALANCE_HIGH")
mule_weight_neg_balance_med: float = Field(0.08, alias="MULE_WEIGHT_NEG_BALANCE_MED")
mule_weight_dc_ratio_match: float = Field(0.10, alias="MULE_WEIGHT_DC_RATIO_MATCH")
mule_weight_credit_hub: float = Field(0.15, alias="MULE_WEIGHT_CREDIT_HUB")
mule_weight_credit_funnel: float = Field(0.10, alias="MULE_WEIGHT_CREDIT_FUNNEL")

# Mule classifier thresholds (15 thresholds)
mule_threshold_age_very_new: int = Field(7, alias="MULE_THRESHOLD_AGE_VERY_NEW")
mule_threshold_age_new: int = Field(30, alias="MULE_THRESHOLD_AGE_NEW")
mule_threshold_age_established: int = Field(365, alias="MULE_THRESHOLD_AGE_ESTABLISHED")
mule_threshold_night_txn_count: int = Field(3, alias="MULE_THRESHOLD_NIGHT_TXN_COUNT")
mule_threshold_velocity_burst_days: int = Field(3, alias="MULE_THRESHOLD_VELOCITY_BURST_DAYS")
mule_threshold_velocity_burst_txn: int = Field(5, alias="MULE_THRESHOLD_VELOCITY_BURST_TXN")
mule_threshold_dormant_days: int = Field(180, alias="MULE_THRESHOLD_DORMANT_DAYS")
mule_threshold_dormant_reactivation_txn: int = Field(10, alias="MULE_THRESHOLD_DORMANT_REACTIVATION_TXN")
mule_threshold_min_total_score: float = Field(0.15, alias="MULE_THRESHOLD_MIN_TOTAL_SCORE")
mule_threshold_classification_ratio: float = Field(1.3, alias="MULE_THRESHOLD_CLASSIFICATION_RATIO")
mule_threshold_dc_ratio_low: float = Field(0.85, alias="MULE_THRESHOLD_DC_RATIO_LOW")
mule_threshold_dc_ratio_high: float = Field(1.15, alias="MULE_THRESHOLD_DC_RATIO_HIGH")
mule_threshold_neg_balance_high: int = Field(10, alias="MULE_THRESHOLD_NEG_BALANCE_HIGH")
mule_threshold_neg_balance_med: int = Field(3, alias="MULE_THRESHOLD_NEG_BALANCE_MED")
mule_threshold_credit_hub: int = Field(50, alias="MULE_THRESHOLD_CREDIT_HUB")
mule_threshold_credit_funnel: int = Field(20, alias="MULE_THRESHOLD_CREDIT_FUNNEL")

# Entity resolution thresholds
entity_match_threshold: float = Field(0.55, alias="ENTITY_MATCH_THRESHOLD")
entity_name_similarity_threshold: float = Field(0.85, alias="ENTITY_NAME_SIMILARITY_THRESHOLD")
entity_addr_similarity_threshold: float = Field(0.80, alias="ENTITY_ADDR_SIMILARITY_THRESHOLD")
entity_weight_gov_id: float = Field(0.75, alias="ENTITY_WEIGHT_GOV_ID")
entity_weight_phone: float = Field(0.55, alias="ENTITY_WEIGHT_PHONE")
entity_weight_email: float = Field(0.45, alias="ENTITY_WEIGHT_EMAIL")
entity_weight_device: float = Field(0.45, alias="ENTITY_WEIGHT_DEVICE")
entity_weight_name: float = Field(0.25, alias="ENTITY_WEIGHT_NAME")
entity_weight_address: float = Field(0.15, alias="ENTITY_WEIGHT_ADDRESS")
```

**Total new parameters:** 58 (!)

---

## Refactoring Priority

### Phase 1: CRITICAL (Do Immediately)

1. **Fix duplicate thresholds** in `mule_classifier.py`
   - Lines 54-55: Remove duplicates, use `settings.passthrough_threshold_high/medium`
   - Lines 78: Remove duplicate CBS passthrough threshold
   - **Effort:** 10 minutes
   - **Risk:** Low (direct replacement)

2. **Add entity resolution config** (9 parameters)
   - **File:** `services/entity_resolution_service.py`
   - **Effort:** 30 minutes
   - **Impact:** MEDIUM - Affects duplicate detection

### Phase 2: HIGH PRIORITY (This Sprint)

3. **Add rule engine thresholds** (13 parameters)
   - **File:** `detection/pipeline.py`
   - **Effort:** 1 hour
   - **Impact:** HIGH - Affects deterministic detection rules

4. **Add mule classifier config** (34 parameters)
   - **File:** `detection/mule_classifier.py`
   - **Effort:** 2 hours
   - **Impact:** HIGH - Affects mule type classification

### Phase 3: MEDIUM PRIORITY (Next Sprint)

5. **Add score aggregation config** (7 parameters)
   - **File:** `detection/pipeline.py` (lines 476-497)
   - **Effort:** 30 minutes
   - **Impact:** MEDIUM - Affects final risk scoring

---

## Acceptance Checklist

After refactoring:

- [ ] All 58 new parameters added to `backend/core/config.py`
- [ ] All hardcoded constants replaced with `settings.parameter_name`
- [ ] Duplicate thresholds removed (mule_classifier.py lines 54-55, 78)
- [ ] All tests pass: `pytest backend/tests -v`
- [ ] Validation maintains 83.3% accuracy: `python backend/scripts/validate_sample_data.py`
- [ ] No grep matches for new hardcoded patterns:
  ```bash
  grep -r "THRESHOLD.*=.*[0-9]" backend/detection/
  grep -r "WEIGHT.*=.*[0-9]" backend/detection/
  ```
- [ ] Configuration documented in .env.example
- [ ] Model version bumped to v2.1

---

## Conclusion

**Current State:** ⚠️ **v2.0 risk scoring is clean, but mule classifier and rule engine have 50 hardcoded values**

**Recommended Action:**
1. Fix duplicates immediately (10 min)
2. Externalize remaining 58 constants over 2 sprints
3. Bump version to v2.1 after complete

**Estimated Total Effort:** 4-6 hours

**Risk:** Low - mostly find-and-replace with config lookups

---

**Generated by:** Automated hardcoded values audit
**Next Step:** Implement Phase 1 fixes (duplicates) immediately
