"""One-command demo: python run_demo.py

Writes the circuit diagram, charts and CSV tables to ./results/.
All results come from a local Qiskit Aer SIMULATOR, not real quantum hardware.
"""
from __future__ import annotations

import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bell_fidelity import bell_basis_circuit, cost_table, full_report, sweep  # noqa: E402

OUT = "results"
SHOTS = 4000
SEED = 11
LABEL = "Qiskit AerSimulator - not real hardware"


def save_csv(name: str, rows: list[dict]) -> None:
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _text_to_png(text: str, path: str, title: str) -> None:
    """Render a text circuit diagram to a PNG using only matplotlib (no pylatexenc)."""
    lines = text.splitlines()
    width = max(len(line) for line in lines)
    fig = plt.figure(figsize=(max(5.0, width * 0.085), max(1.8, len(lines) * 0.2 + 0.6)))
    fig.text(0.01, 0.99, title, va="top", ha="left", fontsize=9, fontweight="bold")
    fig.text(0.01, 0.88, text, va="top", ha="left", family="DejaVu Sans Mono", fontsize=8)
    fig.text(0.99, 0.01, LABEL, ha="right", fontsize=6, style="italic")
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_circuit() -> None:
    """Save one circuit diagram per measurement basis: circuit_X/Y/Z.png and .txt."""
    for basis in ("Z", "X", "Y"):
        qc = bell_basis_circuit(basis)
        text = str(qc.draw("text", fold=-1))
        with open(os.path.join(OUT, f"circuit_{basis}.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        path = os.path.join(OUT, f"circuit_{basis}.png")
        try:
            fig = qc.draw("mpl")  # prettier, but needs the optional pylatexenc package
            fig.savefig(path, dpi=200, bbox_inches="tight")
            plt.close(fig)
        except Exception:
            _text_to_png(text, path, f"Bell-state circuit, measured in the {basis} basis")


def chart_dephasing(rows: list[dict]) -> None:
    x = [r["dephasing"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.plot(x, [r["postselected_classical_fidelity"] for r in rows], "o-", lw=2,
            label="Postselected Z-basis fidelity (looks perfect)")
    ax.plot(x, [r["z_basis_classical_fidelity"] for r in rows], "s--", lw=2,
            label="Raw Z-basis classical fidelity")
    ax.plot(x, [r["true_fidelity_raw"] for r in rows], "^-", lw=2.5, color="crimson",
            label="TRUE Bell-state fidelity (XX, YY, ZZ)")
    ax.set_xlabel("Dephasing (phase-flip) probability per gate")
    ax.set_ylabel("Fidelity")
    ax.set_ylim(0, 1.05)
    ax.set_title("A 'rescued' result can look clean while the state is damaged")
    ax.grid(alpha=0.25)
    ax.legend(loc="lower left", fontsize=8)
    fig.text(0.99, 0.01, LABEL, ha="right", fontsize=7, style="italic")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig1_postselection_fooled.png"), dpi=200)
    plt.close(fig)


def chart_depolarizing(rows: list[dict]) -> None:
    x = [r["depolarizing"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.plot(x, [r["true_fidelity_raw"] for r in rows], "o-", lw=2, label="Raw")
    ax.plot(x, [r["true_fidelity_readout_mitigated"] for r in rows], "s-", lw=2,
            label="Readout mitigated")
    ax.plot(x, [r["true_fidelity_zne"] for r in rows], "^-", lw=2, label="Readout + ZNE")
    ax.set_xlabel("Depolarizing error parameter (after H and CX)")
    ax.set_ylabel("True Bell-state fidelity")
    ax.set_ylim(0, 1.05)
    ax.set_title("Which mitigation helps with gate noise?")
    ax.grid(alpha=0.25)
    ax.legend(loc="lower left", fontsize=8)
    fig.text(0.99, 0.01, LABEL, ha="right", fontsize=7, style="italic")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_mitigation_vs_gate_noise.png"), dpi=200)
    plt.close(fig)


def chart_counts(row_noisy: dict) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    names = ["<XX>", "<YY>", "<ZZ>"]
    vals = [row_noisy["xx"], row_noisy["yy"], row_noisy["zz"]]
    ideal = [1, -1, 1]
    xs = range(3)
    ax.bar([i - 0.2 for i in xs], ideal, 0.4, label="Ideal")
    ax.bar([i + 0.2 for i in xs], vals, 0.4, label="Noisy (dephasing only)")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(names)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_title("Dephasing leaves <ZZ> intact but destroys <XX>, <YY>")
    ax.legend(fontsize=8)
    fig.text(0.99, 0.01, LABEL, ha="right", fontsize=7, style="italic")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig3_correlators.png"), dpi=200)
    plt.close(fig)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    print("1/5 Saving circuit diagram...")
    save_circuit()

    print("2/5 Experiment A: dephasing sweep (postselection vs true fidelity)...")
    deph = sweep("dephasing", [0.0, 0.05, 0.10, 0.20, 0.30, 0.40], shots=SHOTS, seed=SEED,
                 run_zne=False, depolarizing=0.0, readout=0.0)
    save_csv("dephasing_sweep.csv", deph)
    chart_dephasing(deph)

    print("3/5 Experiment B: depolarizing sweep (raw vs readout vs ZNE)...")
    depol = sweep("depolarizing", [0.0, 0.01, 0.02, 0.04, 0.06, 0.08, 0.10], shots=SHOTS,
                  seed=SEED + 1, run_zne=True, readout=0.03)
    save_csv("depolarizing_sweep.csv", depol)
    chart_depolarizing(depol)

    print("4/5 Correlator chart + cost table...")
    chart_counts(deph[3])
    save_csv("cost_table.csv", cost_table(SHOTS))

    print("5/5 Headline numbers")
    d = deph[3]
    print(f"\n  Dephasing p={d['dephasing']:.2f}:")
    print(f"    postselected Z-basis fidelity = {d['postselected_classical_fidelity']:.3f}")
    print(f"    TRUE Bell fidelity            = {d['true_fidelity_raw']:.3f}")
    e = depol[3]
    print(f"\n  Depolarizing p={e['depolarizing']:.2f}, readout flip {e['readout']:.2f}:")
    print(f"    raw {e['true_fidelity_raw']:.3f} | readout-mitigated "
          f"{e['true_fidelity_readout_mitigated']:.3f} | +ZNE {e['true_fidelity_zne']:.3f}")
    print(f"\nFiles written to ./{OUT}/  ({LABEL})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
