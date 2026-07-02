"""
Sensitivity Analysis: Equal Albumin & CNI Type
================================================
Runs PK/PD simulation with albumin and tacrolimus proportion
equalized between Western and Indian populations to isolate
the contribution of body weight and UGT differences.

Scenarios:
1. Western 1000mg (original)
2. Indian 1000mg (original)
3. Indian 1000mg (equalized albumin=4.0, prop_tac=0.70)
4. Indian 12mg/kg (equalized albumin=4.0, prop_tac=0.70)
"""

import sys
import os
import copy
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import warnings

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from model.mpa_pbpk import (
    simulate_steady_state, PKParameters, DrugParameters, PatientParameters
)
from model.mpa_pd import (
    PDParameters, compute_pd_outcomes
)
from populations.virtual_populations import (
    generate_virtual_population, PopulationDistributions,
    WESTERN_POPULATION, INDIAN_POPULATION
)

warnings.filterwarnings('ignore')

N_PATIENTS = 500
N_DOSES_SS = 14
OUTPUT_DIR = os.path.join(project_root, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def round_to_available(dose_mg):
    return max(250, round(dose_mg / 250) * 250)


def simulate_pkpd_population(patients, dose_func, label=""):
    pk = PKParameters()
    drug = DrugParameters()
    pd_params = PDParameters()

    results = []
    for i, patient in enumerate(patients):
        if (i + 1) % 200 == 0:
            print(f"    [{label}] {i+1}/{len(patients)}...")
        try:
            dose = dose_func(patient)
            pk_res = simulate_steady_state(dose, patient, pk, drug, N_DOSES_SS)
            pd_res = compute_pd_outcomes(pk_res, pd_params)
            pd_res['patient'] = patient
            pd_res['dose'] = dose
            results.append(pd_res)
        except Exception:
            pass
    return results


def extract_metrics(results):
    return {
        'auc_total': np.array([r['auc_total'] for r in results]),
        'auc_free': np.array([r['auc_free'] for r in results]),
        'avg_impdh': np.array([r['avg_impdh_inhibition'] for r in results]),
        'p_rejection': np.array([r['p_rejection'] for r in results]),
        'p_gi_tox': np.array([r['p_gi_toxicity'] for r in results]),
        'p_leukopenia': np.array([r['p_leukopenia'] for r in results]),
        'p_any_adverse': np.array([r['p_any_adverse'] for r in results]),
        'therapeutic_index': np.array([r['therapeutic_index'] for r in results]),
        'zone': [r['clinical_zone'] for r in results],
        'weight': np.array([r['patient'].body_weight for r in results]),
        'albumin': np.array([r['patient'].albumin for r in results]),
    }


def print_comparison_table(groups: dict):
    print("\n" + "=" * 110)
    print("  SENSITIVITY ANALYSIS: Equal Albumin & CNI Type")
    print("=" * 110)

    header_names = list(groups.keys())
    header = f"  {'Metric':<35s}" + "".join(f"{n:>18s}" for n in header_names)
    print(header)
    print("  " + "-" * 105)

    def ms(arr): return f"{np.mean(arr):.2f} +/- {np.std(arr):.2f}"
    def pct(arr): return f"{np.mean(arr)*100:.1f}%"

    rows = [
        ("Body weight (kg)", 'weight', ms),
        ("Albumin (g/dL)", 'albumin', ms),
        ("", None, None),
        ("Total AUC (mg.h/L)", 'auc_total', ms),
        ("Free AUC (mg.h/L)", 'auc_free', ms),
        ("Avg IMPDH inhibition", 'avg_impdh', ms),
        ("", None, None),
        ("% Target (30-60 mg.h/L)", 'auc_total',
         lambda a: f"{np.mean((a >= 30) & (a <= 60))*100:.1f}%"),
        ("% Overexposed (>60 mg.h/L)", 'auc_total',
         lambda a: f"{np.mean(a > 60)*100:.1f}%"),
        ("", None, None),
        ("P(rejection)", 'p_rejection', pct),
        ("P(GI toxicity)", 'p_gi_tox', pct),
        ("P(leukopenia)", 'p_leukopenia', pct),
        ("P(any adverse)", 'p_any_adverse', pct),
        ("", None, None),
        ("Therapeutic index", 'therapeutic_index', ms),
        ("% Therapeutic zone", 'zone',
         lambda z: f"{sum(1 for x in z if x=='THERAPEUTIC')/len(z)*100:.1f}%"),
        ("% Overexposed zone", 'zone',
         lambda z: f"{sum(1 for x in z if x=='OVEREXPOSED')/len(z)*100:.1f}%"),
        ("% Underexposed zone", 'zone',
         lambda z: f"{sum(1 for x in z if x=='UNDEREXPOSED')/len(z)*100:.1f}%"),
    ]

    for label, key, fmt in rows:
        if key is None:
            print()
            continue
        line = f"  {label:<35s}"
        for name in header_names:
            line += f"{fmt(groups[name][key]):>18s}"
        print(line)

    print("=" * 110)


def main():
    print("\n" + "#" * 75)
    print("#  Sensitivity Analysis: Equal Albumin & CNI Type")
    print("#  Isolating body weight + UGT contribution")
    print("#" * 75)

    # --- Create equalized Indian population ---
    # Same as INDIAN but with Western albumin (4.0 +/- 0.4) and prop_tac=0.70
    indian_equalized = PopulationDistributions(
        name="Indian (equalized Alb+CNI)",
        wt_mean=INDIAN_POPULATION.wt_mean,
        wt_sd=INDIAN_POPULATION.wt_sd,
        wt_min=INDIAN_POPULATION.wt_min,
        wt_max=INDIAN_POPULATION.wt_max,
        ht_mean=INDIAN_POPULATION.ht_mean,
        ht_sd=INDIAN_POPULATION.ht_sd,
        # Equalized to Western values:
        alb_mean=WESTERN_POPULATION.alb_mean,     # 4.0
        alb_sd=WESTERN_POPULATION.alb_sd,          # 0.4
        alb_min=WESTERN_POPULATION.alb_min,        # 2.5
        alb_max=WESTERN_POPULATION.alb_max,        # 5.5
        gfr_mean=INDIAN_POPULATION.gfr_mean,
        gfr_sd=INDIAN_POPULATION.gfr_sd,
        gfr_min=INDIAN_POPULATION.gfr_min,
        gfr_max=INDIAN_POPULATION.gfr_max,
        # Equalized to Western values:
        prop_tacrolimus=WESTERN_POPULATION.prop_tacrolimus,  # 0.70
        # Keep Indian UGT activity
        ugt1a9_mean=INDIAN_POPULATION.ugt1a9_mean,
        ugt1a9_sd=INDIAN_POPULATION.ugt1a9_sd,
        ugt2b7_mean=INDIAN_POPULATION.ugt2b7_mean,
        ugt2b7_sd=INDIAN_POPULATION.ugt2b7_sd,
        abcc2_mean=INDIAN_POPULATION.abcc2_mean,
        abcc2_sd=INDIAN_POPULATION.abcc2_sd,
    )

    # Generate populations
    print("\n[1/3] Generating populations...")
    western_pts = generate_virtual_population(WESTERN_POPULATION, N_PATIENTS, seed=42)
    indian_pts = generate_virtual_population(INDIAN_POPULATION, N_PATIENTS, seed=123)
    indian_eq_pts = generate_virtual_population(indian_equalized, N_PATIENTS, seed=123)

    print(f"  Western:            WT={np.mean([p.body_weight for p in western_pts]):.1f} kg, "
          f"Alb={np.mean([p.albumin for p in western_pts]):.2f} g/dL, "
          f"Tac={sum(1 for p in western_pts if p.cni_type=='tacrolimus')/len(western_pts)*100:.0f}%")
    print(f"  Indian (original):  WT={np.mean([p.body_weight for p in indian_pts]):.1f} kg, "
          f"Alb={np.mean([p.albumin for p in indian_pts]):.2f} g/dL, "
          f"Tac={sum(1 for p in indian_pts if p.cni_type=='tacrolimus')/len(indian_pts)*100:.0f}%")
    print(f"  Indian (equalized): WT={np.mean([p.body_weight for p in indian_eq_pts]):.1f} kg, "
          f"Alb={np.mean([p.albumin for p in indian_eq_pts]):.2f} g/dL, "
          f"Tac={sum(1 for p in indian_eq_pts if p.cni_type=='tacrolimus')/len(indian_eq_pts)*100:.0f}%")

    # Run simulations
    print("\n[2/3] Running PK/PD simulations...")
    scenarios = {}

    print("  Western 1000mg BID...")
    scenarios['West 1000mg'] = simulate_pkpd_population(
        western_pts, lambda p: 1000, "West 1000mg")

    print("  Indian 1000mg BID (original)...")
    scenarios['Ind 1000mg'] = simulate_pkpd_population(
        indian_pts, lambda p: 1000, "Ind 1000mg")

    print("  Indian 1000mg BID (equalized Alb+CNI)...")
    scenarios['Ind 1000mg\n(eq Alb+CNI)'] = simulate_pkpd_population(
        indian_eq_pts, lambda p: 1000, "Ind 1000mg eq")

    print("  Indian 12mg/kg BID (equalized Alb+CNI)...")
    scenarios['Ind 12mg/kg\n(eq Alb+CNI)'] = simulate_pkpd_population(
        indian_eq_pts, lambda p: round_to_available(12 * p.body_weight), "Ind 12mg/kg eq")

    # Extract and print
    print("\n[3/3] Analyzing results...")
    metrics = {name: extract_metrics(res) for name, res in scenarios.items()}
    print_comparison_table(metrics)

    # --- Compute contribution of albumin+CNI vs weight+UGT ---
    west_auc = np.mean(metrics['West 1000mg']['auc_total'])
    ind_orig_auc = np.mean(metrics['Ind 1000mg']['auc_total'])
    ind_eq_auc = np.mean(metrics['Ind 1000mg\n(eq Alb+CNI)']['auc_total'])

    total_diff = ind_orig_auc - west_auc
    alb_cni_contribution = ind_orig_auc - ind_eq_auc
    wt_ugt_contribution = ind_eq_auc - west_auc

    print("\n  Factor Decomposition (Total AUC difference):")
    print(f"  Total difference (Indian - Western):  {total_diff:+.1f} mg.h/L")
    print(f"  Due to albumin + CNI type:            {alb_cni_contribution:+.1f} mg.h/L "
          f"({alb_cni_contribution/total_diff*100:.0f}%)" if total_diff != 0 else "")
    print(f"  Due to body weight + UGT activity:    {wt_ugt_contribution:+.1f} mg.h/L "
          f"({wt_ugt_contribution/total_diff*100:.0f}%)" if total_diff != 0 else "")

    # Same for free AUC
    west_fauc = np.mean(metrics['West 1000mg']['auc_free'])
    ind_orig_fauc = np.mean(metrics['Ind 1000mg']['auc_free'])
    ind_eq_fauc = np.mean(metrics['Ind 1000mg\n(eq Alb+CNI)']['auc_free'])

    total_diff_f = ind_orig_fauc - west_fauc
    alb_cni_f = ind_orig_fauc - ind_eq_fauc
    wt_ugt_f = ind_eq_fauc - west_fauc

    print(f"\n  Factor Decomposition (Free AUC difference):")
    print(f"  Total difference (Indian - Western):  {total_diff_f:+.3f} mg.h/L")
    print(f"  Due to albumin + CNI type:            {alb_cni_f:+.3f} mg.h/L "
          f"({alb_cni_f/total_diff_f*100:.0f}%)" if total_diff_f != 0 else "")
    print(f"  Due to body weight + UGT activity:    {wt_ugt_f:+.3f} mg.h/L "
          f"({wt_ugt_f/total_diff_f*100:.0f}%)" if total_diff_f != 0 else "")

    # --- Figure ---
    fig, axes = plt.subplots(2, 3, figsize=(18, 11))

    colors = {
        'West 1000mg': '#2196F3',
        'Ind 1000mg': '#F44336',
        'Ind 1000mg\n(eq Alb+CNI)': '#FF9800',
        'Ind 12mg/kg\n(eq Alb+CNI)': '#4CAF50',
    }

    short = {k: k.replace('\n', ' ') for k in metrics}

    # A: Total AUC
    ax = axes[0, 0]
    for name, m in metrics.items():
        ax.hist(m['auc_total'], bins=30, alpha=0.35, color=colors[name],
                label=f"{short[name]}\n({np.mean(m['auc_total']):.1f})",
                density=True, edgecolor='white')
    ax.axvline(30, color='orange', ls='--', alpha=0.5)
    ax.axvline(60, color='red', ls='--', alpha=0.5)
    ax.axvspan(30, 60, alpha=0.05, color='green')
    ax.set_xlabel('Total AUC (mg.h/L)')
    ax.set_ylabel('Density')
    ax.set_title('A. Total MPA AUC Distribution')
    ax.legend(fontsize=7)

    # B: Free AUC
    ax = axes[0, 1]
    for name, m in metrics.items():
        ax.hist(m['auc_free'], bins=30, alpha=0.35, color=colors[name],
                label=f"{short[name]}\n({np.mean(m['auc_free']):.2f})",
                density=True, edgecolor='white')
    ax.set_xlabel('Free AUC (mg.h/L)')
    ax.set_ylabel('Density')
    ax.set_title('B. Free MPA AUC Distribution')
    ax.legend(fontsize=7)

    # C: IMPDH inhibition
    ax = axes[0, 2]
    for name, m in metrics.items():
        ax.hist(m['avg_impdh'], bins=30, alpha=0.35, color=colors[name],
                label=f"{short[name]}\n({np.mean(m['avg_impdh']):.3f})",
                density=True, edgecolor='white')
    ax.axvline(0.30, color='orange', ls='--')
    ax.axvline(0.70, color='red', ls='--')
    ax.axvspan(0.30, 0.70, alpha=0.05, color='green')
    ax.set_xlabel('Average IMPDH Inhibition')
    ax.set_ylabel('Density')
    ax.set_title('C. IMPDH Inhibition Distribution')
    ax.legend(fontsize=7)

    # D: Factor decomposition waterfall
    ax = axes[1, 0]
    labels = ['Western\nbaseline', 'Weight +\nUGT effect', 'Albumin +\nCNI effect', 'Indian\ntotal']
    vals = [west_auc, wt_ugt_contribution, alb_cni_contribution, ind_orig_auc]
    bar_colors = ['#2196F3', '#FF9800', '#9C27B0', '#F44336']

    # Waterfall chart
    cumulative = [west_auc, west_auc + wt_ugt_contribution,
                  west_auc + wt_ugt_contribution + alb_cni_contribution, ind_orig_auc]
    bottoms = [0, west_auc, west_auc + wt_ugt_contribution, 0]
    heights = [west_auc, wt_ugt_contribution, alb_cni_contribution, ind_orig_auc]

    bars = ax.bar(labels, heights, bottom=bottoms, color=bar_colors, alpha=0.8, edgecolor='gray')
    for bar, h, b in zip(bars, heights, bottoms):
        ax.text(bar.get_x() + bar.get_width()/2, b + h + 0.5,
                f"{h:+.1f}" if b > 0 else f"{h:.1f}",
                ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_ylabel('Total AUC (mg.h/L)')
    ax.set_title('D. AUC Factor Decomposition\n(Waterfall)')
    ax.set_ylim(0, max(ind_orig_auc, west_auc) * 1.15)

    # E: Adverse event comparison
    ax = axes[1, 1]
    group_names = [short[n] for n in metrics]
    x = np.arange(len(group_names))
    width = 0.2

    mean_rej = [np.mean(metrics[n]['p_rejection'])*100 for n in metrics]
    mean_gi = [np.mean(metrics[n]['p_gi_tox'])*100 for n in metrics]
    mean_leu = [np.mean(metrics[n]['p_leukopenia'])*100 for n in metrics]
    mean_any = [np.mean(metrics[n]['p_any_adverse'])*100 for n in metrics]

    ax.bar(x - 1.5*width, mean_rej, width, label='Rejection', color='#9C27B0', alpha=0.8)
    ax.bar(x - 0.5*width, mean_gi, width, label='GI Toxicity', color='#F44336', alpha=0.8)
    ax.bar(x + 0.5*width, mean_leu, width, label='Leukopenia', color='#FF9800', alpha=0.8)
    ax.bar(x + 1.5*width, mean_any, width, label='Any Adverse', color='#795548', alpha=0.8)

    ax.set_ylabel('Probability (%)')
    ax.set_title('E. Clinical Outcome Probabilities')
    ax.set_xticks(x)
    ax.set_xticklabels(group_names, fontsize=7, rotation=10)
    ax.legend(fontsize=7)

    # F: Therapeutic index
    ax = axes[1, 2]
    ti_means = [np.mean(metrics[n]['therapeutic_index']) for n in metrics]
    ti_sds = [np.std(metrics[n]['therapeutic_index']) for n in metrics]
    bar_cols = [colors[n] for n in metrics]
    bars = ax.bar(x, ti_means, yerr=ti_sds, color=bar_cols, alpha=0.8,
                  capsize=5, edgecolor='gray')
    for bar, val in zip(bars, ti_means):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                f"{val:.3f}", ha='center', va='bottom', fontsize=9, fontweight='bold')
    ax.set_ylabel('Therapeutic Index')
    ax.set_title('F. Therapeutic Index Comparison')
    ax.set_xticks(x)
    ax.set_xticklabels(group_names, fontsize=7, rotation=10)

    fig.suptitle('Sensitivity Analysis: Equalizing Albumin & CNI Type\n'
                 'Isolating body weight + UGT contribution to Indian overexposure',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'sensitivity_albumin_cni.png'),
                dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"\n  Figure saved: {os.path.join(OUTPUT_DIR, 'sensitivity_albumin_cni.png')}")

    print("\n" + "#" * 75)
    print("#  Sensitivity analysis complete.")
    print("#" * 75 + "\n")


if __name__ == "__main__":
    main()
