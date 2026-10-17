import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.pyplot as plt

from quantum_engine import (
    bell_circuit, run_experiment, sweep_noise, bell_distribution_fidelity,
    count_vector, parity_error_rate
)

st.set_page_config(page_title="Quantum Rescue", page_icon="⚛️", layout="wide")
st.title("⚛️ Quantum Rescue")
st.subheader("Detect. Recover. Verify.")
st.write(
    "Can we improve the reliability of a noisy Bell-state experiment? "
    "This educational project compares raw results, parity postselection, "
    "and calibrated readout mitigation using Qiskit Aer."
)
st.info("All results on this dashboard come from a local simulator, not real quantum hardware.")

with st.sidebar:
    st.header("Experiment controls")
    shots = st.select_slider("Shots per run", options=[500, 1000, 2500, 5000, 10000], value=2500)
    dep = st.slider("Depolarizing error parameter", 0.0, 0.20, 0.04, 0.01)
    readout = st.slider("Readout flip probability", 0.0, 0.20, 0.04, 0.01)
    seed = st.number_input("Random seed", min_value=0, max_value=100000, value=7, step=1)
    run = st.button("Run experiment", type="primary", use_container_width=True)

if "experiment" not in st.session_state or run:
    with st.spinner("Running Qiskit Aer simulations and calibration circuits..."):
        st.session_state.experiment = run_experiment(shots, dep, readout, int(seed))
        st.session_state.params = (shots, dep, readout, int(seed))

r = st.session_state.experiment
params = st.session_state.params

left, right = st.columns([1, 1])
with left:
    st.markdown("### Bell-state circuit")
    st.code("q0: ──H──■──M──\n          │\nq1: ──────X──M──", language="text")
    st.latex(r"|\Phi^+\rangle = (|00\rangle + |11\rangle)/\sqrt{2}")
    st.caption("The ideal Z-basis outcomes are 00 and 11, each with probability 1/2.")
with right:
    st.markdown("### Main findings")
    a, b, c = st.columns(3)
    a.metric("Noisy parity error", f"{100*r['parity_error']:.2f}%")
    b.metric("Shots retained", f"{r['shots_kept']:,}/{r['shots']:,}")
    c.metric("Retention", f"{100*r['retention']:.1f}%")
    st.caption("Postselection keeps only even-parity outcomes (00/11); it cannot detect every possible error.")

st.divider()

st.markdown("### Outcome counts")

import numpy as np
import matplotlib.pyplot as plt

outcomes = ["00", "01", "10", "11"]

ideal_values = [r["ideal_counts"].get(k, 0) for k in outcomes]
noisy_values = [r["noisy_counts"].get(k, 0) for k in outcomes]
selected_values = [
    r["postselected_counts"].get(k, 0) for k in outcomes
]

x = np.arange(len(outcomes))
width = 0.25

fig, ax = plt.subplots(figsize=(9, 4.5))

ax.bar(x - width, ideal_values, width, label="Ideal")
ax.bar(x, noisy_values, width, label="Noisy")
ax.bar(x + width, selected_values, width, label="Postselected")

ax.set_xlabel("Measured outcome")
ax.set_ylabel("Number of shots")
ax.set_xticks(x)
ax.set_xticklabels(outcomes)
ax.set_title("Bell-state measurement comparison")
ax.legend()
ax.grid(axis="y", alpha=0.25)

fig.tight_layout()
st.pyplot(fig)
plt.close(fig)


st.markdown("### Rescue comparison")

comparison = pd.DataFrame([
    {
        "Method": "Raw noisy run",
        "Shots used": r["shots"],
        "Extra calibration circuits": 0,
        "Calibration shots": 0,
        "What it does": "Baseline with gate and readout noise",
    },
    {
        "Method": "Even-parity postselection",
        "Shots used": r["shots_kept"],
        "Extra calibration circuits": 0,
        "Calibration shots": 0,
        "What it does": "Discards odd-parity outcomes",
    },
    {
        "Method": "Readout mitigation",
        "Shots used": r["shots"],
        "Extra calibration circuits": r["calibration_circuits"],
        "Calibration shots": r["calibration_shots"],
        "What it does": "Corrects estimated readout bias",
    },
])

st.dataframe(
    comparison,
    use_container_width=True,
    hide_index=True,
)

