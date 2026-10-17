"""True Bell-state fidelity, dephasing noise, and zero-noise extrapolation (ZNE).

Everything here runs on a local Qiskit Aer simulator, NOT real quantum hardware.

Key idea
--------
Z-basis counts only reveal ZZ correlations. For |Phi+> the true fidelity is

    F = (1 + <XX> - <YY> + <ZZ>) / 4

so we measure the same prepared state in the X, Y and Z bases.
Parity postselection only checks ZZ, so it is blind to phase (dephasing) errors:
the Z histogram can look perfect while F drops.
"""
from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error, pauli_error

from quantum_engine import (
    OUTCOMES,
    bell_distribution_fidelity,
    calibration_matrix,
    count_vector,
    mitigate_readout,
)

BASES = ("X", "Y", "Z")


# --------------------------------------------------------------------------- noise
def build_noise_model(depolarizing: float = 0.0, readout: float = 0.0,
                      dephasing: float = 0.0) -> NoiseModel:
    """Depolarizing + phase-flip (dephasing) errors after H/CX, symmetric readout flips.

    Noise is attached only to 'h' and 'cx' (state preparation). Measurement-basis
    rotations use ry/rx, which are noiseless here, so the basis change itself
    does not add error.
    """
    depolarizing = float(np.clip(depolarizing, 0.0, 1.0))
    dephasing = float(np.clip(dephasing, 0.0, 1.0))
    readout = float(np.clip(readout, 0.0, 0.49))
    model = NoiseModel()
    if depolarizing > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(depolarizing, 1), ["h"])
        model.add_all_qubit_quantum_error(depolarizing_error(depolarizing, 2), ["cx"])
    if dephasing > 0:
        model.add_all_qubit_quantum_error(
            pauli_error([("Z", dephasing), ("I", 1.0 - dephasing)]), ["h"])
        model.add_all_qubit_quantum_error(
            pauli_error([("II", 1.0 - dephasing), ("ZI", dephasing / 2), ("IZ", dephasing / 2)]),
            ["cx"])
    if readout > 0:
        model.add_all_qubit_readout_error(
            ReadoutError([[1.0 - readout, readout], [readout, 1.0 - readout]]))
    return model


# ------------------------------------------------------------------------- circuits
def bell_basis_circuit(basis: str, cx_fold: int = 1) -> QuantumCircuit:
    """Prepare |Phi+> and measure both qubits in the X, Y or Z basis.

    cx_fold = 1, 3, 5, ... replaces CX with CX.CX.CX... (logically identical, noisier)
    for zero-noise extrapolation. Barriers stop the transpiler cancelling the pairs.
    """
    if basis not in BASES:
        raise ValueError(f"basis must be one of {BASES}")
    if cx_fold < 1 or cx_fold % 2 == 0:
        raise ValueError("cx_fold must be a positive odd integer")
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.barrier()
    for _ in range(cx_fold):
        qc.cx(0, 1)
        qc.barrier()
    if basis == "X":      # Ry(-pi/2) maps the X eigenbasis to Z
        qc.ry(-np.pi / 2, 0)
        qc.ry(-np.pi / 2, 1)
    elif basis == "Y":    # Rx(+pi/2) maps the Y eigenbasis to Z
        qc.rx(np.pi / 2, 0)
        qc.rx(np.pi / 2, 1)
    qc.measure([0, 1], [0, 1])
    return qc


def run_probs(qc: QuantumCircuit, shots: int, model: NoiseModel | None, seed: int):
    sim = AerSimulator(noise_model=model, seed_simulator=seed)
    compiled = transpile(qc, sim, optimization_level=0, seed_transpiler=seed)
    raw = sim.run(compiled, shots=int(shots)).result().get_counts()
    counts = {k.replace(" ", "").zfill(2): int(v) for k, v in raw.items()}
    return counts, count_vector(counts)


# ------------------------------------------------------------------------- metrics
def parity_expectation(p: np.ndarray) -> float:
    """<PP> for any basis: +1 for even-parity outcomes (00, 11), -1 for odd."""
    return float(p[0] + p[3] - p[1] - p[2])


def fidelity_from_expectations(xx: float, yy: float, zz: float) -> float:
    """Fidelity with |Phi+>, clipped to [0, 1] against finite-shot overshoot."""
    return float(np.clip((1.0 + xx - yy + zz) / 4.0, 0.0, 1.0))


def measure_fidelity(shots: int, model: NoiseModel, seed: int, cx_fold: int = 1,
                     matrix: np.ndarray | None = None) -> dict:
    """Measure XX, YY, ZZ. If `matrix` is given, also apply readout mitigation."""
    raw_exp, mit_exp, probs, counts = {}, {}, {}, {}
    for i, basis in enumerate(BASES):
        c, p = run_probs(bell_basis_circuit(basis, cx_fold), shots, model, seed + 7 * i)
        counts[basis], probs[basis] = c, p
        raw_exp[basis] = parity_expectation(p)
        if matrix is not None:
            mit_exp[basis] = parity_expectation(mitigate_readout(c, matrix))
    out = {
        "counts": counts,
        "probs": probs,
        "raw_exp": raw_exp,
        "fidelity_raw": fidelity_from_expectations(raw_exp["X"], raw_exp["Y"], raw_exp["Z"]),
    }
    if matrix is not None:
        out["mit_exp"] = mit_exp
        out["fidelity_mitigated"] = fidelity_from_expectations(
            mit_exp["X"], mit_exp["Y"], mit_exp["Z"])
    return out


