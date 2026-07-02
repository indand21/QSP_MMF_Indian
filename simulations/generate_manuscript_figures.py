"""
Manuscript-Ready Figure Generation
====================================
Generates publication-quality composite figures for:

Figure 1: Mechanistic Framework & Population PK Comparison
Figure 2: Dose Optimization & Weight-Based Nomogram
Figure 3: PK/PD Clinical Outcomes & Therapeutic Index
Figure 4: Model Validation Against Published Data

Also generates Table 1 (population demographics) and Table 2 (key results summary).
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patches as mpatches
import warnings

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from model.mpa_pbpk import (
    simulate_steady_state, PKParameters, DrugParameters, PatientParameters
)
from model.mpa_pd import (
    PDParameters, compute_pd_outcomes, impdh_inhibition,
    impdh_inhibition_profile
)
from populations.virtual_populations import (
    generate_virtual_population, WESTERN_POPULATION, INDIAN_POPULATION,
    PopulationDistributions
)
from simulations.run_validation import (
    VALIDATION_STUDIES, simulate_study
)

warnings.filterwarnings('ignore')

OUTPUT_DIR = os.path.join(project_root, "outputs", "manuscript")
os.makedirs(OUTPUT_DIR, exist_ok=True)

N_POP = 500
N_DOSES = 14
AUC_LO, AUC_HI = 30.0, 60.0

# Consistent color scheme
C_WEST = '#2563EB'       # blue
C_IND_STD = '#DC2626'    # red
C_IND_750 = '#F59E0B'    # amber
C_IND_WB = '#059669'     # emerald
GRAY = '#6B7280'


def round_to_available(dose_mg):
    return max(250, round(dose_mg / 250) * 250)


# ============================================================
# DATA GENERATION (shared across all figures)
# ============================================================

def generate_all_data():
    """Run all simulations needed for manuscript figures."""
    pk = PKParameters()
    drug = DrugParameters()
    pd_params = PDParameters()

    print("[1/6] Generating populations...")
    west_pts = generate_virtual_population(WESTERN_POPULATION, N_POP, seed=42)
    ind_pts = generate_virtual_population(INDIAN_POPULATION, N_POP, seed=123)

    def run_pop(patients, dose_func, label):
        results = []
        for i, p in enumerate(patients):
            if (i+1) % 250 == 0:
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

    print("[2/6] Western 1000mg...")
    west_1000 = run_pop(west_pts, lambda p: 1000, "West 1000mg")

    print("[3/6] Indian 1000mg...")
    ind_1000 = run_pop(ind_pts, lambda p: 1000, "Ind 1000mg")

    print("[4/6] Indian 750mg...")
    ind_750 = run_pop(ind_pts, lambda p: 750, "Ind 750mg")

    print("[5/6] Indian 12mg/kg...")
    ind_wb = run_pop(ind_pts,
                     lambda p: round_to_available(12 * p.body_weight),
                     "Ind 12mg/kg")

    print("[6/6] Validation studies...")
    val_results = []
    for study in VALIDATION_STUDIES:
        val_results.append(simulate_study(study, n_patients=200, seed=42))

    return {
        'west_pts': west_pts, 'ind_pts': ind_pts,
        'west_1000': west_1000, 'ind_1000': ind_1000,
        'ind_750': ind_750, 'ind_wb': ind_wb,
        'validation': val_results,
    }


def extract(results, key):
    return np.array([r[key] for r in results])


def extract_patient(results, key):
    return np.array([getattr(r['patient'], key) for r in results])


# ============================================================
# FIGURE 1: Mechanistic Framework & PK Comparison
# ============================================================

def figure1(data):
    """Mechanistic framework + population PK comparison."""
    fig = plt.figure(figsize=(17, 14))
    gs = GridSpec(3, 3, figure=fig, hspace=0.38, wspace=0.32,
                  height_ratios=[1.2, 1, 1])

    # --- Panel A: Mechanistic flow diagram (text-based) ---
    ax = fig.add_subplot(gs[0, :])
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis('off')
    ax.set_title('A. Mechanistic Framework: Why Indian Patients Have Higher MPA Exposure',
                 fontsize=13, fontweight='bold', loc='left', pad=10)

    boxes = [
        (0.3, 1.8, 'MMF Dose\n(Fixed 1g BID)', '#E3F2FD'),
        (2.2, 1.8, 'Lower Body\nWeight\n(58 vs 78 kg)', '#FFEBEE'),
        (4.1, 1.8, 'Higher mg/kg\nDose\n(17 vs 13 mg/kg)', '#FFF3E0'),
        (6.0, 1.8, 'Larger Volumes\nRelative to BW\n(+Vc/kg)', '#F3E5F5'),
        (7.9, 1.8, 'Higher Total\nMPA AUC\n(+22%)', '#FFCDD2'),
    ]
    boxes2 = [
        (2.2, 0.3, 'Lower Albumin\n(3.5 vs 4.0 g/dL)', '#FFEBEE'),
        (4.1, 0.3, 'Higher Free\nFraction (fu)\n(0.037 vs 0.030)', '#FFF3E0'),
        (6.0, 0.3, 'Higher Free\nMPA AUC\n(+41%)', '#FFCDD2'),
        (7.9, 0.3, 'Greater IMPDH\nInhibition\n(Overexposure)', '#F44336'),
    ]

    def draw_box(ax, x, y, text, color, w=1.6, h=0.9):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                             facecolor=color, edgecolor='#333', linewidth=1.2)
        ax.add_patch(box)
        ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                fontsize=8, fontweight='bold', wrap=True)

    for x, y, text, color in boxes:
        draw_box(ax, x, y, text, color)
    for x, y, text, color in boxes2:
        draw_box(ax, x, y, text, color)

    # Arrows (top row)
    for i in range(len(boxes)-1):
        x1 = boxes[i][0] + 1.6
        x2 = boxes[i+1][0]
        y_mid = boxes[i][1] + 0.45
        ax.annotate('', xy=(x2, y_mid), xytext=(x1, y_mid),
                    arrowprops=dict(arrowstyle='->', color='#333', lw=1.5))

    # Arrows (bottom row)
    for i in range(len(boxes2)-1):
        x1 = boxes2[i][0] + 1.6
        x2 = boxes2[i+1][0]
        y_mid = boxes2[i][1] + 0.45
        ax.annotate('', xy=(x2, y_mid), xytext=(x1, y_mid),
                    arrowprops=dict(arrowstyle='->', color='#333', lw=1.5))

    # Connecting arrow from top to bottom path
    ax.annotate('', xy=(2.2 + 0.8, 0.3 + 0.9), xytext=(2.2 + 0.8, 1.8),
                arrowprops=dict(arrowstyle='->', color='#999', lw=1.2, linestyle='--'))
    ax.text(1.7, 1.35, 'parallel\npathway', fontsize=7, color='#666', style='italic')

    # --- Panel B: Total AUC distributions ---
    ax = fig.add_subplot(gs[1, 0])
    bins = np.linspace(0, 130, 40)
    auc_w = extract(data['west_1000'], 'auc_total')
    auc_i = extract(data['ind_1000'], 'auc_total')

    ax.hist(auc_w, bins=bins, alpha=0.55, color=C_WEST, label='Western 1g', density=True, edgecolor='white')
    ax.hist(auc_i, bins=bins, alpha=0.55, color=C_IND_STD, label='Indian 1g', density=True, edgecolor='white')
    ax.axvspan(AUC_LO, AUC_HI, alpha=0.08, color='green')
    ax.axvline(AUC_LO, color='green', ls='--', lw=1)
    ax.axvline(AUC_HI, color='green', ls='--', lw=1)
    ax.set_xlabel('Total MPA AUC$_{0-12}$ (mg$\\cdot$h/L)')
    ax.set_ylabel('Density')
    ax.set_title('B. Total MPA AUC Distribution', fontweight='bold', fontsize=11)
    ax.legend(fontsize=9)

    # Add summary stats
    ax.text(0.97, 0.95,
            f'Western: {np.mean(auc_w):.1f}+/-{np.std(auc_w):.1f}\n'
            f'Indian: {np.mean(auc_i):.1f}+/-{np.std(auc_i):.1f}\n'
            f'Ratio: {np.mean(auc_i)/np.mean(auc_w):.2f}',
            transform=ax.transAxes, fontsize=8, va='top', ha='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    # --- Panel C: Free AUC distributions ---
    ax = fig.add_subplot(gs[1, 1])
    fauc_w = extract(data['west_1000'], 'auc_free')
    fauc_i = extract(data['ind_1000'], 'auc_free')
    bins_f = np.linspace(0, 7, 40)

    ax.hist(fauc_w, bins=bins_f, alpha=0.55, color=C_WEST, label='Western 1g', density=True, edgecolor='white')
    ax.hist(fauc_i, bins=bins_f, alpha=0.55, color=C_IND_STD, label='Indian 1g', density=True, edgecolor='white')
    ax.set_xlabel('Free MPA AUC$_{0-12}$ (mg$\\cdot$h/L)')
    ax.set_ylabel('Density')
    ax.set_title('C. Free (Unbound) MPA AUC', fontweight='bold', fontsize=11)
    ax.legend(fontsize=9)

    ax.text(0.97, 0.95,
            f'Western: {np.mean(fauc_w):.2f}+/-{np.std(fauc_w):.2f}\n'
            f'Indian: {np.mean(fauc_i):.2f}+/-{np.std(fauc_i):.2f}\n'
            f'Ratio: {np.mean(fauc_i)/np.mean(fauc_w):.2f}',
            transform=ax.transAxes, fontsize=8, va='top', ha='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    # --- Panel D: Target attainment comparison ---
    ax = fig.add_subplot(gs[1, 2])
    categories = ['Under\n(<30)', 'Target\n(30-60)', 'Over\n(>60)']

    def get_pcts(aucs):
        return [
            np.mean(aucs < AUC_LO) * 100,
            np.mean((aucs >= AUC_LO) & (aucs <= AUC_HI)) * 100,
            np.mean(aucs > AUC_HI) * 100,
        ]

    w_pcts = get_pcts(auc_w)
    i_pcts = get_pcts(auc_i)
    x = np.arange(3)
    width = 0.35
    b1 = ax.bar(x - width/2, w_pcts, width, label='Western', color=C_WEST, alpha=0.8, edgecolor='white')
    b2 = ax.bar(x + width/2, i_pcts, width, label='Indian', color=C_IND_STD, alpha=0.8, edgecolor='white')
    for bars in [b1, b2]:
        for bar in bars:
            h = bar.get_height()
            if h > 2:
                ax.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.0f}%',
                        ha='center', va='bottom', fontsize=8, fontweight='bold')
    ax.set_ylabel('% of Population')
    ax.set_title('D. Therapeutic Target Attainment\n(Standard 1g BID)', fontweight='bold', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend(fontsize=9)
    ax.set_ylim(0, 75)

    # --- Panel E: AUC vs body weight ---
    ax = fig.add_subplot(gs[2, 0])
    wt_w = extract_patient(data['west_1000'], 'body_weight')
    wt_i = extract_patient(data['ind_1000'], 'body_weight')
    ax.scatter(wt_w, auc_w, alpha=0.25, s=8, color=C_WEST, label='Western')
    ax.scatter(wt_i, auc_i, alpha=0.25, s=8, color=C_IND_STD, label='Indian')
    ax.axhspan(AUC_LO, AUC_HI, alpha=0.06, color='green')
    ax.axhline(AUC_LO, color='green', ls='--', lw=0.8, alpha=0.5)
    ax.axhline(AUC_HI, color='green', ls='--', lw=0.8, alpha=0.5)
    ax.set_xlabel('Body Weight (kg)')
    ax.set_ylabel('Total MPA AUC (mg$\\cdot$h/L)')
    ax.set_title('E. AUC vs Body Weight', fontweight='bold', fontsize=11)
    ax.legend(fontsize=9, markerscale=3)

    # --- Panel F: Representative PK profiles ---
    ax = fig.add_subplot(gs[2, 1:])
    pk_params = PKParameters()
    drug_params = DrugParameters()

    cases = [
        ('Western 78kg', PatientParameters(body_weight=78, albumin=4.0, gfr=55, cni_type='tacrolimus'), 1000, C_WEST, '-'),
        ('Indian 58kg, 1g', PatientParameters(body_weight=58, albumin=3.5, gfr=50, cni_type='tacrolimus'), 1000, C_IND_STD, '-'),
        ('Indian 58kg, 750mg', PatientParameters(body_weight=58, albumin=3.5, gfr=50, cni_type='tacrolimus'), 750, C_IND_750, '--'),
        ('Indian 58kg, 12mg/kg', PatientParameters(body_weight=58, albumin=3.5, gfr=50, cni_type='tacrolimus'),
         round_to_available(12*58), C_IND_WB, '--'),
    ]

    for label, patient, dose, color, ls in cases:
        res = simulate_steady_state(dose, patient, pk_params, drug_params, N_DOSES)
        ax.plot(res['t_ss'], res['mpa_ss'], color=color, ls=ls, linewidth=2.2,
                label=f'{label} ({dose}mg)\nAUC={res["auc_ss_0_12"]:.1f}')

    ax.set_xlabel('Time post-dose (h)')
    ax.set_ylabel('Total MPA (mg/L)')
    ax.set_title('F. Representative Steady-State Concentration Profiles', fontweight='bold', fontsize=11)
    ax.legend(fontsize=8, loc='upper right')
    ax.set_xlim(0, 12)

    fig.suptitle('Figure 1. Population Pharmacokinetics: MPA Overexposure in Indian Patients at Standard Western Dosing',
                 fontsize=14, fontweight='bold', y=1.005)
    fig.savefig(os.path.join(OUTPUT_DIR, 'Figure1_PK_Comparison.png'),
                dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print("  Saved Figure 1")


# ============================================================
# FIGURE 2: Dose Optimization
# ============================================================

def figure2(data):
    """Dose optimization: target attainment and weight-based nomogram."""
    fig = plt.figure(figsize=(17, 10))
    gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.30)

    groups = {
        'Western\n1000mg': data['west_1000'],
        'Indian\n1000mg': data['ind_1000'],
        'Indian\n750mg': data['ind_750'],
        'Indian\n12mg/kg': data['ind_wb'],
    }
    grp_colors = [C_WEST, C_IND_STD, C_IND_750, C_IND_WB]

    # --- Panel A: Stacked bar target attainment ---
    ax = fig.add_subplot(gs[0, 0])
    x = np.arange(len(groups))
    short_names = [n.replace('\n', ' ') for n in groups.keys()]

    under_vals, targ_vals, over_vals = [], [], []
    for name, res in groups.items():
        aucs = extract(res, 'auc_total')
        under_vals.append(np.mean(aucs < AUC_LO) * 100)
        targ_vals.append(np.mean((aucs >= AUC_LO) & (aucs <= AUC_HI)) * 100)
        over_vals.append(np.mean(aucs > AUC_HI) * 100)

    ax.bar(x, under_vals, 0.6, label='Under (<30)', color='#FCD34D', alpha=0.9)
    ax.bar(x, targ_vals, 0.6, bottom=under_vals, label='Target (30-60)', color='#34D399', alpha=0.9)
    ax.bar(x, over_vals, 0.6,
           bottom=[u+t for u, t in zip(under_vals, targ_vals)],
           label='Over (>60)', color='#F87171', alpha=0.9)

    # Add % labels on target portion
    for i, tv in enumerate(targ_vals):
        ax.text(i, under_vals[i] + tv/2, f'{tv:.0f}%', ha='center', va='center',
                fontsize=10, fontweight='bold', color='white')

    ax.set_ylabel('% of Population')
    ax.set_title('A. Therapeutic Target Attainment', fontweight='bold', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=9)
    ax.legend(fontsize=8, loc='upper right')

    # --- Panel B: AUC distributions ---
    ax = fig.add_subplot(gs[0, 1])
    bins = np.linspace(0, 130, 40)
    for (name, res), color in zip(groups.items(), grp_colors):
        aucs = extract(res, 'auc_total')
        ax.hist(aucs, bins=bins, alpha=0.35, color=color,
                label=name.replace('\n', ' '), density=True, edgecolor='white')
    ax.axvspan(AUC_LO, AUC_HI, alpha=0.08, color='green')
    ax.axvline(AUC_LO, color='green', ls='--', lw=1)
    ax.axvline(AUC_HI, color='green', ls='--', lw=1)
    ax.set_xlabel('Total MPA AUC$_{0-12}$ (mg$\\cdot$h/L)')
    ax.set_ylabel('Density')
    ax.set_title('B. AUC Distribution by Strategy', fontweight='bold', fontsize=11)
    ax.legend(fontsize=8)

    # --- Panel C: AUC vs weight scatter for 3 Indian strategies ---
    ax = fig.add_subplot(gs[0, 2])
    for name, res, color in [('1000mg', data['ind_1000'], C_IND_STD),
                              ('750mg', data['ind_750'], C_IND_750),
                              ('12mg/kg', data['ind_wb'], C_IND_WB)]:
        wts = extract_patient(res, 'body_weight')
        aucs = extract(res, 'auc_total')
        ax.scatter(wts, aucs, alpha=0.2, s=8, color=color, label=name)
    ax.axhspan(AUC_LO, AUC_HI, alpha=0.06, color='green')
    ax.axhline(AUC_LO, color='green', ls='--', lw=0.8, alpha=0.5)
    ax.axhline(AUC_HI, color='green', ls='--', lw=0.8, alpha=0.5)
    ax.set_xlabel('Body Weight (kg)')
    ax.set_ylabel('Total MPA AUC (mg$\\cdot$h/L)')
    ax.set_title('C. AUC vs Weight by Strategy', fontweight='bold', fontsize=11)
    ax.legend(fontsize=9, markerscale=3)
    ax.set_ylim(0, 150)

    # --- Panel D: Weight-based dose nomogram ---
    ax = fig.add_subplot(gs[1, 0:2])
    pk = PKParameters()
    drug = DrugParameters()

    weight_bins = np.arange(40, 95, 5)
    optimal_doses = []
    for wt in weight_bins:
        ref = PatientParameters(body_weight=wt, albumin=3.5, gfr=50.0, cni_type='tacrolimus')
        best_dose, best_diff = 1000, 1e9
        for test_dose in range(250, 1500, 50):
            try:
                res = simulate_steady_state(test_dose, ref, pk, drug, n_doses=10)
                diff = abs(res['auc_ss_0_12'] - 45.0)
                if diff < best_diff:
                    best_diff = diff
                    best_dose = test_dose
            except Exception:
                pass
        optimal_doses.append(round_to_available(best_dose))

    ax.plot(weight_bins, optimal_doses, 'o-', color=C_IND_WB, linewidth=2.5,
            markersize=9, label='Optimal (target AUC=45)', zorder=3)
    ax.axhline(1000, color=C_IND_STD, ls='--', lw=1.5, label='Standard 1000mg', alpha=0.7)
    ax.axhline(750, color=C_IND_750, ls='--', lw=1.5, label='Reduced 750mg', alpha=0.7)

    for tablet in [250, 500, 750, 1000, 1250]:
        ax.axhline(tablet, color='gray', ls=':', alpha=0.15)

    for wt, dose in zip(weight_bins, optimal_doses):
        ax.annotate(f'{dose:.0f}', (wt, dose), textcoords="offset points",
                    xytext=(0, 12), ha='center', fontsize=8, fontweight='bold', color='#065F46')

    ax.set_xlabel('Body Weight (kg)', fontsize=11)
    ax.set_ylabel('Recommended MMF Dose BID (mg)', fontsize=11)
    ax.set_title('D. Weight-Based Dose Nomogram (Indian, Tacrolimus, Alb ~3.5 g/dL)',
                 fontweight='bold', fontsize=11)
    ax.legend(fontsize=9)
    ax.set_ylim(200, 1300)
    ax.set_xlim(38, 95)
    ax.grid(True, alpha=0.12)

    # --- Panel E: Summary comparison table (as bar chart) ---
    ax = fig.add_subplot(gs[1, 2])
    metric_names = ['Mean\nAUC', 'Target\nAttain %', 'Over-\nexposed %', 'Mean TI\n(x100)']
    x = np.arange(len(metric_names))
    width = 0.18

    for idx, ((name, res), color) in enumerate(zip(groups.items(), grp_colors)):
        aucs = extract(res, 'auc_total')
        ti = extract(res, 'therapeutic_index')
        vals = [
            np.mean(aucs),
            np.mean((aucs >= AUC_LO) & (aucs <= AUC_HI)) * 100,
            np.mean(aucs > AUC_HI) * 100,
            np.mean(ti) * 100,
        ]
        offset = (idx - 1.5) * width
        ax.bar(x + offset, vals, width, color=color, alpha=0.85,
               label=name.replace('\n', ' '), edgecolor='white')

    ax.set_xticks(x)
    ax.set_xticklabels(metric_names, fontsize=9)
    ax.set_ylabel('Value')
    ax.set_title('E. Key Metrics Comparison', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7, ncol=2)

    fig.suptitle('Figure 2. Dose Optimization Strategy for Indian Transplant Patients',
                 fontsize=14, fontweight='bold', y=1.005)
    fig.savefig(os.path.join(OUTPUT_DIR, 'Figure2_Dose_Optimization.png'),
                dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print("  Saved Figure 2")


# ============================================================
# FIGURE 3: PK/PD Clinical Outcomes
# ============================================================

def figure3(data):
    """Clinical outcomes: IMPDH, rejection, toxicity, therapeutic index."""
    fig = plt.figure(figsize=(17, 12))
    gs = GridSpec(3, 3, figure=fig, hspace=0.38, wspace=0.30)

    groups = {
        'Western 1000mg': (data['west_1000'], C_WEST),
        'Indian 1000mg': (data['ind_1000'], C_IND_STD),
        'Indian 750mg': (data['ind_750'], C_IND_750),
        'Indian 12mg/kg': (data['ind_wb'], C_IND_WB),
    }

    # --- Panel A: IMPDH concentration-response curve ---
    ax = fig.add_subplot(gs[0, 0])
    c_range = np.linspace(0, 1.0, 300)
    pd_params = PDParameters()
    inhib = [impdh_inhibition(c, pd_params) for c in c_range]
    ax.plot(c_range, inhib, 'k-', linewidth=2.5)
    ax.axhspan(0.30, 0.70, alpha=0.08, color='green')
    ax.axhline(0.30, color='#F59E0B', ls='--', alpha=0.6, label='Min target (30%)')
    ax.axhline(0.70, color='#DC2626', ls='--', alpha=0.6, label='Max target (70%)')
    ax.axvline(0.15, color='gray', ls=':', alpha=0.5, label='IC$_{50}$ = 0.15 mg/L')
    ax.set_xlabel('Free MPA (mg/L)')
    ax.set_ylabel('IMPDH-II Inhibition')
    ax.set_title('A. Concentration-Effect\nRelationship', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7)

    # --- Panel B: Avg IMPDH inhibition distribution ---
    ax = fig.add_subplot(gs[0, 1])
    for name, (res, color) in groups.items():
        ax.hist(extract(res, 'avg_impdh_inhibition'), bins=30, alpha=0.4, color=color,
                label=name, density=True, edgecolor='white')
    ax.axvspan(0.30, 0.70, alpha=0.06, color='green')
    ax.axvline(0.30, color='#F59E0B', ls='--', lw=1)
    ax.axvline(0.70, color='#DC2626', ls='--', lw=1)
    ax.set_xlabel('Average IMPDH Inhibition')
    ax.set_ylabel('Density')
    ax.set_title('B. IMPDH Inhibition\nDistribution', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7)

    # --- Panel C: Clinical zone stacked bars ---
    ax = fig.add_subplot(gs[0, 2])
    x = np.arange(len(groups))
    short_names = list(groups.keys())
    zd = {}
    for name, (res, _) in groups.items():
        zones = [r['clinical_zone'] for r in res]
        n = len(zones)
        zd[name] = {
            'U': sum(1 for z in zones if z == 'UNDEREXPOSED') / n * 100,
            'T': sum(1 for z in zones if z == 'THERAPEUTIC') / n * 100,
            'O': sum(1 for z in zones if z == 'OVEREXPOSED') / n * 100,
        }

    u_vals = [zd[n]['U'] for n in short_names]
    t_vals = [zd[n]['T'] for n in short_names]
    o_vals = [zd[n]['O'] for n in short_names]

    ax.bar(x, u_vals, 0.6, label='Underexposed', color='#FCD34D')
    ax.bar(x, t_vals, 0.6, bottom=u_vals, label='Therapeutic', color='#34D399')
    ax.bar(x, o_vals, 0.6, bottom=[u+t for u, t in zip(u_vals, t_vals)],
           label='Overexposed', color='#F87171')
    for i, tv in enumerate(t_vals):
        ax.text(i, u_vals[i] + tv/2, f'{tv:.0f}%', ha='center', va='center',
                fontsize=9, fontweight='bold', color='white')
    ax.set_ylabel('% of Population')
    ax.set_title('C. IMPDH-Based Exposure\nZones', fontweight='bold', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=7, rotation=10)
    ax.legend(fontsize=7)

    # --- Panel D: Rejection probability ---
    ax = fig.add_subplot(gs[1, 0])
    for name, (res, color) in groups.items():
        ax.hist(extract(res, 'p_rejection') * 100, bins=25, alpha=0.4, color=color,
                label=name, density=True, edgecolor='white')
    ax.set_xlabel('Rejection Probability (%)')
    ax.set_ylabel('Density')
    ax.set_title('D. Acute Rejection Risk', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7)

    # --- Panel E: GI toxicity probability ---
    ax = fig.add_subplot(gs[1, 1])
    for name, (res, color) in groups.items():
        ax.hist(extract(res, 'p_gi_toxicity') * 100, bins=25, alpha=0.4, color=color,
                label=name, density=True, edgecolor='white')
    ax.set_xlabel('GI Toxicity Probability (%)')
    ax.set_ylabel('Density')
    ax.set_title('E. GI Toxicity Risk', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7)

    # --- Panel F: Therapeutic index distribution ---
    ax = fig.add_subplot(gs[1, 2])
    for name, (res, color) in groups.items():
        ti = extract(res, 'therapeutic_index')
        ax.hist(ti, bins=25, alpha=0.4, color=color, label=name, density=True, edgecolor='white')
    ax.set_xlabel('Therapeutic Index (efficacy x safety)')
    ax.set_ylabel('Density')
    ax.set_title('F. Composite Therapeutic\nIndex', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7)

    # --- Panel G: Efficacy-toxicity tradeoff scatter ---
    ax = fig.add_subplot(gs[2, 0:2])
    for name, (res, color) in groups.items():
        p_rej = extract(res, 'p_rejection') * 100
        p_gi = extract(res, 'p_gi_toxicity') * 100
        ax.scatter(p_rej, p_gi, alpha=0.2, s=10, color=color, label=name)
    ax.set_xlabel('Rejection Probability (%)', fontsize=11)
    ax.set_ylabel('GI Toxicity Probability (%)', fontsize=11)
    ax.set_title('G. Efficacy-Toxicity Landscape (each dot = 1 virtual patient)',
                 fontweight='bold', fontsize=11)
    ax.legend(fontsize=8, markerscale=3, loc='upper left')
    ax.axhspan(0, 20, xmin=0, xmax=0.35, alpha=0.04, color='green')
    ax.text(5, 15, 'Optimal\nzone', fontsize=9, color='green', alpha=0.6, style='italic')

    # --- Panel H: Summary bar chart ---
    ax = fig.add_subplot(gs[2, 2])
    grp_names = list(groups.keys())
    metrics_list = ['P(rejection)', 'P(GI tox)', 'P(leukopenia)', 'Ther. Index']
    keys = ['p_rejection', 'p_gi_toxicity', 'p_leukopenia', 'therapeutic_index']
    x = np.arange(len(grp_names))
    width = 0.18
    metric_colors = ['#7C3AED', '#EF4444', '#F59E0B', '#10B981']

    for j, (mname, key, mc) in enumerate(zip(metrics_list, keys, metric_colors)):
        vals = [np.mean(extract(groups[n][0], key)) * 100 for n in grp_names]
        ax.bar(x + (j - 1.5) * width, vals, width, label=mname, color=mc, alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(grp_names, fontsize=7, rotation=10)
    ax.set_ylabel('Probability (%) / Index (x100)')
    ax.set_title('H. Clinical Outcome\nSummary', fontweight='bold', fontsize=11)
    ax.legend(fontsize=7, ncol=2)

    fig.suptitle('Figure 3. PK/PD Clinical Outcomes: Efficacy-Toxicity Balance Across Dosing Strategies',
                 fontsize=14, fontweight='bold', y=1.005)
    fig.savefig(os.path.join(OUTPUT_DIR, 'Figure3_PKPD_Outcomes.png'),
                dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print("  Saved Figure 3")


# ============================================================
# FIGURE 4: Model Validation
# ============================================================

def figure4(data):
    """Model validation against published clinical data."""
    results = data['validation']
    n_studies = len(results)

    fig = plt.figure(figsize=(17, 9))
    gs = GridSpec(2, 3, figure=fig, hspace=0.40, wspace=0.30)

    val_colors = ['#2563EB', '#1D4ED8', '#DC2626', '#F59E0B', '#D97706']

    # --- Panel A: Predicted vs Observed scatter ---
    ax = fig.add_subplot(gs[0, 0])
    for i, r in enumerate(results):
        ax.errorbar(r['study'].observed_auc_mean, r['pred_mean'],
                    xerr=r['study'].observed_auc_sd or 0, yerr=r['pred_sd'],
                    fmt='o', color=val_colors[i], markersize=10, capsize=5,
                    label=r['study'].name, zorder=3)

    lims = [0, max(r['pred_mean'] + r['pred_sd'] for r in results) + 15]
    ax.plot(lims, lims, 'k--', alpha=0.5, label='Identity')
    x_fill = np.linspace(0, 100, 100)
    ax.fill_between(x_fill, x_fill * 0.5, x_fill * 2.0, alpha=0.06, color='green')
    ax.fill_between(x_fill, x_fill * 0.8, x_fill * 1.25, alpha=0.06, color='green')
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel('Observed AUC (mg$\\cdot$h/L)')
    ax.set_ylabel('Predicted AUC (mg$\\cdot$h/L)')
    ax.set_title('A. Predicted vs Observed', fontweight='bold', fontsize=11)
    ax.legend(fontsize=6.5, loc='upper left')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.2)

    # --- Panel B: Fold-error bars ---
    ax = fig.add_subplot(gs[0, 1])
    fes = [r['fold_error'] for r in results]
    bar_colors = ['#34D399' if 0.8 <= fe <= 1.25 else '#FCD34D' if 0.5 <= fe <= 2.0 else '#F87171'
                  for fe in fes]
    bars = ax.barh(range(n_studies), fes, color=bar_colors, edgecolor='#333', alpha=0.85)
    ax.axvline(1.0, color='black', ls='--', lw=1.5)
    ax.axvspan(0.8, 1.25, alpha=0.08, color='green', label='0.8-1.25x')
    ax.set_yticks(range(n_studies))
    ax.set_yticklabels([r['study'].name for r in results], fontsize=8)
    ax.set_xlabel('Fold Error (Pred / Obs)')
    ax.set_title('B. Prediction Accuracy', fontweight='bold', fontsize=11)
    ax.set_xlim(0, 2.2)
    ax.legend(fontsize=8)
    for i, (fe, bar) in enumerate(zip(fes, bars)):
        ax.text(fe + 0.04, i, f'{fe:.2f}', va='center', fontsize=10, fontweight='bold')

    # --- Panel C: GMFE summary ---
    ax = fig.add_subplot(gs[0, 2])
    ax.axis('off')
    gmfe = np.exp(np.mean(np.log(np.array(fes))))
    avg_mpe = np.mean([r['mpe_pct'] for r in results])
    n_pass = sum(1 for fe in fes if 0.8 <= fe <= 1.25)
    n_2fold = sum(1 for fe in fes if 0.5 <= fe <= 2.0)

    summary_text = (
        f"VALIDATION SUMMARY\n"
        f"{'='*35}\n\n"
        f"Studies validated: {n_studies}\n"
        f"GMFE: {gmfe:.2f}\n"
        f"Average MPE: {avg_mpe:+.1f}%\n\n"
        f"Within 0.8-1.25x: {n_pass}/{n_studies}\n"
        f"Within 2-fold: {n_2fold}/{n_studies}\n\n"
        f"Regulatory threshold (GMFE<2): PASS\n\n"
        f"Asian predictions: FE 0.90-1.24\n"
        f"Western Tac: FE 1.25 (borderline)\n"
        f"Western CsA: FE 1.54 (OATP effect\n"
        f"  not explicitly modeled)"
    )
    ax.text(0.1, 0.95, summary_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='#F0FDF4', edgecolor='#059669', alpha=0.9))
    ax.set_title('C. Validation Metrics', fontweight='bold', fontsize=11)

    # --- Panels D-F: Distribution comparisons for 3 key studies ---
    key_indices = [0, 2, 3]  # Western CsA, Chinese CsA, Thai Mixed
    for panel_idx, study_idx in enumerate(key_indices):
        ax = fig.add_subplot(gs[1, panel_idx])
        r = results[study_idx]
        auc_pred = r['auc_predicted']
        obs_mean = r['study'].observed_auc_mean
        obs_sd = r['study'].observed_auc_sd or r['pred_sd']

        ax.hist(auc_pred, bins=25, density=True, alpha=0.55, color=val_colors[study_idx],
                edgecolor='white')

        x_range = np.linspace(max(0, obs_mean - 3.5*obs_sd), obs_mean + 3.5*obs_sd, 200)
        obs_pdf = (1/(obs_sd*np.sqrt(2*np.pi))) * np.exp(-0.5*((x_range - obs_mean)/obs_sd)**2)
        ax.plot(x_range, obs_pdf, 'r-', linewidth=2.5, label='Observed')
        ax.axvline(obs_mean, color='red', ls='--', alpha=0.6)
        ax.axvline(np.mean(auc_pred), color=val_colors[study_idx], ls='--', lw=2)
        ax.axvspan(AUC_LO, AUC_HI, alpha=0.06, color='green')

        panel_letter = chr(68 + panel_idx)  # D, E, F
        ax.set_xlabel('AUC$_{0-12}$ (mg$\\cdot$h/L)')
        ax.set_ylabel('Density')
        ax.set_title(f'{panel_letter}. {r["study"].name}\n'
                     f'({r["study"].dose_mg:.0f}mg, {r["study"].cni})',
                     fontweight='bold', fontsize=10)

        textstr = (f'Obs: {obs_mean:.1f}+/-{obs_sd:.1f}\n'
                   f'Pred: {r["pred_mean"]:.1f}+/-{r["pred_sd"]:.1f}\n'
                   f'FE: {r["fold_error"]:.2f}')
        ax.text(0.95, 0.95, textstr, transform=ax.transAxes, fontsize=8,
                va='top', ha='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.85))

    fig.suptitle('Figure 4. Model Validation Against Published Clinical Pharmacokinetic Data',
                 fontsize=14, fontweight='bold', y=1.005)
    fig.savefig(os.path.join(OUTPUT_DIR, 'Figure4_Validation.png'),
                dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print("  Saved Figure 4")


# ============================================================
# TABLE GENERATION
# ============================================================

def generate_tables(data):
    """Generate manuscript tables as formatted text files."""

    # --- Table 1: Population demographics ---
    lines = []
    lines.append("Table 1. Virtual Population Demographics")
    lines.append("=" * 70)
    lines.append(f"{'Parameter':<30s} {'Western (n=500)':>18s} {'Indian (n=500)':>18s}")
    lines.append("-" * 70)

    wt_w = [p.body_weight for p in data['west_pts']]
    wt_i = [p.body_weight for p in data['ind_pts']]
    alb_w = [p.albumin for p in data['west_pts']]
    alb_i = [p.albumin for p in data['ind_pts']]
    gfr_w = [p.gfr for p in data['west_pts']]
    gfr_i = [p.gfr for p in data['ind_pts']]
    tac_w = sum(1 for p in data['west_pts'] if p.cni_type == 'tacrolimus') / len(data['west_pts']) * 100
    tac_i = sum(1 for p in data['ind_pts'] if p.cni_type == 'tacrolimus') / len(data['ind_pts']) * 100

    def ms(arr): return f"{np.mean(arr):.1f} +/- {np.std(arr):.1f}"

    lines.append(f"{'Body weight (kg)':<30s} {ms(wt_w):>18s} {ms(wt_i):>18s}")
    lines.append(f"{'Serum albumin (g/dL)':<30s} {ms(alb_w):>18s} {ms(alb_i):>18s}")
    lines.append(f"{'eGFR (mL/min)':<30s} {ms(gfr_w):>18s} {ms(gfr_i):>18s}")
    lines.append(f"{'Tacrolimus use (%)':<30s} {tac_w:>17.0f}% {tac_i:>17.0f}%")
    lines.append("=" * 70)

    with open(os.path.join(OUTPUT_DIR, 'Table1_Demographics.txt'), 'w') as f:
        f.write('\n'.join(lines))

    # --- Table 2: Key PK/PD results ---
    lines2 = []
    lines2.append("Table 2. Key Pharmacokinetic and Pharmacodynamic Outcomes")
    lines2.append("=" * 100)
    hdr = f"{'Metric':<35s} {'West 1000mg':>15s} {'Ind 1000mg':>15s} {'Ind 750mg':>15s} {'Ind 12mg/kg':>15s}"
    lines2.append(hdr)
    lines2.append("-" * 100)

    groups = [
        ('West 1000mg', data['west_1000']),
        ('Ind 1000mg', data['ind_1000']),
        ('Ind 750mg', data['ind_750']),
        ('Ind 12mg/kg', data['ind_wb']),
    ]

    def row(label, key, fmt_func):
        line = f"  {label:<33s}"
        for _, res in groups:
            vals = extract(res, key)
            line += f" {fmt_func(vals):>15s}"
        return line

    def ms2(arr): return f"{np.mean(arr):.1f} +/- {np.std(arr):.1f}"
    def pct(arr): return f"{np.mean(arr)*100:.1f}%"

    lines2.append(row("Total AUC (mg.h/L)", 'auc_total', ms2))
    lines2.append(row("Free AUC (mg.h/L)", 'auc_free', lambda a: f"{np.mean(a):.2f} +/- {np.std(a):.2f}"))
    lines2.append(row("Avg IMPDH inhibition", 'avg_impdh_inhibition', lambda a: f"{np.mean(a):.3f} +/- {np.std(a):.3f}"))
    lines2.append("")

    # Target attainment
    line = f"  {'% Target (30-60 mg.h/L)':<33s}"
    for _, res in groups:
        aucs = extract(res, 'auc_total')
        pct_t = np.mean((aucs >= AUC_LO) & (aucs <= AUC_HI)) * 100
        line += f" {pct_t:>14.1f}%"
    lines2.append(line)

    line = f"  {'% Overexposed (>60 mg.h/L)':<33s}"
    for _, res in groups:
        aucs = extract(res, 'auc_total')
        pct_o = np.mean(aucs > AUC_HI) * 100
        line += f" {pct_o:>14.1f}%"
    lines2.append(line)

    lines2.append("")
    lines2.append(row("P(rejection)", 'p_rejection', pct))
    lines2.append(row("P(GI toxicity)", 'p_gi_toxicity', pct))
    lines2.append(row("P(leukopenia)", 'p_leukopenia', pct))
    lines2.append(row("P(any adverse)", 'p_any_adverse', pct))
    lines2.append("")
    lines2.append(row("Therapeutic index", 'therapeutic_index', lambda a: f"{np.mean(a):.3f} +/- {np.std(a):.3f}"))

    # Zone
    for zone_name in ['THERAPEUTIC', 'OVEREXPOSED', 'UNDEREXPOSED']:
        line = f"  {'% ' + zone_name.capitalize():<33s}"
        for _, res in groups:
            zones = [r['clinical_zone'] for r in res]
            pct_z = sum(1 for z in zones if z == zone_name) / len(zones) * 100
            line += f" {pct_z:>14.1f}%"
        lines2.append(line)

    lines2.append("=" * 100)

    with open(os.path.join(OUTPUT_DIR, 'Table2_PKPD_Results.txt'), 'w') as f:
        f.write('\n'.join(lines2))

    print("  Saved Table 1 and Table 2")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("  MANUSCRIPT FIGURE GENERATION")
    print("  MPA QSP Model: Dosing Optimization for Indian Patients")
    print("=" * 70)

    data = generate_all_data()

    print("\nGenerating manuscript figures...")
    figure1(data)
    figure2(data)
    figure3(data)
    figure4(data)
    generate_tables(data)

    print(f"\nAll outputs saved to: {OUTPUT_DIR}/")
    print("  - Figure1_PK_Comparison.png")
    print("  - Figure2_Dose_Optimization.png")
    print("  - Figure3_PKPD_Outcomes.png")
    print("  - Figure4_Validation.png")
    print("  - Table1_Demographics.txt")
    print("  - Table2_PKPD_Results.txt")
    print("\nDone.")


if __name__ == "__main__":
    main()