st.markdown("### Fidelity vs depolarizing noise")
st.caption(
    "Fidelity here means classical fidelity of the measured Z-basis distribution against "
    "the ideal 00/11 distribution. It is not full quantum-state fidelity. "
    "Postselected fidelity is conditional on retained shots and must be read alongside retention."
)
with st.spinner("Sweeping noise levels..."):
    rows = sweep_noise(shots=max(1000, int(params[0] // 2)), readout=params[2], seed=params[3] + 500)
df = pd.DataFrame(rows).set_index("Depolarizing parameter")

fig, ax = plt.subplots(figsize=(9, 4.5))

for column in [
    "Ideal",
    "Noisy",
    "Postselected (conditional)",
    "Readout mitigated",
]:
    ax.plot(
        df.index,
        df[column],
        marker="o",
        markersize=4,
        linewidth=2,
        label=column,
    )

ax.set_title("Classical Distribution Fidelity vs Noise")
ax.set_xlabel("Depolarizing error parameter")
ax.set_ylabel("Classical distribution fidelity")
ax.set_xlim(0, 0.15)
ax.set_ylim(0, 1.05)
ax.set_xticks(df.index)
ax.grid(alpha=0.25)
ax.legend(loc="lower left", fontsize=8)
fig.tight_layout()

st.pyplot(fig)
plt.close(fig)

st.dataframe(df.style.format({
    "Ideal": "{:.3f}", "Noisy": "{:.3f}",
    "Postselected (conditional)": "{:.3f}", "Readout mitigated": "{:.3f}",
    "Postselection retention": "{:.1%}", "Noisy parity error": "{:.1%}",
}), use_container_width=True)

st.divider()
st.markdown("## 🧠 Quantum Rescue Intelligence Lab")
st.write(
    "A single run can be misleading. Repeat the experiment with independent "
    "simulator seeds to evaluate consistency, uncertainty, and recovery trade-offs."
)

st.caption(
    "The intervals below describe variation across repeated finite-shot "
    "simulations. They are approximate 95% confidence intervals for the mean, "
    "not guarantees about real quantum hardware."
)

trial_count = st.select_slider(
    "Independent trials",
    options=[5, 10, 20, 30],
    value=20,
    key="robustness_trial_count",
)

if st.button("Run robustness study", type="primary"):
    trial_shots = max(1000, int(params[0] // 2))
    trial_rows = []

    progress = st.progress(0, text="Running independent experiments...")

    for i in range(trial_count):
        trial_result = run_experiment(
            shots=trial_shots,
            depolarizing=params[1],
            readout=params[2],
            seed=params[3] + 1000 + i * 31,
        )

        trial_rows.append({
            "Trial": i + 1,
            "Noisy fidelity": bell_distribution_fidelity(
                trial_result["noisy_probs"]
            ),
            "Postselected fidelity": bell_distribution_fidelity(
                trial_result["postselected_probs"]
            ),
            "Mitigated fidelity": bell_distribution_fidelity(
                trial_result["mitigated_probs"]
            ),
            "Retention": trial_result["retention"],
            "Parity error": trial_result["parity_error"],
        })

        progress.progress(
            (i + 1) / trial_count,
            text=f"Completed {i + 1} of {trial_count} trials",
        )

    progress.empty()
    st.session_state["robustness_results"] = trial_rows
    st.session_state["robustness_params"] = params

if (
    "robustness_results" in st.session_state
    and st.session_state.get("robustness_params") == params
):
    results_df = pd.DataFrame(st.session_state["robustness_results"])

    def mean_ci(series):
        values = np.asarray(series, dtype=float)
        mean = float(np.mean(values))

        if len(values) < 2:
            return mean, mean, mean

        margin = 1.96 * float(np.std(values, ddof=1)) / np.sqrt(len(values))
        return mean, max(0.0, mean - margin), min(1.0, mean + margin)

    st.markdown("### Repeatability results")

    metric_columns = [
        ("Noisy fidelity", "Noisy"),
        ("Postselected fidelity", "Postselected"),
        ("Mitigated fidelity", "Readout mitigated"),
        ("Retention", "Shot retention"),
    ]

    summary_rows = []

    for column, label in metric_columns:
        mean, lower, upper = mean_ci(results_df[column])
        summary_rows.append({
            "Metric": label,
            "Mean": mean,
            "95% CI lower": lower,
            "95% CI upper": upper,
        })

    summary_df = pd.DataFrame(summary_rows)

    st.dataframe(
        summary_df.style.format({
            "Mean": "{:.3f}",
            "95% CI lower": "{:.3f}",
            "95% CI upper": "{:.3f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Consistency across trials")

    fig, ax = plt.subplots(figsize=(9, 4.5))

    plotted_metrics = [
        ("Noisy fidelity", "Noisy"),
        ("Postselected fidelity", "Postselected"),
        ("Mitigated fidelity", "Readout mitigated"),
    ]

    for column, label in plotted_metrics:
        mean, lower, upper = mean_ci(results_df[column])

        ax.errorbar(
            label,
            mean,
            yerr=[[mean - lower], [upper - mean]],
            fmt="o",
            capsize=5,
            markersize=7,
            label=f"{label}: mean and 95% CI",
        )

    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Classical distribution fidelity")
    ax.set_title("Recovery performance across independent trials")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()

    st.pyplot(fig)
    plt.close(fig)

    noisy_mean = float(results_df["Noisy fidelity"].mean())
    mitigated_mean = float(results_df["Mitigated fidelity"].mean())
    retention_mean = float(results_df["Retention"].mean())
    parity_mean = float(results_df["Parity error"].mean())

    mitigation_gain = mitigated_mean - noisy_mean

    st.markdown("### Rescue Decision Engine")

    st.metric(
        "Mean mitigation change",
        f"{mitigation_gain:+.3f}",
        help="Mitigated fidelity minus noisy fidelity, averaged across trials.",
    )

    if mitigation_gain > 0.01:
        st.success(
            "Readout mitigation improved the measured distribution-fidelity "
            "estimate on average in this experiment. Check the uncertainty "
            "interval and remember that gate noise remains."
        )
    elif mitigation_gain < -0.01:
        st.warning(
            "Readout mitigation performed worse on average in this experiment. "
            "Finite calibration shots and matrix inversion can amplify estimation "
            "noise. Do not assume mitigation always helps."
        )
    else:
        st.info(
            "No meaningful average fidelity change was observed using the "
            "0.01 threshold. The added calibration cost may not be worthwhile "
            "for this particular setting."
        )

    if parity_mean > 0.02 and retention_mean >= 0.75:
        st.info(
            f"Postselection retained {retention_mean:.1%} of shots on average "
            f"and filtered odd-parity outcomes. It may be useful as a diagnostic "
            f"filter, but it does not establish that the original state was "
            f"recovered."
        )
    elif retention_mean < 0.75:
        st.warning(
            f"Only {retention_mean:.1%} of shots were retained on average. "
            "Postselection has a substantial data cost in this setting."
        )
    else:
        st.info(
            "The observed parity-error rate is low. Compare the data discarded "
            "by postselection against the benefit before choosing it."
        )

    with st.expander("Inspect individual trial results"):
        st.dataframe(
            results_df.style.format({
                "Noisy fidelity": "{:.3f}",
                "Postselected fidelity": "{:.3f}",
                "Mitigated fidelity": "{:.3f}",
                "Retention": "{:.1%}",
                "Parity error": "{:.1%}",
            }),
            use_container_width=True,
            hide_index=True,
        )

with st.expander("View the calibration assignment matrix"):
    st.write("Rows = observed outcomes; columns = prepared true outcomes; order is 00, 01, 10, 11.")
    st.dataframe(pd.DataFrame(r["calibration_matrix"], index=["obs 00","obs 01","obs 10","obs 11"],
                              columns=["true 00","true 01","true 10","true 11"]).style.format("{:.3f}"))
    st.caption("Four basis-state calibration circuits are used. Finite-shot inversion can produce negative estimates, so this demo clips negative probabilities and renormalizes them.")

st.markdown("### What we learned")
st.markdown("""
- **Postselection** can remove observed odd-parity shots, but reduces the amount of data and cannot identify every error.
- **Readout mitigation** estimates and corrects measurement bias; it does not undo depolarizing gate errors.
- A better-looking conditional distribution is not automatically a better estimate of the full quantum state.
- This is a simplified simulation. Real devices can have correlated, drifting, and gate-dependent noise.
""")
st.caption("Reproducibility: adjust the random seed and rerun. Finite-shot results vary; trends should be evaluated across repeated runs.")
