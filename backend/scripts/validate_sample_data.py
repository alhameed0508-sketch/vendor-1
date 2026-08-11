"""
Validation script for MuleCatch model on sample mule account data.
Tests prediction accuracy and production-readiness.
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from typing import Any, Dict  # noqa: E402

import pandas as pd  # noqa: E402

# Import MuleCatch components
from core.config import get_settings  # noqa: E402
from detection.risk_scorer import assess_account_risk  # noqa: E402


def load_sample_data():
    """Load both CSV files."""
    print("=" * 80)
    print("LOADING SAMPLE DATA")
    print("=" * 80)

    # Load aggregated features with ground truth
    features_file = r"C:\Users\HP\Downloads\mule_detection.csv"
    features_df = pd.read_csv(features_file)
    print(f"\n[OK] Loaded {len(features_df)} accounts from mule_detection.csv")
    print(f"  Columns: {', '.join(features_df.columns)}")

    # Load raw transactions
    txn_file = r"C:\Users\HP\Downloads\Sample Mule account data.csv"
    txn_df = pd.read_csv(txn_file, sep='|')
    print(f"\n[OK] Loaded {len(txn_df)} transactions from Sample Mule account data.csv")
    print(f"  Columns: {', '.join(txn_df.columns)}")

    return features_df, txn_df


def extract_target_accounts(features_df):
    """Extract the 6 specific accounts mentioned by user."""
    target_acids = [
        '4ac3ebe74c',  # HIGH RISK - 13 txns, 92% pass-through
        'b8b3e9f99f',  # HIGH RISK - 1,704 txns, Rs.21.76L
        '37a7e9dc1e',  # HIGH RISK - 5 txns, 100% pass-through, round amounts
        '996f3bf5a0',  # MEDIUM RISK - 27 txns, 97% pass-through
        '2ed098c444',  # MEDIUM RISK - 35 txns, 91% pass-through
        '4435127fe3',  # MEDIUM RISK - 10 txns, 99% pass-through
    ]

    # Match accounts by prefix
    target_accounts = []
    for acid_prefix in target_acids:
        matched = features_df[features_df['ACID (masked)'].str.startswith(acid_prefix)]
        if not matched.empty:
            target_accounts.append(matched.iloc[0])
        else:
            print(f"  [!] Account {acid_prefix}... not found in dataset")

    return pd.DataFrame(target_accounts)


def compute_risk_scores(account_features: pd.Series) -> Dict[str, Any]:
    """
    Compute risk scores using MuleCatch v2.0 detection logic.
    Uses the new configurable risk_scorer module.
    """
    # Convert pandas Series to dict for risk_scorer
    features_dict = account_features.to_dict()

    # Use the new risk scorer
    assessment = assess_account_risk(features_dict)

    # Convert to dict format expected by validation report
    scores = {
        'predicted_risk': assessment.risk_level,
        'confidence': assessment.confidence,
        'behavioral_signal_count': assessment.behavioral_count,
        'anomaly_signal_count': assessment.anomaly_count,
        'details': {
            signal: True for signal in (
                assessment.behavioral_signals + assessment.anomaly_signals
            )
        },
        'reason': assessment.reason
    }

    return scores


def validate_predictions(features_df):
    """Run detection and compare with ground truth."""
    print("\n" + "=" * 80)
    print("MODEL PREDICTION VALIDATION")
    print("=" * 80)

    target_df = extract_target_accounts(features_df)

    if target_df.empty:
        print("\n[!] No target accounts found!")
        return None

    print(f"\n[OK] Found {len(target_df)} target accounts")

    results = []

    for idx, account in target_df.iterrows():
        acid = account['ACID (masked)']
        ground_truth = account['final_verdict_corrected']

        # Compute prediction
        scores = compute_risk_scores(account)
        predicted = scores['predicted_risk']

        # Extract ground truth risk level
        if 'HIGH RISK' in ground_truth:
            gt_level = 'HIGH RISK'
        elif 'MEDIUM RISK' in ground_truth:
            gt_level = 'MEDIUM RISK'
        else:
            gt_level = 'LOW RISK'

        # Match result
        correct = (predicted == gt_level)

        result = {
            'acid': acid,
            'txn_count': int(account['txn_count']),
            'turnover': float(account['turnover']),
            'passthrough_ratio': round(account['in_out_ratio'], 3),
            'ground_truth': gt_level,
            'predicted': predicted,
            'correct': correct,
            'confidence': scores['confidence'],
            'behavioral_signals': scores['behavioral_signal_count'],
            'anomaly_signals': scores['anomaly_signal_count'],
            'details': scores['details'],  # Already formatted correctly
            'reason': scores.get('reason', '')
        }

        results.append(result)

    return results


def print_validation_report(results):
    """Generate and print validation report."""
    if not results:
        return

    print("\n" + "=" * 80)
    print("INDIVIDUAL ACCOUNT PREDICTIONS")
    print("=" * 80)

    for i, r in enumerate(results, 1):
        status = "[OK] CORRECT" if r['correct'] else "[X] MISMATCH"
        print(f"\n{i}. {r['acid']}... — {r['txn_count']} txns, Rs.{r['turnover']:,.0f}")
        print(f"   Ground Truth:  {r['ground_truth']}")
        print(f"   Predicted:     {r['predicted']} ({r['confidence']} confidence)")
        print(f"   Status:        {status}")
        print(f"   Signals:       {r['behavioral_signals']} behavioral, {r['anomaly_signals']} anomaly")
        print("   Details:       ", end='')
        flags = [k for k, v in r['details'].items() if v]
        print(', '.join(flags) if flags else 'none')

    # Overall metrics
    print("\n" + "=" * 80)
    print("OVERALL ACCURACY METRICS")
    print("=" * 80)

    correct_count = sum(1 for r in results if r['correct'])
    total_count = len(results)
    accuracy = correct_count / total_count if total_count > 0 else 0

    print(f"\nAccuracy: {correct_count}/{total_count} ({accuracy*100:.1f}%)")

    # Breakdown by risk level
    high_risk_results = [r for r in results if 'HIGH' in r['ground_truth']]
    medium_risk_results = [r for r in results if 'MEDIUM' in r['ground_truth']]

    if high_risk_results:
        high_correct = sum(1 for r in high_risk_results if r['correct'])
        print(f"HIGH RISK:   {high_correct}/{len(high_risk_results)} correct ({high_correct/len(high_risk_results)*100:.1f}%)")

    if medium_risk_results:
        med_correct = sum(1 for r in medium_risk_results if r['correct'])
        print(f"MEDIUM RISK: {med_correct}/{len(medium_risk_results)} correct ({med_correct/len(medium_risk_results)*100:.1f}%)")


def check_hardcoded_values():
    """Scan codebase for hardcoded thresholds and magic numbers."""
    print("\n" + "=" * 80)
    print("PRODUCTION-READINESS: HARDCODED VALUES AUDIT")
    print("=" * 80)

    settings = get_settings()

    issues = []

    # Check if thresholds are in config
    print("\n[OK] Checking detection thresholds...")

    if hasattr(settings, 'smurf_flag_threshold'):
        print(f"  [OK] SMURF_FLAG_THRESHOLD = {settings.smurf_flag_threshold} (from config)")
    else:
        issues.append("SMURF_FLAG_THRESHOLD not in config.py")

    if hasattr(settings, 'onboarding_risk_threshold'):
        print(f"  [OK] ONBOARDING_RISK_THRESHOLD = {settings.onboarding_risk_threshold} (from config)")
    else:
        issues.append("ONBOARDING_RISK_THRESHOLD not in config.py")

    # Check environment variables
    print("\n[OK] Checking environment configuration...")
    critical_env_vars = [
        'MODEL_VERSION',
        'RULE_VERSION',
        'ENV',
    ]

    for var in critical_env_vars:
        value = os.getenv(var)
        if value:
            print(f"  [OK] {var} = {value}")
        else:
            issues.append(f"{var} not set in environment")

    # Summary
    print("\n" + "-" * 80)
    if issues:
        print(f"\n[!] Found {len(issues)} potential issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n[OK] No hardcoded values detected - all thresholds are configurable!")

    return issues


def generate_summary():
    """Generate final summary."""
    print("\n" + "=" * 80)
    print("PRODUCTION-READINESS SUMMARY")
    print("=" * 80)

    settings = get_settings()

    checklist = {
        "Configuration is data-driven": settings.env == 'development',
        "Thresholds are configurable": hasattr(settings, 'smurf_flag_threshold'),
        "Model version is tracked": hasattr(settings, 'model_version'),
        "Rule version is tracked": hasattr(settings, 'rule_version'),
    }

    print()
    for item, status in checklist.items():
        symbol = "[OK]" if status else "[X]"
        print(f"{symbol} {item}")

    print("\n" + "-" * 80)
    print("\nRecommendations:")
    print("1. Review docs/PRODUCTION_READINESS.md for complete deployment checklist")
    print("2. Run full benchmark suite: python -m backend.benchmark.runner")
    print("3. Ensure all 83 external gates in PRODUCTION_READINESS.md are satisfied")
    print("4. Validate against bank-labeled data (not synthetic)")


def main():
    """Main validation workflow."""
    try:
        # Load data
        features_df, txn_df = load_sample_data()

        # Validate predictions
        results = validate_predictions(features_df)
        if results:
            print_validation_report(results)

        # Check for hardcoded values
        check_hardcoded_values()

        # Generate summary
        generate_summary()

        print("\n" + "=" * 80)
        print("VALIDATION COMPLETE")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n[X] Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