def zne_fidelity(shots: int, model: NoiseModel, seed: int, matrix: np.ndarray,
                 scales: tuple[int, ...] = (1, 3, 5)) -> dict:
    """Linear zero-noise extrapolation of XX, YY, ZZ (on top of readout mitigation).

    Only the CX gates are folded, so this targets two-qubit gate noise. Single-qubit H
    noise and any residual readout error are NOT removed.
    """
    per_scale = {}
    for j, s in enumerate(scales):
        r = measure_fidelity(shots, model, seed + 100 * j, cx_fold=s, matrix=matrix)
        per_scale[s] = r["mit_exp"]
    xs = np.array(scales, dtype=float)
    extrap = {}
    for b in BASES:
        ys = np.array([per_scale[s][b] for s in scales])
        slope, intercept = np.polyfit(xs, ys, 1)
        extrap[b] = float(np.clip(intercept, -1.0, 1.0))
    return {
        "per_scale_exp": per_scale,
        "extrapolated_exp": extrap,
        "fidelity_zne": fidelity_from_expectations(extrap["X"], extrap["Y"], extrap["Z"]),
        "fidelity_by_scale": {
            s: fidelity_from_expectations(v["X"], v["Y"], v["Z"]) for s, v in per_scale.items()
        },
    }


def full_report(shots: int = 4000, depolarizing: float = 0.03, readout: float = 0.03,
                dephasing: float = 0.0, seed: int = 11, run_zne: bool = True) -> dict:
    """One noise setting -> every metric we compare."""
    model = build_noise_model(depolarizing, readout, dephasing)
    matrix = calibration_matrix(max(1000, shots // 2), readout, seed + 900) if readout > 0 \
        else np.eye(4)
    base = measure_fidelity(shots, model, seed, 1, matrix)
    pz = base["probs"]["Z"]

    # Z-basis view: what a "looks clean" analysis would see
    selected = np.array([pz[0], 0.0, 0.0, pz[3]])
    retention = float(pz[0] + pz[3])
    sel_probs = selected / selected.sum() if selected.sum() > 0 else selected

    row = {
        "depolarizing": depolarizing,
        "readout": readout,
        "dephasing": dephasing,
        "xx": base["raw_exp"]["X"],
        "yy": base["raw_exp"]["Y"],
        "zz": base["raw_exp"]["Z"],
        "z_basis_classical_fidelity": bell_distribution_fidelity(pz),
        "postselected_classical_fidelity": bell_distribution_fidelity(sel_probs),
        "postselection_retention": retention,
        "true_fidelity_raw": base["fidelity_raw"],
        "true_fidelity_readout_mitigated": base["fidelity_mitigated"],
    }
    if run_zne:
        z = zne_fidelity(shots, model, seed + 5000, matrix)
        row["true_fidelity_zne"] = z["fidelity_zne"]
    return row


def sweep(param: str, levels: list[float], shots: int = 4000, seed: int = 11,
          run_zne: bool = True, **fixed) -> list[dict]:
    """Sweep one of 'depolarizing' / 'dephasing' while holding the others in `fixed`."""
    rows = []
    for i, level in enumerate(levels):
        kwargs = {"depolarizing": 0.0, "readout": 0.03, "dephasing": 0.0}
        kwargs.update(fixed)
        kwargs[param] = level
        rows.append(full_report(shots=shots, seed=seed + 13 * i, run_zne=run_zne, **kwargs))
    return rows


# Circuit-cost bookkeeping used in the README / charts
def cost_table(shots: int, scales: tuple[int, ...] = (1, 3, 5)) -> list[dict]:
    cal_shots = max(1000, shots // 2)
    return [
        {"Method": "Raw (3 bases)", "Circuits": 3, "Total shots": 3 * shots,
         "Targets": "-"},
        {"Method": "Parity postselection (Z only)", "Circuits": 1, "Total shots": shots,
         "Targets": "Bit-flip-like errors seen in ZZ; blind to phase errors"},
        {"Method": "Readout mitigation", "Circuits": 3 + 4, "Total shots": 3 * shots + 4 * cal_shots,
         "Targets": "Measurement assignment error only"},
        {"Method": f"Readout + ZNE (folds {scales})", "Circuits": 3 * len(scales) + 4,
         "Total shots": 3 * len(scales) * shots + 4 * cal_shots,
         "Targets": "Part of CX gate noise; higher variance"},
    ]
