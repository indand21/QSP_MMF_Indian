"""
Population Simulation: Western vs. Indian MPA Exposure Comparison
==================================================================
Simulates MMF 1g BID at steady state in both populations and compares:
1. AUC_0-12h distributions (total and free MPA)
2. Fraction of patients with overexposure (AUC > 60 mg.h/L)
3. Fraction with underexposure (AUC < 30 mg.h/L)
4. Sensitivity analysis: contribution of each mechanistic factor

Target therapeutic window: MPA AUC_0-12h = 30-60 mg.h/L
(Consensus: Staatz & Tett 2007, van Gelder et al. 2006)
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import warnings

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from model.mpa_pbpk import (
    simulate_steady_state, PKParameters, DrugParameters, PatientParameters
)
from populations.virtual_populations import (
    generate_virtual_population, print_population_summary,
    WESTERN_POPULATION, INDIAN_POPULATION, PopulationDistributions
)

# Suppress integration warnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning)

# Configuration
N_PATIENTS = 500        # per population (increase for publication-quality)
DOSE_MG = 1000          # MMF 1g BID (standard Western dose)
N_DOSES_SS = 14         # 7 days BID to reach steady state
OUTPUT_DIR = os.path.join(project_root, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Therapeutic window
AUC_LOWER = 30.0  # mg.h/L
AUC_UPPER = 60.0  # mg.h/L


def simulate_population(patients, dose_mg, label=""):
    """Simulate steady-state PK for a population of patients."""
    pk = PKParameters()
    drug = DrugParameters()

    results = []
    n_failed = 0

    for i, patient in enumerate(patients):
        if (i + 1) % 100 == 0:
            print(f"  [{label}] Simulating patient {i+1}/{len(patients)}...")
        try:
            res = simulate_steady_state(
                dose_mg=dose_mg,
                patient=patient,
                pk_params=pk,
                drug_params=drug,
                n_doses=N_DOSES_SS,
                tau=12.0
            )
            results.append(res)
        except Exception:
            n_failed += 1

    if n_failed > 0:
        print(f"  [{label}] Warning: {n_failed}/{len(patients)} simulations failed.")

    return results


def extract_metrics(results):
    """Extract key PK metrics from simulation results."""
    aucs = np.array([r['auc_ss_0_12'] for r in results])
    aucs_free = np.array([r['auc_free_ss_0_12'] for r in results])
    cmax = np.array([r['cmax_ss'] for r in results])
    troughs = np.array([r['c_trough_ss'] for r in results])
    weights = np.array([r['patient'].body_weight for r in results])
    albumins = np.array([r['patient'].albumin for r in results])

    return {
        'auc': aucs,
        'auc_free': aucs_free,
        'cmax': cmax,
        'trough': troughs,
        'weight': weights,
        'albumin': albumins,
    }


def print_comparison_table(west_metrics, indian_metrics):
    """Print formatted comparison of PK metrics."""
    print("\n" + "=" * 75)
    print("  STEADY-STATE PK COMPARISON: Western vs. Indian (MMF 1g BID)")
    print("=" * 75)

    fmt = "  {:<30s}  {:>15s}  {:>15s}"
    print(fmt.format("Parameter", "Western", "Indian"))
    print("  " + "-" * 62)

    def ms(arr):
        return f"{np.mean(arr):.1f} +/- {np.std(arr):.1f}"

    print(fmt.format("AUC_0-12h (mg.h/L)", ms(west_metrics['auc']), ms(indian_metrics['auc'])))
    print(fmt.format("AUC_free_0-12h (mg.h/L)", ms(west_metrics['auc_free']), ms(indian_metrics['auc_free'])))
    print(fmt.format("Cmax (mg/L)", ms(west_metrics['cmax']), ms(indian_metrics['cmax'])))
    print(fmt.format("C_trough (mg/L)", ms(west_metrics['trough']), ms(indian_metrics['trough'])))

    # Therapeutic window
    w_in = np.mean((west_metrics['auc'] >= AUC_LOWER) & (west_metrics['auc'] <= AUC_UPPER)) * 100
    i_in = np.mean((indian_metrics['auc'] >= AUC_LOWER) & (indian_metrics['auc'] <= AUC_UPPER)) * 100
    w_over = np.mean(west_metrics['auc'] > AUC_UPPER) * 100
    i_over = np.mean(indian_metrics['auc'] > AUC_UPPER) * 100
    w_under = np.mean(west_metrics['auc'] < AUC_LOWER) * 100
    i_under = np.mean(indian_metrics['auc'] < AUC_LOWER) * 100

    print()
    print(fmt.format("% Within target (30-60)", f"{w_in:.1f}%", f"{i_in:.1f}%"))
    print(fmt.format("% Overexposed (>60)", f"{w_over:.1f}%", f"{i_over:.1f}%"))
    print(fmt.format("% Underexposed (<30)", f"{w_under:.1f}%", f"{i_under:.1f}%"))

    # Dose/kg comparison
    w_dose_kg = DOSE_MG / west_metrics['weight']
    i_dose_kg = DOSE_MG / indian_metrics['weight']
    print()
    print(fmt.format("Dose/kg (mg/kg)", ms(w_dose_kg), ms(i_dose_kg)))
    print("=" * 75)


def plot_comparison(west_metrics, indian_metrics, west_results, indian_results):
    """Generate comprehensive comparison plots."""
    fig = plt.figure(figsize=(18, 14))
    gs = GridSpec(3, 3, figure=fig, hspace=0.35, wspace=0.30)

    colors_w = '#2196F3'  # blue for Western
    colors_i = '#FF5722'  # orange-red for Indian

    # --- Plot 1: AUC Distribution ---
    ax1 = fig.add_subplot(gs[0, 0])
    bins = np.linspace(0, 120, 40)
    ax1.hist(west_metrics['auc'], bins=bins, alpha=0.6, color=colors_w,
             label='Western', density=True, edgecolor='white')
    ax1.hist(indian_metrics['auc'], bins=bins, alpha=0.6, color=colors_i,
             label='Indian', density=True, edgecolor='white')
    ax1.axvline(AUC_LOWER, color='green', linestyle='--', linewidth=1.5, label='Target range')
    ax1.axvline(AUC_UPPER, color='green', linestyle='--', linewidth=1.5)
    ax1.axvspan(AUC_LOWER, AUC_UPPER, alpha=0.08, color='green')
    ax1.set_xlabel('MPA AUC$_{0-12h}$ (mg$\\cdot$h/L)')
    ax1.set_ylabel('Density')
    ax1.set_title('Total MPA AUC Distribution')
    ax1.legend(fontsize=8)

    # --- Plot 2: Free MPA AUC Distribution ---
    ax2 = fig.add_subplot(gs[0, 1])
    bins_free = np.linspace(0, 6, 40)
    ax2.hist(west_metrics['auc_free'], bins=bins_free, alpha=0.6, color=colors_w,
             label='Western', density=True, edgecolor='white')
    ax2.hist(indian_metrics['auc_free'], bins=bins_free, alpha=0.6, color=colors_i,
             label='Indian', density=True, edgecolor='white')
    ax2.set_xlabel('Free MPA AUC$_{0-12h}$ (mg$\\cdot$h/L)')
    ax2.set_ylabel('Density')
    ax2.set_title('Free (Unbound) MPA AUC Distribution')
    ax2.legend(fontsize=8)

    # --- Plot 3: Therapeutic Target Attainment (Bar) ---
    ax3 = fig.add_subplot(gs[0, 2])
    categories = ['Under\n(<30)', 'Target\n(30-60)', 'Over\n(>60)']
    w_pcts = [
        np.mean(west_metrics['auc'] < AUC_LOWER) * 100,
        np.mean((west_metrics['auc'] >= AUC_LOWER) & (west_metrics['auc'] <= AUC_UPPER)) * 100,
        np.mean(west_metrics['auc'] > AUC_UPPER) * 100,
    ]
    i_pcts = [
        np.mean(indian_metrics['auc'] < AUC_LOWER) * 100,
        np.mean((indian_metrics['auc'] >= AUC_LOWER) & (indian_metrics['auc'] <= AUC_UPPER)) * 100,
        np.mean(indian_metrics['auc'] > AUC_UPPER) * 100,
    ]
    x = np.arange(len(categories))
    width = 0.35
    ax3.bar(x - width/2, w_pcts, width, label='Western', color=colors_w, alpha=0.8)
    ax3.bar(x + width/2, i_pcts, width, label='Indian', color=colors_i, alpha=0.8)
    ax3.set_ylabel('% of Population')
    ax3.set_title('Therapeutic Target Attainment')
    ax3.set_xticks(x)
    ax3.set_xticklabels(categories)
    ax3.legend(fontsize=8)
    for i_idx in range(3):
        ax3.text(x[i_idx] - width/2, w_pcts[i_idx] + 1, f'{w_pcts[i_idx]:.0f}%',
                 ha='center', va='bottom', fontsize=7, color=colors_w)
        ax3.text(x[i_idx] + width/2, i_pcts[i_idx] + 1, f'{i_pcts[i_idx]:.0f}%',
                 ha='center', va='bottom', fontsize=7, color=colors_i)

    # --- Plot 4: AUC vs Body Weight ---
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.scatter(west_metrics['weight'], west_metrics['auc'], alpha=0.3,
                s=10, color=colors_w, label='Western')
    ax4.scatter(indian_metrics['weight'], indian_metrics['auc'], alpha=0.3,
                s=10, color=colors_i, label='Indian')
    ax4.axhline(AUC_LOWER, color='green', linestyle='--', alpha=0.5)
    ax4.axhline(AUC_UPPER, color='green', linestyle='--', alpha=0.5)
    ax4.set_xlabel('Body Weight (kg)')
    ax4.set_ylabel('MPA AUC$_{0-12h}$ (mg$\\cdot$h/L)')
    ax4.set_title('AUC vs. Body Weight')
    ax4.legend(fontsize=8)

    # --- Plot 5: AUC vs Albumin ---
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.scatter(west_metrics['albumin'], west_metrics['auc'], alpha=0.3,
                s=10, color=colors_w, label='Western')
    ax5.scatter(indian_metrics['albumin'], indian_metrics['auc'], alpha=0.3,
                s=10, color=colors_i, label='Indian')
    ax5.axhline(AUC_LOWER, color='green', linestyle='--', alpha=0.5)
    ax5.axhline(AUC_UPPER, color='green', linestyle='--', alpha=0.5)
    ax5.set_xlabel('Serum Albumin (g/dL)')
    ax5.set_ylabel('MPA AUC$_{0-12h}$ (mg$\\cdot$h/L)')
    ax5.set_title('AUC vs. Albumin')
    ax5.legend(fontsize=8)

    # --- Plot 6: Free AUC vs Albumin ---
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.scatter(west_metrics['albumin'], west_metrics['auc_free'], alpha=0.3,
                s=10, color=colors_w, label='Western')
    ax6.scatter(indian_metrics['albumin'], indian_metrics['auc_free'], alpha=0.3,
                s=10, color=colors_i, label='Indian')
    ax6.set_xlabel('Serum Albumin (g/dL)')
    ax6.set_ylabel('Free MPA AUC$_{0-12h}$ (mg$\\cdot$h/L)')
    ax6.set_title('Free MPA AUC vs. Albumin')
    ax6.legend(fontsize=8)

    # --- Plot 7: Representative PK profiles ---
    ax7 = fig.add_subplot(gs[2, 0:2])
    # Pick median AUC patient from each population
    w_aucs = np.array([r['auc_ss_0_12'] for r in west_results])
    i_aucs = np.array([r['auc_ss_0_12'] for r in indian_results])
    w_median_idx = np.argmin(np.abs(w_aucs - np.median(w_aucs)))
    i_median_idx = np.argmin(np.abs(i_aucs - np.median(i_aucs)))

    w_rep = west_results[w_median_idx]
    i_rep = indian_results[i_median_idx]

    ax7.plot(w_rep['t_ss'], w_rep['mpa_ss'], color=colors_w, linewidth=2,
             label=f"Western (median): WT={w_rep['patient'].body_weight}kg, "
                   f"Alb={w_rep['patient'].albumin}, AUC={w_rep['auc_ss_0_12']:.1f}")
    ax7.plot(i_rep['t_ss'], i_rep['mpa_ss'], color=colors_i, linewidth=2,
             label=f"Indian (median): WT={i_rep['patient'].body_weight}kg, "
                   f"Alb={i_rep['patient'].albumin}, AUC={i_rep['auc_ss_0_12']:.1f}")
    ax7.set_xlabel('Time post-dose (h)')
    ax7.set_ylabel('MPA Concentration (mg/L)')
    ax7.set_title('Representative Steady-State MPA Concentration-Time Profiles')
    ax7.legend(fontsize=8)
    ax7.set_xlim(0, 12)

    # --- Plot 8: Dose per kg distribution ---
    ax8 = fig.add_subplot(gs[2, 2])
    w_dose_kg = DOSE_MG / west_metrics['weight']
    i_dose_kg = DOSE_MG / indian_metrics['weight']
    ax8.hist(w_dose_kg, bins=30, alpha=0.6, color=colors_w, label='Western',
             density=True, edgecolor='white')
    ax8.hist(i_dose_kg, bins=30, alpha=0.6, color=colors_i, label='Indian',
             density=True, edgecolor='white')
    ax8.set_xlabel('Dose per kg (mg/kg)')
    ax8.set_ylabel('Density')
    ax8.set_title('Effective mg/kg Dose Distribution')
    ax8.legend(fontsize=8)

    fig.suptitle('MPA PBPK Population Simulation: Western vs. Indian\n'
                 f'MMF {DOSE_MG}mg BID | n={N_PATIENTS} per population',
                 fontsize=14, fontweight='bold', y=1.01)

    plt.savefig(os.path.join(OUTPUT_DIR, 'population_comparison.png'),
                dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"\n  Figure saved: {os.path.join(OUTPUT_DIR, 'population_comparison.png')}")


def run_sensitivity_analysis(indian_patients):
    """Sensitivity analysis: quantify contribution of each factor.

    Strategy: Start with Indian body composition but swap individual
    parameters to Western values one at a time.
    """
    print("\n" + "=" * 75)
    print("  SENSITIVITY ANALYSIS: Factor Contribution to AUC Difference")
    print("=" * 75)

    pk = PKParameters()
    drug = DrugParameters()

    # Baseline: full Indian population
    baseline_aucs = []
    for p in indian_patients[:200]:  # use subset for speed
        try:
            res = simulate_steady_state(DOSE_MG, p, pk, drug, N_DOSES_SS)
            baseline_aucs.append(res['auc_ss_0_12'])
        except Exception:
            pass
    baseline_mean = np.mean(baseline_aucs)

    scenarios = {
        'Indian baseline': lambda p: p,
        'WT -> Western (78 kg)': lambda p: PatientParameters(
            body_weight=78.0, height=p.height, albumin=p.albumin, gfr=p.gfr,
            cni_type=p.cni_type, ugt1a9_activity=p.ugt1a9_activity,
            ugt2b7_activity=p.ugt2b7_activity, abcc2_activity=p.abcc2_activity),
        'Albumin -> Western (4.0)': lambda p: PatientParameters(
            body_weight=p.body_weight, height=p.height, albumin=4.0, gfr=p.gfr,
            cni_type=p.cni_type, ugt1a9_activity=p.ugt1a9_activity,
            ugt2b7_activity=p.ugt2b7_activity, abcc2_activity=p.abcc2_activity),
        'CNI -> 70% Tac (Western)': lambda p: PatientParameters(
            body_weight=p.body_weight, height=p.height, albumin=p.albumin, gfr=p.gfr,
            cni_type="tacrolimus" if np.random.random() < 0.70 else "cyclosporine",
            ugt1a9_activity=p.ugt1a9_activity,
            ugt2b7_activity=p.ugt2b7_activity, abcc2_activity=p.abcc2_activity),
        'All -> Western': lambda p: PatientParameters(
            body_weight=78.0, height=172.0, albumin=4.0, gfr=55.0,
            cni_type="tacrolimus" if np.random.random() < 0.70 else "cyclosporine",
            ugt1a9_activity=1.0, ugt2b7_activity=1.0, abcc2_activity=1.0),
    }

    scenario_aucs = {}
    for scenario_name, modifier in scenarios.items():
        aucs = []
        for p in indian_patients[:200]:
            try:
                modified_p = modifier(p)
                res = simulate_steady_state(DOSE_MG, modified_p, pk, drug, N_DOSES_SS)
                aucs.append(res['auc_ss_0_12'])
            except Exception:
                pass
        mean_auc = np.mean(aucs) if aucs else float('nan')
        scenario_aucs[scenario_name] = mean_auc
        pct_change = ((mean_auc - baseline_mean) / baseline_mean) * 100
        print(f"  {scenario_name:<35s}  AUC = {mean_auc:6.1f} mg.h/L  "
              f"({pct_change:+.1f}% from Indian baseline)")

    # Plot tornado chart
    fig, ax = plt.subplots(figsize=(10, 5))
    factors = list(scenario_aucs.keys())[1:]  # skip baseline
    changes = [(scenario_aucs[f] - baseline_mean) for f in factors]

    y_pos = np.arange(len(factors))
    bars = ax.barh(y_pos, changes, color=['#2196F3' if c < 0 else '#FF5722' for c in changes],
                   alpha=0.8, edgecolor='white')
    ax.set_yticks(y_pos)
    ax.set_yticklabels(factors)
    ax.set_xlabel('Change in Mean AUC$_{0-12h}$ (mg$\\cdot$h/L)')
    ax.set_title('Sensitivity Analysis: Impact of Swapping Indian -> Western Parameters')
    ax.axvline(0, color='black', linewidth=0.5)

    for bar, change in zip(bars, changes):
        ax.text(bar.get_width() + (0.5 if change >= 0 else -0.5),
                bar.get_y() + bar.get_height()/2,
                f'{change:+.1f}', ha='left' if change >= 0 else 'right',
                va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'sensitivity_tornado.png'),
                dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"\n  Tornado chart saved: {os.path.join(OUTPUT_DIR, 'sensitivity_tornado.png')}")

    return scenario_aucs


def main():
    print("\n" + "#" * 75)
    print("#  MPA PBPK Population Simulation: Western vs. Indian")
    print(f"#  MMF Dose: {DOSE_MG} mg BID | n = {N_PATIENTS} per population")
    print("#" * 75)

    # Step 1: Generate virtual populations
    print("\n[1/4] Generating virtual populations...")
    west_patients = generate_virtual_population(WESTERN_POPULATION, N_PATIENTS, seed=42)
    indian_patients = generate_virtual_population(INDIAN_POPULATION, N_PATIENTS, seed=123)

    print_population_summary(west_patients, WESTERN_POPULATION.name)
    print_population_summary(indian_patients, INDIAN_POPULATION.name)

    # Step 2: Simulate steady-state PK
    print("[2/4] Simulating Western population...")
    west_results = simulate_population(west_patients, DOSE_MG, "Western")
    print(f"  Completed: {len(west_results)} patients")

    print("\n[3/4] Simulating Indian population...")
    indian_results = simulate_population(indian_patients, DOSE_MG, "Indian")
    print(f"  Completed: {len(indian_results)} patients")

    # Step 3: Compare results
    west_metrics = extract_metrics(west_results)
    indian_metrics = extract_metrics(indian_results)

    print_comparison_table(west_metrics, indian_metrics)

    # Step 4: Generate plots
    print("\n[4/4] Generating comparison plots...")
    plot_comparison(west_metrics, indian_metrics, west_results, indian_results)

    # Step 5: Sensitivity analysis
    print("\nRunning sensitivity analysis (subset of Indian population)...")
    run_sensitivity_analysis(indian_patients)

    print("\n" + "#" * 75)
    print("#  Simulation complete. Check outputs/ folder for figures.")
    print("#" * 75 + "\n")


if __name__ == "__main__":
    main()
