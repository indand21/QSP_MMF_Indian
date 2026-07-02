# QSP_MMF_Indian

Quantitative systems pharmacology (QSP) / PBPK–PD model of **mycophenolic acid (MPA)** exposure in
renal transplant recipients, developed to study **weight-driven overexposure in low-body-weight
(e.g. Indian) populations** and to evaluate weight-based dosing versus therapeutic drug monitoring.

This repository contains the model code, virtual-population generator, and analysis scripts that
reproduce the figures, tables, and validation reported in the accompanying manuscript:

> *Disentangling Body Weight from UGT1A9 Variability in Mycophenolic Acid Exposure: A Quantitative
> Systems Pharmacology Basis for Weight-Based Dosing and Monitoring in Low-Body-Weight Transplant
> Recipients.* Pattanaik S, Kenwar DB, Singh S, Sharma A, Anil A, Srinivasan A.

## Key findings the code reproduces

- Fixed 1 g twice-daily MMF delivers a **~35% higher milligram-per-kilogram dose** to lean Indian
  recipients (17.8 vs 13.2 mg/kg), so ~68% exceed the 30–60 mg·h/L AUC target.
- **Body weight governs the between-population mean shift**; **UGT1A9 activity governs the
  within-population variability** (≈73% of explained variance).
- Weight-based dosing (12 mg/kg BID) flattens the AUC–weight relationship (log-log slope
  −0.89 → ≈0) and restores the mean, but leaves CV% ≈34% and ~1/3 off-target — hence weight
  normalization is *necessary but not sufficient*, and AUC-guided TDM remains essential.
- The model reproduces an independent Indian transplant AUC cohort (Singh et al. 2025;
  observed 63.7 mg·h/L) with a **fold error of 1.11** once the cohort's mixed 1.5–2 g/day dosing
  is represented.

## Repository layout

```
model/
  mpa_pbpk.py        Semi-mechanistic PBPK model (2-compartment disposition, UGT metabolism,
                     enterohepatic recirculation, allometric scaling, well-stirred hepatic CL)
  mpa_pd.py          Pharmacodynamics: IMPDH-II inhibition (sigmoidal Emax) + clinical outcomes
populations/
  virtual_populations.py   Western/Indian virtual-population generators (weight, albumin, eGFR,
                           CNI type, UGT1A9/UGT2B7/ABCC2 activity)
simulations/
  run_population_comparison.py       Western vs Indian exposure at fixed 1 g BID
  run_pkpd_comparison.py             Linked PK/PD outcomes and therapeutic index
  run_validation.py                  Validation vs published Western/Chinese/Thai PK studies
  external_validation_indian_cohort.py   External validation vs Singh et al. 2025 (Indian cohort)
  residual_weight_dependence.py      Dose-inflation + residual weight-dependence analysis
  run_dose_optimization.py           Weight-based dosing / nomogram derivation
  run_variability_decomposition.py   Variance/partial-correlation decomposition of AUC variability
  run_parameter_sensitivity.py       Local +/-20% parameter-uncertainty sensitivity analysis
  run_sensitivity_albumin_cni.py     Albumin/CNI matched-scenario sensitivity check
  run_scenario_indian_young.py       Additional lean/young-recipient scenario
  generate_manuscript_figures.py     Regenerates the main figures (Fig1-4) and Table1/Table2
figures/             Main manuscript figures (Fig1-4, publication TIFFs) and analysis PNGs
results/             Numerical result tables (demographics, PK/PD outcomes, validation,
                     PK/PD parameter tables)
docs/
  literature_review_MPA_Indian_PK.md   Parameter sourcing and clinical-evidence review
requirements.txt     Pinned dependencies
```

## Figures and results

Precomputed **figures** (`figures/`) and **result tables** (`results/`) are included so the main
outputs can be inspected without rerunning the pipeline:

- `figures/Fig1-4.tif` — the four main manuscript figures (PK comparison, dose optimization,
  PK/PD outcomes, model validation), plus supporting analysis PNGs.
- `results/Table1_Demographics.txt`, `Table2_PKPD_Results.txt`, `Table3_Validation.txt`,
  `TableS1_PD_Parameters.txt`, `TableS2_PK_Parameters.txt` — the numerical results underlying the
  manuscript tables.

Everything in `figures/` and `results/` is regenerable from the scripts in `simulations/`.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requires Python 3.9+ (developed on 3.9–3.12).

## Reproducing the results

Run from the repository root so the package imports resolve:

```bash
python simulations/run_population_comparison.py
python simulations/run_pkpd_comparison.py
python simulations/run_validation.py
python simulations/external_validation_indian_cohort.py
python simulations/residual_weight_dependence.py
python simulations/run_dose_optimization.py
python simulations/run_variability_decomposition.py
python simulations/run_parameter_sensitivity.py
```

The two analyses added for the manuscript revision are self-contained and print their results to
stdout:

- `external_validation_indian_cohort.py` — external validation against the Singh et al. (2025)
  Indian renal-transplant cohort, with dose-bracketed predictions and fold errors.
- `residual_weight_dependence.py` — the realized mg/kg dose inflation and the residual
  AUC–weight dependence under fixed vs weight-based dosing.

## Model summary

- **PK**: first-order absorption with lag; two-compartment disposition; UGT1A9/UGT2B7 hepatic
  metabolism via the well-stirred equation; albumin- and MPAG-dependent free fraction; ABCC2/MRP2
  enterohepatic recirculation; renal MPAG elimination; allometric scaling (V proportional to BW^1.0,
  CL proportional to BW^0.75, liver weight to BW^0.86). Solved with an adaptive-step LSODA
  integrator to steady state.
- **PD**: sigmoidal Emax IMPDH-II inhibition (IC50 = 0.15 mg/L free MPA, gamma = 1.5) linked to
  phenomenological rejection, GI-toxicity, leukopenia, and infection probabilities, and a composite
  therapeutic index.

## Citation

If you use this code, please cite the manuscript above.

## License

Released under the MIT License (see `LICENSE`).
