"""
Dose Optimization for Indian Population
=========================================
Simulates multiple dosing strategies and compares therapeutic target attainment:

1. Fixed-dose strategies:
   - Standard Western: 1000 mg BID
   - Reduced fixed: 750 mg BID, 500 mg BID

2. Weight-based strategies:
   - Various mg/kg BID regimens

3. Identifies optimal strategy to maximize % within target (30-60 mg.h/L)
   while minimizing overexposure

4. Compares total vs free MPA target attainment

Target: MPA AUC_0-12h = 30-60 mg.h/L (total)
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import warnings

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from model.mpa_pbpk import (
    simulate_steady_state, PKParameters, DrugParameters, PatientParameters
)
from populations.virtual_populations import (
    generate_virtual_population, print_population_summary,
    WESTERN_POPULATION, INDIAN_POPULATION
)

warnings.filterwarnings('ignore', category=RuntimeWarning)

N_PATIENTS = 500
N_DOSES_SS = 14
OUTPUT_DIR = os.path.join(project_root, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

AUC_LOWER = 30.0
AUC_UPPER = 60.0


def simulate_dose_strategy(patients, dose_func, label=""):
    """Simulate a dosing strategy across a population.

    Parameters
    ----------
    patients : list of PatientParameters
    dose_func : callable
        Takes a PatientParameters, returns dose in mg.
    label : str

    Returns
    -------
    dict with AUC arrays and metrics.
    """
    pk = PKParameters()
    drug = DrugParameters()

    aucs = []
    aucs_free = []
    doses_used = []
    weights = []
    cmax_vals = []
    trough_vals = []

    for i, patient in enumerate(patients):
        if (i + 1) % 200 == 0:
            print(f"    [{label}] {i+1}/{len(patients)}...")
        try:
            dose = dose_func(patient)
            res = simulate_steady_state(dose, patient, pk, drug, N_DOSES_SS)
            aucs.append(res['auc_ss_0_12'])
            aucs_free.append(res['auc_free_ss_0_12'])
            doses_used.append(dose)
            weights.append(patient.body_weight)
            cmax_vals.append(res['cmax_ss'])
            trough_vals.append(res['c_trough_ss'])
        except Exception:
            pass

    aucs = np.array(aucs)
    aucs_free = np.array(aucs_free)
    doses_used = np.array(doses_used)
    weights = np.array(weights)
    cmax_vals = np.array(cmax_vals)
    trough_vals = np.array(trough_vals)

    n = len(aucs)
    pct_under = np.mean(aucs < AUC_LOWER) * 100 if n > 0 else 0
    pct_target = np.mean((aucs >= AUC_LOWER) & (aucs <= AUC_UPPER)) * 100 if n > 0 else 0
    pct_over = np.mean(aucs > AUC_UPPER) * 100 if n > 0 else 0

    return {
        'label': label,
        'auc': aucs,
        'auc_free': aucs_free,
        'doses': doses_used,
        'weights': weights,
        'cmax': cmax_vals,
        'trough': trough_vals,
        'n': n,
        'auc_mean': np.mean(aucs) if n > 0 else 0,
        'auc_sd': np.std(aucs) if n > 0 else 0,
        'auc_free_mean': np.mean(aucs_free) if n > 0 else 0,
        'auc_free_sd': np.std(aucs_free) if n > 0 else 0,
        'dose_mean': np.mean(doses_used) if n > 0 else 0,
        'dose_per_kg_mean': np.mean(doses_used / weights) if n > 0 else 0,
        'pct_under': pct_under,
        'pct_target': pct_target,
        'pct_over': pct_over,
    }


def round_to_available(dose_mg):
    """Round dose to nearest available tablet strength.

    MMF tablets: 250 mg, 500 mg
    Myfortic (EC-MPS): 180 mg, 360 mg
    For simplicity, round to nearest 250 mg.
    """
    return max(250, round(dose_mg / 250) * 250)


def main():
    print("\n" + "#" * 75)
    print("#  MPA Dose Optimization for Indian Population")
    print("#  Target AUC_0-12h: 30-60 mg.h/L")
    print("#" * 75)

    # Generate populations
    print("\n[1/5] Generating virtual populations...")
    indian_patients = generate_virtual_population(INDIAN_POPULATION, N_PATIENTS, seed=123)
    western_patients = generate_virtual_population(WESTERN_POPULATION, N_PATIENTS, seed=42)
    print_population_summary(indian_patients, INDIAN_POPULATION.name)

    # ================================================================
    # STRATEGY DEFINITIONS
    # ================================================================
    strategies = {}

    # --- Western reference ---
    print("\n[2/5] Simulating Western reference (1000 mg BID)...")
    strategies['Western 1000mg'] = simulate_dose_strategy(
        western_patients, lambda p: 1000, "Western 1000mg")

    # --- Indian fixed-dose strategies ---
    print("\n[3/5] Simulating Indian fixed-dose strategies...")
    for dose in [1000, 750, 500]:
        label = f"Indian {dose}mg"
        print(f"  Strategy: {label} BID")
        strategies[label] = simulate_dose_strategy(
            indian_patients, lambda p, d=dose: d, label)

    # --- Indian weight-based strategies ---
    print("\n[4/5] Simulating Indian weight-based strategies...")
    for mg_per_kg in [10, 12, 14, 16]:
        label = f"Indian {mg_per_kg}mg/kg"
        print(f"  Strategy: {label} BID")
        strategies[label] = simulate_dose_strategy(
            indian_patients,
            lambda p, mpk=mg_per_kg: round_to_available(mpk * p.body_weight),
            label
        )

    # --- Indian weight-based with tablet rounding + cap ---
    label_opt = "Indian 12mg/kg (rounded)"
    print(f"  Strategy: {label_opt} BID")
    strategies[label_opt] = simulate_dose_strategy(
        indian_patients,
        lambda p: round_to_available(12 * p.body_weight),
        label_opt
    )

    # ================================================================
    # RESULTS TABLE
    # ================================================================
    print("\n" + "=" * 100)
    print("  DOSE OPTIMIZATION RESULTS")
    print("=" * 100)
    header = f"  {'Strategy':<28s} {'Dose (mg)':<12s} {'mg/kg':<8s} {'AUC mean':>10s} {'% Under':>8s} {'% Target':>9s} {'% Over':>8s} {'fAUC mean':>10s}"
    print(header)
    print("  " + "-" * 95)

    # Sort by % in target (descending)
    sorted_strategies = sorted(strategies.items(), key=lambda x: -x[1]['pct_target'])

    best_strategy = None
    best_pct = 0

    for name, s in sorted_strategies:
        line = (f"  {name:<28s} {s['dose_mean']:>8.0f}    {s['dose_per_kg_mean']:>5.1f}  "
                f"{s['auc_mean']:>7.1f}+/-{s['auc_sd']:<5.1f}"
                f"{s['pct_under']:>7.1f}% {s['pct_target']:>8.1f}% {s['pct_over']:>7.1f}%"
                f"  {s['auc_free_mean']:>6.2f}+/-{s['auc_free_sd']:<4.2f}")
        # Mark the best Indian strategy
        if 'Indian' in name and s['pct_target'] > best_pct:
            best_pct = s['pct_target']
            best_strategy = name
            line += "  <-- BEST"
        print(line)

    print("=" * 100)
    if best_strategy:
        print(f"\n  >> Recommended strategy for Indian population: {best_strategy}")
        bs = strategies[best_strategy]
        print(f"     Mean dose: {bs['dose_mean']:.0f} mg BID ({bs['dose_per_kg_mean']:.1f} mg/kg)")
        print(f"     Target attainment: {bs['pct_target']:.1f}% within 30-60 mg.h/L")
        print(f"     Overexposure reduced from {strategies['Indian 1000mg']['pct_over']:.1f}% "
              f"to {bs['pct_over']:.1f}%")

    # ================================================================
    # FIGURES
    # ================================================================
    print("\n[5/5] Generating figures...")

    # --- Figure 1: Target attainment comparison ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Panel A: Fixed-dose comparison (bar chart)
    ax = axes[0]
    fixed_names = ['Western 1000mg', 'Indian 1000mg', 'Indian 750mg', 'Indian 500mg']
    fixed_labels = ['Western\n1000mg', 'Indian\n1000mg', 'Indian\n750mg', 'Indian\n500mg']
    x = np.arange(len(fixed_names))
    width = 0.25

    under = [strategies[n]['pct_under'] for n in fixed_names]
    target = [strategies[n]['pct_target'] for n in fixed_names]
    over = [strategies[n]['pct_over'] for n in fixed_names]

    bars1 = ax.bar(x - width, under, width, label='Under (<30)', color='#FFC107', alpha=0.8)
    bars2 = ax.bar(x, target, width, label='Target (30-60)', color='#4CAF50', alpha=0.8)
    bars3 = ax.bar(x + width, over, width, label='Over (>60)', color='#F44336', alpha=0.8)

    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            h = bar.get_height()
            if h > 2:
                ax.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.0f}%',
                        ha='center', va='bottom', fontsize=7)

    ax.set_ylabel('% of Population')
    ax.set_title('A. Fixed-Dose Strategies: Target Attainment')
    ax.set_xticks(x)
    ax.set_xticklabels(fixed_labels, fontsize=9)
    ax.legend(fontsize=8)
    ax.set_ylim(0, 85)

    # Panel B: Weight-based comparison
    ax = axes[1]
    wt_names = ['Indian 10mg/kg', 'Indian 12mg/kg', 'Indian 14mg/kg', 'Indian 16mg/kg']
    wt_labels = ['10\nmg/kg', '12\nmg/kg', '14\nmg/kg', '16\nmg/kg']
    x = np.arange(len(wt_names))

    under_w = [strategies[n]['pct_under'] for n in wt_names]
    target_w = [strategies[n]['pct_target'] for n in wt_names]
    over_w = [strategies[n]['pct_over'] for n in wt_names]

    bars1 = ax.bar(x - width, under_w, width, label='Under (<30)', color='#FFC107', alpha=0.8)
    bars2 = ax.bar(x, target_w, width, label='Target (30-60)', color='#4CAF50', alpha=0.8)
    bars3 = ax.bar(x + width, over_w, width, label='Over (>60)', color='#F44336', alpha=0.8)

    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            h = bar.get_height()
            if h > 2:
                ax.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.0f}%',
                        ha='center', va='bottom', fontsize=7)

    ax.set_ylabel('% of Population')
    ax.set_title('B. Weight-Based Strategies: Target Attainment')
    ax.set_xticks(x)
    ax.set_xticklabels(wt_labels, fontsize=9)
    ax.legend(fontsize=8)
    ax.set_ylim(0, 85)

    # Panel C: AUC distributions for key strategies
    ax = axes[2]
    key_strategies = ['Indian 1000mg', 'Indian 750mg', 'Indian 12mg/kg']
    colors = ['#F44336', '#FF9800', '#4CAF50']
    for name, color in zip(key_strategies, colors):
        s = strategies[name]
        ax.hist(s['auc'], bins=np.linspace(0, 120, 35), alpha=0.4, color=color,
                label=f"{name} (target={s['pct_target']:.0f}%)", density=True,
                edgecolor='white')
    ax.axvline(AUC_LOWER, color='green', linestyle='--', linewidth=1.5)
    ax.axvline(AUC_UPPER, color='green', linestyle='--', linewidth=1.5)
    ax.axvspan(AUC_LOWER, AUC_UPPER, alpha=0.08, color='green')
    ax.set_xlabel('MPA AUC$_{0-12h}$ (mg$\\cdot$h/L)')
    ax.set_ylabel('Density')
    ax.set_title('C. AUC Distribution: Key Strategies')
    ax.legend(fontsize=8)

    fig.suptitle('MPA Dose Optimization for Indian Population\n'
                 f'n={N_PATIENTS} virtual patients | Target AUC: 30-60 mg$\\cdot$h/L',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'dose_optimization_target_attainment.png'),
                dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()

    # --- Figure 2: AUC vs body weight for different strategies ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    plot_strategies = [
        ('Indian 1000mg', '#F44336', 'Standard 1000mg BID'),
        ('Indian 750mg', '#FF9800', 'Reduced 750mg BID'),
        ('Indian 12mg/kg', '#4CAF50', 'Weight-based 12mg/kg BID'),
    ]

    for ax, (sname, color, title) in zip(axes, plot_strategies):
        s = strategies[sname]
        ax.scatter(s['weights'], s['auc'], alpha=0.3, s=12, color=color)
        ax.axhline(AUC_LOWER, color='green', linestyle='--', alpha=0.5)
        ax.axhline(AUC_UPPER, color='green', linestyle='--', alpha=0.5)
        ax.axhspan(AUC_LOWER, AUC_UPPER, alpha=0.06, color='green')
        ax.set_xlabel('Body Weight (kg)')
        ax.set_ylabel('MPA AUC$_{0-12h}$ (mg$\\cdot$h/L)')
        ax.set_title(f'{title}\nTarget: {s["pct_target"]:.0f}% | Over: {s["pct_over"]:.0f}%')
        ax.set_ylim(0, 150)
        ax.set_xlim(30, 100)

        # Add regression line
        z = np.polyfit(s['weights'], s['auc'], 1)
        p = np.poly1d(z)
        wt_range = np.linspace(35, 95, 100)
        ax.plot(wt_range, p(wt_range), '--', color='black', alpha=0.5, linewidth=1)

    fig.suptitle('AUC vs. Body Weight Under Different Dosing Strategies (Indian Population)',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'dose_optimization_auc_vs_weight.png'),
                dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()

    # --- Figure 3: Optimal dose nomogram ---
    fig, ax = plt.subplots(figsize=(10, 6))

    # For each weight bin, find the dose that centers AUC at 45 mg.h/L
    weight_bins = np.arange(40, 95, 5)
    pk = PKParameters()
    drug = DrugParameters()

    optimal_doses = []
    for wt_center in weight_bins:
        # Binary search for optimal dose
        target_auc = 45.0  # middle of therapeutic window
        ref_patient = PatientParameters(
            body_weight=wt_center, albumin=3.5, gfr=50.0, cni_type='tacrolimus')

        best_dose = 1000
        best_diff = float('inf')
        for test_dose in range(250, 1500, 50):
            try:
                res = simulate_steady_state(test_dose, ref_patient, pk, drug, n_doses=10)
                diff = abs(res['auc_ss_0_12'] - target_auc)
                if diff < best_diff:
                    best_diff = diff
                    best_dose = test_dose
            except Exception:
                pass
        optimal_doses.append(round_to_available(best_dose))

    # Plot nomogram
    ax.plot(weight_bins, optimal_doses, 'o-', color='#4CAF50', linewidth=2,
            markersize=8, label='Optimal dose (target AUC=45)')
    ax.axhline(1000, color='#F44336', linestyle='--', linewidth=1.5,
               label='Standard Western dose (1000mg)', alpha=0.7)
    ax.axhline(750, color='#FF9800', linestyle='--', linewidth=1.5,
               label='Common Indian practice (750mg)', alpha=0.7)

    # Add tablet-strength gridlines
    for tablet_dose in [250, 500, 750, 1000, 1250]:
        ax.axhline(tablet_dose, color='gray', linestyle=':', alpha=0.2)

    ax.set_xlabel('Body Weight (kg)', fontsize=12)
    ax.set_ylabel('Recommended MMF Dose BID (mg)', fontsize=12)
    ax.set_title('Weight-Based Dose Nomogram for Indian Patients\n'
                 '(Tacrolimus co-therapy, Albumin ~3.5 g/dL, Target AUC=45 mg$\\cdot$h/L)',
                 fontsize=12, fontweight='bold')
    ax.legend(fontsize=10)
    ax.set_ylim(200, 1300)
    ax.set_xlim(38, 95)
    ax.grid(True, alpha=0.15)

    # Add dose annotations
    for wt, dose in zip(weight_bins, optimal_doses):
        ax.annotate(f'{dose:.0f}', (wt, dose), textcoords="offset points",
                    xytext=(0, 12), ha='center', fontsize=8, fontweight='bold',
                    color='#2E7D32')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'dose_nomogram_indian.png'),
                dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"\n  Figures saved to {OUTPUT_DIR}/")
    print("    - dose_optimization_target_attainment.png")
    print("    - dose_optimization_auc_vs_weight.png")
    print("    - dose_nomogram_indian.png")

    # Print nomogram table
    print("\n" + "=" * 55)
    print("  DOSE NOMOGRAM: Indian Patients on Tacrolimus")
    print("  (Albumin ~3.5 g/dL, Target AUC = 45 mg.h/L)")
    print("=" * 55)
    print(f"  {'Weight (kg)':<15s} {'Recommended Dose (mg BID)':<25s}")
    print("  " + "-" * 40)
    for wt, dose in zip(weight_bins, optimal_doses):
        pct_of_standard = (dose / 1000) * 100
        print(f"  {wt:<15.0f} {dose:<10.0f} ({pct_of_standard:.0f}% of standard)")
    print("=" * 55)

    print("\n" + "#" * 75)
    print("#  Dose optimization complete.")
    print("#" * 75 + "\n")


if __name__ == "__main__":
    main()
