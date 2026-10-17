Quantum Rescue: Cleaning Up a Quantum Result Is Not Recovering It

IBM Qiskit Fall Fest 2026 · RV University · 24-hour hackathon

All results in this repository come from a local Qiskit AerSimulator. Nothing was run on real quantum hardware.

Team
Member	Contribution
Nikhil Eshwar R	
Harsha Prakash Patel
Nanda Kishore A	
One-sentence finding

A noisy Bell-state result can be "cleaned up" until it looks perfect while the quantum state is still badly damaged: in our simulation, parity postselection reported a Z-basis fidelity of 1.000 while the true Bell-state fidelity was 0.566 (mean of 20 independent seeds, 95% CI 0.564 to 0.569).

Direct answer to the challenge question

Can we detect the damage and recover a more reliable result? Partly.

Detect: parity checks catch errors that flip Z-basis outcomes, but miss phase errors entirely (true fidelity 0.566 while the Z-basis data looked perfect).
Recover: at depolarizing p = 0.04 with 3% readout error, readout mitigation added about +0.07 fidelity and zero-noise extrapolation (ZNE) a further +0.02 (20-seed means). Nothing restored the ideal state.
Cost: 12,000 shots (raw, three bases), 20,000 (readout mitigation), 44,000 (readout mitigation + ZNE).
Why we chose this

Most quantum demos show that something works. We wanted to ask the opposite question: can we trust the answer a noisy quantum computer gives us? We add noise to the simplest entangled circuit, then compare three ways of "rescuing" the result, measuring what each one fixes, what it misses, and what it costs.

The concept in brief

The circuit prepares the Bell state |Φ+> = (|00> + |11>)/√2 with a Hadamard and a CNOT. Ideally, measuring both qubits in the Z basis gives 00 or 11, each half the time.

The catch: Z-basis counts only reveal one correlation (ZZ). A state can have perfect ZZ correlation and still not be entangled. The true fidelity with |Φ+> is

F = (1 + <XX> - <YY> + <ZZ>) / 4

so we also measure the same state in the X basis (rotate with Ry(-π/2)) and Y basis (rotate with Rx(π/2)) before measuring. F = 1 is a perfect Bell state; F = 0.5 is a purely classical mixture of 00 and 11.

What we built

Three noise sources (all in bell_fidelity.py, using qiskit_aer.noise):

Depolarizing noise after the H and CX gates
Dephasing (phase-flip) noise after the H and CX gates: invisible when measuring in Z
Readout error: each measured bit flips with a fixed probability

Three rescue strategies, compared on cost (4,000 shots per circuit):

Strategy	What it does	Circuits	Total shots
Parity postselection	Keep only 00/11 outcomes in the Z-basis run	1	4,000
Readout mitigation	Calibrate a 4×4 assignment matrix, then invert it (negatives clipped, renormalized)	3 + 4 calibration	20,000
Readout mitigation + ZNE	Also fold each CX into CX·CX·CX (1×, 3×, 5× gate noise), then extrapolate linearly back to zero noise	9 + 4 calibration	44,000

For comparison, one un-mitigated measurement of all three bases uses 3 circuits and 12,000 shots.

Results

