# -*- coding: utf-8 -*-
"""
Residual weight-dependence and dose-inflation analysis.

Quantifies (1) the realized mg/kg delivered by fixed 1 g BID in Western vs Indian cohorts,
(2) the AUC-vs-weight relationship under fixed vs weight-based dosing (log-log slope; allometry
would leave a small positive residual, but the full model flattens it to ~0), and (3) the
residual CV% and off-target fraction that weight-based dosing leaves behind. This supports the
manuscript argument that body weight governs the between-population mean while UGT1A9 governs
the within-population spread.
"""
import os
import sys
import numpy as np
import warnings

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from model.mpa_pbpk import PKParameters, DrugParameters, simulate_steady_state
from populations.virtual_populations import (PopulationDistributions,
                                             generate_virtual_population)

pk, drug = PKParameters(), DrugParameters()

MATCHED_INDIAN = PopulationDistributions(
    name="Matched Indian", wt_mean=58.0, wt_sd=12.0, wt_min=35.0, wt_max=110.0,
    ht_mean=163.0, ht_sd=8.5, alb_mean=4.0, alb_sd=0.4, alb_min=2.5, alb_max=5.5,
    gfr_mean=50.0, gfr_sd=18.0, gfr_min=15.0, gfr_max=110.0, prop_tacrolimus=0.93,
    ugt1a9_mean=0.95, ugt1a9_sd=0.18, ugt2b7_mean=0.92, ugt2b7_sd=0.20,
    abcc2_mean=0.97, abcc2_sd=0.18)
MATCHED_WESTERN = PopulationDistributions(
    name="Matched Western", wt_mean=78.0, wt_sd=15.0, wt_min=45.0, wt_max=140.0,
    ht_mean=172.0, ht_sd=9.0, alb_mean=4.0, alb_sd=0.4, alb_min=2.5, alb_max=5.5,
    gfr_mean=55.0, gfr_sd=18.0, gfr_min=15.0, gfr_max=120.0, prop_tacrolimus=0.93,
    ugt1a9_mean=1.0, ugt1a9_sd=0.15, ugt2b7_mean=1.0, ugt2b7_sd=0.15,
    abcc2_mean=1.0, abcc2_sd=0.15)


def run(pop, dose_fn, n=500, seed=42):
    pats = generate_virtual_population(pop, n=n, seed=seed)
    wt, auc, dose = [], [], []
    for p in pats:
        d = dose_fn(p.body_weight)
        try:
            r = simulate_steady_state(dose_mg=float(d), patient=p, pk_params=pk,
                                      drug_params=drug, n_doses=14, tau=12.0)
            wt.append(p.body_weight)
            auc.append(r["auc_ss_0_12"])
            dose.append(d)
        except Exception:
            pass
    return np.array(wt), np.array(auc), np.array(dose)


def nomogram(bw):
    return 500 if bw < 50 else (750 if bw < 75 else 1000)


def summ(tag, wt, auc, dose):
    b, _ = np.polyfit(np.log(wt), np.log(auc), 1)  # log-log slope = exponent
    r = np.corrcoef(wt, auc)[0, 1]
    mgkg = dose / wt
    print(f"{tag}")
    print(f"   realized mg/kg: {mgkg.mean():.1f} +/- {mgkg.std():.1f}")
    print(f"   mean AUC {auc.mean():.1f} (CV {100 * auc.std() / auc.mean():.1f}%) | "
          f"on-target {100 * np.mean((auc >= 30) & (auc <= 60)):.1f}% | >60 {100 * np.mean(auc > 60):.1f}%")
    print(f"   AUC~BW exponent (log-log slope) b = {b:+.2f} | Pearson r(BW,AUC) = {r:+.2f}")


def main():
    print("=== FIXED 1000 mg BID ===")
    summ("Western fixed 1000", *run(MATCHED_WESTERN, lambda bw: 1000))
    summ("Indian fixed 1000", *run(MATCHED_INDIAN, lambda bw: 1000))
    print("\n=== WEIGHT-BASED 12 mg/kg BID (exact, continuous) ===")
    summ("Indian 12 mg/kg exact", *run(MATCHED_INDIAN, lambda bw: 12.0 * bw))
    print("\n=== WEIGHT-BASED nomogram (500/750/1000 bands) ===")
    summ("Indian nomogram", *run(MATCHED_INDIAN, nomogram))
    print("\nNote: 1000 / 78 = %.1f mg/kg" % (1000 / 78))


if __name__ == "__main__":
    main()
