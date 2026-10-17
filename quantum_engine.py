"""Quantum Rescue: Bell-state noise, postselection, and readout mitigation.

All results are local Qiskit Aer simulations, not real quantum-hardware data.
"""
from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

OUTCOMES = ["00", "01", "10", "11"]
IDEAL = np.array([0.5, 0.0, 0.0, 0.5], dtype=float)


def bell_circuit(measure: bool = True) -> QuantumCircuit:
    """Prepare |Phi+> = (|00> + |11>)/sqrt(2)."""
    qc = QuantumCircuit(2, 2) if measure else QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    if measure:
        qc.measure([0, 1], [0, 1])
    return qc


def build_noise_model(depolarizing: float, readout: float) -> NoiseModel:
    """Apply depolarizing errors after H/CX and symmetric readout flips."""
    depolarizing = float(np.clip(depolarizing, 0.0, 1.0))
    readout = float(np.clip(readout, 0.0, 0.49))
    model = NoiseModel()
    if depolarizing > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(depolarizing, 1), ["h"])
        model.add_all_qubit_quantum_error(depolarizing_error(depolarizing, 2), ["cx"])
    if readout > 0:
        model.add_all_qubit_readout_error(
            ReadoutError([[1.0 - readout, readout], [readout, 1.0 - readout]])
        )
    return model


def run_counts(qc: QuantumCircuit, shots: int, noise_model: NoiseModel | None = None, seed: int = 7):
    """Run a circuit on AerSimulator and return normalized two-bit count keys."""
    simulator = AerSimulator(noise_model=noise_model, seed_simulator=seed)
    compiled = transpile(qc, simulator, seed_transpiler=seed)
    result = simulator.run(compiled, shots=int(shots)).result()
    raw = result.get_counts()
    # Qiskit displays classical bit 1 before bit 0. For this symmetric Bell
    # experiment, this convention still gives the expected 00/11 target.
    return {key.replace(" ", "").zfill(2): int(value) for key, value in raw.items()}


def count_vector(counts: dict[str, int]) -> np.ndarray:
    total = sum(counts.values())
    if total <= 0:
        return np.zeros(4, dtype=float)
    return np.array([counts.get(key, 0) / total for key in OUTCOMES], dtype=float)


def bell_distribution_fidelity(probabilities: np.ndarray) -> float:
    """Classical fidelity of Z-basis outcome distribution vs ideal [0.5,0,0,0.5].

    This is NOT full quantum-state fidelity or proof of entanglement.
    """
    p = np.clip(np.asarray(probabilities, dtype=float), 0, None)
    if p.sum() <= 0:
        return 0.0
    p = p / p.sum()
    return float((np.sqrt(p[0] * 0.5) + np.sqrt(p[3] * 0.5)) ** 2)


def parity_error_rate(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    return (counts.get("01", 0) + counts.get("10", 0)) / total if total else 0.0


def postselect_even_parity(counts: dict[str, int]) -> dict[str, int]:
    """Keep only 00/11 shots. This detects odd-parity outcomes, not every error."""
    return {key: counts.get(key, 0) for key in ("00", "11")}


def calibration_matrix(shots: int, readout: float, seed: int = 17) -> np.ndarray:
    """Estimate the 4x4 assignment matrix M[observed, true] using four calibration circuits."""
    model = build_noise_model(0.0, readout)
    matrix = np.zeros((4, 4), dtype=float)
    for true_index, true_key in enumerate(OUTCOMES):
        qc = QuantumCircuit(2, 2)
        # key order is c1c0, so apply X to the corresponding qubits.
        if true_key[1] == "1":
            qc.x(0)
        if true_key[0] == "1":
            qc.x(1)
        qc.measure([0, 1], [0, 1])
        counts = run_counts(qc, shots, model, seed + true_index)
        probs = count_vector(counts)
        matrix[:, true_index] = probs
    return matrix


def mitigate_readout(counts: dict[str, int], matrix: np.ndarray) -> np.ndarray:
    """Invert calibrated readout assignment matrix and clip/renormalize finite-shot estimates."""
    observed = count_vector(counts)
    try:
        corrected = np.linalg.solve(matrix, observed)
    except np.linalg.LinAlgError:
        corrected = observed.copy()
    corrected = np.clip(corrected, 0.0, None)
    if corrected.sum() <= 0:
        return observed
    return corrected / corrected.sum()


def run_experiment(shots: int = 4000, depolarizing: float = 0.03,
                   readout: float = 0.04, seed: int = 7) -> dict:
    """Run ideal/noisy Bell experiment and both recovery strategies."""
    shots = int(shots)
    ideal_counts = run_counts(bell_circuit(), shots, None, seed)
    model = build_noise_model(depolarizing, readout)
    noisy_counts = run_counts(bell_circuit(), shots, model, seed + 1)

    selected_counts = postselect_even_parity(noisy_counts)
    selected_total = sum(selected_counts.values())
    selected_probs = count_vector(selected_counts) if selected_total else IDEAL.copy()

    matrix = calibration_matrix(max(1000, shots // 2), readout, seed + 100)
    mitigated_probs = mitigate_readout(noisy_counts, matrix)

    ideal_probs = count_vector(ideal_counts)
    noisy_probs = count_vector(noisy_counts)

    return {
        "ideal_counts": ideal_counts,
        "noisy_counts": noisy_counts,
        "postselected_counts": selected_counts,
        "ideal_probs": ideal_probs,
        "noisy_probs": noisy_probs,
        "postselected_probs": selected_probs,
        "mitigated_probs": mitigated_probs,
        "shots": shots,
        "shots_kept": selected_total,
        "retention": selected_total / shots if shots else 0.0,
        "parity_error": parity_error_rate(noisy_counts),
        "calibration_circuits": 4,
        "calibration_shots": max(1000, shots // 2),
        "calibration_matrix": matrix,
    }


def sweep_noise(shots: int = 2500, readout: float = 0.04,
                levels: list[float] | None = None, seed: int = 31) -> list[dict]:
    """Sweep depolarizing noise; report Z-basis distribution fidelity and retention."""
    if levels is None:
        levels = [0.0, 0.01, 0.03, 0.06, 0.10, 0.15]
    rows = []
    for i, level in enumerate(levels):
        result = run_experiment(shots, level, readout, seed + i * 10)
        rows.append({
            "Depolarizing parameter": level,
            "Ideal": bell_distribution_fidelity(result["ideal_probs"]),
            "Noisy": bell_distribution_fidelity(result["noisy_probs"]),
            "Postselected (conditional)": bell_distribution_fidelity(result["postselected_probs"]),
            "Readout mitigated": bell_distribution_fidelity(result["mitigated_probs"]),
            "Postselection retention": result["retention"],
            "Noisy parity error": result["parity_error"],
        })
    return rows
