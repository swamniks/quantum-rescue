"""Repeat the two key experiments with many independent seeds -> confidence intervals.

    python run_robustness.py        (roughly 1-3 minutes)

Experiment A (dephasing p=0.20): does postselection look better than the true state is?
Experiment B (depolarizing p=0.04, readout flip 0.03): do readout mitigation and ZNE help?

Writes to ./results/: robustness_trials.csv, robustness_summary.csv, fig4_robustness.png
All results come from a local Qiskit Aer SIMULATOR, not real quantum hardware.
"""
from __future__ import annotations

import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from bell_fidelity import full_report  # noqa: E402

OUT = "results"
SHOTS = 4000
N_TRIALS = 20
BASE_SEED = 1000
SEED_STEP = 10007  # large prime step so trials never share simulator seeds
LABEL = "Qiskit AerSimulator - not real hardware"

# Two-sided 95% Student-t critical values, keyed by number of trials n (df = n - 1)
T95 = {5: 2.776, 10: 2.262, 20: 2.093, 30: 2.045}

SETTING_A = {"depolarizing": 0.0, "readout": 0.0, "dephasing": 0.20}
SETTING_B = {"depolarizing": 0.04, "readout": 0.03, "dephasing": 0.0}


def mean_ci(values) -> tuple[float, float, float]:
    """Mean and approximate 95% confidence interval of the mean."""
    v = np.asarray(values, dtype=float)
    n = len(v)
    m = float(v.mean())
    if n < 2:
        return m, m, m
    half = T95.get(n, 1.96) * float(v.std(ddof=1)) / np.sqrt(n)
    return m, m - half, m + half


def run_setting(name: str, kwargs: dict, run_zne: bool) -> list[dict]:
    rows = []
    for i in range(N_TRIALS):
        r = full_report(shots=SHOTS, seed=BASE_SEED + SEED_STEP * i, run_zne=run_zne, **kwargs)
        r["setting"] = name
        r["trial"] = i + 1
        rows.append(r)
        print(f"  setting {name}: trial {i + 1}/{N_TRIALS}", end="\r", flush=True)
    print()
    return rows


def summarize(setting: str, rows: list[dict], metrics: list[str]) -> list[dict]:
    out = []
    for m in metrics:
        mean, lo, hi = mean_ci([r[m] for r in rows])
        out.append({"setting": setting, "metric": m, "mean": mean, "ci_low": lo, "ci_high": hi})
    return out


def paired(rows: list[dict], a: str, b: str) -> tuple[float, float, float]:
    """Mean and 95% CI of (a - b), paired by trial."""
    return mean_ci([r[a] - r[b] for r in rows])


def write_csv(path: str, rows: list[dict]) -> None:
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(rows)


def bar_panel(ax, labels, stats, title, colors):
    means = [s[0] for s in stats]
    lows = [s[0] - s[1] for s in stats]
    highs = [s[2] - s[0] for s in stats]
    ax.bar(labels, means, yerr=[lows, highs], capsize=6, color=colors, edgecolor="black")
    for i, m in enumerate(means):
        ax.text(i, m + highs[i] + 0.02, f"{m:.3f}", ha="center", fontsize=9)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Fidelity (mean, 95% CI)")
    ax.set_title(title, fontsize=10)
    ax.grid(axis="y", alpha=0.25)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)

    print(f"Experiment A: dephasing p=0.20, {N_TRIALS} independent seeds...")
    rows_a = run_setting("A_dephasing_0.20", SETTING_A, run_zne=False)
    print(f"Experiment B: depolarizing p=0.04 + readout 0.03, {N_TRIALS} seeds (includes ZNE)...")
    rows_b = run_setting("B_depolarizing_0.04", SETTING_B, run_zne=True)

    write_csv(os.path.join(OUT, "robustness_trials.csv"), rows_a + rows_b)

    metrics_a = ["z_basis_classical_fidelity", "postselected_classical_fidelity", "true_fidelity_raw"]
    metrics_b = ["postselected_classical_fidelity", "true_fidelity_raw",
                 "true_fidelity_readout_mitigated", "true_fidelity_zne"]
    summary = summarize("A_dephasing_0.20", rows_a, metrics_a)
    summary += summarize("B_depolarizing_0.04", rows_b, metrics_b)

    d_ps = paired(rows_a, "postselected_classical_fidelity", "true_fidelity_raw")
    d_ro = paired(rows_b, "true_fidelity_readout_mitigated", "true_fidelity_raw")
    d_zne = paired(rows_b, "true_fidelity_zne", "true_fidelity_readout_mitigated")
    for name, setting, d in [
        ("postselected_minus_true", "A_dephasing_0.20", d_ps),
        ("readout_mitigated_minus_raw", "B_depolarizing_0.04", d_ro),
        ("zne_minus_readout_mitigated", "B_depolarizing_0.04", d_zne),
    ]:
        summary.append({"setting": setting, "metric": name,
                        "mean": d[0], "ci_low": d[1], "ci_high": d[2]})
    write_csv(os.path.join(OUT, "robustness_summary.csv"), summary)

    # ---- figure
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
    bar_panel(
        axes[0],
        ["Postselected\nZ-basis", "True Bell\nfidelity"],
        [mean_ci([r["postselected_classical_fidelity"] for r in rows_a]),
         mean_ci([r["true_fidelity_raw"] for r in rows_a])],
        f"A: dephasing p=0.20 ({N_TRIALS} seeds)", ["#4c78a8", "#d62728"])
    bar_panel(
        axes[1],
        ["Raw", "Readout\nmitigated", "Readout\n+ ZNE"],
        [mean_ci([r["true_fidelity_raw"] for r in rows_b]),
         mean_ci([r["true_fidelity_readout_mitigated"] for r in rows_b]),
         mean_ci([r["true_fidelity_zne"] for r in rows_b])],
        f"B: depolarizing p=0.04, readout flip 0.03 ({N_TRIALS} seeds)",
        ["#9ecae1", "#4c78a8", "#2ca02c"])
    fig.suptitle("Results repeated over independent seeds (error bars: approx. 95% CI)", fontsize=11)
    fig.text(0.99, 0.01, LABEL, ha="right", fontsize=7, style="italic")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(os.path.join(OUT, "fig4_robustness.png"), dpi=200)
    plt.close(fig)

    # ---- printed summary
    print("\n=== Summary (mean and approx. 95% CI over "
          f"{N_TRIALS} seeds, {SHOTS} shots/circuit) ===")
    for s in summary:
        print(f"  {s['setting']:<22} {s['metric']:<34} "
              f"{s['mean']:+.3f}  [{s['ci_low']:+.3f}, {s['ci_high']:+.3f}]")
    print("\nPaired differences: if the interval excludes 0, the effect is distinguishable from noise.")
    print(f"\nFiles written to ./{OUT}/  ({LABEL})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
