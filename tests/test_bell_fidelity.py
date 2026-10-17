import numpy as np
import pytest

from bell_fidelity import (
    bell_basis_circuit,
    fidelity_from_expectations,
    full_report,
    parity_expectation,
)


def test_fidelity_formula_ideal_and_mixed():
    assert fidelity_from_expectations(1, -1, 1) == pytest.approx(1.0)
    assert fidelity_from_expectations(0, 0, 0) == pytest.approx(0.25)


def test_parity_expectation():
    assert parity_expectation(np.array([0.5, 0, 0, 0.5])) == pytest.approx(1.0)
    assert parity_expectation(np.array([0, 0.5, 0.5, 0])) == pytest.approx(-1.0)


def test_cx_fold_must_be_odd():
    with pytest.raises(ValueError):
        bell_basis_circuit("Z", cx_fold=2)


def test_noiseless_gives_unit_fidelity():
    r = full_report(shots=4000, depolarizing=0, readout=0, dephasing=0, run_zne=False)
    assert r["true_fidelity_raw"] > 0.97
    assert r["postselection_retention"] == pytest.approx(1.0)


def test_postselection_is_blind_to_dephasing():
    r = full_report(shots=4000, depolarizing=0, readout=0, dephasing=0.3, run_zne=False)
    assert r["postselected_classical_fidelity"] > 0.97   # looks perfect
    assert r["true_fidelity_raw"] < 0.8                   # but the state is damaged


def test_reproducible_with_seed():
    a = full_report(shots=1000, run_zne=False, seed=3)
    b = full_report(shots=1000, run_zne=False, seed=3)
    assert a["true_fidelity_raw"] == b["true_fidelity_raw"]
