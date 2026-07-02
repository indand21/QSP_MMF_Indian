"""
Pharmacodynamic Model for MPA: IMPDH Inhibition & Lymphocyte Dynamics
======================================================================
Links free MPA concentrations to:
1. IMPDH type II inhibition (Emax model)
2. Lymphocyte proliferation suppression
3. Clinical outcome probabilities (rejection risk, infection/toxicity risk)

References:
- Glander et al., Clin Pharmacol Ther 2004; 75(5):P76
- Staatz & Tett, Clin Pharmacokinet 2007; 46(1):13-58
- Le Meur et al., Am J Transplant 2007; 7(11):2576-2586
- Langman et al., Ther Drug Monit 2006; 28(2):274-279
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class PDParameters:
    """Pharmacodynamic parameters for MPA-IMPDH-lymphocyte axis."""

    # IMPDH Type II inhibition by MPA (Emax model)
    # Calibrated so that the THERAPEUTIC AUC range (30-60 mg.h/L total,
    # ~1.0-2.5 mg.h/L free, average free conc ~0.08-0.21 mg/L)
    # produces ~30-70% average IMPDH inhibition.
    # IC50 set to match clinical IMPDH activity data (Glander et al. 2004,
    # Sombogaard et al. 2009): ~50% suppression at therapeutic midpoint.
    Emax_impdh: float = 1.0           # Maximum fractional inhibition (complete)
    IC50_impdh_free: float = 0.15     # mg/L, IC50 for free MPA on IMPDH-II
    gamma_impdh: float = 1.5          # Hill coefficient

    # Lymphocyte dynamics
    # Baseline lymphocyte count in transplant patients
    lymph_baseline: float = 2.0       # x10^9/L (normal 1.0-4.0)
    lymph_min: float = 0.2            # x10^9/L, minimum viable count
    k_lymph_prolif: float = 0.05      # /h, lymphocyte proliferation rate
    k_lymph_death: float = 0.05       # /h, baseline death rate (balanced)
    impdh_inhibition_effect: float = 3.0  # fold increase in effective death
                                          # rate at maximum IMPDH inhibition

    # Clinical outcome thresholds (based on literature)
    # Rejection risk: higher when IMPDH inhibition is insufficient
    # Average IMPDH inhibition over dosing interval
    impdh_inhib_rejection_threshold: float = 0.30  # <30% avg inhibition -> rejection risk
    impdh_inhib_target_min: float = 0.30           # minimum desired inhibition
    impdh_inhib_target_max: float = 0.70           # maximum before toxicity concern

    # AUC-based outcome thresholds (total MPA)
    auc_rejection_threshold: float = 30.0   # mg.h/L, below this -> rejection
    auc_toxicity_threshold: float = 60.0    # mg.h/L, above this -> toxicity

    # Free AUC-based thresholds
    auc_free_rejection_threshold: float = 0.9   # mg.h/L
    auc_free_toxicity_threshold: float = 2.8    # mg.h/L

    # Adverse event probabilities (logistic model parameters)
    # GI toxicity: related to total MPA AUC
    gi_tox_auc50: float = 70.0        # AUC at 50% probability of GI symptoms
    gi_tox_gamma: float = 3.0         # steepness

    # Leukopenia: related to average IMPDH inhibition
    leuko_inhib50: float = 0.65       # IMPDH inhibition at 50% leukopenia risk
    leuko_gamma: float = 4.0

    # Infection risk: related to lymphocyte nadir
    infection_lymph_threshold: float = 0.5  # x10^9/L, lymphopenia threshold


def impdh_inhibition(c_free_mpa: float, params: PDParameters = None) -> float:
    """Calculate fractional IMPDH-II inhibition from free MPA concentration.

    Parameters
    ----------
    c_free_mpa : float
        Free (unbound) MPA concentration in mg/L.
    params : PDParameters

    Returns
    -------
    float
        Fractional inhibition (0 to 1).
    """
    if params is None:
        params = PDParameters()

    if c_free_mpa <= 0:
        return 0.0

    inhibition = (params.Emax_impdh * c_free_mpa ** params.gamma_impdh /
                  (params.IC50_impdh_free ** params.gamma_impdh +
                   c_free_mpa ** params.gamma_impdh))
    return float(np.clip(inhibition, 0.0, 1.0))


def impdh_inhibition_profile(c_free_mpa_profile: np.ndarray,
                              params: PDParameters = None) -> np.ndarray:
    """Calculate IMPDH inhibition over a concentration-time profile."""
    if params is None:
        params = PDParameters()
    return np.array([impdh_inhibition(c, params) for c in c_free_mpa_profile])


def average_impdh_inhibition(t: np.ndarray, c_free_mpa: np.ndarray,
                              params: PDParameters = None) -> float:
    """Calculate time-averaged IMPDH inhibition over a dosing interval."""
    inhib_profile = impdh_inhibition_profile(c_free_mpa, params)
    return float(np.trapz(inhib_profile, t) / (t[-1] - t[0]))


def lymphocyte_steady_state(avg_impdh_inhibition: float,
                             params: PDParameters = None) -> float:
    """Estimate steady-state lymphocyte count given average IMPDH inhibition.

    Simplified model: at steady state, proliferation = death
    With IMPDH inhibition reducing proliferation capacity.
    """
    if params is None:
        params = PDParameters()

    # Effective proliferation rate is reduced by IMPDH inhibition
    prolif_effective = params.k_lymph_prolif * (1.0 - avg_impdh_inhibition)
    death_rate = params.k_lymph_death

    if death_rate <= 0:
        return params.lymph_baseline

    # Steady state ratio
    ratio = prolif_effective / death_rate
    lymph_ss = params.lymph_baseline * ratio

    return float(np.clip(lymph_ss, params.lymph_min, params.lymph_baseline * 1.5))


def rejection_probability(avg_impdh_inhibition: float, auc_total: float,
                           params: PDParameters = None) -> float:
    """Estimate acute rejection probability.

    Based on both IMPDH inhibition and AUC thresholds.
    Uses logistic model centered on threshold values.
    """
    if params is None:
        params = PDParameters()

    # IMPDH-based risk (higher risk when inhibition is low)
    risk_impdh = 1.0 / (1.0 + np.exp(10 * (avg_impdh_inhibition - params.impdh_inhib_rejection_threshold)))

    # AUC-based risk
    risk_auc = 1.0 / (1.0 + np.exp(0.15 * (auc_total - params.auc_rejection_threshold)))

    # Combined (take the higher risk)
    # Base rejection rate ~15% with adequate immunosuppression, ~35% without
    base_risk = 0.10
    max_additional_risk = 0.30
    combined_risk = base_risk + max_additional_risk * max(risk_impdh, risk_auc)

    return float(np.clip(combined_risk, 0.0, 1.0))


def gi_toxicity_probability(auc_total: float,
                             params: PDParameters = None) -> float:
    """GI adverse event probability based on total MPA AUC."""
    if params is None:
        params = PDParameters()

    prob = auc_total ** params.gi_tox_gamma / (
        params.gi_tox_auc50 ** params.gi_tox_gamma +
        auc_total ** params.gi_tox_gamma)
    return float(np.clip(prob, 0.0, 1.0))


def leukopenia_probability(avg_impdh_inhibition: float,
                            params: PDParameters = None) -> float:
    """Leukopenia probability based on IMPDH inhibition."""
    if params is None:
        params = PDParameters()

    prob = avg_impdh_inhibition ** params.leuko_gamma / (
        params.leuko_inhib50 ** params.leuko_gamma +
        avg_impdh_inhibition ** params.leuko_gamma)
    return float(np.clip(prob, 0.0, 1.0))


def infection_probability(lymphocyte_count: float,
                           params: PDParameters = None) -> float:
    """Infection risk based on lymphocyte count."""
    if params is None:
        params = PDParameters()

    if lymphocyte_count >= 1.0:
        return 0.05  # baseline risk
    elif lymphocyte_count >= params.infection_lymph_threshold:
        # Linear increase from baseline to moderate risk
        return 0.05 + 0.20 * (1.0 - lymphocyte_count) / (1.0 - params.infection_lymph_threshold)
    else:
        # High risk below threshold
        return 0.25 + 0.35 * (params.infection_lymph_threshold - lymphocyte_count) / params.infection_lymph_threshold


def compute_pd_outcomes(pk_result: dict, pd_params: PDParameters = None) -> dict:
    """Compute all PD outcomes from a steady-state PK simulation result.

    Parameters
    ----------
    pk_result : dict
        Output from simulate_steady_state().
    pd_params : PDParameters

    Returns
    -------
    dict with PD metrics.
    """
    if pd_params is None:
        pd_params = PDParameters()

    t_ss = pk_result['t_ss']
    mpa_free_ss = pk_result['mpa_free_ss']
    auc_total = pk_result['auc_ss_0_12']
    auc_free = pk_result['auc_free_ss_0_12']

    # IMPDH inhibition profile
    inhib_profile = impdh_inhibition_profile(mpa_free_ss, pd_params)
    avg_inhib = average_impdh_inhibition(t_ss, mpa_free_ss, pd_params)
    max_inhib = float(np.max(inhib_profile))
    min_inhib = float(np.min(inhib_profile))

    # Lymphocyte count
    lymph_ss = lymphocyte_steady_state(avg_inhib, pd_params)

    # Clinical outcome probabilities
    p_rejection = rejection_probability(avg_inhib, auc_total, pd_params)
    p_gi_tox = gi_toxicity_probability(auc_total, pd_params)
    p_leukopenia = leukopenia_probability(avg_inhib, pd_params)
    p_infection = infection_probability(lymph_ss, pd_params)

    # Composite safety score (probability of any adverse event)
    p_any_adverse = 1.0 - (1.0 - p_gi_tox) * (1.0 - p_leukopenia) * (1.0 - p_infection)

    # Therapeutic index: efficacy / toxicity balance
    efficacy_score = avg_inhib  # higher = better protection from rejection
    safety_score = 1.0 - p_any_adverse  # higher = safer
    therapeutic_index = efficacy_score * safety_score  # composite (0 to 1)

    # Categorize into clinical outcome zones
    if avg_inhib < pd_params.impdh_inhib_target_min:
        zone = "UNDEREXPOSED"
    elif avg_inhib > pd_params.impdh_inhib_target_max:
        zone = "OVEREXPOSED"
    else:
        zone = "THERAPEUTIC"

    return {
        # IMPDH
        'impdh_profile': inhib_profile,
        'avg_impdh_inhibition': avg_inhib,
        'max_impdh_inhibition': max_inhib,
        'min_impdh_inhibition': min_inhib,
        # Lymphocytes
        'lymphocyte_ss': lymph_ss,
        # Probabilities
        'p_rejection': p_rejection,
        'p_gi_toxicity': p_gi_tox,
        'p_leukopenia': p_leukopenia,
        'p_infection': p_infection,
        'p_any_adverse': p_any_adverse,
        # Composite
        'efficacy_score': efficacy_score,
        'safety_score': safety_score,
        'therapeutic_index': therapeutic_index,
        'clinical_zone': zone,
        # Pass-through PK
        'auc_total': auc_total,
        'auc_free': auc_free,
    }
