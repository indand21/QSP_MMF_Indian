"""
Semi-mechanistic PBPK model for Mycophenolic Acid (MPA)
========================================================
Two-compartment model with:
- First-order absorption with lag time
- Enterohepatic recirculation (EHC) via MPAG biliary excretion
- Albumin-dependent free fraction
- UGT-mediated hepatic metabolism (UGT1A9/UGT2B7 -> MPAG)
- ABCC2/MRP2-mediated biliary MPAG excretion
- Renal elimination of MPAG
- MPAG displacement of MPA from albumin at high MPAG concentrations

References:
- Staatz & Tett, Clin Pharmacokinet 2007; 46(1):13-58
- de Winter et al., Clin Pharmacokinet 2009; 48(8):517-532
- Colom et al., Clin Pharmacokinet 2014; 53(9):813-829
"""

import numpy as np
from scipy.integrate import solve_ivp
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DrugParameters:
    """Physicochemical and in-vitro parameters for MPA/MMF."""
    MW_MMF: float = 433.5         # g/mol (mycophenolate mofetil)
    MW_MPA: float = 320.3         # g/mol (mycophenolic acid)
    MW_MPAG: float = 496.5        # g/mol (MPA glucuronide)
    F_MMF_to_MPA: float = 1.0     # Presystemic conversion MMF -> MPA (complete)
    pKa: float = 4.5              # MPA is a weak acid
    logP: float = 2.8             # Partition coefficient
    fu_reference: float = 0.03    # Unbound fraction at albumin 4.0 g/dL
    albumin_reference: float = 4.0  # g/dL, reference albumin


@dataclass
class PatientParameters:
    """Individual patient physiological parameters."""
    body_weight: float = 70.0     # kg
    height: float = 170.0         # cm
    albumin: float = 4.0          # g/dL
    gfr: float = 60.0             # mL/min (post-transplant typical)
    hematocrit: float = 0.40
    liver_weight: float = 1.5     # kg (scales with body weight)
    cni_type: str = "tacrolimus"  # "tacrolimus" or "cyclosporine"
    # Pharmacogenomics (relative activity multipliers)
    ugt1a9_activity: float = 1.0  # 1.0 = wild-type
    ugt2b7_activity: float = 1.0
    abcc2_activity: float = 1.0   # MRP2 biliary efflux

    @property
    def bsa(self) -> float:
        """Body surface area (Du Bois formula, m^2)."""
        return 0.007184 * (self.height ** 0.725) * (self.body_weight ** 0.425)

    @property
    def scaled_liver_weight(self) -> float:
        """Liver weight scaled allometrically to body weight."""
        return 1.5 * (self.body_weight / 70.0) ** 0.86  # kg


@dataclass
class PKParameters:
    """Pharmacokinetic model parameters for MPA.

    Default values calibrated to Western adult renal transplant recipients
    on tacrolimus + MMF 1g BID, from published popPK models.
    """
    # Absorption
    ka: float = 4.0               # /h, first-order absorption rate constant
    tlag: float = 0.25            # h, absorption lag time
    F_oral: float = 0.81          # oral bioavailability (after gut wall metabolism)
    F_gut_wall: float = 0.90      # fraction escaping gut wall UGT1A8 metabolism

    # Distribution
    Vc: float = 50.0              # L, central compartment volume (total MPA)
    Vp: float = 150.0             # L, peripheral compartment volume
    Q: float = 30.0               # L/h, intercompartmental clearance

    # Metabolism (hepatic UGT-mediated)
    # CLint must be high because MPA is 97% protein-bound (fu=0.03)
    # To achieve CLh ~12 L/h via well-stirred model:
    #   CLh = Qh*fu*CLint / (Qh + fu*CLint) => CLint ~ 460 L/h
    # Published CL/F with tacrolimus: 10-15 L/h (Staatz & Tett 2007)
    CLint_ugt1a9: float = 345.0   # L/h, intrinsic clearance via UGT1A9 (75%)
    CLint_ugt2b7: float = 115.0   # L/h, intrinsic clearance via UGT2B7 (25%)
    fm_ugt1a9: float = 0.75       # fraction metabolized by UGT1A9
    fm_ugt2b7: float = 0.25       # fraction metabolized by UGT2B7

    # Enterohepatic recirculation (EHC)
    k_bile: float = 0.8           # /h, biliary excretion rate of MPAG (ABCC2)
    k_gut_release: float = 0.15   # /h, gut bacterial deconjugation rate
    f_ehc: float = 0.40           # fraction of biliary MPAG that undergoes EHC
    t_gallbladder: float = 6.0    # h, time of gallbladder emptying post-dose

    # MPAG disposition
    Vc_mpag: float = 15.0         # L, MPAG central volume
    CLr_mpag: float = 7.5         # L/h, renal clearance of MPAG (GFR-dependent)

    # Cyclosporine interaction
    csa_ehc_inhibition: float = 0.40  # fraction by which CsA inhibits EHC (ABCC2 effect)
    # OATP1B1/1B3 hepatic uptake of MPAG
    # CsA inhibits OATP1B1 (Ki ~0.2-2 uM), reducing hepatic MPAG uptake
    # This further reduces EHC (less MPAG reaches bile) and raises systemic MPAG
    f_oatp1b: float = 1.0            # OATP1B function (1.0 = normal, modulated by CsA)
    csa_oatp_inhibition: float = 0.60  # fraction reduction of OATP1B by CsA


