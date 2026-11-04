"""Figures for the BuildX pitch deck. Every number is read from the committed result files in docs/buildx/.

Run: python docs/pitch/make_figures.py   (needs matplotlib)
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "buildx"
OUT = Path(__file__).resolve().parent / "figures"

NAVY, CARD, LINE = "#14142B", "#23224A", "#3B3A66"
TEXT, MUTED = "#F1EEFA", "#A9A6C2"
ORANGE, GREEN, RED, GREY = "#F5A623", "#2E9E5B", "#D64545", "#6E6B8C"
plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": TEXT, "axes.labelcolor": MUTED})


def load(name):
    return json.loads((RESULTS / name).read_text())


def style(ax):
    ax.set_facecolor(NAVY)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=MUTED, length=0)


def workload():
    """Reviews needed to reach 90 % of mule accounts, hardened scenario, with genuine accounts exposed."""
    w = load("evaluation_results_v2.json")["scenarios"]["hardened"]["investigator_workload"]
    rows = [
        ("Rules, one account at a time", w["A_rules_baseline_account_queue"], GREY),
        ("Graph + timing, one account at a time", w["B_graph_temporal_account_queue"], GREY),
        ("MuleCatch cases, ranked by member evidence", w["C_mulecatch_case_queue_as_shipped"], GREEN),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 3.4), dpi=200, facecolor=NAVY)
    style(ax)
    ys = list(range(len(rows)))[::-1]
    for y, (label, row, colour) in zip(ys, rows):
        units = row["median_units_opened"]
        exposed = row["median_legit_accounts_exposed"]
        reached = row["datasets_reaching_target"]
        ax.barh(y, units, color=colour, height=0.58)
        ax.text(units + 6, y + 0.14, f"{units:g} reviews", va="center", fontsize=12, fontweight="bold", color=TEXT)
        ax.text(units + 6, y - 0.22, f"{exposed:g} genuine accounts pulled in", va="center", fontsize=9.5, color=MUTED)
        ax.text(units + 6, y - 0.42, f"reached 90% in {reached} runs", va="center", fontsize=9, color=MUTED)
    ax.spines["bottom"].set_visible(False)
    ax.set_yticks(ys, [r[0] for r in rows], fontsize=10, color=TEXT)
    ax.set_xlim(0, 480)
    ax.set_xticks([])
    ax.set_title("Reviews needed to reach 90% of mule accounts", loc="left", fontsize=12, color=TEXT, pad=10)
    fig.text(0.01, 0.01, "Synthetic data, hardened scenario, median of 20 held-out datasets (seeds 100-119).",
             fontsize=9, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "workload.png", facecolor=NAVY)
    plt.close(fig)


def evasion():
    """Share of mule payments flagged when mules change tactics. The weak spots stay visible."""
    s = load("evasion_results_v3.json")["scenarios"]["standard"]
    order = [
        ("baseline", "No\nevasion"), ("split", "Split\npayments"), ("noise", "Decoy\npayments"),
        ("slow_drip", "Slow drip\n(6x)"), ("combo", "All three"), ("dilute", "Pay many\nbystanders"),
        ("slower", "Slower\n(24x)"),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 3.5), dpi=200, facecolor=NAVY)
    style(ax)
    for i, (key, label) in enumerate(order):
        v = s[key]["mule_payment_recall"] * 100
        ax.bar(i, v, color=GREEN if v >= 90 else RED, width=0.62)
        ax.text(i, v + 2, f"{v:.0f}%", ha="center", fontsize=11, fontweight="bold", color=TEXT)
    ax.set_xticks(range(len(order)), [o[1] for o in order], fontsize=9, color=MUTED)
    ax.set_ylim(0, 118)
    ax.set_yticks([])
    ax.set_title("Mule payments still flagged when the mules change tactics", loc="left", fontsize=12, pad=10)
    fig.text(0.01, 0.01, "Synthetic data, 5 held-out datasets. Playbooks written by our own team.",
             fontsize=9, color=MUTED, style="italic")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "evasion.png", facecolor=NAVY)
    plt.close(fig)


def box(ax, x, y, w, h, title, sub, edge=LINE, fill=CARD):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05", fc=fill, ec=edge, lw=1.5))
    ax.text(x + w / 2, y + h * 0.64, title, ha="center", va="center", fontsize=10, fontweight="bold", color=TEXT)
    ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", fontsize=8, color=MUTED, linespacing=1.3)


def architecture():
    p50 = load("payment_eval_results_v4.json")["scenarios"]["hardened"]["test"]["latency_ms_p50"]
    fig, ax = plt.subplots(figsize=(9.8, 3.0), dpi=200, facecolor=NAVY)
    ax.set_facecolor(NAVY)
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0.6, 3.75)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    stages = [
        ("Payment in", "UPI / IMPS feed,\nKafka or CSV", LINE),
        ("Score payment", "Smurfing and timing\nper account", ORANGE),
        ("Find the ring", "Louvain communities\non the account graph", ORANGE),
        ("Purity gate", "Members need their\nown evidence", ORANGE),
        ("Ranked case", "Reasons, money path,\nwho else is touched", GREEN),
        ("Human decides", "Reason required,\nhash-chained audit", GREEN),
    ]
    w, gap, y, h = 1.85, 0.22, 1.55, 1.25
    for i, (title, sub, edge) in enumerate(stages):
        x = 0.1 + i * (w + gap)
        box(ax, x, y, w, h, title, sub, edge=edge)
        if i < len(stages) - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.03, y + h / 2), (x + w + gap - 0.03, y + h / 2),
                                         arrowstyle="-|>", mutation_scale=14, color=MUTED, lw=1.4))
    ax.text(0.1, 3.45, "Runs on one server. No LLM in the decision path.", fontsize=10.5, color=TEXT, fontweight="bold")
    ax.text(0.1, 3.12, "Never blocks a payment or freezes an account. FLAG means route to a person.",
            fontsize=9.5, color=MUTED)
    for label, x0, x1, colour in ((f"Real-time scoring, about {p50:.0f} ms per payment (median)", 2.17, 8.3, ORANGE),
                                  ("Investigation and audit", 8.3, 12.3, GREEN)):
        ax.plot([x0, x1 - 0.1], [1.22, 1.22], color=colour, lw=3, solid_capstyle="round")
        ax.text((x0 + x1) / 2 - 0.05, 0.85, label, ha="center", fontsize=9.5, color=colour, fontweight="bold")
    fig.savefig(OUT / "architecture.png", facecolor=NAVY)
    plt.close(fig)


def ring():
    """Illustration only: one source fans out to mules, which consolidate into collectors. Not real data."""
    fig, ax = plt.subplots(figsize=(5.4, 4.4), dpi=200, facecolor=NAVY)
    ax.set_facecolor(NAVY)
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    src = (1.2, 4.0)
    mules = [(4.2, 7.0 - i * 1.5) for i in range(5)]
    cols = [(8.3, 5.2), (8.3, 2.8)]
    others = [(2.2, 0.9), (4.8, 0.5), (6.5, 7.4), (0.7, 7.2)]
    for m in mules:
        ax.plot(*zip(src, m), color=ORANGE, lw=1.4, alpha=0.9)
        for c in cols[:1] if m[1] > 4 else cols[1:]:
            ax.plot(*zip(m, c), color=ORANGE, lw=1.4, alpha=0.9)
    for o in others:
        ax.plot(*zip(o, mules[len(others) % 5]), color=LINE, lw=1, alpha=0.8)
    ax.scatter(*zip(*others), s=120, color=GREY, zorder=3)
    ax.scatter(*zip(*mules), s=210, color=RED, zorder=3)
    ax.scatter(*zip(*cols), s=300, color=RED, zorder=3, marker="s")
    ax.scatter(*src, s=360, color=ORANGE, zorder=3, marker="D")
    ax.text(src[0], src[1] - 0.95, "scam money in", ha="center", fontsize=9, color=MUTED)
    ax.text(4.2, 0.1, "mule accounts", ha="center", fontsize=9, color=MUTED)
    ax.text(8.3, 0.9, "collectors", ha="center", fontsize=9, color=MUTED)
    fig.text(0.02, 0.01, "Illustration, not real data.", fontsize=8, color=MUTED, style="italic")
    fig.savefig(OUT / "ring.png", facecolor=NAVY)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for fn in (workload, evasion, architecture, ring):
        fn()
    print("figures written to", OUT)
