# MuleCatch Implementation Log

## Date: 2026-05-08

## Overview

This document records the implementation of the Onboarding Risk Scorer, security fixes, and frontend design system overhaul for the MuleCatch hackathon submission targeting IOB CyberNova Problem Statement #2.

---

## Phase 1: Onboarding Risk Scorer (Backend)

### Problem Addressed

The hackathon problem statement explicitly requires detection **during onboarding as well as post-onboarding**. Previously, MuleCatch only handled post-onboarding detection via transactional analysis. This was the single biggest gap versus the judging criteria.

### Architecture Decision

Followed the existing Repository -> Service -> Route layered pattern already established by the screening module. This ensures consistency across the codebase and makes the new feature immediately understandable to reviewers.

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `models/onboarding/__init__.py` | 0 | Python package init |
| `models/onboarding/risk_scorer.py` | ~270 | Core scoring engine with 14 signal scorers |
| `backend/repositories/onboarding_repository.py` | ~65 | In-memory data access layer |
| `backend/services/onboarding_service.py` | ~60 | Business logic orchestration |
| `backend/api/v1/routes/onboarding.py` | ~80 | REST API endpoints |

### Files Modified

| File | Changes |
|------|---------|
| `backend/api/deps.py` | Added `get_onboarding_repository()` and `get_onboarding_service()` singletons |
| `backend/api/v1/router.py` | Imported and registered `register_onboarding_routes` |
| `infra/security/auth.py` | Added `onboarding:read` and `onboarding:write` permissions to all roles |
| `backend/core/config.py` | Added `onboarding_risk_threshold` setting (default 0.50) |

### 14 Signal Scorers

Each scorer returns a value between 0.0 (no risk) and 1.0 (maximum risk):

| # | Signal | Weight | Reason Code | Risk Indicator |
|---|--------|--------|-------------|----------------|
| 1 | Account Age | 0.10 | OB01 | Accounts < 7 days old |
| 2 | KYC Completeness | 0.12 | OB02 | Incomplete KYC documentation |
| 3 | Document Verification Speed | 0.06 | OB03 | Suspiciously fast (<30s) = bot |
| 4 | Device Fingerprint Overlap | 0.10 | OB04 | Device shared with flagged accounts |
| 5 | IP Geolocation Mismatch | 0.08 | OB05 | IP vs declared address mismatch |
| 6 | Phone Number Age | 0.06 | OB06 | Recently activated phone numbers |
| 7 | Email Age | 0.06 | OB07 | Recently created email addresses |
| 8 | Address Verification | 0.05 | OB08 | Address not verified |
| 9 | Selfie Match | 0.08 | OB09 | Low selfie-document confidence |
| 10 | Application Velocity | 0.09 | OB10 | Multiple apps from same device/IP |
| 11 | Similar Name Accounts | 0.05 | OB11 | Name variants in system |
| 12 | High-Risk Geography | 0.05 | OB12 | FATF high-risk region |
| 13 | Nocturnal Application | 0.04 | OB13 | Applications at unusual hours (11PM-5AM) |
| 14 | Dormancy After Onboarding | 0.06 | OB14 | Account parked for future mule use |

### Risk Level Classification