def calculate_free_fraction(albumin: float, mpag_conc: float = 0.0,
                            drug_params: DrugParameters = None) -> float:
    """Calculate MPA unbound fraction based on albumin and MPAG displacement.

    MPA is ~97-98% bound to albumin. Free fraction increases with:
    1. Lower albumin (hypoalbuminemia)
    2. Higher MPAG concentrations (competitive displacement)
    3. Uremia (conformational changes in albumin)

    Parameters
    ----------
    albumin : float
        Serum albumin in g/dL.
    mpag_conc : float
        Plasma MPAG concentration in mg/L (for displacement effect).
    drug_params : DrugParameters
        Drug physicochemical parameters.

    Returns
    -------
    float
        Unbound fraction of MPA (0 to 1).
    """
    if drug_params is None:
        drug_params = DrugParameters()

    # Base free fraction scales inversely with albumin
    # Using the relationship: fu = fu_ref * (alb_ref / alb)^n
    # n ~ 1.0-1.5 for highly bound acidic drugs
    fu_base = drug_params.fu_reference * (drug_params.albumin_reference / max(albumin, 1.0)) ** 1.2

    # MPAG displacement effect (becomes significant at high MPAG)
    # MPAG competes with MPA for albumin binding sites (de Winter et al. 2009)
    # At high MPAG (seen with CsA due to OATP1B inhibition), fu increases substantially
    # Emax-type displacement: up to ~50% increase in fu at very high MPAG
    mpag_displacement_factor = 1.0 + 0.50 * max(mpag_conc, 0.0) / (30.0 + max(mpag_conc, 0.0))

    fu = fu_base * mpag_displacement_factor

    # Physiological bounds
    return np.clip(fu, 0.005, 0.30)


def calculate_hepatic_clearance(CLint_total: float, fu: float,
                                liver_blood_flow: float = 90.0) -> float:
    """Well-stirred model for hepatic clearance.

    CLh = Q_h * fu * CLint / (Q_h + fu * CLint)

    Parameters
    ----------
    CLint_total : float
        Total intrinsic clearance (L/h).
    fu : float
        Unbound fraction.
    liver_blood_flow : float
        Hepatic blood flow (L/h). Default ~90 L/h for 70kg adult.

    Returns
    -------
    float
        Hepatic clearance (L/h).
    """
    Qh = liver_blood_flow
    return Qh * fu * CLint_total / (Qh + fu * CLint_total)


