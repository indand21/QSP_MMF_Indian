"""
Model Validation: Predicted vs Observed MPA PK from Published Studies
=====================================================================
Compares model-predicted AUC0-12 distributions against published clinical
PK data from multiple ethnic populations and dosing scenarios.

Validation studies:
1. Western Caucasian: 1g BID + CsA → AUC ~33.3 mg.h/L (Shaw et al. 2003)
2. Chinese renal Tx: 1g BID + CsA → AUC 52.16±12.50 (Zicheng et al. 2006)
3. Thai renal Tx: 500mg BID + CsA/Tac → AUC ~39.49 (Pithukpakorn et al. 2014)
4. Thai renal Tx: 500mg BID + CsA → AUC ~37.54 (Yau & Vathsala 2007 ref)
5. Indian lupus nephritis: popPK (Koloskoff et al. 2024) - qualitative
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.mpa_pbpk import (PatientParameters, PKParameters, DrugParameters,
                              simulate_steady_state)
from populations.virtual_populations import (
    PopulationDistributions, generate_virtual_population,
    WESTERN_POPULATION, INDIAN_POPULATION, _truncated_normal
)


# ============================================================
# VALIDATION STUDY DEFINITIONS
# ============================================================

@dataclass
class ValidationStudy:
    """Published clinical PK data for model validation."""
    name: str
    reference: str
    population: str         # descriptive label
    dose_mg: float          # MMF dose per administration
    regimen: str            # "BID" etc.
    cni: str                # "cyclosporine", "tacrolimus", or "mixed"
    n_patients: int
    observed_auc_mean: float       # mg.h/L (AUC0-12 or AUC0-tau)
    observed_auc_sd: Optional[float] = None
    observed_auc_median: Optional[float] = None
    # Population characteristics (if reported)
    wt_mean: Optional[float] = None
    wt_sd: Optional[float] = None
    alb_mean: Optional[float] = None
    alb_sd: Optional[float] = None
    gfr_mean: Optional[float] = None
    gfr_sd: Optional[float] = None
    prop_tacrolimus: Optional[float] = None


VALIDATION_STUDIES = [
    ValidationStudy(
        name="Western Caucasian (CsA)",
        reference="Shaw et al. Ther Drug Monit 2003; Le Meur et al. 2007",
        population="Western",
        dose_mg=1000.0,
        regimen="BID",
        cni="cyclosporine",
        n_patients=100,  # approximate pooled
        observed_auc_mean=33.3,
        observed_auc_sd=13.7,
        wt_mean=78.0, wt_sd=15.0,
        alb_mean=4.0, alb_sd=0.4,
        gfr_mean=55.0, gfr_sd=18.0,
        prop_tacrolimus=0.0,
    ),
    ValidationStudy(
        name="Western Tacrolimus",
        reference="van Hest et al. Clin Pharmacokinet 2006; Staatz & Tett 2007",
        population="Western",
        dose_mg=1000.0,
        regimen="BID",
        cni="tacrolimus",
        n_patients=80,
        observed_auc_mean=47.0,
        observed_auc_sd=18.0,
        wt_mean=78.0, wt_sd=15.0,
        alb_mean=4.0, alb_sd=0.4,
        gfr_mean=55.0, gfr_sd=18.0,
        prop_tacrolimus=1.0,
    ),
    ValidationStudy(
        name="Chinese Renal Tx (CsA)",
        reference="Zicheng et al. Eur J Clin Pharmacol 2006",
        population="Chinese",
        dose_mg=1000.0,
        regimen="BID",
        cni="cyclosporine",
        n_patients=31,
        observed_auc_mean=52.16,
        observed_auc_sd=12.50,
        wt_mean=62.0, wt_sd=10.0,   # typical Chinese transplant
        alb_mean=3.8, alb_sd=0.4,
        gfr_mean=55.0, gfr_sd=15.0,
        prop_tacrolimus=0.0,
    ),
    ValidationStudy(
        name="Thai Renal Tx (Mixed CNI)",
        reference="Pithukpakorn et al. Pharmacogenomics 2014",
        population="Thai",
        dose_mg=500.0,
        regimen="BID",
        cni="mixed",
        n_patients=138,
        observed_auc_mean=39.49,
        observed_auc_sd=15.0,   # estimated from range
        wt_mean=55.0, wt_sd=10.0,
        alb_mean=3.7, alb_sd=0.5,
        gfr_mean=50.0, gfr_sd=15.0,
        prop_tacrolimus=0.60,   # mixed
    ),
    ValidationStudy(
        name="Thai Renal Tx (CsA)",
        reference="Yau & Vathsala Asian data 2007",
        population="Thai",
        dose_mg=500.0,
        regimen="BID",
        cni="cyclosporine",
        n_patients=16,
        observed_auc_mean=37.54,
        observed_auc_sd=12.0,   # estimated
        wt_mean=55.0, wt_sd=10.0,
        alb_mean=3.6, alb_sd=0.5,
        gfr_mean=50.0, gfr_sd=15.0,
        prop_tacrolimus=0.0,
    ),
]


# ============================================================
# VIRTUAL POPULATION MATCHING
# ============================================================

def create_matched_population(study: ValidationStudy, n: int = 200,
                               seed: int = 42) -> PopulationDistributions:
    """Create a population distribution matching the study demographics."""
    # Use study-reported values where available, otherwise use defaults
    pop = PopulationDistributions(
        name=f"Matched: {study.name}",
        wt_mean=study.wt_mean or 70.0,
        wt_sd=study.wt_sd or 12.0,
        ht_mean=165.0 if study.population in ["Chinese", "Thai", "Indian"] else 172.0,
        ht_sd=8.0,
        alb_mean=study.alb_mean or 3.8,
        alb_sd=study.alb_sd or 0.4,
        gfr_mean=study.gfr_mean or 55.0,
        gfr_sd=study.gfr_sd or 15.0,
        prop_tacrolimus=study.prop_tacrolimus if study.prop_tacrolimus is not None else 0.5,
        # Asian populations may have slightly different UGT activity
        ugt1a9_mean=0.95 if study.population in ["Chinese", "Thai", "Indian"] else 1.0,
        ugt1a9_sd=0.18 if study.population in ["Chinese", "Thai", "Indian"] else 0.15,
        ugt2b7_mean=0.93 if study.population in ["Chinese", "Thai", "Indian"] else 1.0,
        ugt2b7_sd=0.18 if study.population in ["Chinese", "Thai", "Indian"] else 0.15,
        abcc2_mean=0.97 if study.population in ["Chinese", "Thai", "Indian"] else 1.0,
        abcc2_sd=0.18 if study.population in ["Chinese", "Thai", "Indian"] else 0.15,
    )
    return pop


def simulate_study(study: ValidationStudy, n_patients: int = 200,
                   seed: int = 42) -> dict:
    """Simulate a matched virtual population for a validation study."""
    print(f"\n  Simulating: {study.name} ({study.dose_mg}mg {study.regimen}, {study.cni})")
    print(f"  Reference: {study.reference}")

    pop_dist = create_matched_population(study, n_patients, seed)
    patients = generate_virtual_population(pop_dist, n=n_patients, seed=seed)

    # Force CNI type if study specifies a single CNI
    if study.cni == "cyclosporine":
        for p in patients:
            p.cni_type = "cyclosporine"
    elif study.cni == "tacrolimus":
        for p in patients:
            p.cni_type = "tacrolimus"
    # "mixed" keeps the randomized allocation

    pk_params = PKParameters()
    drug_params = DrugParameters()

    auc_values = []
    auc_free_values = []
    cmax_values = []
    trough_values = []
    failed = 0

    for i, patient in enumerate(patients):
        try:
            result = simulate_steady_state(
                dose_mg=study.dose_mg,
                patient=patient,
                pk_params=pk_params,
                drug_params=drug_params,
                n_doses=14,
                tau=12.0,
            )
            auc_values.append(result['auc_ss_0_12'])
            auc_free_values.append(result['auc_free_ss_0_12'])
            cmax_values.append(result['cmax_ss'])
            trough_values.append(result['c_trough_ss'])
        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"    Warning: patient {i} failed: {e}")

    auc_values = np.array(auc_values)
    auc_free_values = np.array(auc_free_values)

    pred_mean = np.mean(auc_values)
    pred_sd = np.std(auc_values)
    pred_median = np.median(auc_values)

    # Prediction error metrics
    mpe = (pred_mean - study.observed_auc_mean) / study.observed_auc_mean * 100
    fold_error = pred_mean / study.observed_auc_mean

    print(f"  Observed AUC: {study.observed_auc_mean:.1f} +/- {study.observed_auc_sd or 0:.1f} mg.h/L (n={study.n_patients})")
    print(f"  Predicted AUC: {pred_mean:.1f} +/- {pred_sd:.1f} mg.h/L (n={len(auc_values)})")
    print(f"  MPE: {mpe:+.1f}%  |  Fold error: {fold_error:.2f}")
    if failed > 0:
        print(f"  ({failed} simulations failed)")

    return {
        'study': study,
        'auc_predicted': auc_values,
        'auc_free_predicted': auc_free_values,
        'cmax_predicted': np.array(cmax_values),
        'trough_predicted': np.array(trough_values),
        'pred_mean': pred_mean,
        'pred_sd': pred_sd,
        'pred_median': pred_median,
        'mpe_pct': mpe,
        'fold_error': fold_error,
        'n_simulated': len(auc_values),
        'n_failed': failed,
    }


# ============================================================
# VISUALIZATION
# ============================================================

def plot_validation(results: List[dict], output_dir: str):
    """Generate validation comparison plots."""

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('Model Validation: Predicted vs Observed MPA AUC₀₋₁₂',
                 fontsize=16, fontweight='bold', y=0.98)

    # --- Panel 1: Predicted vs Observed scatter (top-left) ---
    ax = axes[0, 0]
    obs_means = [r['study'].observed_auc_mean for r in results]
    pred_means = [r['pred_mean'] for r in results]
    obs_sds = [r['study'].observed_auc_sd or 0 for r in results]
    pred_sds = [r['pred_sd'] for r in results]
    labels = [r['study'].name for r in results]
    colors = ['#2196F3', '#1976D2', '#FF5722', '#FF9800', '#FFC107']

    for i, r in enumerate(results):
        ax.errorbar(r['study'].observed_auc_mean, r['pred_mean'],
                    xerr=r['study'].observed_auc_sd or 0,
                    yerr=r['pred_sd'],
                    fmt='o', color=colors[i], markersize=10, capsize=5,
                    label=r['study'].name, zorder=3)

    # Identity line and 2-fold bounds
    lims = [0, max(max(obs_means) + 20, max(pred_means) + 20)]
    ax.plot(lims, lims, 'k--', alpha=0.5, label='Identity')
    ax.fill_between(np.linspace(0, 100, 100),
                    np.linspace(0, 100, 100) * 0.5,
                    np.linspace(0, 100, 100) * 2.0,
                    alpha=0.08, color='green', label='2-fold range')
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel('Observed AUC₀₋₁₂ (mg·h/L)', fontsize=11)
    ax.set_ylabel('Predicted AUC₀₋₁₂ (mg·h/L)', fontsize=11)
    ax.set_title('Predicted vs Observed', fontweight='bold')
    ax.legend(fontsize=7, loc='upper left')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # --- Panel 2: Fold-error bar chart (top-center) ---
    ax = axes[0, 1]
    fold_errors = [r['fold_error'] for r in results]
    bar_colors = ['#4CAF50' if 0.8 <= fe <= 1.25 else '#FF9800' if 0.5 <= fe <= 2.0 else '#F44336'
                  for fe in fold_errors]
    bars = ax.barh(range(len(results)), fold_errors, color=bar_colors, edgecolor='black', alpha=0.8)
    ax.axvline(x=1.0, color='black', linestyle='--', linewidth=1.5)
    ax.axvspan(0.8, 1.25, alpha=0.1, color='green', label='Acceptable (0.8-1.25)')
    ax.axvspan(0.5, 0.8, alpha=0.05, color='orange')
    ax.axvspan(1.25, 2.0, alpha=0.05, color='orange')
    ax.set_yticks(range(len(results)))
    ax.set_yticklabels([r['study'].name for r in results], fontsize=9)
    ax.set_xlabel('Fold Error (Predicted / Observed)', fontsize=11)
    ax.set_title('Prediction Accuracy', fontweight='bold')
    ax.set_xlim(0, 2.5)
    ax.legend(fontsize=8)
    ax.grid(True, axis='x', alpha=0.3)

    # Add fold-error values on bars
    for i, (fe, bar) in enumerate(zip(fold_errors, bars)):
        ax.text(fe + 0.05, i, f'{fe:.2f}', va='center', fontsize=10, fontweight='bold')

    # --- Panel 3: MPE% bar chart (top-right) ---
    ax = axes[0, 2]
    mpes = [r['mpe_pct'] for r in results]
    mpe_colors = ['#4CAF50' if abs(m) <= 25 else '#FF9800' if abs(m) <= 50 else '#F44336'
                  for m in mpes]
    bars = ax.barh(range(len(results)), mpes, color=mpe_colors, edgecolor='black', alpha=0.8)
    ax.axvline(x=0, color='black', linestyle='-', linewidth=1)
    ax.axvspan(-25, 25, alpha=0.1, color='green', label='Acceptable (±25%)')
    ax.set_yticks(range(len(results)))
    ax.set_yticklabels([r['study'].name for r in results], fontsize=9)
    ax.set_xlabel('Mean Prediction Error (%)', fontsize=11)
    ax.set_title('Mean Prediction Error', fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, axis='x', alpha=0.3)
    for i, (m, bar) in enumerate(zip(mpes, bars)):
        ax.text(m + (2 if m >= 0 else -2), i, f'{m:+.1f}%',
                va='center', ha='left' if m >= 0 else 'right', fontsize=10, fontweight='bold')

    # --- Panels 4-5-6: Predicted AUC distributions vs observed (bottom row) ---
    # Combine into distribution comparison panels
    for idx, r in enumerate(results):
        if idx >= 3:
            break
        ax = axes[1, idx]
        auc_pred = r['auc_predicted']

        # Histogram of predictions
        ax.hist(auc_pred, bins=25, density=True, alpha=0.6, color=colors[idx],
                edgecolor='black', label='Predicted')

        # Observed distribution (normal approximation)
        obs_mean = r['study'].observed_auc_mean
        obs_sd = r['study'].observed_auc_sd or r['pred_sd']
        x_range = np.linspace(max(0, obs_mean - 3*obs_sd), obs_mean + 3*obs_sd, 200)
        obs_pdf = (1 / (obs_sd * np.sqrt(2*np.pi))) * np.exp(-0.5 * ((x_range - obs_mean)/obs_sd)**2)
        ax.plot(x_range, obs_pdf, 'r-', linewidth=2.5, label='Observed (normal approx)')
        ax.axvline(obs_mean, color='red', linestyle='--', alpha=0.7, label=f'Obs mean: {obs_mean:.1f}')
        ax.axvline(np.mean(auc_pred), color=colors[idx], linestyle='--', alpha=0.7,
                   label=f'Pred mean: {np.mean(auc_pred):.1f}')

        # Therapeutic window
        ax.axvspan(30, 60, alpha=0.08, color='green')

        ax.set_xlabel('AUC₀₋₁₂ (mg·h/L)', fontsize=11)
        ax.set_ylabel('Density', fontsize=11)
        ax.set_title(r['study'].name, fontweight='bold', fontsize=10)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    outpath = os.path.join(output_dir, 'model_validation.png')
    plt.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n  Saved: {outpath}")
    return outpath


def plot_validation_distributions(results: List[dict], output_dir: str):
    """Additional panel: all 5 studies AUC distributions side by side."""
    n_studies = len(results)
    fig, axes = plt.subplots(1, n_studies, figsize=(4*n_studies, 5), sharey=True)
    if n_studies == 1:
        axes = [axes]

    colors = ['#2196F3', '#1976D2', '#FF5722', '#FF9800', '#FFC107']

    for i, r in enumerate(results):
        ax = axes[i]
        auc_pred = r['auc_predicted']
        obs_mean = r['study'].observed_auc_mean
        obs_sd = r['study'].observed_auc_sd or r['pred_sd']

        ax.hist(auc_pred, bins=20, density=True, alpha=0.6, color=colors[i],
                edgecolor='black')

        x_range = np.linspace(max(0, obs_mean - 3.5*obs_sd), obs_mean + 3.5*obs_sd, 200)
        obs_pdf = (1 / (obs_sd * np.sqrt(2*np.pi))) * np.exp(-0.5 * ((x_range - obs_mean)/obs_sd)**2)
        ax.plot(x_range, obs_pdf, 'r-', linewidth=2)
        ax.axvline(obs_mean, color='red', linestyle='--', alpha=0.7)
        ax.axvline(np.mean(auc_pred), color=colors[i], linestyle='--', linewidth=2)

        ax.axvspan(30, 60, alpha=0.08, color='green')
        ax.set_xlabel('AUC₀₋₁₂ (mg·h/L)')
        ax.set_title(f"{r['study'].name}\n{r['study'].dose_mg:.0f}mg {r['study'].cni}",
                     fontsize=9, fontweight='bold')

        # Add text box with metrics
        textstr = (f"Obs: {obs_mean:.1f}±{obs_sd:.1f}\n"
                   f"Pred: {r['pred_mean']:.1f}±{r['pred_sd']:.1f}\n"
                   f"FE: {r['fold_error']:.2f}")
        ax.text(0.95, 0.95, textstr, transform=ax.transAxes, fontsize=8,
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    axes[0].set_ylabel('Density')
    fig.suptitle('Predicted vs Observed AUC Distributions Across Studies',
                 fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    outpath = os.path.join(output_dir, 'validation_distributions.png')
    plt.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {outpath}")
    return outpath


def print_validation_summary(results: List[dict]):
    """Print a formatted validation summary table."""
    print("\n" + "="*90)
    print("  MODEL VALIDATION SUMMARY")
    print("="*90)
    print(f"  {'Study':<30} {'Obs AUC':<15} {'Pred AUC':<15} {'FE':<8} {'MPE%':<10} {'Status'}")
    print("-"*90)

    all_fe = []
    for r in results:
        obs = r['study'].observed_auc_mean
        obs_sd = r['study'].observed_auc_sd or 0
        pred = r['pred_mean']
        pred_sd = r['pred_sd']
        fe = r['fold_error']
        mpe = r['mpe_pct']
        all_fe.append(fe)

        if 0.8 <= fe <= 1.25:
            status = "PASS"
        elif 0.5 <= fe <= 2.0:
            status = "ACCEPTABLE"
        else:
            status = "FAIL"

        print(f"  {r['study'].name:<30} {obs:>5.1f}±{obs_sd:<5.1f}   "
              f"{pred:>5.1f}±{pred_sd:<5.1f}   {fe:<8.2f} {mpe:<+10.1f} {status}")

    print("-"*90)
    avg_fe = np.mean(all_fe)
    gmfe = np.exp(np.mean(np.log(np.array(all_fe))))
    n_pass = sum(1 for fe in all_fe if 0.8 <= fe <= 1.25)
    n_acceptable = sum(1 for fe in all_fe if 0.5 <= fe <= 2.0)
    print(f"\n  Average Fold Error: {avg_fe:.2f}")
    print(f"  Geometric Mean Fold Error (GMFE): {gmfe:.2f}")
    print(f"  Within 0.8-1.25: {n_pass}/{len(all_fe)} studies")
    print(f"  Within 0.5-2.0:  {n_acceptable}/{len(all_fe)} studies")
    print(f"\n  Regulatory acceptance: GMFE < 2.0 -> {'PASS' if gmfe < 2.0 else 'FAIL'}")
    print("="*90)


# ============================================================
# MAIN
# ============================================================

def main():
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'outputs')
    os.makedirs(output_dir, exist_ok=True)

    print("="*70)
    print("  MPA PBPK MODEL VALIDATION")
    print("  Comparing Predicted vs Published Clinical PK Data")
    print("="*70)

    # Run all validation studies
    results = []
    for study in VALIDATION_STUDIES:
        r = simulate_study(study, n_patients=200, seed=42)
        results.append(r)

    # Print summary
    print_validation_summary(results)

    # Generate plots
    print("\nGenerating validation figures...")
    plot_validation(results, output_dir)
    plot_validation_distributions(results, output_dir)

    print("\nValidation complete.")


if __name__ == "__main__":
    main()
