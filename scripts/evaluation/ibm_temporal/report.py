"""Curves (PNG) and the Markdown report for the IBM AMLworld evaluation."""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

LABELS = {
    "static_rules": "Static rules (bank-style)",
    "logistic_regression": "Logistic regression",
    "gradient_boosting": "Gradient-boosted trees",
}
COLORS = {"static_rules": "#8a8f98", "logistic_regression": "#2f6fdf", "gradient_boosting": "#0f9d6b"}
POINTS = {
    "best_f1_on_validation": "best F1",
    "false_alerts_at_most_0.1pct": "FPR<=0.1%",
    "false_alerts_at_most_0.5pct": "FPR<=0.5%",
}


def plot_curves(run: dict, out_dir: str) -> str:
    fig, (roc, pr) = plt.subplots(1, 2, figsize=(12, 5))
    for model, r in run["results"].items():
        c = r["curves_test"]
        t = r["test"]
        roc.plot(c["fpr"], c["tpr"], color=COLORS[model], label=f"{LABELS[model]} (ROC-AUC {t['roc_auc']:.3f})")
        pr.plot(c["recall"], c["precision"], color=COLORS[model], label=f"{LABELS[model]} (PR-AUC {t['pr_auc']:.3f})")
    gb = run["results"]["gradient_boosting"]["operating_points"]
    for key, label in POINTS.items():
        m = gb[key]["test"]
        roc.scatter([max(m["false_positive_rate"], 1e-6)], [m["recall"]], color="black", s=22, zorder=5)
        roc.annotate(
            label,
            (max(m["false_positive_rate"], 1e-6), m["recall"]),
            textcoords="offset points",
            xytext=(5, -10),
            fontsize=8,
        )
        pr.scatter([m["recall"]], [m["precision"]], color="black", s=22, zorder=5)
        pr.annotate(label, (m["recall"], m["precision"]), textcoords="offset points", xytext=(5, 4), fontsize=8)
    prevalence = run["results"]["gradient_boosting"]["test"]["prevalence"]
    roc.set_xscale("log")
    roc.set_xlim(1e-5, 1)
    roc.set_ylim(0, 1.01)
    roc.set_xlabel("False-positive rate (genuine payments flagged), log scale")
    roc.set_ylabel("True-positive rate (recall)")
    roc.set_title(f"{run['dataset']}: ROC on the test period")
    pr.axhline(prevalence, color="#bbbbbb", linestyle="--", linewidth=1, label=f"chance (prevalence {prevalence:.4%})")
    pr.set_xlim(0, 1)
    pr.set_ylim(0, 1.01)
    pr.set_xlabel("Recall")
    pr.set_ylabel("Precision")
    pr.set_title(f"{run['dataset']}: precision-recall on the test period")
    for ax in (roc, pr):
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="lower right" if ax is roc else "upper right")
    fig.text(
        0.5,
        0.01,
        "Black dots: thresholds chosen on the validation period, applied to the test period. "
        "IBM AMLworld synthetic data.",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    path = os.path.join(out_dir, f"{run['dataset']}_roc_pr.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def _pct(v, d=2):
    return f"{100 * v:.{d}f}%"


def markdown(payload: dict) -> str:
    L = [
        "# IBM AMLworld evaluation: real-time suspicious-payment detection",
        "",
        f"> **Data:** {payload['data']}. Generated {payload['generated_at']} by "
        "`scripts/evaluation/evaluate_ibm_temporal.py`; raw numbers in `docs/evaluation/ibm/results.json`.",
        "",
        "**Problem statement:** identify suspicious transactions in real time while minimising false alerts for "
        "genuine customers. So every feature uses only earlier minutes, and results are reported at false-alert "
        "budgets as well as at the best-F1 point.",
        "",
    ]
    for run in payload["runs"]:
        q, s = run["data_quality"], run["split"]
        L += [
            f"## {run['dataset']}",
            "",
            "### Preprocessing applied",
            "",
            "| Step | Result |",
            "|---|---|",
            "| Schema check (11 named columns) | passed |",
            f"| Rows read / used | {q['source_rows']:,} / {q['rows_used']:,} |",
            f"| Invalid rows (bad time, amount, label or id) | {q['invalid_rows']:,} ({q['invalid_rows_laundering']} laundering), kept out and counted |",
            f"| Blank values | {sum(q['blank_values'].values()):,} |",
            f"| Exact duplicate rows | {q['exact_duplicate_rows']:,} ({q['exact_duplicate_rows_laundering']} laundering), kept and flagged |",
            f"| Self-transfers | {q['self_transfers']:,} ({q['self_transfers_laundering']} laundering), kept, used as a feature |",
            f"| Timestamps normalised | {q['time_coverage']['first']} to {q['time_coverage']['last']} ({q['time_coverage']['days']} days) |",
            f"| Account ids | bank + account, trimmed and upper-cased: {q['accounts']:,} accounts |",
            f"| Currencies to US dollars | {len(q['currency_rates_to_usd'])} currencies, rates taken from the file's own cross-currency payments |",
            f"| Laundering rows / rate | {q['laundering_rows']:,} / {_pct(q['laundering_rate'], 3)} |",
            f"| Typologies matched | {run['typologies']['matched_to_a_typology']:,} of {run['typologies']['laundering_rows']:,} laundering rows |",
            f"| Point-in-time features | {len(run['features'])} features, each from strictly earlier minutes; labels never used as features |",
            "",
            "### Chronological split (minute boundaries, no overlap)",
            "",
            "| Split | Period | Payments | Laundering | Rate |",
            "|---|---|---|---|---|",
        ]
        for k in ("train", "validation", "test", "tail_after_ordinary_traffic_ends"):
            if s[k]["rows"]:
                L.append(
                    f"| {k.replace('_', ' ')} | {s[k]['from']} to {s[k]['to']} | {s[k]['rows']:,} | {s[k]['laundering']:,} | {_pct(s[k]['laundering_rate'], 3)} |"
                )
        if s["tail_after_ordinary_traffic_ends"]["rows"]:
            L += [
                "",
                "The generator stops producing ordinary payments after the main period; the trailing days are mostly "
                "laundering, which would make detection look easier than it is. They are kept out of the test metrics "
                "and reported on their own below.",
            ]
        L += [
            "",
            "### Test-period results (thresholds chosen on validation)",
            "",
            "| Model | ROC-AUC | PR-AUC | Operating point | Precision | Recall | F1 | False-positive rate | False alerts per 10k genuine |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for model, r in run["results"].items():
            for key, label in POINTS.items():
                m = r["operating_points"][key]["test"]
                L.append(
                    f"| {LABELS[model]} | {r['test']['roc_auc']:.3f} | {r['test']['pr_auc']:.3f} | {label} | "
                    f"{_pct(m['precision'], 1)} | {_pct(m['recall'], 1)} | {m['f1']:.3f} | {_pct(m['false_positive_rate'], 3)} | "
                    f"{m['false_alerts_per_10k_genuine']:.1f} |"
                )
        gb = run["results"]["gradient_boosting"]
        ci = gb["operating_points"]["best_f1_on_validation"]["test_95ci"]
        L += [
            "",
            f"Gradient boosting at the best-F1 point, 95% bootstrap intervals on test: precision "
            f"{_pct(ci['precision'][0], 1)}-{_pct(ci['precision'][1], 1)}, recall {_pct(ci['recall'][0], 1)}-{_pct(ci['recall'][1], 1)}, "
            f"F1 {ci['f1'][0]:.3f}-{ci['f1'][1]:.3f}. Validation: ROC-AUC {gb['validation']['roc_auc']:.3f}, PR-AUC {gb['validation']['pr_auc']:.3f}.",
            "",
            "**Confusion matrices (gradient boosting, test period)**",
            "",
            "| Operating point | TP | FP | FN | TN |",
            "|---|---|---|---|---|",
        ]
        for key, label in POINTS.items():
            c = gb["operating_points"][key]["test"]["confusion"]
            L.append(f"| {label} | {c['tp']:,} | {c['fp']:,} | {c['fn']:,} | {c['tn']:,} |")
        L += [
            "",
            "**Accounts (test period):** an account's score is its highest payment score; it is positive if it took part "
            "in any laundering payment.",
            "",
            "| Model | ROC-AUC | PR-AUC | Precision | Recall | F1 |",
            "|---|---|---|---|---|---|",
        ]
        for model, r in run["results"].items():
            a, m = r["accounts"]["test"], r["accounts"]["best_f1_on_validation"]
            L.append(
                f"| {LABELS[model]} | {a['roc_auc']:.3f} | {a['pr_auc']:.3f} | {_pct(m['precision'], 1)} | {_pct(m['recall'], 1)} | {m['f1']:.3f} |"
            )
        L += [
            "",
            "**Recall by laundering typology (gradient boosting, test period)**",
            "",
            "| Typology | Laundering payments | Recall at best F1 | Recall at FPR<=0.5% |",
            "|---|---|---|---|",
        ]
        t1 = gb["typology_recall_test"]["best_f1_on_validation"]
        t2 = gb["typology_recall_test"]["false_alerts_at_most_0.5pct"]
        for k in t1:
            L.append(
                f"| {k} | {t1[k]['laundering_payments']:,} | {_pct(t1[k]['recall'], 1)} | {_pct(t2[k]['recall'], 1)} |"
            )
        tail = gb.get("tail_after_ordinary_traffic_ends")
        if tail:
            m = tail["best_f1_on_validation"]
            L += [
                "",
                f"**Wind-down tail (reported apart):** at the best-F1 threshold, recall {_pct(m['recall'], 1)}, "
                f"precision {_pct(m['precision'], 1)} on {m['confusion']['tp'] + m['confusion']['fn']:,} laundering and "
                f"{m['confusion']['fp'] + m['confusion']['tn']:,} ordinary payments.",
            ]
        lat = run["latency_gradient_boosting"]
        L += [
            "",
            f"**Speed:** model inference for one payment p50 {lat['single_payment_ms_p50']:.2f} ms, p95 "
            f"{lat['single_payment_ms_p95']:.2f} ms; batch {lat['batch_payments_per_second']:,.0f} payments/s. "
            "Feature lookups are per-account state reads in production and are not included.",
            "",
            f"**Model choice:** {run['models']['gradient_boosting']['chosen']} (best validation PR-AUC of "
            f"{len(run['models']['gradient_boosting']['grid'])} settings).",
            "",
            f"![{run['dataset']} curves](evaluation/ibm/{run['dataset']}_roc_pr.png)",
            "",
        ]
    L += [
        "## What these numbers are and are not",
        "",
        "- IBM AMLworld is synthetic data from IBM's generator, independent of MuleCatch's own simulator. It is not "
        "bank data; real precision depends on the real fraud rate and on real behaviour.",
        "- Thresholds and model settings were chosen on the validation period only; the test period was scored once.",
        "- The models here are new candidates trained on point-in-time features. MuleCatch's current mule detector "
        "was built for structured smurfing and, on the same data, flagged 0 of 136 laundering payments "
        "(docs/buildx/05-evaluation.md 7.8); it is not re-scored here.",
        "- Laundering in the test period can belong to attempts that started in the validation period; that is how a "
        "deployed system meets it, so it is kept.",
        "",
    ]
    return "\n".join(L)