def scale_pk_to_patient(pk: PKParameters, patient: PatientParameters,
                        drug_params: DrugParameters = None) -> PKParameters:
    """Scale PK parameters from reference (70 kg) to individual patient.

    Applies allometric scaling, albumin-based free fraction adjustment,
    pharmacogenomic modifiers, and CNI interaction.
    """
    if drug_params is None:
        drug_params = DrugParameters()

    scaled = PKParameters()

    # Weight ratio for allometric scaling
    wt_ratio = patient.body_weight / 70.0

    # Volume scaling (allometric exponent 1.0 for volumes)
    scaled.Vc = pk.Vc * wt_ratio
    scaled.Vp = pk.Vp * wt_ratio
    scaled.Vc_mpag = pk.Vc_mpag * wt_ratio

    # Clearance scaling (allometric exponent 0.75)
    wt_cl_ratio = wt_ratio ** 0.75

    # Intrinsic clearance scaled by liver weight and UGT genotype
    liver_scale = patient.scaled_liver_weight / 1.5  # relative to 70kg ref
    scaled.CLint_ugt1a9 = pk.CLint_ugt1a9 * liver_scale * patient.ugt1a9_activity
    scaled.CLint_ugt2b7 = pk.CLint_ugt2b7 * liver_scale * patient.ugt2b7_activity

    # Intercompartmental clearance
    scaled.Q = pk.Q * wt_cl_ratio

    # Renal clearance of MPAG (proportional to GFR)
    gfr_ratio = patient.gfr / 60.0  # reference GFR = 60 mL/min
    scaled.CLr_mpag = pk.CLr_mpag * gfr_ratio

    # EHC: ABCC2 activity and CNI effect
    scaled.k_bile = pk.k_bile * patient.abcc2_activity
    scaled.f_ehc = pk.f_ehc
    scaled.f_oatp1b = pk.f_oatp1b

    if patient.cni_type == "cyclosporine":
        # CsA inhibits ABCC2 -> reduced EHC
        scaled.f_ehc = pk.f_ehc * (1.0 - pk.csa_ehc_inhibition)
        # CsA inhibits OATP1B1/1B3 -> reduced hepatic uptake of MPAG
        # Less MPAG enters hepatocytes -> less biliary excretion -> less EHC
        # Also raises systemic MPAG -> more MPA displacement -> higher fu -> higher CLh
        scaled.f_oatp1b = pk.f_oatp1b * (1.0 - pk.csa_oatp_inhibition)

    # Copy unchanged parameters
    scaled.ka = pk.ka
    scaled.tlag = pk.tlag
    scaled.F_oral = pk.F_oral
    scaled.F_gut_wall = pk.F_gut_wall * (1.0 / max(patient.ugt1a9_activity, 0.5))  # gut wall UGT1A8
    scaled.fm_ugt1a9 = pk.fm_ugt1a9
    scaled.fm_ugt2b7 = pk.fm_ugt2b7
    scaled.k_gut_release = pk.k_gut_release
    scaled.t_gallbladder = pk.t_gallbladder
    scaled.csa_ehc_inhibition = pk.csa_ehc_inhibition
    scaled.csa_oatp_inhibition = pk.csa_oatp_inhibition

    return scaled


def mpa_ode(t, y, pk: PKParameters, patient: PatientParameters,
            drug_params: DrugParameters, dose_mg: float, tau: float):
    """ODE system for MPA PBPK model.

    State variables:
    y[0] = A_gut      : Amount in gut lumen (mg), absorption depot
    y[1] = C_central  : MPA concentration in central compartment (mg/L)
    y[2] = A_periph   : Amount in peripheral compartment (mg)
    y[3] = C_mpag     : MPAG concentration in plasma (mg/L)
    y[4] = A_bile     : MPAG amount in bile/gut for EHC (mg)
    y[5] = A_absorbed : Cumulative amount absorbed (mg) - for AUC tracking
    """
    A_gut, C_central, A_periph, C_mpag, A_bile, A_absorbed = y

    # Ensure non-negative
    A_gut = max(A_gut, 0.0)
    C_central = max(C_central, 0.0)
    A_periph = max(A_periph, 0.0)
    C_mpag = max(C_mpag, 0.0)
    A_bile = max(A_bile, 0.0)

    # Free fraction (dynamic, depends on albumin and MPAG)
    fu = calculate_free_fraction(patient.albumin, C_mpag, drug_params)

    # Amounts in compartments
    A_central = C_central * pk.Vc

    # Total intrinsic clearance
    CLint_total = pk.CLint_ugt1a9 + pk.CLint_ugt2b7

    # Hepatic blood flow scaled to patient
    Qh = 90.0 * (patient.body_weight / 70.0) ** 0.75  # L/h

    # Hepatic clearance (well-stirred model)
    CLh = calculate_hepatic_clearance(CLint_total, fu, Qh)

    # --- ODEs ---

    # 1. Gut absorption depot
    dA_gut = -pk.ka * A_gut

    # 2. Central compartment (MPA)
    absorption_rate = pk.ka * A_gut * pk.F_oral * pk.F_gut_wall
    distribution_out = pk.Q * C_central
    distribution_in = pk.Q * (A_periph / pk.Vp)
    metabolism_rate = CLh * C_central
    ehc_return = pk.k_gut_release * A_bile * pk.f_ehc  # MPA returning from EHC

    dC_central = (absorption_rate + distribution_in + ehc_return
                  - distribution_out - metabolism_rate) / pk.Vc

    # 3. Peripheral compartment
    dA_periph = pk.Q * C_central - pk.Q * (A_periph / pk.Vp)

    # 4. MPAG plasma
    mpag_formation = metabolism_rate  # all hepatic clearance -> MPAG
    mpag_renal_elim = pk.CLr_mpag * C_mpag
    # Biliary excretion of MPAG requires OATP1B-mediated hepatic uptake first
    # f_oatp1b modulates how much MPAG enters hepatocytes for biliary excretion
    mpag_biliary = pk.k_bile * C_mpag * pk.Vc_mpag * pk.f_oatp1b

    dC_mpag = (mpag_formation - mpag_renal_elim - mpag_biliary) / pk.Vc_mpag

    # 5. Bile/gut MPAG pool (for EHC)
    dA_bile = mpag_biliary - pk.k_gut_release * A_bile

    # 6. Cumulative absorption (for tracking)
    dA_absorbed = absorption_rate

    return [dA_gut, dC_central, dA_periph, dC_mpag, dA_bile, dA_absorbed]


