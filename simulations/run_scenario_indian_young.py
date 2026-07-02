"""
Scenario Simulation: Young Indian Population (WT 54+/-10, Age 35+/-10)
=======================================================================
Simulates a younger, lower-weight Indian transplant cohort and compares
against the default Indian and Western populations.

Age effects on PK parameters:
- GFR: age-dependent decline (CKD-EPI approximation for post-transplant)
- Liver metabolic capacity: slight age-dependent scaling
- Albumin: younger patients may have slightly better nutritional status
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import warnings

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from model.mpa_pbpk import (
    simulate_steady_state, PKParameters, DrugParameters, PatientParameters
)
from model.mpa_pd import PDParameters, compute_pd_outcomes
from populations.virtual_populations import (
    generate_virtual_population, PopulationDistributions,
    WESTERN_POPULATION, INDIAN_POPULATION, _truncated_normal
)

warnings.filterwarnings('ignore')

OUTPUT_DIR = os.path.join(project_root, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

N_POP = 500
N_DOSES = 14
AUC_LO, AUC_HI = 30.0, 60.0


# ============================================================
# YOUNG INDIAN POPULATION (WT 54+/-10, Age 35+/-10)
# ============================================================

YOUNG_INDIAN_POPULATION = PopulationDistributions(
    name="Young Indian (54 kg, Age 35)",
    wt_mean=54.0,
    wt_sd=10.0,
    wt_min=35.0,
    wt_max=100.0,
    ht_mean=163.0,
    ht_sd=8.5,
    # Albumin: younger patients may have slightly better nutritional status
    # but still lower than Western due to CKD burden
    alb_mean=3.5,
    alb_sd=0.5,
    alb_min=2.0,
    alb_max=5.0,
    # GFR: younger post-transplant patients tend to have better graft function
    gfr_mean=58.0,
    gfr_sd=18.0,
    gfr_min=15.0,
    gfr_max=120.0,
    # Same CNI pattern
    prop_tacrolimus=0.88,
    ugt1a9_mean=0.95,
    ugt1a9_sd=0.18,
    ugt2b7_mean=0.92,
    ugt2b7_sd=0.20,
    abcc2_mean=0.97,
    abcc2_sd=0.18,
)


def generate_age_aware_population(pop_dist, age_mean, age_sd, n=500, seed=42):
    """Generate a virtual population with age-dependent physiological adjustments.

    Age modifies:
    - GFR: younger patients have ~1 mL/min/year higher GFR
    - UGT activity: slight age-dependent scaling (~0.5% increase per year younger)
    - Liver metabolic capacity incorporated via UGT scaling
    """
    rng = np.random.default_rng(seed)

    # Sample ages
    ages = _truncated_normal(age_mean, age_sd, 18.0, 70.0, n, rng)

    # Generate base population
    patients = generate_virtual_population(pop_dist, n, seed)

    # Apply age-dependent adjustments
    ref_age = 45.0  # reference age for default parameters
    for i, p in enumerate(patients):
        age = ages[i]
        age_diff = ref_age - age  # positive = younger than reference

        # GFR adjustment: ~0.8 mL/min per year of age
        gfr_adj = p.gfr + age_diff * 0.8
        p.gfr = max(15.0, min(120.0, gfr_adj))

        # UGT activity: younger patients have slightly higher metabolic capacity
        # ~0.3% per year
        ugt_factor = 1.0 + age_diff * 0.003
        p.ugt1a9_activity *= ugt_factor
        p.ugt2b7_activity *= ugt_factor

    return patients, ages


def round_to_available(dose_mg):
    return max(250, round(dose_mg / 250) * 250)


def run_population_sim(patients, dose_func, label):
    """Run PK/PD simulation for a population."""
    pk = PKParameters()
    drug = DrugParameters()
    pd_params = PDParameters()

    results = []
    for i, p in enumerate(patients):
        if (i + 1) % 250 == 0:
            print(f"    {label}: {i+1}/{len(patients)}")
        try:
            dose = dose_func(p)
            pk_res = simulate_steady_state(dose, p, pk, drug, N_DOSES)
            pd_res = compute_pd_outcomes(pk_res, pd_params)
            pd_res['patient'] = p
            pd_res['dose'] = dose
            pd_res['pk'] = pk_res
            results.append(pd_res)
        except Exception:
            pass
    print(f"    {label}: {len(results)}/{len(patients)} completed")
    return results


def extract(results, key):
    return np.array([r[key] for r in results])


def extract_patient(results, key):
    return np.array([getattr(r['patient'], key) for r in results])


def print_comparison(groups):
    """Print formatted comparison table."""
    print("\n" + "=" * 110)
    print("  SCENARIO COMPARISON: Young Indian (WT 54+/-10, Age 35+/-10)")
    print("=" * 110)

    hdr = f"  {'Metric':<35s}"
    for name in groups:
        hdr += f" {name:>18s}"
    print(hdr)
    print("  " + "-" * 106)

    def row(label, key, fmt):
        line = f"  {label:<35s}"
        for name, res in groups.items():
            vals = extract(res, key)
            line += f" {fmt(vals):>18s}"
        print(line)

    def ms(a): return f"{np.mean(a):.1f} +/- {np.std(a):.1f}"
    def ms2(a): return f"{np.mean(a):.2f} +/- {np.std(a):.2f}"
    def pct(a): return f"{np.mean(a)*100:.1f}%"

    row("Total AUC (mg.h/L)", 'auc_total', ms)
    row("Free AUC (mg.h/L)", 'auc_free', ms2)
    row("Avg IMPDH inhibition", 'avg_impdh_inhibition', lambda a: f"{np.mean(a):.3f} +/- {np.std(a):.3f}")

    print()
    # Target attainment
    for name, res in groups.items():
        aucs = extract(res, 'auc_total')
        targ = np.mean((aucs >= AUC_LO) & (aucs <= AUC_HI)) * 100
        over = np.mean(aucs > AUC_HI) * 100
        under = np.mean(aucs < AUC_LO) * 100
        # Print once per group
    line_t = f"  {'% Target (30-60)':35s}"
    line_o = f"  {'% Overexposed (>60)':35s}"
    line_u = f"  {'% Underexposed (<30)':35s}"
    for name, res in groups.items():
        aucs = extract(res, 'auc_total')
        line_t += f" {np.mean((aucs>=AUC_LO)&(aucs<=AUC_HI))*100:>17.1f}%"
        line_o += f" {np.mean(aucs>AUC_HI)*100:>17.1f}%"
        line_u += f" {np.mean(aucs<AUC_LO)*100:>17.1f}%"
    print(line_t)
    print(line_o)
    print(line_u)

    print()
    row("P(rejection)", 'p_rejection', pct)
    row("P(GI toxicity)", 'p_gi_toxicity', pct)
    row("P(leukopenia)", 'p_leukopenia', pct)
    row("P(any adverse)", 'p_any_adverse', pct)
    print()
    row("Therapeutic index", 'therapeutic_index', lambda a: f"{np.mean(a):.3f} +/- {np.std(a):.3f}")

    # Demographics
    print()
    line_wt = f"  {'Body weight (kg)':35s}"
    line_dose = f"  {'Effective dose (mg/kg)':35s}"
    for name, res in groups.items():
        wts = extract_patient(res, 'body_weight')
        doses = np.array([r['dose'] for r in res])
        line_wt += f" {np.mean(wts):>8.1f}+/-{np.std(wts):<7.1f}"
        line_dose += f" {np.mean(doses/wts):>8.1f}+/-{np.std(doses/wts):<7.1f}"
    print(line_wt)
    print(line_dose)
    print("=" * 110)


def plot_scenario(groups, ages_young):
    """Generate comprehensive scenario comparison plots."""
    fig = plt.figure(figsize=(18, 14))
    gs = GridSpec(3, 3, figure=fig, hspace=0.38, wspace=0.30)

    colors = {
        'Western 1g': '#2563EB',
        'Indian (std) 1g': '#DC2626',
        'Young Indian 1g': '#7C3AED',
        'Young Indian 12mg/kg': '#059669',
    }

    # --- Panel A: AUC distributions ---
    ax = fig.add_subplot(gs[0, 0])
    bins = np.linspace(0, 140, 40)
    for name, res in groups.items():
        aucs = extract(res, 'auc_total')
        ax.hist(aucs, bins=bins, alpha=0.4, color=colors[name],
                label=name, density=True, edgecolor='white')
    ax.axvspan(AUC_LO, AUC_HI, alpha=0.08, color='green')
    ax.axvline(AUC_LO, color='green', ls='--', lw=1)
    ax.axvline(AUC_HI, color='green', ls='--', lw=1)
    ax.set_xlabel('Total MPA AUC$_{0-12}$ (mg$\\cdot$h/L)')
    ax.set_ylabel('Density')
    ax.set_title('A. Total MPA AUC Distribution', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7)

    # --- Panel B: Free AUC ---
    ax = fig.add_subplot(gs[0, 1])
    bins_f = np.linspace(0, 7, 40)
    for name, res in groups.items():
        faucs = extract(res, 'auc_free')
        ax.hist(faucs, bins=bins_f, alpha=0.4, color=colors[name],
                label=name, density=True, edgecolor='white')
    ax.set_xlabel('Free MPA AUC$_{0-12}$ (mg$\\cdot$h/L)')
    ax.set_ylabel('Density')
    ax.set_title('B. Free MPA AUC Distribution', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7)

    # --- Panel C: Target attainment stacked bars ---
    ax = fig.add_subplot(gs[0, 2])
    grp_names = list(groups.keys())
    x = np.arange(len(grp_names))
    under, targ, over = [], [], []
    for name, res in groups.items():
        aucs = extract(res, 'auc_total')
        under.append(np.mean(aucs < AUC_LO) * 100)
        targ.append(np.mean((aucs >= AUC_LO) & (aucs <= AUC_HI)) * 100)
        over.append(np.mean(aucs > AUC_HI) * 100)

    ax.bar(x, under, 0.6, label='Under (<30)', color='#FCD34D')
    ax.bar(x, targ, 0.6, bottom=under, label='Target (30-60)', color='#34D399')
    ax.bar(x, over, 0.6, bottom=[u+t for u, t in zip(under, targ)],
           label='Over (>60)', color='#F87171')
    for i, tv in enumerate(targ):
        ax.text(i, under[i] + tv/2, f'{tv:.0f}%', ha='center', va='center',
                fontsize=10, fontweight='bold', color='white')
    ax.set_ylabel('% of Population')
    ax.set_title('C. Target Attainment', fontweight='bold', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels([n.replace(' ', '\n') for n in grp_names], fontsize=8)
    ax.legend(fontsize=7)

    # --- Panel D: AUC vs body weight ---
    ax = fig.add_subplot(gs[1, 0])
    for name, res in groups.items():
        wts = extract_patient(res, 'body_weight')
        aucs = extract(res, 'auc_total')
        ax.scatter(wts, aucs, alpha=0.2, s=8, color=colors[name], label=name)
    ax.axhspan(AUC_LO, AUC_HI, alpha=0.06, color='green')
    ax.axhline(AUC_LO, color='green', ls='--', lw=0.8, alpha=0.5)
    ax.axhline(AUC_HI, color='green', ls='--', lw=0.8, alpha=0.5)
    ax.set_xlabel('Body Weight (kg)')
    ax.set_ylabel('Total MPA AUC (mg$\\cdot$h/L)')
    ax.set_title('D. AUC vs Body Weight', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7, markerscale=3)

    # --- Panel E: Age distribution of young Indian cohort ---
    ax = fig.add_subplot(gs[1, 1])
    ax.hist(ages_young, bins=25, color='#7C3AED', alpha=0.7, edgecolor='white')
    ax.set_xlabel('Age (years)')
    ax.set_ylabel('Count')
    ax.set_title(f'E. Age Distribution\n(Mean {np.mean(ages_young):.1f} +/- {np.std(ages_young):.1f} y)',
                 fontweight='bold', fontsize=11)
    ax.axvline(np.mean(ages_young), color='#7C3AED', ls='--', lw=2)

    # --- Panel F: Dose per kg distribution ---
    ax = fig.add_subplot(gs[1, 2])
    for name, res in groups.items():
        wts = extract_patient(res, 'body_weight')
        doses = np.array([r['dose'] for r in res])
        dose_per_kg = doses / wts
        ax.hist(dose_per_kg, bins=30, alpha=0.4, color=colors[name],
                label=name, density=True, edgecolor='white')
    ax.set_xlabel('Effective Dose (mg/kg)')
    ax.set_ylabel('Density')
    ax.set_title('F. Dose per kg Distribution', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7)

    # --- Panel G: IMPDH inhibition ---
    ax = fig.add_subplot(gs[2, 0])
    for name, res in groups.items():
        ax.hist(extract(res, 'avg_impdh_inhibition'), bins=30, alpha=0.4,
                color=colors[name], label=name, density=True, edgecolor='white')
    ax.axvspan(0.30, 0.70, alpha=0.06, color='green')
    ax.set_xlabel('Average IMPDH Inhibition')
    ax.set_ylabel('Density')
    ax.set_title('G. IMPDH Inhibition', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7)

    # --- Panel H: Therapeutic index ---
    ax = fig.add_subplot(gs[2, 1])
    for name, res in groups.items():
        ax.hist(extract(res, 'therapeutic_index'), bins=25, alpha=0.4,
                color=colors[name], label=name, density=True, edgecolor='white')
    ax.set_xlabel('Therapeutic Index')
    ax.set_ylabel('Density')
    ax.set_title('H. Therapeutic Index', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7)

    # --- Panel I: Summary metrics bar chart ---
    ax = fig.add_subplot(gs[2, 2])
    metrics = ['P(reject)\n(%)', 'P(GI tox)\n(%)', 'P(leuko)\n(%)', 'TI\n(x100)']
    keys = ['p_rejection', 'p_gi_toxicity', 'p_leukopenia', 'therapeutic_index']
    x = np.arange(len(metrics))
    width = 0.18
    for idx, (name, res) in enumerate(groups.items()):
        vals = []
        for key in keys:
            v = np.mean(extract(res, key))
            vals.append(v * 100)
        offset = (idx - 1.5) * width
        ax.bar(x + offset, vals, width, color=colors[name], alpha=0.85,
               label=name, edgecolor='white')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9)
    ax.set_ylabel('Value')
    ax.set_title('I. Clinical Outcomes', fontweight='bold', fontsize=11)
    ax.legend(fontsize=6, ncol=2)

    fig.suptitle('Scenario Analysis: Young Indian Population (WT 54$\\pm$10 kg, Age 35$\\pm$10 y)\n'
                 f'n = {N_POP} per population, MMF BID at steady state',
                 fontsize=14, fontweight='bold', y=1.01)
    plt.savefig(os.path.join(OUTPUT_DIR, 'scenario_young_indian.png'),
                dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"\n  Figure saved: {os.path.join(OUTPUT_DIR, 'scenario_young_indian.png')}")


def main():
    print("=" * 70)
    print("  SCENARIO: Young Indian Population")
    print("  Weight: 54 +/- 10 kg | Age: 35 +/- 10 years")
    print("=" * 70)

    # Generate populations
    print("\n[1/5] Generating populations...")
    west_pts = generate_virtual_population(WESTERN_POPULATION, N_POP, seed=42)
    ind_std_pts = generate_virtual_population(INDIAN_POPULATION, N_POP, seed=123)
    young_ind_pts, ages = generate_age_aware_population(
        YOUNG_INDIAN_POPULATION, age_mean=35.0, age_sd=10.0, n=N_POP, seed=456
    )

    # Print demographics
    print(f"\n  Young Indian demographics:")
    print(f"    Weight: {np.mean([p.body_weight for p in young_ind_pts]):.1f} "
          f"+/- {np.std([p.body_weight for p in young_ind_pts]):.1f} kg")
    print(f"    Age: {np.mean(ages):.1f} +/- {np.std(ages):.1f} years")
    print(f"    Albumin: {np.mean([p.albumin for p in young_ind_pts]):.2f} "
          f"+/- {np.std([p.albumin for p in young_ind_pts]):.2f} g/dL")
    print(f"    GFR: {np.mean([p.gfr for p in young_ind_pts]):.1f} "
          f"+/- {np.std([p.gfr for p in young_ind_pts]):.1f} mL/min")
    print(f"    Tacrolimus: {sum(1 for p in young_ind_pts if p.cni_type=='tacrolimus')/N_POP*100:.0f}%")

    # Simulations
    print("\n[2/5] Simulating Western 1g BID...")
    west_1g = run_population_sim(west_pts, lambda p: 1000, "Western 1g")

    print("[3/5] Simulating standard Indian 1g BID...")
    ind_std_1g = run_population_sim(ind_std_pts, lambda p: 1000, "Indian std 1g")

    print("[4/5] Simulating Young Indian 1g BID...")
    young_1g = run_population_sim(young_ind_pts, lambda p: 1000, "Young Indian 1g")

    print("[5/5] Simulating Young Indian 12mg/kg BID...")
    young_wb = run_population_sim(
        young_ind_pts,
        lambda p: round_to_available(12 * p.body_weight),
        "Young Indian 12mg/kg"
    )

    groups = {
        'Western 1g': west_1g,
        'Indian (std) 1g': ind_std_1g,
        'Young Indian 1g': young_1g,
        'Young Indian 12mg/kg': young_wb,
    }

    # Print results
    print_comparison(groups)

    # Generate plots
    print("\nGenerating plots...")
    plot_scenario(groups, ages)

    print("\nScenario simulation complete.")


if __name__ == "__main__":
    main()
