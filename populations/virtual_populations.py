"""
Virtual Population Generator for MPA PBPK Simulations
======================================================
Generates virtual patient populations for:
1. Western (reference) - based on US/European transplant demographics
2. Indian - based on Indian anthropometric and clinical data

Population parameters are sampled from published distributions.

Data sources:
- NFHS-5 (India): body weight, height distributions
- ICMR anthropometric data
- Published Indian transplant cohort studies
- Western reference: NHANES, European transplant registries
"""

import numpy as np
from dataclasses import dataclass
from typing import List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.mpa_pbpk import PatientParameters


@dataclass
class PopulationDistributions:
    """Distribution parameters for a virtual population."""
    name: str

    # Body weight: mean, sd (kg) - truncated normal
    wt_mean: float
    wt_sd: float
    wt_min: float = 35.0
    wt_max: float = 150.0

    # Height: mean, sd (cm)
    ht_mean: float = 170.0
    ht_sd: float = 8.0

    # Serum albumin: mean, sd (g/dL)
    alb_mean: float = 4.0
    alb_sd: float = 0.4
    alb_min: float = 2.0
    alb_max: float = 5.5

    # GFR post-transplant: mean, sd (mL/min)
    gfr_mean: float = 55.0
    gfr_sd: float = 15.0
    gfr_min: float = 15.0
    gfr_max: float = 120.0

    # CNI type: proportion on tacrolimus (rest on cyclosporine)
    prop_tacrolimus: float = 0.70

    # UGT1A9 relative activity: mean, sd (1.0 = wild-type)
    ugt1a9_mean: float = 1.0
    ugt1a9_sd: float = 0.15

    # UGT2B7 relative activity: mean, sd
    ugt2b7_mean: float = 1.0
    ugt2b7_sd: float = 0.15

    # ABCC2/MRP2 relative activity: mean, sd
    abcc2_mean: float = 1.0
    abcc2_sd: float = 0.15


# ============================================================
# WESTERN REFERENCE POPULATION
# Based on US/European renal transplant registries
# ============================================================
WESTERN_POPULATION = PopulationDistributions(
    name="Western (US/European)",
    # Body weight: typical Western transplant recipient
    wt_mean=78.0,
    wt_sd=15.0,
    wt_min=45.0,
    wt_max=140.0,
    # Height
    ht_mean=172.0,
    ht_sd=9.0,
    # Albumin: generally well-nourished, post-transplant recovery
    alb_mean=4.0,
    alb_sd=0.4,
    alb_min=2.5,
    alb_max=5.5,
    # GFR
    gfr_mean=55.0,
    gfr_sd=18.0,
    gfr_min=15.0,
    gfr_max=120.0,
    # CNI: ~70% tacrolimus in modern Western practice
    prop_tacrolimus=0.70,
    # UGT activity (reference)
    ugt1a9_mean=1.0,
    ugt1a9_sd=0.15,
    ugt2b7_mean=1.0,
    ugt2b7_sd=0.15,
    abcc2_mean=1.0,
    abcc2_sd=0.15,
)

# ============================================================
# INDIAN POPULATION
# Based on:
# - NFHS-5 adult anthropometric data
# - Indian transplant cohort studies (PGIMER, AIIMS, CMC Vellore)
# - Koloskoff et al. 2024 (Indian LN patients)
# - Yau & Vathsala 2007 (Asian transplant data)
# ============================================================
INDIAN_POPULATION = PopulationDistributions(
    name="Indian",
    # Body weight: Indian adults significantly lower
    # NFHS-5: mean BMI ~24, avg height ~165cm male, ~153cm female
    # Male transplant recipients: ~60-65 kg typical
    # Female: ~50-55 kg
    # Combined estimate for transplant cohort
    wt_mean=58.0,
    wt_sd=12.0,
    wt_min=35.0,
    wt_max=110.0,
    # Height: lower average
    ht_mean=163.0,
    ht_sd=8.5,
    # Albumin: often lower due to CKD burden, nutritional status
    # Indian transplant cohorts report 3.2-3.8 g/dL commonly
    alb_mean=3.5,
    alb_sd=0.5,
    alb_min=2.0,
    alb_max=5.0,
    # GFR: similar post-transplant, but Indian CKD patients
    # often present later with lower baseline function
    gfr_mean=50.0,
    gfr_sd=18.0,
    gfr_min=15.0,
    gfr_max=110.0,
    # CNI: India has shifted heavily to tacrolimus-based regimens
    # ~85-90% tacrolimus in modern Indian transplant practice
    prop_tacrolimus=0.88,
    # UGT activity: limited Indian-specific data
    # UGT2B7*2 frequency ~30% in South Asians (may have altered activity)
    # Conservative: slight reduction in mean activity
    ugt1a9_mean=0.95,
    ugt1a9_sd=0.18,
    ugt2b7_mean=0.92,
    ugt2b7_sd=0.20,
    # ABCC2: limited data, assume similar with slightly more variability
    abcc2_mean=0.97,
    abcc2_sd=0.18,
)


