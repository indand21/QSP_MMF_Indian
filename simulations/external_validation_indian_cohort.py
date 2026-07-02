# -*- coding: utf-8 -*-
"""
External validation against an Indian renal-transplant AUC cohort (Singh et al. 2025).

Singh et al. (Indian J Urol 2025; PMID 41112717) reported full MPA AUC0-12h at 4 weeks in
120 live-related Indian renal transplant recipients on tacrolimus-based triple therapy:
observed 63.7 +/- 23.1 mg.h/L, 55.8% > 60, BMI 20.8 +/- 3.8, MMF 1.5-2 g/day.

Because the exact 1.5- vs 2-g/day split was not reported, predictions are bracketed by the
all-1.5 g/day (750 mg BID) and all-2 g/day (1000 mg BID) scenarios, plus a representative
50:50 mixture. Also reproduces the manuscript matched-Indian baseline to confirm model parity.
"""
import os
import sys
import numpy as np
import warnings

warnings.filterwarnings("ignore")

# Resolve project root relative to this file so the script is portable.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from model.mpa_pbpk import PKParameters, DrugParameters, simulate_steady_state
from populations.virtual_populations import (PopulationDistributions,
                                             generate_virtual_population)

pk, drug = PKParameters(), DrugParameters()


def sim_pop(pop, dose_mg, n=500, seed=42, force_tac=True):
    pats = generate_virtual_population(pop, n=n, seed=seed)
    if force_tac:
        for p in pats:
            p.cni_type = "tacrolimus"
    aucs = []
    for p in pats:
        try:
            r = simulate_steady_state(dose_mg=dose_mg, patient=p, pk_params=pk,
                                      drug_params=drug, n_doses=14, tau=12.0)
            aucs.append(r["auc_ss_0_12"])
        except Exception:
            pass
    return np.array(aucs)


MATCHED_INDIAN = PopulationDistributions(
    name="Matched Indian (manuscript)",
    wt_mean=58.0, wt_sd=12.0, wt_min=35.0, wt_max=110.0,
    ht_mean=163.0, ht_sd=8.5,
    alb_mean=4.0, alb_sd=0.4, alb_min=2.5, alb_max=5.5,
    gfr_mean=50.0, gfr_sd=18.0, gfr_min=15.0, gfr_max=110.0,
    prop_tacrolimus=0.93,
    ugt1a9_mean=0.95, ugt1a9_sd=0.18,
    ugt2b7_mean=0.92, ugt2b7_sd=0.20,
    abcc2_mean=0.97, abcc2_sd=0.18,
)

# Singh-matched cohort: weight ~57 kg from BMI 20.8 at height ~165 cm; 100% tacrolimus;
# albumin 4.0 g/dL (4-week post-transplant, matched assumption); eGFR for good early graft.
SINGH = PopulationDistributions(
    name="Singh-matched",
    wt_mean=57.0, wt_sd=11.0, wt_min=38.0, wt_max=95.0,
    ht_mean=165.0, ht_sd=8.0,
    alb_mean=4.0, alb_sd=0.4, alb_min=2.5, alb_max=5.5,
    gfr_mean=60.0, gfr_sd=18.0, gfr_min=15.0, gfr_max=120.0,
    prop_tacrolimus=1.0,
    ugt1a9_mean=0.95, ugt1a9_sd=0.18,
    ugt2b7_mean=0.92, ugt2b7_sd=0.20,
    abcc2_mean=0.97, abcc2_sd=0.18,
)

OBSERVED_MEAN = 63.7  # mg.h/L (Singh et al. 2025)


def main():
    a = sim_pop(MATCHED_INDIAN, 1000)
    print(f"[Parity] Matched Indian, 1000 mg BID: mean AUC = {a.mean():.1f} +/- {a.std():.1f} "
          f"(manuscript 75.1 +/- 27.2); >60: {100 * np.mean(a > 60):.1f}% (manuscript 68.0%)")

    for dose, lab in [(750, "1.5 g/day (750 BID)"), (1000, "2 g/day (1000 BID)")]:
        a = sim_pop(SINGH, dose)
        print(f"[Singh] {lab}: pred {a.mean():.1f} +/- {a.std():.1f}, FE={a.mean() / OBSERVED_MEAN:.2f}, "
              f">60: {100 * np.mean(a > 60):.1f}%, "
              f"30-60: {100 * np.mean((a >= 30) & (a <= 60)):.1f}%, <30: {100 * np.mean(a < 30):.1f}%")

    pats = generate_virtual_population(SINGH, n=500, seed=7)
    for p in pats:
        p.cni_type = "tacrolimus"
    rng = np.random.default_rng(7)
    doses = rng.choice([750, 1000], size=len(pats), p=[0.5, 0.5])
    aucs = []
    for p, d in zip(pats, doses):
        try:
            r = simulate_steady_state(dose_mg=float(d), patient=p, pk_params=pk,
                                      drug_params=drug, n_doses=14, tau=12.0)
            aucs.append(r["auc_ss_0_12"])
        except Exception:
            pass
    aucs = np.array(aucs)
    print(f"[Singh] MIXED 50/50 (750/1000 BID): pred {aucs.mean():.1f} +/- {aucs.std():.1f}, "
          f"FE={aucs.mean() / OBSERVED_MEAN:.2f}, >60: {100 * np.mean(aucs > 60):.1f}%, "
          f"30-60: {100 * np.mean((aucs >= 30) & (aucs <= 60)):.1f}%, <30: {100 * np.mean(aucs < 30):.1f}%")
    print(f"Observed (Singh et al. 2025): {OBSERVED_MEAN} +/- 23.1, >60: 55.8%, 30-60: 33.4%, <30: 10.8%")


if __name__ == "__main__":
    main()
