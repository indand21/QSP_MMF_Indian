"""
Variability Decomposition Analysis
====================================
Quantifies the relative contribution of each input parameter
(body weight, UGT1A9, UGT2B7, GFR, ABCC2, albumin) to the
interindividual variability in MPA AUC for each population.

Methods:
1. Partial correlation analysis
2. Variance reduction analysis (fix each parameter at its mean,
   measure reduction in AUC CV%)
3. Nonlinear weight-AUC relationship demonstration

Generates: FigureS4_Variability_Decomposition.png
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
from populations.virtual_populations import (
    generate_virtual_population, PopulationDistributions
)

warnings.filterwarnings('ignore')

N_PATIENTS = 500
N_DOSES_SS = 14
OUTPUT_DIR = os.path.join(project_root, "outputs", "manuscript_updated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Equalized populations (same as manuscript)
ALBUMIN_MEAN = 4.0
ALBUMIN_SD = 0.4
PROP_TACROLIMUS = 0.92

WESTERN_EQ = PopulationDistributions(
    name="Western",
    wt_mean=78.0, wt_sd=15.0, wt_min=45.0, wt_max=140.0,
    ht_mean=172.0, ht_sd=9.0,
    alb_mean=ALBUMIN_MEAN, alb_sd=ALBUMIN_SD, alb_min=2.5, alb_max=5.5,
    gfr_mean=55.0, gfr_sd=18.0, gfr_min=15.0, gfr_max=120.0,
    prop_tacrolimus=PROP_TACROLIMUS,
    ugt1a9_mean=1.0, ugt1a9_sd=0.15,
    ugt2b7_mean=1.0, ugt2b7_sd=0.15,
    abcc2_mean=1.0, abcc2_sd=0.15,
)

INDIAN_EQ = PopulationDistributions(
    name="Indian",
    wt_mean=58.0, wt_sd=12.0, wt_min=35.0, wt_max=110.0,
    ht_mean=163.0, ht_sd=8.5,
    alb_mean=ALBUMIN_MEAN, alb_sd=ALBUMIN_SD, alb_min=2.5, alb_max=5.5,
    gfr_mean=50.0, gfr_sd=18.0, gfr_min=15.0, gfr_max=110.0,
    prop_tacrolimus=PROP_TACROLIMUS,
    ugt1a9_mean=0.95, ugt1a9_sd=0.18,
    ugt2b7_mean=0.92, ugt2b7_sd=0.20,
    abcc2_mean=0.97, abcc2_sd=0.18,
)


def simulate_population(patients, dose_mg=1000, label=""):
    """Simulate a population and return AUC + patient parameters."""
    pk = PKParameters()
    drug = DrugParameters()
    aucs = []
    aucs_free = []
    weights = []
    albumins = []
    gfrs = []
    ugt1a9s = []
    ugt2b7s = []
    abcc2s = []

    for i, patient in enumerate(patients):
        if (i + 1) % 250 == 0:
            print(f"    {label}: {i+1}/{len(patients)}")
        try:
            pk_res = simulate_steady_state(dose_mg, patient, pk, drug, N_DOSES_SS)
            aucs.append(pk_res['auc_ss_0_12'])
            aucs_free.append(pk_res['auc_free_ss_0_12'])
            weights.append(patient.body_weight)
            albumins.append(patient.albumin)
            gfrs.append(patient.gfr)
            ugt1a9s.append(patient.ugt1a9_activity)
            ugt2b7s.append(patient.ugt2b7_activity)
            abcc2s.append(patient.abcc2_activity)
        except Exception:
            pass

    return {
        'auc': np.array(aucs),
        'auc_free': np.array(aucs_free),
        'weight': np.array(weights),
        'albumin': np.array(albumins),
        'gfr': np.array(gfrs),
        'ugt1a9': np.array(ugt1a9s),
        'ugt2b7': np.array(ugt2b7s),
        'abcc2': np.array(abcc2s),
    }


def simulate_fixed_param(patients, fix_param, fix_value, dose_mg=1000, label=""):
    """Simulate with one parameter fixed at its mean value."""
    pk = PKParameters()
    drug = DrugParameters()
    aucs = []

    for i, patient in enumerate(patients):
        # Create modified patient with fixed parameter
        modified = PatientParameters(
            body_weight=fix_value if fix_param == 'weight' else patient.body_weight,
            height=patient.height,
            albumin=fix_value if fix_param == 'albumin' else patient.albumin,
            gfr=fix_value if fix_param == 'gfr' else patient.gfr,
            hematocrit=patient.hematocrit,
            cni_type=patient.cni_type,
            ugt1a9_activity=fix_value if fix_param == 'ugt1a9' else patient.ugt1a9_activity,
            ugt2b7_activity=fix_value if fix_param == 'ugt2b7' else patient.ugt2b7_activity,
            abcc2_activity=fix_value if fix_param == 'abcc2' else patient.abcc2_activity,
        )
        try:
            pk_res = simulate_steady_state(dose_mg, modified, pk, drug, N_DOSES_SS)
            aucs.append(pk_res['auc_ss_0_12'])
        except Exception:
            pass

    return np.array(aucs)


def partial_correlation(x, y, covariates):
    """Compute partial correlation between x and y controlling for covariates."""
    from numpy.linalg import lstsq
    # Regress x on covariates
    C = np.column_stack(covariates)
    C_aug = np.column_stack([C, np.ones(len(x))])
    coef_x, _, _, _ = lstsq(C_aug, x, rcond=None)
    resid_x = x - C_aug @ coef_x
    # Regress y on covariates
    coef_y, _, _, _ = lstsq(C_aug, y, rcond=None)
    resid_y = y - C_aug @ coef_y
    # Correlation of residuals
    r = np.corrcoef(resid_x, resid_y)[0, 1]
    return r


def compute_correlations(data):
    """Compute Pearson and partial correlations with AUC."""
    params = {
        'Body Weight': data['weight'],
        'UGT1A9': data['ugt1a9'],
        'UGT2B7': data['ugt2b7'],
        'GFR': data['gfr'],
        'ABCC2': data['abcc2'],
        'Albumin': data['albumin'],
    }

    pearson = {}
    partial = {}

    for name, values in params.items():
        # Pearson correlation
        pearson[name] = np.corrcoef(values, data['auc'])[0, 1]

        # Partial correlation (controlling for all other params)
        covariates = [v for n, v in params.items() if n != name]
        partial[name] = partial_correlation(values, data['auc'], covariates)

    return pearson, partial


def compute_variance_reduction(patients, data, pop_dist, dose_mg=1000, label=""):
    """Fix each parameter at mean, compute resulting CV% reduction."""
    baseline_cv = np.std(data['auc']) / np.mean(data['auc']) * 100

    param_configs = {
        'Body Weight': ('weight', pop_dist.wt_mean),
        'UGT1A9': ('ugt1a9', pop_dist.ugt1a9_mean),
        'UGT2B7': ('ugt2b7', pop_dist.ugt2b7_mean),
        'GFR': ('gfr', pop_dist.gfr_mean),
        'ABCC2': ('abcc2', pop_dist.abcc2_mean),
        'Albumin': ('albumin', pop_dist.alb_mean),
    }

    reductions = {}
    for name, (param, value) in param_configs.items():
        print(f"    Fixing {name} at {value:.2f} ({label})...")
        fixed_aucs = simulate_fixed_param(patients, param, value, dose_mg, label)
        if len(fixed_aucs) > 0:
            fixed_cv = np.std(fixed_aucs) / np.mean(fixed_aucs) * 100
            reductions[name] = baseline_cv - fixed_cv
        else:
            reductions[name] = 0.0

    return baseline_cv, reductions


def generate_figure(west_data, ind_data, west_corr, ind_corr,
                    west_var, ind_var, west_cv, ind_cv):
    """Generate 6-panel supplementary figure."""
    fig = plt.figure(figsize=(16, 14))
    gs = GridSpec(3, 2, figure=fig, hspace=0.35, wspace=0.30)

    colors_w = '#2196F3'
    colors_i = '#FF5722'

    # -------------------------------------------------------
    # Panel A: Pearson correlations (bar chart)
    # -------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, 0])
    params = list(west_corr[0].keys())
    x = np.arange(len(params))
    width = 0.35
    west_pearson = [west_corr[0][p] for p in params]
    ind_pearson = [ind_corr[0][p] for p in params]

    bars1 = ax1.bar(x - width/2, west_pearson, width, label='Western',
                     color=colors_w, alpha=0.8, edgecolor='black', linewidth=0.5)
    bars2 = ax1.bar(x + width/2, ind_pearson, width, label='Indian',
                     color=colors_i, alpha=0.8, edgecolor='black', linewidth=0.5)
    ax1.set_xlabel('Parameter', fontsize=10)
    ax1.set_ylabel('Pearson Correlation with AUC', fontsize=10)
    ax1.set_title('A. Univariate Correlations with AUC', fontsize=12, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(params, rotation=30, ha='right', fontsize=9)
    ax1.axhline(y=0, color='black', linewidth=0.5)
    ax1.legend(fontsize=9)
    ax1.set_ylim(-1.0, 0.3)

    # -------------------------------------------------------
    # Panel B: Partial correlations (bar chart)
    # -------------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    west_partial = [west_corr[1][p] for p in params]
    ind_partial = [ind_corr[1][p] for p in params]

    bars1 = ax2.bar(x - width/2, west_partial, width, label='Western',
                     color=colors_w, alpha=0.8, edgecolor='black', linewidth=0.5)
    bars2 = ax2.bar(x + width/2, ind_partial, width, label='Indian',
                     color=colors_i, alpha=0.8, edgecolor='black', linewidth=0.5)
    ax2.set_xlabel('Parameter', fontsize=10)
    ax2.set_ylabel('Partial Correlation with AUC', fontsize=10)
    ax2.set_title('B. Partial Correlations (Adjusted)', fontsize=12, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(params, rotation=30, ha='right', fontsize=9)
    ax2.axhline(y=0, color='black', linewidth=0.5)
    ax2.legend(fontsize=9)
    ax2.set_ylim(-1.0, 0.3)

    # -------------------------------------------------------
    # Panel C: Variance reduction waterfall (Indian)
    # -------------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 0])
    # Sort by reduction magnitude
    sorted_params = sorted(ind_var.keys(), key=lambda p: ind_var[p], reverse=True)
    reductions = [ind_var[p] for p in sorted_params]
    total_reduction = sum(reductions)
    pct_contributions = [r / total_reduction * 100 if total_reduction > 0 else 0 for r in reductions]

    bars = ax3.barh(range(len(sorted_params)), reductions, color=colors_i,
                     alpha=0.8, edgecolor='black', linewidth=0.5)
    ax3.set_yticks(range(len(sorted_params)))
    ax3.set_yticklabels(sorted_params, fontsize=10)
    ax3.set_xlabel('CV% Reduction When Fixed at Mean', fontsize=10)
    ax3.set_title(f'C. Variance Attribution (Indian, Baseline CV={ind_cv:.1f}%)',
                  fontsize=12, fontweight='bold')
    ax3.invert_yaxis()
    # Add percentage labels
    for i, (r, pct) in enumerate(zip(reductions, pct_contributions)):
        if r > 0.1:
            ax3.text(r + 0.2, i, f'{r:.1f}% ({pct:.0f}%)', va='center', fontsize=9)

    # -------------------------------------------------------
    # Panel D: Variance reduction comparison (both populations)
    # -------------------------------------------------------
    ax4 = fig.add_subplot(gs[1, 1])
    params_sorted = sorted(west_var.keys(), key=lambda p: max(west_var[p], ind_var[p]), reverse=True)
    y_pos = np.arange(len(params_sorted))
    width_h = 0.35

    west_red = [west_var[p] for p in params_sorted]
    ind_red = [ind_var[p] for p in params_sorted]

    ax4.barh(y_pos + width_h/2, west_red, width_h, label=f'Western (CV={west_cv:.1f}%)',
             color=colors_w, alpha=0.8, edgecolor='black', linewidth=0.5)
    ax4.barh(y_pos - width_h/2, ind_red, width_h, label=f'Indian (CV={ind_cv:.1f}%)',
             color=colors_i, alpha=0.8, edgecolor='black', linewidth=0.5)
    ax4.set_yticks(y_pos)
    ax4.set_yticklabels(params_sorted, fontsize=10)
    ax4.set_xlabel('CV% Reduction When Fixed at Mean', fontsize=10)
    ax4.set_title('D. Variance Attribution Comparison', fontsize=12, fontweight='bold')
    ax4.invert_yaxis()
    ax4.legend(fontsize=9, loc='lower right')

    # -------------------------------------------------------
    # Panel E: Nonlinear weight-AUC relationship
    # -------------------------------------------------------
    ax5 = fig.add_subplot(gs[2, 0])
    ax5.scatter(west_data['weight'], west_data['auc'], alpha=0.3, s=15,
                color=colors_w, label='Western')
    ax5.scatter(ind_data['weight'], ind_data['auc'], alpha=0.3, s=15,
                color=colors_i, label='Indian')

    # Fit and plot theoretical curve: AUC ~ Dose / (BW^0.75 * const)
    bw_range = np.linspace(35, 140, 200)
    # Theoretical: AUC proportional to Dose / CL, CL ~ BW^0.75
    # Normalize to match observed data
    ref_auc_w = np.median(west_data['auc'])
    ref_bw_w = np.median(west_data['weight'])
    scale_factor = ref_auc_w * (ref_bw_w ** 0.75)
    theoretical_auc = scale_factor / (bw_range ** 0.75)

    ax5.plot(bw_range, theoretical_auc, 'k--', linewidth=2, alpha=0.7,
             label=r'Theoretical: AUC $\propto$ BW$^{-0.75}$')

    # Highlight the steeper slope region
    ax5.axvspan(35, 65, alpha=0.08, color=colors_i, label='Indian BW range')
    ax5.axvspan(60, 110, alpha=0.06, color=colors_w, label='Western BW range')

    ax5.set_xlabel('Body Weight (kg)', fontsize=10)
    ax5.set_ylabel('Total MPA AUC (mg\u00b7h/L)', fontsize=10)
    ax5.set_title('E. Nonlinear Weight\u2013AUC Relationship', fontsize=12, fontweight='bold')
    ax5.legend(fontsize=8, loc='upper right')
    ax5.set_xlim(30, 145)
    ax5.set_ylim(0, 180)

    # -------------------------------------------------------
    # Panel F: Derivative showing steeper slope at lower BW
    # -------------------------------------------------------
    ax6 = fig.add_subplot(gs[2, 1])
    # |dAUC/dBW| = 0.75 * scale_factor / BW^1.75
    derivative = 0.75 * scale_factor / (bw_range ** 1.75)

    ax6.plot(bw_range, derivative, 'k-', linewidth=2)
    ax6.fill_between(bw_range, derivative, alpha=0.15, color='gray')

    # Mark population means
    deriv_ind = 0.75 * scale_factor / (58.0 ** 1.75)
    deriv_west = 0.75 * scale_factor / (78.0 ** 1.75)
    ax6.axvline(x=58, color=colors_i, linewidth=1.5, linestyle='--')
    ax6.axvline(x=78, color=colors_w, linewidth=1.5, linestyle='--')
    ax6.plot(58, deriv_ind, 'o', color=colors_i, markersize=10, zorder=5)
    ax6.plot(78, deriv_west, 'o', color=colors_w, markersize=10, zorder=5)

    ratio = deriv_ind / deriv_west
    ax6.annotate(f'Indian mean\n|slope| = {deriv_ind:.2f}',
                 xy=(58, deriv_ind), xytext=(42, deriv_ind * 1.15),
                 fontsize=9, color=colors_i, fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color=colors_i))
    ax6.annotate(f'Western mean\n|slope| = {deriv_west:.2f}',
                 xy=(78, deriv_west), xytext=(90, deriv_west * 1.5),
                 fontsize=9, color=colors_w, fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color=colors_w))

    ax6.text(0.5, 0.95, f'Slope ratio (Indian/Western): {ratio:.2f}\u00d7',
             transform=ax6.transAxes, fontsize=11, fontweight='bold',
             ha='center', va='top',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', edgecolor='orange'))

    ax6.set_xlabel('Body Weight (kg)', fontsize=10)
    ax6.set_ylabel('|dAUC/dBW| (mg\u00b7h/L per kg)', fontsize=10)
    ax6.set_title('F. Sensitivity of AUC to Weight Change', fontsize=12, fontweight='bold')
    ax6.set_xlim(30, 145)

    fig.suptitle('Supplementary Figure S4: Variability Decomposition Analysis',
                 fontsize=14, fontweight='bold', y=0.98)

    plt.savefig(os.path.join(OUTPUT_DIR, 'FigureS4_Variability_Decomposition.png'),
                dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print("  FigureS4_Variability_Decomposition.png saved.")


def main():
    print("=" * 60)
    print("VARIABILITY DECOMPOSITION ANALYSIS")
    print("=" * 60)

    # Generate populations (fixed seed for reproducibility)
    print("\n1. Generating populations...")
    west_patients = generate_virtual_population(WESTERN_EQ, N_PATIENTS, seed=42)
    ind_patients = generate_virtual_population(INDIAN_EQ, N_PATIENTS, seed=42)

    # Full simulation
    print("\n2. Running full simulations...")
    print("  Western 1000mg BID:")
    west_data = simulate_population(west_patients, 1000, "Western")
    print("  Indian 1000mg BID:")
    ind_data = simulate_population(ind_patients, 1000, "Indian")

    west_cv = np.std(west_data['auc']) / np.mean(west_data['auc']) * 100
    ind_cv = np.std(ind_data['auc']) / np.mean(ind_data['auc']) * 100
    print(f"\n  Baseline CV%: Western={west_cv:.1f}%, Indian={ind_cv:.1f}%")

    # Partial correlations
    print("\n3. Computing correlations...")
    west_corr = compute_correlations(west_data)
    ind_corr = compute_correlations(ind_data)

    print("\n  Pearson correlations with AUC:")
    print(f"  {'Parameter':<15} {'Western':>10} {'Indian':>10}")
    for p in west_corr[0]:
        print(f"  {p:<15} {west_corr[0][p]:>10.3f} {ind_corr[0][p]:>10.3f}")

    print("\n  Partial correlations with AUC:")
    for p in west_corr[1]:
        print(f"  {p:<15} {west_corr[1][p]:>10.3f} {ind_corr[1][p]:>10.3f}")

    # Variance reduction analysis
    print("\n4. Variance reduction analysis...")
    print("  Western:")
    west_cv_base, west_var = compute_variance_reduction(
        west_patients, west_data, WESTERN_EQ, 1000, "Western")
    print("  Indian:")
    ind_cv_base, ind_var = compute_variance_reduction(
        ind_patients, ind_data, INDIAN_EQ, 1000, "Indian")

    print(f"\n  Variance reduction (CV% drop when parameter fixed):")
    print(f"  {'Parameter':<15} {'Western':>12} {'Indian':>12}")
    for p in west_var:
        print(f"  {p:<15} {west_var[p]:>10.2f}% {ind_var[p]:>10.2f}%")

    # Generate figure
    print("\n5. Generating figure...")
    generate_figure(west_data, ind_data, west_corr, ind_corr,
                    west_var, ind_var, west_cv, ind_cv)

    # Print summary for manuscript
    print("\n" + "=" * 60)
    print("SUMMARY FOR MANUSCRIPT")
    print("=" * 60)

    total_west = sum(west_var.values())
    total_ind = sum(ind_var.values())
    print(f"\nIndian population variance attribution:")
    for p in sorted(ind_var.keys(), key=lambda k: ind_var[k], reverse=True):
        pct = ind_var[p] / total_ind * 100 if total_ind > 0 else 0
        print(f"  {p}: {ind_var[p]:.2f}% CV reduction ({pct:.0f}% of total)")

    print(f"\nWestern population variance attribution:")
    for p in sorted(west_var.keys(), key=lambda k: west_var[k], reverse=True):
        pct = west_var[p] / total_west * 100 if total_west > 0 else 0
        print(f"  {p}: {west_var[p]:.2f}% CV reduction ({pct:.0f}% of total)")

    # Nonlinearity analysis
    ref_auc = np.median(west_data['auc'])
    ref_bw = np.median(west_data['weight'])
    scale = ref_auc * (ref_bw ** 0.75)
    deriv_58 = 0.75 * scale / (58.0 ** 1.75)
    deriv_78 = 0.75 * scale / (78.0 ** 1.75)
    print(f"\nNonlinearity analysis:")
    print(f"  |dAUC/dBW| at 58 kg: {deriv_58:.2f} mg\u00b7h/L per kg")
    print(f"  |dAUC/dBW| at 78 kg: {deriv_78:.2f} mg\u00b7h/L per kg")
    print(f"  Slope ratio: {deriv_58/deriv_78:.2f}x steeper at Indian mean weight")
    print(f"  This means a 1 kg weight difference causes {deriv_58/deriv_78:.2f}x more AUC change")


if __name__ == "__main__":
    main()
