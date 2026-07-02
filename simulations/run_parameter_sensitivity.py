"""
Parameter Uncertainty Sensitivity Analysis
===========================================
Local one-at-a-time (OAT) sensitivity of MPA AUC to +/-20% perturbation
of six structural PBPK/PD parameters, evaluated at the Indian mean
patient (BW 58 kg, albumin 4.0 g/dL, tacrolimus, UGT1A9=0.95,
UGT2B7=0.92, eGFR 50). Produces a tornado plot for FigureS5.

This is a deterministic sensitivity analysis, not a probabilistic one:
the intent is to demonstrate that the paper's conclusions (Indian > Western
total/free AUC; 12 mg/kg BID corrects overexposure) are structurally
robust to +/-20% perturbations of the dominant uncertain parameters.
"""

import os
import sys
import copy
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.mpa_pbpk import (
    DrugParameters,
    PatientParameters,
    PKParameters,
    simulate_steady_state,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG_DIR = os.path.join(PROJECT_ROOT, "outputs", "manuscript_updated")
FIG_PATH = os.path.join(FIG_DIR, "FigureS5_ParameterSensitivity.png")


def make_baseline_patient():
    """Indian mean patient."""
    return PatientParameters(
        body_weight=58.0,
        height=165.0,
        albumin=4.0,
        gfr=50.0,
        hematocrit=0.38,
        cni_type="tacrolimus",
        ugt1a9_activity=0.95,
        ugt2b7_activity=0.92,
    )


def compute_auc(pk, drug, patient, dose_mg=1000.0):
    """Simulate 14-dose BID steady state and return the last-interval total MPA AUC (mg.h/L)."""
    result = simulate_steady_state(
        dose_mg=dose_mg,
        patient=patient,
        pk_params=pk,
        drug_params=drug,
        n_doses=14,
        tau=12.0,
    )
    return result["auc_ss_0_12"]


def vary(base_pk, base_drug, attr_path, factor):
    """Return (pk, drug) copies with one attribute scaled by `factor`.

    `attr_path` is a tuple ('pk', name) or ('drug', name).
    """
    pk = copy.deepcopy(base_pk)
    drug = copy.deepcopy(base_drug)
    target, name = attr_path
    obj = pk if target == "pk" else drug
    setattr(obj, name, getattr(obj, name) * factor)
    return pk, drug


def run_psa():
    patient = make_baseline_patient()
    base_pk = PKParameters()
    base_drug = DrugParameters()

    baseline_auc = compute_auc(base_pk, base_drug, patient)
    print(f"Baseline AUC (Indian mean patient, 1 g BID): {baseline_auc:.2f} mg.h/L")

    # (display_label, (target, attr), nominal value for caption)
    parameters = [
        ("fu,ref (free fraction at alb 4.0)", ("drug", "fu_reference"), base_drug.fu_reference),
        ("CLint UGT1A9",                     ("pk",   "CLint_ugt1a9"),  base_pk.CLint_ugt1a9),
        ("CLint UGT2B7",                     ("pk",   "CLint_ugt2b7"),  base_pk.CLint_ugt2b7),
        ("Vc (central volume)",              ("pk",   "Vc"),            base_pk.Vc),
        ("ka (absorption)",                  ("pk",   "ka"),            base_pk.ka),
        ("k_bile (biliary efflux rate)",     ("pk",   "k_bile"),        base_pk.k_bile),
    ]

    results = []
    for label, path, nominal in parameters:
        pk_lo, drug_lo = vary(base_pk, base_drug, path, 0.8)
        pk_hi, drug_hi = vary(base_pk, base_drug, path, 1.2)
        auc_lo = compute_auc(pk_lo, drug_lo, patient)
        auc_hi = compute_auc(pk_hi, drug_hi, patient)
        pct_lo = 100.0 * (auc_lo - baseline_auc) / baseline_auc
        pct_hi = 100.0 * (auc_hi - baseline_auc) / baseline_auc
        results.append(
            dict(label=label, nominal=nominal,
                 auc_lo=auc_lo, auc_hi=auc_hi,
                 pct_lo=pct_lo, pct_hi=pct_hi,
                 rng=abs(pct_hi - pct_lo))
        )
        print(f"  {label:40s}  -20%: {pct_lo:+6.2f}%  +20%: {pct_hi:+6.2f}%")

    results.sort(key=lambda r: r["rng"], reverse=True)
    return baseline_auc, results


def plot_tornado(baseline_auc, results):
    fig, ax = plt.subplots(figsize=(9.0, 5.5))
    labels = [r["label"] for r in results][::-1]  # largest at top
    lo_pct = [r["pct_lo"] for r in results][::-1]
    hi_pct = [r["pct_hi"] for r in results][::-1]
    y = np.arange(len(labels))

    for i in range(len(labels)):
        lo = lo_pct[i]
        hi = hi_pct[i]
        left = min(lo, hi, 0.0)
        width_neg = 0.0 - min(lo, hi) if min(lo, hi) < 0 else 0.0
        width_pos = max(lo, hi) if max(lo, hi) > 0 else 0.0
        if lo < 0:
            ax.barh(y[i], lo, color="#2E86AB", edgecolor="black", height=0.6)
        if hi > 0:
            ax.barh(y[i], hi, color="#C73E1D", edgecolor="black", height=0.6)
        if lo > 0:
            ax.barh(y[i], lo, color="#C73E1D", edgecolor="black", height=0.6)
        if hi < 0:
            ax.barh(y[i], hi, color="#2E86AB", edgecolor="black", height=0.6)

    ax.axvline(0.0, color="black", linewidth=1.0)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Change in total MPA AUC\u2080\u208b\u2081\u2082\u2095 (%) from baseline", fontsize=11)
    ax.set_title(
        f"Parameter Sensitivity Analysis (Indian mean patient, 1 g MMF BID)\n"
        f"Baseline AUC = {baseline_auc:.1f} mg\u00b7h/L;  \u00b120% perturbation on each parameter",
        fontsize=11,
    )
    ax.grid(axis="x", linestyle=":", alpha=0.5)

    from matplotlib.patches import Patch
    ax.legend(
        handles=[
            Patch(facecolor="#2E86AB", label="\u221220% parameter \u2192 AUC decreases"),
            Patch(facecolor="#C73E1D", label="+20% parameter \u2192 AUC increases"),
        ],
        loc="lower right",
        fontsize=9,
    )

    plt.tight_layout()
    plt.savefig(FIG_PATH, dpi=200)
    plt.close()
    print(f"\nTornado plot saved: {FIG_PATH}")


if __name__ == "__main__":
    baseline, results = run_psa()
    plot_tornado(baseline, results)

    print("\nSummary (sorted by |effect|):")
    print(f"{'Parameter':42s}  {'-20% AUC':>10s}  {'+20% AUC':>10s}  {'Range':>7s}")
    for r in results:
        print(f"{r['label']:42s}  {r['pct_lo']:+9.2f}%  {r['pct_hi']:+9.2f}%  {r['rng']:6.1f}%")
