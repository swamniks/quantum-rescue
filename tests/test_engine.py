import numpy as np
from quantum_engine import (
    bell_circuit, build_noise_model, run_counts, count_vector,
    postselect_even_parity, parity_error_rate, IDEAL
)

def test_ideal_bell_state_only_even_parity():
    counts = run_counts(bell_circuit(), 3000, None, 12)
    assert counts.get("01", 0) + counts.get("10", 0) == 0
    assert abs(counts.get("00", 0) / 3000 - 0.5) < 0.06
    assert abs(counts.get("11", 0) / 3000 - 0.5) < 0.06

def test_postselection_keeps_only_even_parity():
    result = postselect_even_parity({"00": 10, "01": 5, "10": 4, "11": 9})
    assert result == {"00": 10, "11": 9}
    assert sum(result.values()) == 19

def test_noise_model_runs():
    model = build_noise_model(0.05, 0.03)
    counts = run_counts(bell_circuit(), 1000, model, 21)
    assert sum(counts.values()) == 1000
    assert set(counts).issubset({"00", "01", "10", "11"})

def test_parity_error_is_bounded():
    value = parity_error_rate({"00": 50, "01": 10, "10": 10, "11": 30})
    assert np.isclose(value, 0.2)
    assert 0 <= value <= 1
