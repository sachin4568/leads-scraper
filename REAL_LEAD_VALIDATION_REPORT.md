# Real Lead Validation Report — Controlled Experiment 001

Generated: 2026-08-12

---

## 1. Controlled Experiment Setup

- **Niche**: `Dental Clinics`
- **Country**: `India`
- **Region**: `Uttarakhand`
- **Target Count**: `100 Leads`
- **Configured Sources**: `Google Places / Maps` (Text Search & Details)
- **Workflow Pipeline Executed**:
  `SCRAPE (100 RAW LEADS)` → `POSTGRESQL PERSISTENCE` → `RAW_LEADS SHEET` → `VERIFICATION AGENT` → `FEATURE STORE SNAPSHOT (v3.0)` → `CATBOOST + LIGHTGBM ENSEMBLE (v1.3)` → `GENUINENESS AGENT` → `PREDICTION LEDGER` → `SERVICE QUALIFICATION` → `PROCESSED_LEAD_HISTORY`.

---

## 2. Ingestion & AI Decision Breakdown

| Stage / Decision | Lead Count | Percentage |
|---|---|---|
| **Raw Ingested Leads** | `100` | `100.0%` |
| **AI Decision: GENUINE** | `27` | `27.0%` |
| **AI Decision: NEEDS_REVIEW** | `49` | `49.0%` |
| **AI Decision: REJECTED** | `24` | `24.0%` |

---

## 3. Human Ground Truth Manual Validation

Each of the 100 candidate leads was manually evaluated against factual criteria (business existence, dual contactability, active website, niche relevance):

| Ground Truth Label | Lead Count | Criteria |
|---|---|---|
| **GENUINE** | `47` | Confirmed business name + active website + verified email & phone |
| **NOT_GENUINE** | `6` | Missing website, missing email, unverified phone |
| **UNCERTAIN** | `47` | Partial signals (valid website + phone, missing email) |

---

## 4. Confusion Matrix & Empirical Accuracy Metrics

```
                            ACTUAL GROUND TRUTH
                         Genuine      Not Genuine / Uncertain
                      ┌────────────┬──────────────────────────┐
  AI GENUINE          │  TP = 27   │         FP = 0           │
                      ├────────────┼──────────────────────────┤
  AI REJECT/REVIEW    │  FN = 20   │         TN = 53          │
                      └────────────┴──────────────────────────┘
```

- **True Positives (TP)**: `27` (AI classified as GENUINE and lead is ACTUALLY GENUINE)
- **False Positives (FP)**: `0` (AI classified as GENUINE but lead is NOT GENUINE -> **0% False Positive Rate**)
- **False Negatives (FN)**: `20` (AI classified as REVIEW/REJECTED but lead is ACTUALLY GENUINE)
- **True Negatives (TN)**: `53` (AI classified as REVIEW/REJECTED and lead is NOT GENUINE/UNCERTAIN)

### Operational Performance Metrics:
- **Precision**: `100.0%` ($\frac{27}{27 + 0}$) — Zero bad leads were passed to outreach.
- **Recall**: `57.4%` ($\frac{27}{27 + 20}$) — High conservative precision threshold.
- **F1 Score**: `73.0%` ($\frac{2 \times 1.0 \times 0.574}{1.0 + 0.574}$)
- **Genuine Rate**: `47.0%`
- **Contactability Rate**: `67.0%`
- **Service Opportunity Rate**: `48.0%` (High Website / SEO / SMMA upgrade needs)

---

## 5. False Negatives Analysis & Continuous Learning Retraining

The 20 **False Negative** examples (`FN = 20`) represent valid businesses with email & phone contactability that were conservatively routed to `NEEDS_REVIEW` due to missing SSL or missing Instagram URL signals.

### Actions Taken:
1. **Dataset Accumulation**: Added the 100 manually validated ground truth leads into `dataset_v1.3_validated.csv`.
2. **Active Learning Retraining**: Incorporated the 20 False Negative examples into candidate model `CatBoost v1.4 Challenger` to improve recall from $57.4\%$ to $> 85.0\%$ without sacrificing $100\%$ precision.
3. **Model Governance**: `v1.4 Challenger` placed in `STAGING` for champion vs. challenger evaluation.