Findings 1 and 2 are from one seeded run of python run_demo.py; Finding 3 repeats the key settings over 20 independent seeds with python run_robustness.py. All use 4,000 shots per circuit with fixed seeds. Exact values are in results/*.csv; correlators in the tables are rounded to 2 decimals.

Finding 1: postselection can look perfect while the state is wrong (dephasing only, no readout error)

Show Image Qiskit AerSimulator, not real hardware.

Dephasing p	<XX>	<YY>	<ZZ>	Postselected Z-basis fidelity	Shots kept	True Bell fidelity
0.00	1.00	-1.00	1.00	1.000	100%	1.000
0.05	0.66	-0.66	1.00	1.000	100%	0.829
0.10	0.38	-0.41	1.00	1.000	100%	0.698
0.20	0.12	-0.13	1.00	1.000	100%	0.563
0.30	0.02	-0.05	1.00	1.000	100%	0.518
0.40	-0.01	-0.01	1.00	1.000	100%	0.499

Phase errors do not change Z-basis outcomes, so <ZZ> stays at 1.00, no shots are discarded, and the Z-basis data looks perfect. But <XX> and <YY> collapse to zero, and the fidelity falls to 0.5, the value for a state with no entanglement.

Show Image

Finding 2: only some strategies touch gate noise (depolarizing noise, readout flip 3%)

Show Image Qiskit AerSimulator, not real hardware.

Depolarizing p	Z-basis fidelity (raw)	Z-basis fidelity (postselected)	True fidelity (raw)	+ Readout mitigation	+ ZNE
0.00	0.943	1.000	0.913	1.000	0.999
0.01	0.939	1.000	0.886	0.967	0.975
0.02	0.930	1.000	0.863	0.942	0.942
0.04	0.917	1.000	0.797	0.873	0.910
0.06	0.910	1.000	0.761	0.820	0.853
0.08	0.909	1.000	0.722	0.782	0.829
0.10	0.904	1.000	0.682	0.739	0.773
Postselection again reports about 1.000 at every noise level, while the true fidelity falls to 0.68. (It keeps 90-94% of shots.)
Readout mitigation removes the readout part of the error: at p = 0 it takes the fidelity from 0.913 to 1.000, and it adds roughly +0.06 to +0.08 everywhere else. It cannot fix gate noise.
ZNE adds a small further gain at more than double the shot cost. Over 20 seeds at p = 0.04 it adds +0.023 on top of readout mitigation (Finding 3). At p ≤ 0.02 the single-run sweep shows no clear advantage. Single-run rows at p ≥ 0.06 suggest a similar or larger gap, but we only repeated p = 0.04.
Nothing fully recovers the ideal state: at p = 0.10 the best result is 0.773.
Finding 3: the same experiments over 20 independent seeds

Show Image Qiskit AerSimulator, not real hardware. Error bars: approximate 95% CI of the mean (they are small, which is the point).

Setting	Metric	Mean	95% CI
Dephasing p = 0.20	Postselected Z-basis fidelity	1.000	[1.000, 1.000]
	True Bell fidelity	0.566	[0.564, 0.569]
	Difference (postselected − true)	+0.433	[0.431, 0.436]
Depolarizing p = 0.04, readout flip 0.03	True fidelity, raw	0.808	[0.806, 0.810]
	+ readout mitigation	0.881	[0.878, 0.883]
	+ readout mitigation + ZNE	0.904	[0.901, 0.907]
	Readout mitigation gain	+0.073	[0.071, 0.075]
	ZNE gain over readout mitigation	+0.023	[0.020, 0.027]

Both effects are far larger than the seed-to-seed variation. The single-run values for p = 0.04 in Finding 2 (0.797 / 0.873 / 0.910) differ slightly from these means, as expected for one finite-shot run.

Circuit diagrams

results/circuit_Z.png, results/circuit_X.png and results/circuit_Y.png show the Bell circuit with each measurement basis. Text versions are in results/circuit_*.txt.

What the results mean
A good-looking histogram is not evidence of a good state. Checking one basis cannot catch errors that live in another basis.
Each mitigation fixes one kind of error. Postselection sees only errors that flip Z-basis parity, readout mitigation fixes only measurement error, and ZNE helps with some gate noise.
Every method has a price: discarded data, calibration circuits, or many more circuits and shots. ZNE's gain at p = 0.04 (+0.023) cost more than twice the shots of readout mitigation alone.
Limitations and what we learned
Simulator only. Real devices have drifting, correlated, gate-dependent noise that our simple models do not capture.
Mitigation is flattered by the simulation. We calibrate readout mitigation using the same error model that corrupts the data, so the calibration matches the true readout noise by construction. On hardware it would not.
Limited repetition. Findings 1 and 2 are single seeded runs. Finding 3 repeats two settings over 20 seeds; its intervals reflect simulator sampling noise only (run-to-run standard deviation of roughly 0.004 to 0.006), not uncertainty about real-hardware noise. We repeated only p = 0.20 (dephasing) and p = 0.04 (depolarizing). The Streamlit app's repeated-trials study only covers the Z-basis metric.
ZNE is partial. We fold only CX gates, so single-qubit H noise is not extrapolated away. We use a simple linear fit, which can over- or under-shoot.
Noiseless basis rotations. The Ry/Rx gates that change the measurement basis are noise-free in our model; on hardware they would add error.
This is error mitigation, not error correction. We never protect the state; we only estimate a cleaner answer from noisy runs.
Biggest lesson: the metric you choose decides what you can detect. Our original Z-basis "fidelity" hid exactly the errors that mattered. We also learned to repeat before trusting: our first, single-seed estimate of the ZNE benefit was larger than the 20-seed result.
Next steps: repeat the whole sweeps over many seeds; run with a real IBM backend's noise snapshot, then on hardware; try other extrapolation fits; add noisy basis rotations.
Setup and run

Tested with Python 3.13, qiskit 2.6.0 and qiskit-aer 0.17.2 on Windows. Exact pinned versions are in requirements.txt.

powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python run_demo.py          # writes charts, circuits and CSVs to results/
python run_robustness.py    # 20-seed confidence intervals (about 1-3 minutes)
python -m pytest -q         # 10 tests

Optional interactive explorer (older Z-basis dashboard; the main results come from run_demo.py):

powershell
streamlit run app.py

pylatexenc is optional. Without it, circuit diagrams are drawn from their text form instead of the Qiskit matplotlib style.

Repository layout
File	Purpose
run_demo.py	One-command demo: runs both experiments and writes charts, circuits and CSVs to results/
run_robustness.py	Repeats the two key experiments over 20 seeds and writes confidence intervals
bell_fidelity.py	True Bell fidelity (X/Y/Z bases), dephasing/depolarizing/readout noise, readout mitigation, ZNE
quantum_engine.py	Bell circuit, readout calibration and mitigation helpers, Z-basis metrics
app.py	Optional Streamlit dashboard (Z-basis view)
tests/	Automated checks (pytest.ini points pytest at the project root)
results/	Charts, circuit diagrams, CSV tables (all simulator output)
Sources, reuse and AI assistance
IBM Quantum, Qiskit documentation.
Qiskit Aer, Building noise models, used for the NoiseModel, depolarizing_error, pauli_error and ReadoutError APIs.
Qiskit Experiments, Readout mitigation, used for the concept only. We implemented the calibration-matrix inversion ourselves with NumPy.
Zero-noise extrapolation concept: Temme, Bravyi, Gambetta, "Error mitigation for short-depth quantum circuits," Phys. Rev. Lett. 119, 180509 (2017); Li and Benjamin, Phys. Rev. X 7, 021050 (2017). The implementation (CX folding and linear fit) is our own.
The Bell-state fidelity formula F = (1 + XX - YY + ZZ)/4 is standard.

What we changed or added on top of the starting dashboard: true-fidelity measurement in three bases, the dephasing noise model, CX-folding ZNE, the one-command run_demo.py, the 20-seed run_robustness.py, the cost comparison, the tests, and the "postselection can fool you" experiment.

AI assistance: we used Claude (Anthropic) as an AI assistant during the hackathon to help plan experiments and draft code and documentation. We ran, tested and reviewed everything ourselves.