| Level | Score Range | Recommendation |
|-------|-------------|----------------|
| LOW | < 0.30 | APPROVE |
| MEDIUM | 0.30 - 0.50 | APPROVE_WITH_MONITORING |
| HIGH | 0.50 - 0.70 | MANUAL_REVIEW |
| CRITICAL | > 0.70 | BLOCK |

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/onboarding/assess` | `onboarding:write` | Single account assessment |
| POST | `/api/v1/onboarding/batch` | `onboarding:write` | Batch assessment |
| GET | `/api/v1/onboarding/assessments` | `onboarding:read` | List with filtering |
| GET | `/api/v1/onboarding/assessments/{id}` | `onboarding:read` | Single assessment |
| GET | `/api/v1/onboarding/stats` | `onboarding:read` | Aggregate statistics |

---

## Phase 2: Security Fixes

### 2.1 LDAP Injection Prevention

**File:** `infra/ldap/ldap_client.py`

**Before:** Raw string interpolation in LDAP filter
```python
search_filter = f"(sAMAccountName={username})"
```

**After:** Escaped with `ldap3.utils.conv.escape_filter_chars`
```python
from ldap3.utils.conv import escape_filter_chars
search_filter = f"(sAMAccountName={escape_filter_chars(username)})"
```

**Impact:** Prevents LDAP injection attacks where malicious usernames like `admin)(|(password=*` could bypass authentication.

### 2.2 SHA256 to bcrypt Migration

**File:** `infra/security/auth.py`

**Before:** Demo user passwords hashed with SHA256 (unsalted, fast, vulnerable to rainbow tables)
```python
"password_hash": hashlib.sha256(b"iob@2024").hexdigest()
```

**After:** Passwords hashed with bcrypt via the existing `hash_password()` function
```python
"password_hash": hash_password("iob@2024")
```

Authentication now uses `verify_password()` (bcrypt comparison) instead of direct SHA256 hash comparison. The `hashlib` import was removed as it is no longer needed.

**Impact:** Bcrypt is salted, slow-by-design, and industry standard for password storage. Critical for a cybersecurity hackathon submission.

### 2.3 Print to Logger Migration

**File:** `backend/detection/pipeline.py`

Replaced 4 `print()` calls in production code with proper `logging.getLogger(__name__)`:
- GNN scoring fallback warning
- Explainability failure warning
- Classification/narrative failure warning
- Pipeline completion info message

**Impact:** Structured logging enables proper log aggregation, filtering, and monitoring in production.

---

## Phase 3: Frontend Design System Overhaul

### Color Palette Migration

Migrated from emerald/green Darktrace-inspired palette to cyan/navy Sora/fintech design system.

#### Dark Theme Key Changes

| Variable | Old Value | New Value |
|----------|-----------|-----------|
| `--bg-base` | `#0A0A0F` | `#0B1020` |
| `--bg-card` | `rgba(16,16,24,0.65)` | `rgba(24,34,53,0.85)` |
| `--color-primary` | `#10B981` (emerald) | `#3EE7FF` (cyan) |
| `--color-secondary` | `#22D3EE` | `#00C2A8` (teal) |
| `--text-primary` | `#F0FDF4` | `#F5F7FA` |
| `--text-secondary` | `#94A3B8` | `#A9B4C7` |
| `--critical` | `#F43F5E` | `#FF5C7A` |
| `--high` | `#FB923C` | `#FFB020` |
| `--accent-green` | `#10B981` | `#16C784` |

#### Light Theme Key Changes

| Variable | Old Value | New Value |
|----------|-----------|-----------|
| `--bg-base` | `#F8FAFC` | `#F7FAFC` |
| `--color-primary` | `#059669` | `#0077FF` |
| `--color-secondary` | `#0891B2` | `#00B894` |
| `--text-primary` | `#0F172A` | `#111827` |

### Files Modified

| File | Changes |
|------|---------|
| `App.css` | Root variables, light theme, all hardcoded emerald refs |
| `index.css` | Glass utilities, shimmer gradient, command palette highlights |
| `BackgroundGrid.js` | Background color, orb gradients, grid dots, scanline |
| `SplashScreen.js` | Background, glow, hexagon SVG, MC text fill, cursor color |
| `DemoTour.js` | Architecture layer colors, finale colors, narration bar |
| `NetworkGraph.js` | ROLE_COLORS, edge pattern colors, particle colors |
| `ROIDashboard.js` | Detection breakdown, KPI gradients, chart colors |
| `Dashboard.js` | Pulse dot color |
| `JudgePresentation.js` | Chakravyuha ring colors, architecture layer colors |
| `IndiaMap.js` | Geography fill/hover, pulse circles, tooltip, legend |

---

## Phase 4: Onboarding Frontend Page

### Files Created

| File | Purpose |
|------|---------|
| `frontend/src/onboarding/OnboardingRisk.js` | Full onboarding risk assessment page |

### Files Modified

| File | Changes |
|------|---------|
| `frontend/src/App.js` | Added import and `/onboarding` route |
| `frontend/src/components/Sidebar.js` | Added onboarding icon and nav item |

### Page Features

1. **4 Stat Cards** (GlassCardMetric): Total Assessed, High-Risk Flagged, Auto-Blocked, Pass Rate
2. **Assessment Form**: 14 input fields matching all backend signal parameters
3. **Risk Result Display**: Horizontal gradient risk bar, risk level badge, recommendation
4. **Signal Breakdown Table**: Per-signal score, weight, and weighted contribution
5. **Reason Codes Panel**: Triggered signals with OB01-OB14 codes
6. **Recent Assessments Table**: History of assessments with risk bars and levels

---

## Verification Checklist

- [ ] Backend: `cd backend && python -m pytest tests/ -v` passes all existing tests
- [ ] Onboarding API: POST to `/api/v1/onboarding/assess` returns risk assessment
- [ ] Security: LDAP filter escapes special chars
- [ ] Security: Demo login works with bcrypt-hashed passwords
- [ ] Security: No `print()` calls remain in detection pipeline
- [ ] Frontend: Dark theme shows new cyan/navy palette
- [ ] Frontend: Light theme shows new blue/teal palette
- [ ] Frontend: Onboarding page renders at `/onboarding`
- [ ] Frontend: Sidebar shows 4 navigation items
- [ ] Docker: `docker-compose up --build` starts without errors

---

## Technical Decisions

### Why Frozen Dataclass for OnboardingRiskResult?

Using `@dataclass(frozen=True)` ensures immutability of assessment results. Once computed, a risk score cannot be accidentally modified — critical for audit compliance and legal defensibility.

### Why In-Memory Repository?

For hackathon demo purposes, an in-memory repository provides instant functionality without database dependencies. The repository interface is identical to what a PostgreSQL implementation would use, making the transition trivial.

### Why 14 Signals?

The signal set was designed to cover the complete lifecycle of a mule account onboarding:
- **Identity signals** (KYC, selfie, documents): Detect identity fraud
- **Device/network signals** (fingerprint, IP, velocity): Detect coordinated attacks
- **Behavioral signals** (timing, dormancy): Detect account parking patterns
- **Context signals** (geography, name similarity): Detect synthetic identities

### Why Cyan/Navy Instead of Emerald/Black?

The new palette:
1. Differentiates MuleCatch from competitors using standard green/black cybersecurity themes
2. Provides better contrast ratios for accessibility
3. Aligns with modern fintech design systems (Stripe, Plaid, Sora)
4. Feels more premium and less "generic security dashboard"