def _truncated_normal(mean: float, sd: float, low: float, high: float,
                      size: int, rng: np.random.Generator) -> np.ndarray:
    """Sample from truncated normal distribution."""
    samples = rng.normal(mean, sd, size * 3)  # oversample
    samples = samples[(samples >= low) & (samples <= high)]
    while len(samples) < size:
        extra = rng.normal(mean, sd, size)
        extra = extra[(extra >= low) & (extra <= high)]
        samples = np.concatenate([samples, extra])
    return samples[:size]


def generate_virtual_population(pop_dist: PopulationDistributions,
                                n: int = 1000,
                                seed: int = 42) -> List[PatientParameters]:
    """Generate a virtual population of patients.

    Parameters
    ----------
    pop_dist : PopulationDistributions
        Population distribution parameters.
    n : int
        Number of virtual patients.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    List of PatientParameters, one per virtual patient.
    """
    rng = np.random.default_rng(seed)

    # Sample parameters
    weights = _truncated_normal(pop_dist.wt_mean, pop_dist.wt_sd,
                                pop_dist.wt_min, pop_dist.wt_max, n, rng)
    heights = _truncated_normal(pop_dist.ht_mean, pop_dist.ht_sd,
                                140.0, 200.0, n, rng)
    albumins = _truncated_normal(pop_dist.alb_mean, pop_dist.alb_sd,
                                 pop_dist.alb_min, pop_dist.alb_max, n, rng)
    gfrs = _truncated_normal(pop_dist.gfr_mean, pop_dist.gfr_sd,
                             pop_dist.gfr_min, pop_dist.gfr_max, n, rng)

    # CNI type (binary)
    cni_types = rng.choice(
        ["tacrolimus", "cyclosporine"],
        size=n,
        p=[pop_dist.prop_tacrolimus, 1 - pop_dist.prop_tacrolimus]
    )

    # UGT activities (log-normal to avoid negatives)
    ugt1a9 = np.exp(rng.normal(
        np.log(pop_dist.ugt1a9_mean), pop_dist.ugt1a9_sd, n))
    ugt2b7 = np.exp(rng.normal(
        np.log(pop_dist.ugt2b7_mean), pop_dist.ugt2b7_sd, n))
    abcc2 = np.exp(rng.normal(
        np.log(pop_dist.abcc2_mean), pop_dist.abcc2_sd, n))

    patients = []
    for i in range(n):
        p = PatientParameters(
            body_weight=round(weights[i], 1),
            height=round(heights[i], 1),
            albumin=round(albumins[i], 2),
            gfr=round(gfrs[i], 1),
            cni_type=cni_types[i],
            ugt1a9_activity=round(float(ugt1a9[i]), 3),
            ugt2b7_activity=round(float(ugt2b7[i]), 3),
            abcc2_activity=round(float(abcc2[i]), 3),
        )
        patients.append(p)

    return patients


def summarize_population(patients: List[PatientParameters], name: str = "") -> dict:
    """Compute summary statistics for a virtual population."""
    wts = [p.body_weight for p in patients]
    albs = [p.albumin for p in patients]
    gfrs = [p.gfr for p in patients]
    tac_pct = sum(1 for p in patients if p.cni_type == "tacrolimus") / len(patients) * 100

    summary = {
        'name': name,
        'n': len(patients),
        'weight_mean': np.mean(wts),
        'weight_sd': np.std(wts),
        'weight_median': np.median(wts),
        'albumin_mean': np.mean(albs),
        'albumin_sd': np.std(albs),
        'gfr_mean': np.mean(gfrs),
        'gfr_sd': np.std(gfrs),
        'tacrolimus_pct': tac_pct,
    }
    return summary


def print_population_summary(patients: List[PatientParameters], name: str = ""):
    """Print formatted summary of population characteristics."""
    s = summarize_population(patients, name)
    print(f"\n{'='*60}")
    print(f"  Virtual Population: {s['name']} (n={s['n']})")
    print(f"{'='*60}")
    print(f"  Body Weight:    {s['weight_mean']:.1f} +/- {s['weight_sd']:.1f} kg "
          f"(median {s['weight_median']:.1f})")
    print(f"  Albumin:        {s['albumin_mean']:.2f} +/- {s['albumin_sd']:.2f} g/dL")
    print(f"  GFR:            {s['gfr_mean']:.1f} +/- {s['gfr_sd']:.1f} mL/min")
    print(f"  Tacrolimus use: {s['tacrolimus_pct']:.0f}%")
    print(f"{'='*60}\n")