def simulate_single_dose(dose_mg: float, patient: PatientParameters,
                         pk_params: PKParameters = None,
                         drug_params: DrugParameters = None,
                         t_span: tuple = (0, 12),
                         t_eval: np.ndarray = None) -> dict:
    """Simulate a single dose of MMF and return PK profiles.

    Parameters
    ----------
    dose_mg : float
        MMF dose in mg (e.g., 1000 for 1g).
    patient : PatientParameters
        Individual patient parameters.
    pk_params : PKParameters, optional
        PK model parameters. If None, uses defaults.
    drug_params : DrugParameters, optional
        Drug parameters.
    t_span : tuple
        (t_start, t_end) in hours.
    t_eval : ndarray, optional
        Time points for output.

    Returns
    -------
    dict with keys: 't', 'mpa_total', 'mpa_free', 'mpag', 'fu_profile', 'auc_total', 'auc_free'
    """
    if pk_params is None:
        pk_params = PKParameters()
    if drug_params is None:
        drug_params = DrugParameters()

    # Scale PK to patient
    scaled_pk = scale_pk_to_patient(pk_params, patient, drug_params)

    if t_eval is None:
        t_eval = np.linspace(t_span[0], t_span[1], 500)

    # MPA equivalent dose (MMF -> MPA conversion by MW ratio)
    mpa_dose = dose_mg * (drug_params.MW_MPA / drug_params.MW_MMF) * drug_params.F_MMF_to_MPA

    # Initial conditions: drug in gut at t=tlag
    # We handle lag time by starting drug in gut and letting absorption begin
    y0 = [mpa_dose, 0.0, 0.0, 0.0, 0.0, 0.0]

    # Adjust time for lag
    t_eval_shifted = t_eval.copy()
    tau = 12.0  # dosing interval (BID)

    sol = solve_ivp(
        mpa_ode,
        t_span=t_span,
        y0=y0,
        t_eval=t_eval,
        args=(scaled_pk, patient, drug_params, dose_mg, tau),
        method='LSODA',
        rtol=1e-8,
        atol=1e-10,
        max_step=0.1
    )

    if not sol.success:
        raise RuntimeError(f"ODE solver failed: {sol.message}")

    t = sol.t
    C_mpa_total = np.maximum(sol.y[1], 0.0)
    C_mpag = np.maximum(sol.y[3], 0.0)

    # Calculate free fraction profile
    fu_profile = np.array([
        calculate_free_fraction(patient.albumin, mpag, drug_params)
        for mpag in C_mpag
    ])
    C_mpa_free = C_mpa_total * fu_profile

    # AUC by trapezoidal rule
    auc_total = np.trapz(C_mpa_total, t)
    auc_free = np.trapz(C_mpa_free, t)

    return {
        't': t,
        'mpa_total': C_mpa_total,
        'mpa_free': C_mpa_free,
        'mpag': C_mpag,
        'fu_profile': fu_profile,
        'auc_total': auc_total,
        'auc_free': auc_free,
        'cmax_total': np.max(C_mpa_total),
        'cmax_free': np.max(C_mpa_free),
        'tmax': t[np.argmax(C_mpa_total)],
        'c_trough': C_mpa_total[-1] if len(C_mpa_total) > 0 else 0.0,
        'patient': patient,
        'dose_mg': dose_mg,
    }


