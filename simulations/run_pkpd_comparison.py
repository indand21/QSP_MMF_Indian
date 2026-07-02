"""
PK/PD Population Comparison: Efficacy-Toxicity Tradeoff
=========================================================
Compares Western vs. Indian populations on:
1. IMPDH inhibition profiles
2. Lymphocyte suppression
3. Rejection vs. toxicity probability landscapes
4. Therapeutic index distribution
5. Effect of dose optimization on clinical outcomes

Ties together the full QSP story: Dose -> PK -> PD -> Clinical Outcome
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
from model.mpa_pd import (
    PDParameters, compute_pd_outcomes, impdh_inhibition,
    impdh_inhibition_profile, gi_toxicity_probability,
    rejection_probability, leukopenia_probability
)
from populations.virtual_populations import (
    generate_virtual_population, print_population_summary,
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
    """Run PK + PD simulation for a population."""
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


def extract_pd_metrics(results):
    """Extract arrays of PD metrics from population results."""
    return {
        'auc_total': np.array([r['auc_total'] for r in results]),
        'auc_free': np.array([r['auc_free'] for r in results]),
        'avg_impdh': np.array([r['avg_impdh_inhibition'] for r in results]),
        'lymphocyte': np.array([r['lymphocyte_ss'] for r in results]),
        'p_rejection': np.array([r['p_rejection'] for r in results]),
        'p_gi_tox': np.array([r['p_gi_toxicity'] for r in results]),
        'p_leukopenia': np.array([r['p_leukopenia'] for r in results]),
        'p_infection': np.array([r['p_infection'] for r in results]),
        'p_any_adverse': np.array([r['p_any_adverse'] for r in results]),
        'therapeutic_index': np.array([r['therapeutic_index'] for r in results]),
        'zone': [r['clinical_zone'] for r in results],
        'weight': np.array([r['patient'].body_weight for r in results]),
        'dose': np.array([r['dose'] for r in results]),
    }


def print_pkpd_table(groups: dict):
    """Print comprehensive PK/PD comparison table."""
    print("\n" + "=" * 95)
    print("  PK/PD POPULATION COMPARISON")
    print("=" * 95)

    header_names = list(groups.keys())
    header = f"  {'Metric':<35s}" + "".join(f"{n:>19s}" for n in header_names)
    print(header)
    print("  " + "-" * 90)

    def ms(arr):
        return f"{np.mean(arr):.2f} +/- {np.std(arr):.2f}"

    def pct(arr):
        return f"{np.mean(arr)*100:.1f}%"

    metrics = [
        ("AUC_total (mg.h/L)", 'auc_total', ms),
        ("AUC_free (mg.h/L)", 'auc_free', ms),
        ("Avg IMPDH inhibition", 'avg_impdh', ms),
        ("Lymphocyte count (x10^9/L)", 'lymphocyte', ms),
        ("", None, None),
        ("P(rejection)", 'p_rejection', pct),
        ("P(GI toxicity)", 'p_gi_tox', pct),
        ("P(leukopenia)", 'p_leukopenia', pct),
        ("P(infection)", 'p_infection', pct),
        ("P(any adverse event)", 'p_any_adverse', pct),
        ("", None, None),
        ("Therapeutic Index", 'therapeutic_index', ms),
        ("% Therapeutic zone", 'zone', lambda z: f"{sum(1 for x in z if x=='THERAPEUTIC')/len(z)*100:.1f}%"),
        ("% Overexposed zone", 'zone', lambda z: f"{sum(1 for x in z if x=='OVEREXPOSED')/len(z)*100:.1f}%"),
        ("% Underexposed zone", 'zone', lambda z: f"{sum(1 for x in z if x=='UNDEREXPOSED')/len(z)*100:.1f}%"),
    ]

    for label, key, fmt in metrics:
        if key is None:
            print()
            continue
        line = f"  {label:<35s}"
        for name in header_names:
            m = groups[name]
            line += f"{fmt(m[key]):>19s}"
        print(line)

    print("=" * 95)


def main():
    print("\n" + "#" * 75)
    print("#  MPA PK/PD Population Simulation")
    print("#  Efficacy-Toxicity Tradeoff: Western vs. Indian")
    print("#" * 75)

    # Generate populations
    print("\n[1/4] Generating populations...")
    western_pts = generate_virtual_population(WESTERN_POPULATION, N_PATIENTS, seed=42)
    indian_pts = generate_virtual_population(INDIAN_POPULATION, N_PATIENTS, seed=123)

    # Simulate scenarios
    scenarios = {}

    print("\n[2/4] Running PK/PD simulations...")

    print("  Western 1000mg BID...")
    scenarios['Western\n1000mg'] = simulate_pkpd_population(
        western_pts, lambda p: 1000, "West 1000mg")

    print("  Indian 1000mg BID (standard)...")
    scenarios['Indian\n1000mg'] = simulate_pkpd_population(
        indian_pts, lambda p: 1000, "Ind 1000mg")

    print("  Indian 750mg BID (reduced fixed)...")
    scenarios['Indian\n750mg'] = simulate_pkpd_population(
        indian_pts, lambda p: 750, "Ind 750mg")

    print("  Indian 12mg/kg BID (weight-based)...")
    scenarios['Indian\n12mg/kg'] = simulate_pkpd_population(
        indian_pts, lambda p: round_to_available(12 * p.body_weight), "Ind 12mg/kg")

    # Extract metrics
    print("\n[3/4] Analyzing results...")
    metrics = {name: extract_pd_metrics(res) for name, res in scenarios.items()}
    print_pkpd_table(metrics)

    # ================================================================
    # FIGURES
    # ================================================================
    print("\n[4/4] Generating figures...")

    colors = {
        'Western\n1000mg': '#2196F3',
        'Indian\n1000mg': '#F44336',
        'Indian\n750mg': '#FF9800',
        'Indian\n12mg/kg': '#4CAF50',
    }

    # --- Figure 1: Comprehensive PK/PD Dashboard ---
    fig = plt.figure(figsize=(20, 16))
    gs = GridSpec(3, 4, figure=fig, hspace=0.35, wspace=0.30)

    # 1A: IMPDH inhibition vs Free AUC (mechanism curve)
    ax = fig.add_subplot(gs[0, 0])
    c_range = np.linspace(0, 1.0, 200)
    pd_params = PDParameters()
    inhib_curve = [impdh_inhibition(c, pd_params) for c in c_range]
    ax.plot(c_range, inhib_curve, 'k-', linewidth=2)
    ax.axhline(0.30, color='orange', linestyle='--', alpha=0.5, label='Min target (30%)')
    ax.axhline(0.70, color='red', linestyle='--', alpha=0.5, label='Max target (70%)')
    ax.axhspan(0.30, 0.70, alpha=0.06, color='green')
    ax.set_xlabel('Free MPA concentration (mg/L)')
    ax.set_ylabel('IMPDH-II Inhibition (fraction)')
    ax.set_title('A. IMPDH Inhibition\n(Concentration-Effect)')
    ax.legend(fontsize=7)

    # 1B: Average IMPDH inhibition distribution
    ax = fig.add_subplot(gs[0, 1])
    for name, m in metrics.items():
        ax.hist(m['avg_impdh'], bins=30, alpha=0.4, color=colors[name],
                label=name.replace('\n', ' '), density=True, edgecolor='white')
    ax.axvline(0.30, color='orange', linestyle='--')
    ax.axvline(0.70, color='red', linestyle='--')
    ax.axvspan(0.30, 0.70, alpha=0.06, color='green')
    ax.set_xlabel('Average IMPDH Inhibition')
    ax.set_ylabel('Density')
    ax.set_title('B. IMPDH Inhibition\nDistribution')
    ax.legend(fontsize=7)

    # 1C: Lymphocyte count distribution
    ax = fig.add_subplot(gs[0, 2])
    for name, m in metrics.items():
        ax.hist(m['lymphocyte'], bins=30, alpha=0.4, color=colors[name],
                label=name.replace('\n', ' '), density=True, edgecolor='white')
    ax.axvline(0.5, color='red', linestyle='--', label='Lymphopenia threshold')
    ax.set_xlabel('Lymphocyte Count (x10$^9$/L)')
    ax.set_ylabel('Density')
    ax.set_title('C. Predicted Lymphocyte\nCount')
    ax.legend(fontsize=7)

    # 1D: Clinical zone stacked bars
    ax = fig.add_subplot(gs[0, 3])
    zone_data = {}
    for name, m in metrics.items():
        zones = m['zone']
        n_total = len(zones)
        zone_data[name] = {
            'Under': sum(1 for z in zones if z == 'UNDEREXPOSED') / n_total * 100,
            'Therapeutic': sum(1 for z in zones if z == 'THERAPEUTIC') / n_total * 100,
            'Over': sum(1 for z in zones if z == 'OVEREXPOSED') / n_total * 100,
        }

    x = np.arange(len(metrics))
    short_names = [n.replace('\n', ' ') for n in metrics.keys()]
    width = 0.6

    under_vals = [zone_data[n]['Under'] for n in metrics.keys()]
    ther_vals = [zone_data[n]['Therapeutic'] for n in metrics.keys()]
    over_vals = [zone_data[n]['Over'] for n in metrics.keys()]

    ax.bar(x, under_vals, width, label='Underexposed', color='#FFC107', alpha=0.8)
    ax.bar(x, ther_vals, width, bottom=under_vals, label='Therapeutic', color='#4CAF50', alpha=0.8)
    ax.bar(x, over_vals, width,
           bottom=[u + t for u, t in zip(under_vals, ther_vals)],
           label='Overexposed', color='#F44336', alpha=0.8)
    ax.set_ylabel('% of Population')
    ax.set_title('D. Clinical Exposure\nZones (IMPDH-based)')
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=7, rotation=15)
    ax.legend(fontsize=7, loc='upper right')

    # 2A: Rejection probability
    ax = fig.add_subplot(gs[1, 0])
    for name, m in metrics.items():
        ax.hist(m['p_rejection'] * 100, bins=25, alpha=0.4, color=colors[name],
                label=name.replace('\n', ' '), density=True, edgecolor='white')
    ax.set_xlabel('Rejection Probability (%)')
    ax.set_ylabel('Density')
    ax.set_title('E. Rejection Risk\nDistribution')
    ax.legend(fontsize=7)

    # 2B: GI toxicity probability
    ax = fig.add_subplot(gs[1, 1])
    for name, m in metrics.items():
        ax.hist(m['p_gi_tox'] * 100, bins=25, alpha=0.4, color=colors[name],
                label=name.replace('\n', ' '), density=True, edgecolor='white')
    ax.set_xlabel('GI Toxicity Probability (%)')
    ax.set_ylabel('Density')
    ax.set_title('F. GI Toxicity Risk\nDistribution')
    ax.legend(fontsize=7)

    # 2C: Leukopenia probability
    ax = fig.add_subplot(gs[1, 2])
    for name, m in metrics.items():
        ax.hist(m['p_leukopenia'] * 100, bins=25, alpha=0.4, color=colors[name],
                label=name.replace('\n', ' '), density=True, edgecolor='white')
    ax.set_xlabel('Leukopenia Probability (%)')
    ax.set_ylabel('Density')
    ax.set_title('G. Leukopenia Risk\nDistribution')
    ax.legend(fontsize=7)

    # 2D: Therapeutic index distribution
    ax = fig.add_subplot(gs[1, 3])
    for name, m in metrics.items():
        ax.hist(m['therapeutic_index'], bins=25, alpha=0.4, color=colors[name],
                label=name.replace('\n', ' '), density=True, edgecolor='white')
    ax.set_xlabel('Therapeutic Index (efficacy x safety)')
    ax.set_ylabel('Density')
    ax.set_title('H. Therapeutic Index\nDistribution')
    ax.legend(fontsize=7)

    # 3A: Rejection vs GI Toxicity tradeoff scatter
    ax = fig.add_subplot(gs[2, 0:2])
    for name, m in metrics.items():
        ax.scatter(m['p_rejection'] * 100, m['p_gi_tox'] * 100,
                   alpha=0.2, s=10, color=colors[name],
                   label=name.replace('\n', ' '))
    ax.set_xlabel('Rejection Probability (%)', fontsize=11)
    ax.set_ylabel('GI Toxicity Probability (%)', fontsize=11)
    ax.set_title('I. Efficacy-Toxicity Tradeoff\n(Each dot = one virtual patient)', fontsize=11)
    ax.legend(fontsize=8, markerscale=3)
    # Draw ideal zone (low rejection, low toxicity)
    ax.axhspan(0, 25, xmin=0, xmax=0.4, alpha=0.04, color='green')
    ax.text(5, 20, 'Ideal\nzone', fontsize=9, color='green', alpha=0.5, style='italic')

    # 3B: Summary comparison bar chart
    ax = fig.add_subplot(gs[2, 2:4])
    group_names = [n.replace('\n', ' ') for n in metrics.keys()]
    x = np.arange(len(group_names))
    width = 0.18

    mean_rejection = [np.mean(metrics[n]['p_rejection'])*100 for n in metrics.keys()]
    mean_gi = [np.mean(metrics[n]['p_gi_tox'])*100 for n in metrics.keys()]
    mean_leuko = [np.mean(metrics[n]['p_leukopenia'])*100 for n in metrics.keys()]
    mean_infection = [np.mean(metrics[n]['p_infection'])*100 for n in metrics.keys()]
    mean_ti = [np.mean(metrics[n]['therapeutic_index'])*100 for n in metrics.keys()]

    ax.bar(x - 2*width, mean_rejection, width, label='Rejection', color='#9C27B0', alpha=0.8)
    ax.bar(x - width, mean_gi, width, label='GI Toxicity', color='#F44336', alpha=0.8)
    ax.bar(x, mean_leuko, width, label='Leukopenia', color='#FF9800', alpha=0.8)
    ax.bar(x + width, mean_infection, width, label='Infection', color='#795548', alpha=0.8)
    ax.bar(x + 2*width, mean_ti, width, label='Ther. Index (x100)', color='#4CAF50', alpha=0.8)

    ax.set_ylabel('Probability (%) / Index (x100)')
    ax.set_title('J. Clinical Outcome Summary\n(Mean Probabilities)', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(group_names, fontsize=9)
    ax.legend(fontsize=7, ncol=3)

    fig.suptitle('MPA QSP Model: PK/PD Population Analysis\n'
                 'Western vs. Indian | Dose Optimization Impact on Clinical Outcomes',
                 fontsize=14, fontweight='bold', y=1.01)

    plt.savefig(os.path.join(OUTPUT_DIR, 'pkpd_dashboard.png'),
                dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Dashboard saved: {os.path.join(OUTPUT_DIR, 'pkpd_dashboard.png')}")

    # --- Figure 2: Representative PK/PD profiles ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Pick median patients
    pk_params = PKParameters()
    drug_params = DrugParameters()
    pd_params = PDParameters()

    representative_cases = [
        ("Western 70kg, 1000mg", PatientParameters(body_weight=70, albumin=4.0, gfr=55, cni_type='tacrolimus'), 1000),
        ("Indian 58kg, 1000mg", PatientParameters(body_weight=58, albumin=3.5, gfr=50, cni_type='tacrolimus'), 1000),
        ("Indian 58kg, 750mg", PatientParameters(body_weight=58, albumin=3.5, gfr=50, cni_type='tacrolimus'), 750),
        ("Indian 58kg, 12mg/kg", PatientParameters(body_weight=58, albumin=3.5, gfr=50, cni_type='tacrolimus'),
         round_to_available(12 * 58)),
    ]

    rep_colors = ['#2196F3', '#F44336', '#FF9800', '#4CAF50']

    # Plot PK profiles
    ax_pk = axes[0, 0]
    ax_free = axes[0, 1]
    ax_impdh = axes[1, 0]
    ax_summary = axes[1, 1]

    summary_data = []

    for (label, patient, dose), color in zip(representative_cases, rep_colors):
        pk_res = simulate_steady_state(dose, patient, pk_params, drug_params, N_DOSES_SS)
        pd_res = compute_pd_outcomes(pk_res, pd_params)

        t = pk_res['t_ss']
        ax_pk.plot(t, pk_res['mpa_ss'], color=color, linewidth=2,
                   label=f"{label}\nAUC={pk_res['auc_ss_0_12']:.1f}")
        ax_free.plot(t, pk_res['mpa_free_ss'], color=color, linewidth=2,
                     label=f"{label}\nfAUC={pk_res['auc_free_ss_0_12']:.2f}")
        ax_impdh.plot(t, pd_res['impdh_profile'], color=color, linewidth=2,
                      label=f"{label}\nAvg={pd_res['avg_impdh_inhibition']:.2f}")

        summary_data.append({
            'label': label, 'color': color,
            'auc': pk_res['auc_ss_0_12'],
            'p_rej': pd_res['p_rejection'] * 100,
            'p_gi': pd_res['p_gi_toxicity'] * 100,
            'ti': pd_res['therapeutic_index'],
        })

    ax_pk.set_xlabel('Time (h)')
    ax_pk.set_ylabel('Total MPA (mg/L)')
    ax_pk.set_title('Total MPA Concentration')
    ax_pk.legend(fontsize=7)
    ax_pk.set_xlim(0, 12)

    ax_free.set_xlabel('Time (h)')
    ax_free.set_ylabel('Free MPA (mg/L)')
    ax_free.set_title('Free MPA Concentration')
    ax_free.legend(fontsize=7)
    ax_free.set_xlim(0, 12)

    ax_impdh.set_xlabel('Time (h)')
    ax_impdh.set_ylabel('IMPDH Inhibition (fraction)')
    ax_impdh.set_title('IMPDH-II Inhibition Profile')
    ax_impdh.axhspan(0.30, 0.70, alpha=0.06, color='green')
    ax_impdh.axhline(0.30, color='orange', linestyle='--', alpha=0.3)
    ax_impdh.axhline(0.70, color='red', linestyle='--', alpha=0.3)
    ax_impdh.legend(fontsize=7)
    ax_impdh.set_xlim(0, 12)
    ax_impdh.set_ylim(0, 1)

    # Summary bar chart
    x = np.arange(len(summary_data))
    width = 0.25
    ax_summary.bar(x - width, [d['p_rej'] for d in summary_data], width,
                   color=[d['color'] for d in summary_data], alpha=0.6, label='Rejection %')
    ax_summary.bar(x, [d['p_gi'] for d in summary_data], width,
                   color=[d['color'] for d in summary_data], alpha=0.8, label='GI Tox %')
    ax_summary.bar(x + width, [d['ti'] * 100 for d in summary_data], width,
                   color=[d['color'] for d in summary_data], alpha=1.0, label='Ther. Index x100')
    ax_summary.set_xticks(x)
    ax_summary.set_xticklabels([d['label'].split(',')[0] for d in summary_data],
                                fontsize=8, rotation=10)
    ax_summary.set_ylabel('Value')
    ax_summary.set_title('Clinical Outcome Comparison')
    ax_summary.legend(fontsize=7)

    fig.suptitle('Representative Patient PK/PD Profiles', fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'pkpd_representative_profiles.png'),
                dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Profiles saved: {os.path.join(OUTPUT_DIR, 'pkpd_representative_profiles.png')}")

    print("\n" + "#" * 75)
    print("#  PK/PD simulation complete.")
    print("#" * 75 + "\n")


if __name__ == "__main__":
    main()