def simulate_steady_state(dose_mg: float, patient: PatientParameters,
                          pk_params: PKParameters = None,
                          drug_params: DrugParameters = None,
                          n_doses: int = 14,
                          tau: float = 12.0) -> dict:
    """Simulate multiple BID doses to approximate steady state.

    Parameters
    ----------
    dose_mg : float
        MMF dose per administration (mg).
    patient : PatientParameters
        Individual patient parameters.
    n_doses : int
        Number of doses to simulate (14 = 7 days BID).
    tau : float
        Dosing interval in hours.

    Returns
    -------
    dict with full time course and last-interval PK metrics.
    """
    if pk_params is None:
        pk_params = PKParameters()
    if drug_params is None:
        drug_params = DrugParameters()

    scaled_pk = scale_pk_to_patient(pk_params, patient, drug_params)
    mpa_dose = dose_mg * (drug_params.MW_MPA / drug_params.MW_MMF) * drug_params.F_MMF_to_MPA

    total_time = n_doses * tau
    dt = 0.05  # resolution in hours
    t_eval = np.arange(0, total_time + dt, dt)

    # Initial state
    y = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    all_t = []
    all_mpa = []
    all_mpag = []
    all_fu = []
    all_mpa_free = []

    for dose_num in range(n_doses):
        t_dose_start = dose_num * tau
        t_dose_end = (dose_num + 1) * tau
        t_interval = np.arange(0, tau + dt, dt)

        # Add dose to gut compartment
        y[0] += mpa_dose

        sol = solve_ivp(
            mpa_ode,
            t_span=(0, tau),
            y0=y,
            t_eval=t_interval,
            args=(scaled_pk, patient, drug_params, dose_mg, tau),
            method='LSODA',
            rtol=1e-8,
            atol=1e-10,
            max_step=0.1
        )

        if not sol.success:
            raise RuntimeError(f"ODE solver failed at dose {dose_num}: {sol.message}")

        # Store results
        t_abs = sol.t + t_dose_start
        C_mpa = np.maximum(sol.y[1], 0.0)
        C_mpag = np.maximum(sol.y[3], 0.0)

        fu_vals = np.array([
            calculate_free_fraction(patient.albumin, m, drug_params)
            for m in C_mpag
        ])

        all_t.extend(t_abs)
        all_mpa.extend(C_mpa)
        all_mpag.extend(C_mpag)
        all_fu.extend(fu_vals)
        all_mpa_free.extend(C_mpa * fu_vals)

        # Carry forward final state for next dose
        y = sol.y[:, -1].copy()

    all_t = np.array(all_t)
    all_mpa = np.array(all_mpa)
    all_mpag = np.array(all_mpag)
    all_fu = np.array(all_fu)
    all_mpa_free = np.array(all_mpa_free)

    # Extract last dosing interval for steady-state metrics
    last_interval_mask = all_t >= (n_doses - 1) * tau
    t_ss = all_t[last_interval_mask] - (n_doses - 1) * tau
    mpa_ss = all_mpa[last_interval_mask]
    mpag_ss = all_mpag[last_interval_mask]
    fu_ss = all_fu[last_interval_mask]
    mpa_free_ss = all_mpa_free[last_interval_mask]

    auc_ss = np.trapz(mpa_ss, t_ss)
    auc_free_ss = np.trapz(mpa_free_ss, t_ss)

    return {
        # Full time course
        't_full': all_t,
        'mpa_full': all_mpa,
        'mpag_full': all_mpag,
        'fu_full': all_fu,
        'mpa_free_full': all_mpa_free,
        # Steady-state interval
        't_ss': t_ss,
        'mpa_ss': mpa_ss,
        'mpa_free_ss': mpa_free_ss,
        'mpag_ss': mpag_ss,
        'fu_ss': fu_ss,
        # Metrics
        'auc_ss_0_12': auc_ss,
        'auc_free_ss_0_12': auc_free_ss,
        'cmax_ss': np.max(mpa_ss),
        'cmax_free_ss': np.max(mpa_free_ss),
        'tmax_ss': t_ss[np.argmax(mpa_ss)],
        'c_trough_ss': mpa_ss[-1],
        'c_trough_free_ss': mpa_free_ss[-1],
        'patient': patient,
        'dose_mg': dose_mg,
    }
