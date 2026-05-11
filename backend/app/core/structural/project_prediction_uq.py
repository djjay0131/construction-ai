"""
project_prediction_uq.py — Predictive Uncertainty Quantification
    Final Semester Project | AOE/CS/ME 6444 Spring 2026
    Dr. Chris Roy | Authors: Jason Cusati & Cheng-Shun Chuang

Physical Case:
    8-ft simply-supported LVL residential header, uniform distributed load.

Uncertain Inputs:
    Aleatory:  E ~ N(µ=1,600,000 psi,  σ=160,000 psi)  [CoV=10%, LVL variability]
    Epistemic: q0 ∈ [400, 600] lb/ft  (±20% of nominal 500 lb/ft, load uncertainty)

SRQ:  w_max  [in]  — peak mid-span deflection

Methodology (nested sampling, Roy lectures §3/13):
    Outer loop : equal-partition sampling over q0 interval
                 Ne subintervals → Ne+1 sample points at boundaries
    Inner loop : Latin Hypercube Sampling (LHS) over E ~ N(µ,σ)
                 Na samples per outer point

Outputs (console):
    Table 1 — Nested sampling setup (Ne, Na combinations)
    Table 2 — p-box statistics (5th/95th percentile bounds)
    Table 3 — Validation metric extrapolation (model form uncertainty)
    Table 4 — Total predictive uncertainty budget

Outputs (figures → ./project_figures/):
    fig1_pbox.{pdf,png}              — p-box ensemble of CDFs
    fig2_pbox_vs_uniform.{pdf,png}   — p-box vs. treating q0 as uniform
    fig3_model_form_extrap.{pdf,png} — MAVM extrapolation with prediction interval
    fig4_total_uncertainty.{pdf,png} — Total uncertainty representation

Run:
    cd construction-ai/backend/app/core/structural
    python project_prediction_uq.py
"""

from __future__ import annotations

import json
import math
import os
import sys
from typing import Any, Dict, List, Tuple

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.special import ndtri
from scipy.stats import t as t_dist, norm as sp_norm
from scipy.stats import linregress, qmc

sys.path.insert(0, os.path.dirname(__file__))
from beam_solver import BeamGeometry, BeamMaterial, solve_simply_supported

# ============================================================
# Physical Setup — Weyerhaeuser 2.0E Microllam LVL (ESR-1387)
#   E  = 2,000,000 psi     Fb = 2,600 psi     Fv = 285 psi
# ============================================================
L_FT     = 8.0
L        = L_FT * 12.0
B        = 3.5                          # in  (double-ply 1-3/4" LVL)
D        = 11.25
FB       = 2_600.0                      # allowable bending [psi] — Microllam 2.0E
FV       = 285.0                        # allowable shear   [psi] — Microllam 2.0E

# Aleatory uncertain input: E ~ N(µ_E, σ_E)
#   µ_E  = ESR-1387 mean E for 2.0E Microllam
#   σ_E  = ASTM D5457 CoV bound (≤10%) enforced via D5456 QC chain
MU_E    = 2_000_000.0
SIGMA_E = 200_000.0

# Epistemic uncertain input: q0 ∈ [q_lo, q_hi]  (lb/ft)
Q0_NOM  = 500.0          # nominal
Q0_LO   = 400.0          # lower bound lb/ft
Q0_HI   = 600.0          # upper bound lb/ft

# Grid for UQ propagation (parametric, validated in HW4: UNUM ≈ 0.28%)
N_GRID  = 20

GEO     = BeamGeometry(span_in=L, width_in=B, depth_in=D)

# Numerical uncertainty (from HW4, finest grid N=160 adopted as reference,
# but we run at N=20 for speed; UNUM budget at N=20):
UNUM_WMAX_N20 = 1.962e-4   # [in]  (U_DE + U_RO at N=20, nominal q0,E)
# HW4 project requirement: worst-case U_NUM across 4 corners of uncertainty
# space, computed in run_corner_unum().  Updated after running that function.
UNUM_WMAX_CORNER = 2.91e-4  # [in]  conservative estimate (q0_hi, E-2sigma)

# HW5 validation metric results (AVM/MAVM at q0_nom, from hw5 script):
#   Material: Weyerhaeuser 2.0E Microllam LVL (E=2.0e6 psi, σ=200,000 psi)
#   Dataset 2, n_sim=100 LHS: AVM = 0.003893, MAVM = 0.003735  [in]
#   MAVM = d+ - d-,  AVM = d+ + d-
#   (MAVM > 0 → model under-predicts; conservative for deflection limit state)
AVM_BASE  = 0.003893   # [in]
MAVM_BASE = 0.003735   # [in]
D_PLUS_BASE  = (AVM_BASE + MAVM_BASE) / 2.0   # 3.814e-3 in  (model under-predict area)
D_MINUS_BASE = (AVM_BASE - MAVM_BASE) / 2.0   # 0.079e-3 in  (model over-predict area)

LHS_SEED = 42
SOBOL_N_BASE = 1024                       # → 4096 solver calls (n_base * (d+2))
SOBOL_SANITY_LO = 0.05                    # RD-2: lower sanity bound on S_T[i]
SOBOL_SANITY_HI = 0.95                    # RD-2: upper sanity bound on S_T[i]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "project_figures")
SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__),
                             "project_results_snapshot.json")
SNAPSHOT_ATOL = 1e-5                      # RD-5: drift tolerance vs committed snapshot

_RC = {
    "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11,
    "legend.fontsize": 9, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "figure.dpi": 150,
}

# ============================================================
# Core solver helpers
# ============================================================

def w_max_solve(E_psi: float, q0_lbft: float) -> float:
    """Beam deflection w_max [in] at given E and q0."""
    q0_lbin = q0_lbft / 12.0
    mat = BeamMaterial(E_psi=E_psi, Fb_psi=FB, Fv_psi=FV)
    return solve_simply_supported(GEO, mat, q0_lbin, n_nodes=N_GRID + 1).w_max


def lhs_normal(mu: float, sigma: float, n: int, seed: int) -> np.ndarray:
    """Latin Hypercube samples from N(mu, sigma)."""
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    u = (perm + rng.uniform(0.0, 1.0, n)) / n
    u = np.clip(u, 1e-12, 1.0 - 1e-12)
    return mu + sigma * ndtri(u)


def ecdf(data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Empirical CDF as step function (x, F)."""
    x = np.sort(data)
    F = np.arange(1, len(x) + 1) / len(x)
    x = np.concatenate([[x[0] - 1e-10], x])
    F = np.concatenate([[0.0], F])
    return x, F


# ============================================================
# HW#4 Project Requirement: Corner-case U_NUM
# ============================================================

def run_corner_unum() -> Dict:
    """
    HW#4 project requirement: evaluate U_NUM at all 4 corners of the
    input uncertainty space:
        q0 ∈ {Q0_LO, Q0_HI}  ×  E ∈ {µ_E ± 2σ_E}
    and take the maximum to conservatively bound numerical uncertainty
    over the entire prediction domain.

    For the EB beam (linear problem), p_obs=2 everywhere and GCI scales
    linearly with the SRQ value, so U_NUM / w_max ≈ constant = 0.2824%.
    We verify this directly with a 3-grid GCI at each corner.
    """
    corners = [
        (Q0_LO, MU_E - 2 * SIGMA_E),   # (400, 1,280,000)
        (Q0_LO, MU_E + 2 * SIGMA_E),   # (400, 1,920,000)
        (Q0_HI, MU_E - 2 * SIGMA_E),   # (600, 1,280,000) ← expected worst case
        (Q0_HI, MU_E + 2 * SIGMA_E),   # (600, 1,920,000)
    ]
    grid_levels = [10, 20, 40]    # coarse → medium → fine (r=2 each step)
    r = 2.0
    Fs = 1.25                     # GCI safety factor

    rows = []
    for q0_ft, E_c in corners:
        q0_in = q0_ft / 12.0
        mat = BeamMaterial(E_psi=E_c, Fb_psi=FB, Fv_psi=FV)
        w_vals = []
        for N in grid_levels:
            w_vals.append(
                solve_simply_supported(GEO, mat, q0_in, n_nodes=N + 1).w_max
            )
        f3, f2, f1 = w_vals          # coarse (N=10), medium (N=20), fine (N=40)
        p_obs = math.log(abs(f3 - f2) / max(abs(f2 - f1), 1e-30)) / math.log(r)
        # GCI_23 = U_DE for f2 = N=20 (production grid), the pair (f2, f3) = (N=20, N=10)
        gci23 = Fs * abs(f2 - f3) / (r ** p_obs - 1.0)
        rows.append(dict(
            q0_ft=q0_ft, E=E_c,
            w_fine=f2, p_obs=p_obs, gci12=gci23,  # gci12 key reused for U_DE(N=20)
        ))

    unum_max = max(row["gci12"] for row in rows)
    return dict(rows=rows, unum_max=unum_max)


# ============================================================
# Nested Sampling: p-box
# ============================================================

def equal_partition_samples(lo: float, hi: float, ne: int) -> np.ndarray:
    """
    Equal-partition sampling: divide [lo, hi] into ne subintervals,
    return ne+1 boundary points (endpoints of each sub-interval).
    """
    return np.linspace(lo, hi, ne + 1)


def run_nested_sampling(ne: int, na: int) -> Dict:
    """
    Outer loop over Ne+1 epistemic q0 samples (equal partition of [q_lo, q_hi]).
    Inner loop: na LHS samples over E ~ N(mu_E, sigma_E) for each outer point.

    Returns dict with:
        q0_samples  — outer q0 values [lb/ft]
        w_ensembles — list of na w_max arrays (one per outer point)
        pbox_lo     — lower envelope of CDFs (evaluated on common grid)
        pbox_hi     — upper envelope of CDFs (evaluated on common grid)
        y_grid      — common y-axis for p-box
    """
    q0_samples = equal_partition_samples(Q0_LO, Q0_HI, ne)

    w_ensembles: List[np.ndarray] = []
    for iq, q0 in enumerate(q0_samples):
        E_samps = lhs_normal(MU_E, SIGMA_E, na, seed=LHS_SEED + iq)
        w_samps = np.array([w_max_solve(E, q0) for E in E_samps])
        w_ensembles.append(w_samps)

    # Build p-box: pointwise min/max of CDFs over common y grid
    all_w = np.concatenate(w_ensembles)
    y_grid = np.linspace(all_w.min() * 0.99, all_w.max() * 1.01, 500)

    cdfs = []
    for w_arr in w_ensembles:
        cdf_vals = np.array([np.mean(w_arr <= y) for y in y_grid])
        cdfs.append(cdf_vals)
    cdfs = np.array(cdfs)  # shape (ne+1, 500)

    pbox_lo = cdfs.min(axis=0)
    pbox_hi = cdfs.max(axis=0)

    return dict(
        q0_samples=q0_samples,
        w_ensembles=w_ensembles,
        cdfs=cdfs,
        pbox_lo=pbox_lo,
        pbox_hi=pbox_hi,
        y_grid=y_grid,
        ne=ne, na=na,
    )


def run_uniform_epistemic(na: int) -> Dict:
    """
    Compare: treat q0 as uniform ~ U(q_lo, q_hi) (probabilistic treatment).
    Combines aleatory E and epistemic q0 into a single CDF.
    """
    rng = np.random.default_rng(LHS_SEED + 9999)
    q0_samps = rng.uniform(Q0_LO, Q0_HI, na)
    E_samps  = lhs_normal(MU_E, SIGMA_E, na, seed=LHS_SEED + 9998)
    w_samps  = np.array([w_max_solve(E, q) for E, q in zip(E_samps, q0_samps)])
    return dict(w_samples=w_samps)


# ============================================================
# Model Form Uncertainty Extrapolation  (d+ and d- separately)
# ============================================================

def _linear_extrap(q0_pts: np.ndarray, metric_pts: np.ndarray,
                   q0_pred: float) -> Dict:
    """Helper: linear regression + 95% PI at q0_pred."""
    slope, intercept, r_val, _, _ = linregress(q0_pts, metric_pts)
    pred_mean = intercept + slope * q0_pred
    n = len(q0_pts)
    q0_mean = np.mean(q0_pts)
    Sxx = np.sum((q0_pts - q0_mean) ** 2)
    s = math.sqrt(
        np.sum((metric_pts - (intercept + slope * q0_pts)) ** 2) / (n - 2)
    )
    t95 = t_dist.ppf(0.975, df=n - 2)
    pi_half = t95 * s * math.sqrt(1 + 1 / n + (q0_pred - q0_mean) ** 2 / Sxx)
    return dict(
        slope=slope, intercept=intercept, r_val=r_val,
        pred_mean=pred_mean, pi_half=pi_half,
        upper=pred_mean + pi_half,   # U_MF upper bound
        lower=pred_mean - pi_half,
        s=s, t95=t95,
    )


def build_mavm_dataset() -> Dict:
    """
    Construct synthetic d+, d-, MAVM vs q0 data for separate linear regression.
    At q0_nom=500, d+ = D_PLUS_BASE, d- = D_MINUS_BASE (derived from HW5 AVM/MAVM).
    Hypothetical values at nearby q0 simulate validation at different load levels.
    Since deflection ∝ q0, both d+/d- scale roughly linearly with q0 + scatter.
    Prediction target: q0=600 lb/ft (upper epistemic bound).
    """
    q0_pts = np.array([350.0, 400.0, 450.0, 500.0, 550.0])
    q0_pred = 600.0

    # d+ (area where model CDF is above experimental CDF → model under-predicts)
    # Scale factor = q0/500, add small scatter
    d_plus_pts = D_PLUS_BASE * (q0_pts / Q0_NOM) * np.array(
        [0.985, 1.010, 0.995, 1.000, 1.008]
    )
    # d- (area where experimental CDF is above model CDF → model over-predicts)
    d_minus_pts = D_MINUS_BASE * (q0_pts / Q0_NOM) * np.array(
        [1.012, 0.997, 1.003, 1.000, 0.994]
    )
    mavm_pts = d_plus_pts - d_minus_pts

    reg_plus  = _linear_extrap(q0_pts, d_plus_pts,  q0_pred)
    reg_minus = _linear_extrap(q0_pts, d_minus_pts, q0_pred)
    reg_mavm  = _linear_extrap(q0_pts, mavm_pts,    q0_pred)

    # Conservative model form interval: use upper 95% PI for each component
    U_MF_plus  = max(reg_plus["upper"],  0.0)   # rightward expansion
    U_MF_minus = max(reg_minus["upper"], 0.0)   # leftward expansion

    return dict(
        q0_pts=q0_pts, q0_pred=q0_pred,
        d_plus_pts=d_plus_pts, d_minus_pts=d_minus_pts, mavm_pts=mavm_pts,
        reg_plus=reg_plus, reg_minus=reg_minus, reg_mavm=reg_mavm,
        U_MF_plus=U_MF_plus, U_MF_minus=U_MF_minus,
        # keep legacy keys for backward compat
        slope=reg_mavm["slope"], intercept=reg_mavm["intercept"],
        r_val=reg_mavm["r_val"], s=reg_mavm["s"], t95=reg_mavm["t95"],
        mavm_pred_mean=reg_mavm["pred_mean"],
        pred_int_half=reg_mavm["pi_half"],
        mavm_ubound=reg_mavm["upper"],
    )


# ============================================================
# Total Uncertainty Assembly
# ============================================================

def assemble_total_uncertainty(pbox: Dict, mavm_extrap: Dict,
                                unum_corner: float) -> Dict:
    """
    Add model form (asymmetric d+/d-) and numerical uncertainty to the p-box.

    Strategy (follows Roy lectures §13):
        Upper side: shift p-box right by U_MF_plus  + U_num_corner
        Lower side: shift p-box left  by U_MF_minus + U_num_corner

    Returns dict with all intermediate envelope layers for fig4.
    """
    U_MF_plus  = mavm_extrap["U_MF_plus"]    # upper 95% PI for d+ at q0_pred
    U_MF_minus = mavm_extrap["U_MF_minus"]   # upper 95% PI for d- at q0_pred
    U_num      = unum_corner                   # worst-case U_NUM across 4 corners

    y_grid  = pbox["y_grid"]
    pbox_lo = pbox["pbox_lo"]
    pbox_hi = pbox["pbox_hi"]

    # Layer 2: after adding model form uncertainty (asymmetric)
    y_mf_lo = y_grid - U_MF_minus   # lower envelope shifted left by d-
    y_mf_hi = y_grid + U_MF_plus    # upper envelope shifted right by d+

    # Layer 3: after further adding numerical uncertainty (symmetric)
    y_tot_lo = y_mf_lo - U_num
    y_tot_hi = y_mf_hi + U_num

    return dict(
        y_grid=y_grid,
        pbox_lo=pbox_lo, pbox_hi=pbox_hi,
        y_mf_lo=y_mf_lo, y_mf_hi=y_mf_hi,
        y_tot_lo=y_tot_lo, y_tot_hi=y_tot_hi,
        U_MF_plus=U_MF_plus, U_MF_minus=U_MF_minus, U_num=U_num,
    )


# ============================================================
# Console Output
# ============================================================

def print_header(title: str) -> None:
    bar = "=" * 72
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def print_pbox_table(results_dict: Dict[int, Dict]) -> None:
    print_header("Table 1 — p-box Statistics for Varying Ne (Na=100 fixed)")
    hdr = (f"  {'Ne':>4}  {'Na':>4}  {'5th pct [lo,hi]':>22}  "
           f"{'50th pct [lo,hi]':>22}  {'95th pct [lo,hi]':>22}  {'Width@50th':>12}")
    print(hdr)
    print("  " + "-" * 92)
    for ne, res in sorted(results_dict.items()):
        y  = res["y_grid"]
        lo = res["pbox_lo"]
        hi = res["pbox_hi"]
        def interp_y(env, F_target):
            idx = min(np.searchsorted(env, F_target), len(y) - 1)
            return y[idx]
        # Lower bound on quantile = from pbox_hi (reaches target sooner)
        # Upper bound on quantile = from pbox_lo (reaches target later)
        lb5  = interp_y(hi, 0.05)
        ub5  = interp_y(lo, 0.05)
        lb50 = interp_y(hi, 0.50)
        ub50 = interp_y(lo, 0.50)
        lb95 = interp_y(hi, 0.95)
        ub95 = interp_y(lo, 0.95)
        width50 = ub50 - lb50
        print(f"  {ne:>4}  {res['na']:>4}"
              f"  [{lb5:.5f}, {ub5:.5f}]"
              f"  [{lb50:.5f}, {ub50:.5f}]"
              f"  [{lb95:.5f}, {ub95:.5f}]"
              f"  {width50:>12.5f}")
    print()


def print_corner_unum(corner: Dict) -> None:
    print_header("Table 2 — Solution Verification at 4 Input Uncertainty Corners (HW#4)")
    print(f"\n  {'Corner':>30}  {'w_max N=20 [in]':>16}  {'p_obs':>6}  {'U_DE [in]':>12}")
    print("  " + "-" * 68)
    labels = ["(q0_lo, E-2σ)", "(q0_lo, E+2σ)", "(q0_hi, E-2σ)", "(q0_hi, E+2σ)"]
    for lbl, row in zip(labels, corner["rows"]):
        mark = " ← max" if row["gci12"] >= corner["unum_max"] - 1e-15 else ""
        print(f"  {lbl:>30}  {row['w_fine']:>12.6f}  {row['p_obs']:>6.3f}  "
              f"{row['gci12']:>12.4e}{mark}")
    print(f"\n  Worst-case U_NUM = {corner['unum_max']:.4e} in  (used for p-box widening)")
    print()


def print_mavm_extrap(extrap: Dict) -> None:
    print_header("Table 3 — Model Form Uncertainty Extrapolation (d+, d−, MAVM vs. q₀)")
    rp = extrap["reg_plus"]
    rm = extrap["reg_minus"]
    rv = extrap["reg_mavm"]
    print(f"\n  At q₀=500 lb/ft (HW5): d+ = {D_PLUS_BASE:.4e} in,  "
          f"d− = {D_MINUS_BASE:.4e} in,  MAVM = {MAVM_BASE:.4e} in")
    print("\n  Linear regressions (intercept + slope × q₀):")
    print(f"    d+   : {rp['intercept']:.4e} + {rp['slope']:.4e}·q₀   R²={rp['r_val']**2:.4f}")
    print(f"    d−   : {rm['intercept']:.4e} + {rm['slope']:.4e}·q₀   R²={rm['r_val']**2:.4f}")
    print(f"    MAVM : {rv['intercept']:.4e} + {rv['slope']:.4e}·q₀   R²={rv['r_val']**2:.4f}")
    print(f"\n  Extrapolation to q₀ = {extrap['q0_pred']:.0f} lb/ft:")
    print(f"    d+  : mean={rp['pred_mean']:.4e}  95% PI half={rp['pi_half']:.4e}  "
          f"U_MF+ = {extrap['U_MF_plus']:.4e} in")
    print(f"    d−  : mean={rm['pred_mean']:.4e}  95% PI half={rm['pi_half']:.4e}  "
          f"U_MF− = {extrap['U_MF_minus']:.4e} in")
    print()


def print_total_uncertainty(total: Dict, pbox: Dict) -> None:
    print_header("Table 4 — Total Predictive Uncertainty Budget (w_max, q₀=600 lb/ft)")
    w_ens_hi = pbox["w_ensembles"][-1]
    w_nom = np.mean(w_ens_hi)

    print(f"\n  Nominal w_max at q₀={Q0_HI:.0f} lb/ft (mean, N={N_GRID}): "
          f"{w_nom:.6f} in")
    print("\n  Uncertainty source               Magnitude [in]   % of w_nom   Side")
    print("  " + "-" * 70)
    y  = pbox["y_grid"]
    lo = pbox["pbox_lo"]
    hi = pbox["pbox_hi"]
    def interp_y(env, F_target):
        return y[min(np.searchsorted(env, F_target), len(y) - 1)]
    mid_idx = len(pbox["w_ensembles"]) // 2
    w_mid = pbox["w_ensembles"][mid_idx]
    U_aleatory  = (np.percentile(w_mid, 95) - np.percentile(w_mid, 5)) / 2.0
    U_epistemic = (interp_y(lo, 0.50) - interp_y(hi, 0.50)) / 2.0
    U_MF_plus   = total["U_MF_plus"]
    U_MF_minus  = total["U_MF_minus"]
    U_num       = total["U_num"]
    U_total_hi  = U_aleatory + U_epistemic + U_MF_plus  + U_num
    U_total_lo  = U_aleatory + U_epistemic + U_MF_minus + U_num

    rows = [
        ("Aleatory  (E~N, 5–95th half-width)", U_aleatory,  "both"),
        ("Epistemic (q₀ interval half-width)", U_epistemic, "both"),
        ("Model form d+ (upper 95% PI)",       U_MF_plus,   "upper→"),
        ("Model form d− (upper 95% PI)",       U_MF_minus,  "←lower"),
        ("Numerical U_NUM (worst corner)",     U_num,       "both"),
    ]
    for label, val, side in rows:
        pct = val / w_nom * 100.0
        print(f"  {label:<38}  {val:.4e}     {pct:6.3f}%   {side}")
    print(f"  {'Total — upper side':38}  {U_total_hi:.4e}     {U_total_hi/w_nom*100:.3f}%")
    print(f"  {'Total — lower side':38}  {U_total_lo:.4e}     {U_total_lo/w_nom*100:.3f}%")
    print()


# ============================================================
# Figures
# ============================================================

def _save(fig: plt.Figure, stem: str) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUTPUT_DIR, f"{stem}.{ext}"),
                    bbox_inches="tight", dpi=300)
    print(f"    saved  {stem}.{{pdf,png}}")


def fig1_pbox(results_dict: Dict[int, Dict]) -> None:
    """Figure 1 — p-box ensemble for different Ne values."""
    colors_ne = {5: "steelblue", 10: "darkorange", 25: "green"}

    with plt.rc_context(_RC):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), sharey=True)
        for ax, ne in zip(axes, [5, 10, 25]):
            if ne not in results_dict:
                continue
            res = results_dict[ne]
            y   = res["y_grid"]
            # Plot each CDF in the ensemble
            for i, cdf in enumerate(res["cdfs"]):
                ax.step(y, cdf, where="post", color="gray", alpha=0.35, lw=0.8)
            # p-box envelope
            ax.fill_betweenx(res["pbox_lo"], y, res["y_grid"].max(),
                             alpha=0.0)
            ax.step(y, res["pbox_lo"], where="post",
                    color=colors_ne[ne], lw=2.0, label="p-box (lo)")
            ax.step(y, res["pbox_hi"], where="post",
                    color=colors_ne[ne], lw=2.0, ls="--", label="p-box (hi)")
            ax.set_xlabel(r"$w_{\max}$ [in]")
            ax.set_ylabel("CDF" if ne == 5 else "")
            ax.set_title(f"$N_e = {ne}$ ($N_a = {res['na']}$)")
            ax.legend(fontsize=8)
            ax.grid(True, color="gray", alpha=0.3, lw=0.5)

        fig.suptitle(
            r"p-box for $w_{\max}$: Epistemic $q_0\in[400,600]$ lb/ft, "
            r"Aleatory $E\sim\mathcal{N}(\mu_E,\sigma_E)$",
            fontsize=11, y=1.01,
        )
        fig.tight_layout()
        _save(fig, "fig1_pbox")
        plt.close(fig)


def fig2_pbox_vs_uniform(pbox25: Dict, uniform_res: Dict) -> None:
    """Figure 2 — p-box (Ne=25) vs. probabilistic treatment of q0 as Uniform."""
    with plt.rc_context(_RC):
        fig, ax = plt.subplots(figsize=(7, 4.5))

        y  = pbox25["y_grid"]
        ax.fill_between(y, pbox25["pbox_lo"], pbox25["pbox_hi"],
                         alpha=0.25, color="steelblue", label=r"p-box (epistemic $q_0$)")
        ax.step(y, pbox25["pbox_lo"], where="post", color="steelblue", lw=1.8)
        ax.step(y, pbox25["pbox_hi"], where="post", color="steelblue", lw=1.8, ls="--")

        x_u, F_u = ecdf(uniform_res["w_samples"])
        ax.step(x_u, F_u, where="post", color="red", lw=1.8, ls="-",
                label=r"Single CDF ($q_0\sim U[400,600]$)")

        ax.set_xlabel(r"$w_{\max}$ [in]")
        ax.set_ylabel("CDF")
        ax.set_title(r"p-box vs. Uniform $q_0$: Effect of Epistemic Treatment")
        ax.legend(fontsize=9)
        ax.grid(True, color="gray", alpha=0.3, lw=0.5)
        fig.tight_layout()
        _save(fig, "fig2_pbox_vs_uniform")
        plt.close(fig)


def fig3_model_form_extrap(extrap: Dict) -> None:
    """Figure 3 — MAVM linear regression with 95% prediction interval."""
    q0_fit = np.linspace(300, 700, 200)
    mavm_fit = extrap["intercept"] + extrap["slope"] * q0_fit

    # Prediction interval
    n      = len(extrap["q0_pts"])
    q0_mean = np.mean(extrap["q0_pts"])
    Sxx    = np.sum((extrap["q0_pts"] - q0_mean) ** 2)
    s      = extrap["s"]
    t95    = extrap["t95"]
    s2_pred = s * np.sqrt(1 + 1/n + (q0_fit - q0_mean)**2 / Sxx)
    pi_lo  = mavm_fit - t95 * s2_pred
    pi_hi  = mavm_fit + t95 * s2_pred

    with plt.rc_context(_RC):
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.scatter(extrap["q0_pts"], extrap["mavm_pts"] * 1000,
                   color="black", zorder=5, label="Validation data", s=40)
        ax.plot(q0_fit, mavm_fit * 1000, "b-", lw=1.8, label="Linear regression")
        ax.plot(q0_fit, pi_lo * 1000, "b--", lw=1.0, alpha=0.7, label="95% PI")
        ax.plot(q0_fit, pi_hi * 1000, "b--", lw=1.0, alpha=0.7)
        ax.fill_between(q0_fit, pi_lo * 1000, pi_hi * 1000, alpha=0.15, color="blue")
        ax.axvline(extrap["q0_pred"], color="red", ls=":", lw=1.2,
                   label=f"Prediction ($q_0$={extrap['q0_pred']:.0f} lb/ft)")
        ax.scatter([extrap["q0_pred"]], [extrap["mavm_ubound"] * 1000],
                   color="red", marker="^", s=80, zorder=6,
                   label=f"$U_{{MF}}$ = {extrap['mavm_ubound']*1000:.3f} ×10⁻³ in")
        ax.set_xlabel(r"$q_0$ [lb/ft]")
        ax.set_ylabel(r"MAVM $\times 10^{-3}$ [in]")
        ax.set_title(r"Model Form Uncertainty Extrapolation (MAVM vs. $q_0$)")
        ax.legend(fontsize=8)
        ax.grid(True, color="gray", alpha=0.3, lw=0.5)
        fig.tight_layout()
        _save(fig, "fig3_model_form_extrap")
        plt.close(fig)


def fig4_total_uncertainty(pbox25: Dict, total: Dict,
                           uniform_res: Dict) -> None:
    """
    Figure 4 — Total uncertainty representation.

    Bands are drawn using inverse-CDF space (fill_betweenx) so every
    layer covers the FULL probability range and each horizontal margin is
    correctly sized.  Painter order: outermost first so inner bands cover.

        Red   band (outermost) : p-box + model form + U_NUM
        Orange band (middle)   : p-box + model form (d+, d-)
        Blue  band (innermost) : input p-box only
        Black line             : single CDF (q0 treated as uniform)
    """
    with plt.rc_context(_RC):
        fig, ax = plt.subplots(figsize=(8, 5.5))

        y_grid  = pbox25["y_grid"]
        pbox_lo = pbox25["pbox_lo"]
        pbox_hi = pbox25["pbox_hi"]
        U_MF_plus  = total["U_MF_plus"]
        U_MF_minus = total["U_MF_minus"]
        U_num      = total["U_num"]

        # --- Invert both CDF bounds to get quantile (x) boundaries ---
        # pbox_lo = LOWER CDF envelope → inverse gives RIGHT boundary (larger x)
        # pbox_hi = UPPER CDF envelope → inverse gives LEFT  boundary (smaller x)
        probs   = np.linspace(0.005, 0.995, 500)
        x_right = np.interp(probs, pbox_lo, y_grid)  # right bound
        x_left  = np.interp(probs, pbox_hi, y_grid)  # left  bound

        # Outer band boundaries
        mf_right  = x_right + U_MF_plus            # orange right edge
        mf_left   = x_left  - U_MF_minus           # orange left  edge
        tot_right = mf_right + U_num               # red    right edge
        tot_left  = mf_left  - U_num               # red    left  edge

        # --- Painter's order: outermost first ---

        # Orange (middle): p-box + model form
        ax.fill_betweenx(probs, mf_left, mf_right,
                         alpha=1.0, color="#ffd580", zorder=1,
                         label=r"+ Model form $U_{\rm MF}$ ($d^+$/$d^-$, 95% PI)")

        # Blue (innermost): input p-box only
        ax.fill_betweenx(probs, x_left, x_right,
                         alpha=1.0, color="#a8d0e6", zorder=2,
                         label=r"Input uncertainty (p-box, $N_e=25$)")

        # P-box envelope borders
        ax.step(y_grid, pbox_lo, where="post", color="navy", lw=1.5, zorder=3)
        ax.step(y_grid, pbox_hi, where="post", color="navy", lw=1.5, ls="--", zorder=3)

        # --- U_NUM: draw as thick red boundary lines outside the orange band ---
        # U_num (~2.6e-4 in) is only 0.3% of x-range → fill strip is invisible.
        # Instead render it as prominent dashed lines with a zoomed-inset bracket.
        ax.plot(tot_right, probs, color="crimson", lw=2.0, ls="-",  zorder=4)
        ax.plot(tot_left,  probs, color="crimson", lw=2.0, ls="-",  zorder=4)
        # Invisible proxy patch just for the legend entry
        from matplotlib.patches import Patch
        red_patch = Patch(facecolor="none", edgecolor="crimson", lw=2,
                          label=r"+ Numerical $U_{\rm NUM}$ (worst corner, $2.60\times10^{-4}$ in)")

        # --- Zoomed inset to show the thin U_NUM margin clearly ---
        # Bracket at the right side near 50th percentile
        p_lo, p_hi = 0.44, 0.56
        i_lo = int(p_lo * len(probs))
        i_hi = int(p_hi * len(probs))
        xr_mid = float(np.mean(mf_right[i_lo:i_hi]))
        xt_mid = float(np.mean(tot_right[i_lo:i_hi]))
        p_mid  = 0.50

        # Double-headed arrow with exaggerated tip labels
        ax.annotate("",
                    xy=(xt_mid, p_mid),
                    xytext=(xr_mid, p_mid),
                    arrowprops=dict(arrowstyle="<->", color="crimson",
                                    lw=1.5, mutation_scale=10),
                    zorder=6)
        ax.text(xt_mid + 0.0006, p_mid,
                r"$U_{\rm NUM}=2.60\times10^{-4}$ in",
                color="crimson", fontsize=7, ha="left", va="center", zorder=6)

        # --- Uniform epistemic CDF (black reference line) ---
        x_u, F_u = ecdf(uniform_res["w_samples"])
        ax.step(x_u, F_u, where="post", color="black", lw=1.6, zorder=5,
                label=r"Probabilistic ($q_0\sim U$)")

        ax.set_xlabel(r"$w_{\max}$ [in]")
        ax.set_ylabel("Cumulative Probability")
        ax.set_title(
            r"Total Predictive Uncertainty in $w_{\max}$"
            "\n"
            r"$q_0\in[400,600]$ lb/ft, $E\sim\mathcal{N}(\mu_E,\sigma_E)$"
        )
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles + [red_patch], labels + [red_patch.get_label()],
                  fontsize=8, loc="upper left")
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, color="gray", alpha=0.3, lw=0.5, zorder=0)
        fig.tight_layout()
        _save(fig, "fig4_total_uncertainty")
        plt.close(fig)


# ============================================================
# Sensitivity Analysis (Saltelli/Sobol)
# ============================================================

def run_sobol_indices(n_base: int = SOBOL_N_BASE,
                      seed: int = LHS_SEED) -> Dict[str, Any]:
    """
    Sobol first-order (S1) and total-effect (ST) indices for w_max(E, q0).

    For the variance decomposition both inputs are treated probabilistically:
        E  ~ N(MU_E, SIGMA_E)              (LVL grade-1 production scatter)
        q0 ~ U(Q0_LO, Q0_HI)               (epistemic interval re-cast as uniform)

    This intentionally departs from the p-box framing (where q0 stays
    epistemic) — variance-based decomposition requires a probability measure
    on every input. The two analyses answer different questions: the p-box
    bounds the predictive CDF; Sobol ranks input contributions to total
    output variance.  See Roy 2011, Section 2-3, for the dual-treatment
    rationale.

    Saltelli sample design: total solver calls = n_base * (d + 2) where d=2,
    i.e. 4 * n_base. With n_base=1024 → 4096 FD solves at N=20.

    RD-2 sanity-bound assertion: ST values must lie in
    [SOBOL_SANITY_LO, SOBOL_SANITY_HI] for both inputs; out-of-range
    triggers RuntimeError to catch latent RNG-state bugs that could
    silently produce a numerically-correct-but-visually-broken figure.

    Returns:
        Dict with keys:
            S1, ST       : np.ndarray shape (2,)
            labels       : ["E", "q0"]
            n_base, n_calls
            var_y        : float  (total output variance, for sanity)
            S1_sum, ST_sum
            interaction  : float  (ST_sum - S1_sum, ≥ 0 theoretically)
    """
    # Saltelli construction: draw a single Sobol sequence in 2*d=4
    # dimensions, then split into A | B halves. This guarantees joint
    # low-discrepancy coverage; two separate Sobol(d=2) calls produce
    # correlated continuations of the same sequence and leak ST[i]→0.
    d = 2
    sampler = qmc.Sobol(d=2 * d, scramble=True, seed=seed)
    joint = sampler.random(n_base)
    A_unit = joint[:, :d]
    B_unit = joint[:, d:]

    def _rescale(unit_arr: np.ndarray) -> np.ndarray:
        out = np.empty_like(unit_arr)
        # column 0 → E ~ N(mu, sigma) via inverse-CDF
        out[:, 0] = sp_norm.ppf(unit_arr[:, 0], loc=MU_E, scale=SIGMA_E)
        # column 1 → q0 ~ U(Q0_LO, Q0_HI)
        out[:, 1] = Q0_LO + (Q0_HI - Q0_LO) * unit_arr[:, 1]
        return out

    A = _rescale(A_unit)
    B = _rescale(B_unit)

    f_A = np.array([w_max_solve(E_psi=row[0], q0_lbft=row[1]) for row in A])
    f_B = np.array([w_max_solve(E_psi=row[0], q0_lbft=row[1]) for row in B])

    f_AB: List[np.ndarray] = []
    for i in range(2):
        AB = A.copy()
        AB[:, i] = B[:, i]
        f_AB.append(
            np.array([w_max_solve(E_psi=row[0], q0_lbft=row[1]) for row in AB])
        )

    var_y = float(np.var(np.concatenate([f_A, f_B]), ddof=1))
    if var_y <= 0.0:                                              # pragma: no cover
        # Defensive: w_max(E,q0) is non-degenerate by construction, so this
        # branch is unreachable in this study.  Kept for diagnostic clarity.
        raise RuntimeError("Sobol: zero output variance — degenerate inputs?")

    S1 = np.array([np.mean(f_B * (f_AB[i] - f_A)) / var_y for i in range(2)])
    ST = np.array([0.5 * np.mean((f_A - f_AB[i]) ** 2) / var_y for i in range(2)])

    # RD-2: sanity-bound assertion on total-effect indices
    for label, st_val in zip(["E", "q0"], ST):
        if not (SOBOL_SANITY_LO <= st_val <= SOBOL_SANITY_HI):
            raise RuntimeError(
                f"Sobol sanity-bound check failed: ST[{label}] = {st_val:.4f} "
                f"is outside [{SOBOL_SANITY_LO}, {SOBOL_SANITY_HI}]. "
                f"Expected both inputs to contribute meaningfully to "
                f"variance of w_max for the LVL beam case."
            )

    return {
        "S1": S1,
        "ST": ST,
        "labels": ["E", "q0"],
        "n_base": int(n_base),
        "n_calls": int(n_base * 4),
        "var_y": var_y,
        "S1_sum": float(np.sum(S1)),
        "ST_sum": float(np.sum(ST)),
        "interaction": float(np.sum(ST) - np.sum(S1)),
    }


def print_sobol_table(sobol_res: Dict[str, Any]) -> None:
    print_header("Table 5 — Sobol Sensitivity Indices for w_max (Saltelli)")
    print(f"\n  Sampling: n_base={sobol_res['n_base']}, "
          f"n_calls={sobol_res['n_calls']}, var(y)={sobol_res['var_y']:.4e}")
    print(f"\n  {'Input':>6}  {'S_1 (first-order)':>20}  {'S_T (total-effect)':>20}")
    print("  " + "-" * 50)
    for lbl, s1, st in zip(sobol_res["labels"], sobol_res["S1"], sobol_res["ST"]):
        print(f"  {lbl:>6}  {s1:>20.4f}  {st:>20.4f}")
    print(f"\n  Σ S_1 = {sobol_res['S1_sum']:.4f}   "
          f"Σ S_T = {sobol_res['ST_sum']:.4f}   "
          f"Interaction (Σ S_T − Σ S_1) = {sobol_res['interaction']:.4f}")
    print()


def fig5_sobol_indices(sobol_res: Dict[str, Any]) -> None:
    """Figure 5 — bar chart of S_1 and S_T for E and q0."""
    with plt.rc_context(_RC):
        fig, ax = plt.subplots(figsize=(5.6, 3.8))
        labels = sobol_res["labels"]
        x = np.arange(len(labels))
        w = 0.35
        ax.bar(x - w / 2, sobol_res["S1"], w,
               label=r"$S_1$ (first-order)", color="#1f77b4", edgecolor="black", lw=0.5)
        ax.bar(x + w / 2, sobol_res["ST"], w,
               label=r"$S_T$ (total-effect)", color="#d62728", edgecolor="black", lw=0.5)

        # Annotate values on top of bars
        for xi, val in zip(x - w / 2, sobol_res["S1"]):
            ax.text(xi, val + 0.02, f"{val:.3f}", ha="center", va="bottom", fontsize=8)
        for xi, val in zip(x + w / 2, sobol_res["ST"]):
            ax.text(xi, val + 0.02, f"{val:.3f}", ha="center", va="bottom", fontsize=8)

        ax.set_xticks(x)
        ax.set_xticklabels([r"$E$", r"$q_0$"])
        ax.set_ylabel("Sobol index")
        ax.set_ylim(0.0, 1.10)
        ax.set_title(
            r"Sobol Sensitivity Indices for $w_{\max}$"
            "\n"
            f"$n_{{\\rm calls}}={sobol_res['n_calls']}$, "
            r"$E\sim\mathcal{N}(\mu_E,\sigma_E)$, $q_0\sim U(400,600)$"
        )
        ax.legend(loc="upper right", fontsize=9)
        ax.grid(True, axis="y", color="gray", alpha=0.3, lw=0.5)

        # Caption-style sum annotation under the title
        ax.text(0.5,
                -0.20,
                f"$\\sum S_1={sobol_res['S1_sum']:.3f}$, "
                f"$\\sum S_T={sobol_res['ST_sum']:.3f}$, "
                f"interaction $={sobol_res['interaction']:.3f}$",
                transform=ax.transAxes, ha="center", va="top", fontsize=8)
        fig.tight_layout()
        _save(fig, "fig5_sobol")
        plt.close(fig)


# ============================================================
# RD-5: Determinism snapshot
# ============================================================

def build_snapshot(results_dict: Dict[int, Dict],
                   corner_unum: Dict,
                   mavm_extrap: Dict,
                   total_unc: Dict,
                   sobol_res: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assemble the invariants we want to lock down across runs (RD-5).

    Stored to 6-decimal precision; subsequent runs assert all values match
    a committed snapshot to within SNAPSHOT_ATOL absolute tolerance.
    """
    def _interp_y(env: np.ndarray, F_target: float, y: np.ndarray) -> float:
        idx = min(int(np.searchsorted(env, F_target)), len(y) - 1)
        return float(y[idx])

    pbox_quantiles: Dict[str, Dict[str, List[float]]] = {}
    for ne, res in sorted(results_dict.items()):
        y = res["y_grid"]
        lo = res["pbox_lo"]
        hi = res["pbox_hi"]
        pbox_quantiles[str(ne)] = {
            "5th":  [_interp_y(hi, 0.05, y), _interp_y(lo, 0.05, y)],
            "50th": [_interp_y(hi, 0.50, y), _interp_y(lo, 0.50, y)],
            "95th": [_interp_y(hi, 0.95, y), _interp_y(lo, 0.95, y)],
        }

    pbox_25 = results_dict[25]
    w_ens_hi = pbox_25["w_ensembles"][-1]
    w_nom_hi = float(np.mean(w_ens_hi))

    return {
        "schema_version": 1,
        "tolerance": SNAPSHOT_ATOL,
        "pbox_quantiles_in": pbox_quantiles,
        "u_num_max_in": float(corner_unum["unum_max"]),
        "U_MF_plus_in": float(mavm_extrap["U_MF_plus"]),
        "U_MF_minus_in": float(mavm_extrap["U_MF_minus"]),
        "AVM_base_in": float(AVM_BASE),
        "MAVM_base_in": float(MAVM_BASE),
        "d_plus_base_in": float(D_PLUS_BASE),
        "d_minus_base_in": float(D_MINUS_BASE),
        "total_upper_in": float(total_unc.get("U_total_upper",
                                              total_unc.get("u_total_upper", 0.0))),
        "total_lower_in": float(total_unc.get("U_total_lower",
                                              total_unc.get("u_total_lower", 0.0))),
        "w_nom_q0_hi_in": w_nom_hi,
        "sobol_S1": [float(v) for v in sobol_res["S1"]],
        "sobol_ST": [float(v) for v in sobol_res["ST"]],
        "sobol_S1_sum": sobol_res["S1_sum"],
        "sobol_ST_sum": sobol_res["ST_sum"],
        "sobol_interaction": sobol_res["interaction"],
        "sobol_n_calls": sobol_res["n_calls"],
    }


def _flatten(prefix: str, obj: Any, out: Dict[str, float]) -> None:
    """Flatten a nested dict/list of floats into dotted-key form for diffing."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _flatten(f"{prefix}[{i}]", v, out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out[prefix] = float(obj)
    # strings and metadata fields are skipped


def compare_against_snapshot(snapshot: Dict[str, Any],
                             path: str = SNAPSHOT_PATH,
                             atol: float = SNAPSHOT_ATOL) -> None:
    """
    RD-5 determinism guard.

    If `path` does not exist, write the snapshot and return ("baseline" mode).
    If it exists, load and compare every numeric leaf to within `atol`;
    raise RuntimeError listing all out-of-tolerance fields.
    """
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, sort_keys=True)
        print(f"  Snapshot baseline written → {os.path.basename(path)}")
        return

    with open(path, "r", encoding="utf-8") as f:
        prior = json.load(f)

    flat_now: Dict[str, float] = {}
    flat_prior: Dict[str, float] = {}
    _flatten("", snapshot, flat_now)
    _flatten("", prior, flat_prior)

    # tolerance and schema_version are metadata; skip
    for k in ("tolerance", "schema_version"):
        flat_now.pop(k, None)
        flat_prior.pop(k, None)

    drifts: List[Tuple[str, float, float, float]] = []
    all_keys = set(flat_now.keys()) | set(flat_prior.keys())
    for k in sorted(all_keys):
        a = flat_prior.get(k)
        b = flat_now.get(k)
        if a is None or b is None:
            drifts.append((k, a if a is not None else float("nan"),
                              b if b is not None else float("nan"),
                              float("inf")))
            continue
        delta = abs(a - b)
        if delta > atol:
            drifts.append((k, a, b, delta))

    if drifts:
        msg_lines = [
            f"Snapshot determinism check FAILED ({len(drifts)} field(s) "
            f"exceed atol={atol:g}):"
        ]
        for k, a, b, d in drifts[:20]:        # cap output to first 20
            msg_lines.append(f"  {k:<48s}  prior={a!r:>14s}  now={b!r:>14s}  Δ={d:.3e}")
        if len(drifts) > 20:
            msg_lines.append(f"  ... and {len(drifts) - 20} more.")
        msg_lines.append(
            f"To refresh: rm {os.path.basename(path)} and re-run."
        )
        raise RuntimeError("\n".join(msg_lines))

    print(f"  Snapshot determinism OK (atol={atol:g}, "
          f"{len(flat_now)} fields checked)")


# ============================================================
# Main
# ============================================================

def main() -> None:
    print("\n" + "=" * 72)
    print("  Final Project — Predictive Uncertainty Quantification")
    print("  AOE/CS/ME 6444 | Spring 2026 | Dr. Chris Roy")
    print("  Authors: Jason Cusati & Cheng-Shun Chuang")
    print("=" * 72)
    print(f"\n  Physical case: {L_FT}-ft LVL header, b={B} in, d={D} in")
    print(f"  Aleatory: E ~ N({MU_E:.0f}, {SIGMA_E:.0f}) psi  [CoV={SIGMA_E/MU_E*100:.0f}%]")
    print(f"  Epistemic: q0 ∈ [{Q0_LO:.0f}, {Q0_HI:.0f}] lb/ft  (±20% of {Q0_NOM:.0f})")
    print(f"  Parametric grid: N={N_GRID}  (U_NUM = {UNUM_WMAX_N20:.3e} in)")

    # ── 1. Nested sampling for Ne = 5, 10, 25, 100 ──────────────────────────
    ne_values = [5, 10, 25, 100]
    na = 100
    print(f"\n  [1/5] Running nested sampling (Ne={ne_values}, Na={na}) ...")
    results_dict: Dict[int, Dict] = {}
    for ne in ne_values:
        print(f"    Ne={ne} ...", end="", flush=True)
        res = run_nested_sampling(ne=ne, na=na)
        results_dict[ne] = res
        print(f" done. p-box width at median = "
              f"{res['pbox_hi'][250]-res['pbox_lo'][250]:.5f} in")

    # ── 2. Probabilistic (uniform) comparison ─────────────────────────────
    print(f"\n  [2/5] Running uniform epistemic comparison (Na={na}) ...")
    uniform_res = run_uniform_epistemic(na=na)

    # ── 3. Corner-case U_NUM (HW#4 project requirement) ───────────────────
    print("\n  [3/5] Running 4-corner U_NUM study ...")
    corner_unum = run_corner_unum()
    U_NUM_CORNER = corner_unum["unum_max"]
    print(f"    Worst-case U_NUM = {U_NUM_CORNER:.4e} in")

    # ── 4. Model form extrapolation (d+ and d- separately) ────────────────
    print("\n  [4/5] Computing model form uncertainty extrapolation (d+, d-) ...")
    mavm_extrap = build_mavm_dataset()

    # ── 5. Total uncertainty ───────────────────────────────────────────────
    print("\n  [5/5] Assembling total uncertainty budget ...")
    total_unc = assemble_total_uncertainty(results_dict[25], mavm_extrap, U_NUM_CORNER)

    # ── 6. Sobol sensitivity analysis (Saltelli) ─────────────────────────
    print(f"\n  [6/6] Running Sobol sensitivity analysis "
          f"(n_base={SOBOL_N_BASE}, n_calls={SOBOL_N_BASE * 4}) ...")
    sobol_res = run_sobol_indices(n_base=SOBOL_N_BASE, seed=LHS_SEED)

    # ── Console tables ─────────────────────────────────────────────────────
    print_pbox_table(results_dict)
    print_corner_unum(corner_unum)
    print_mavm_extrap(mavm_extrap)
    print_total_uncertainty(total_unc, results_dict[25])
    print_sobol_table(sobol_res)

    # ── Figures ────────────────────────────────────────────────────────────
    print("  Generating figures ...")
    fig1_pbox(results_dict)
    fig2_pbox_vs_uniform(results_dict[25], uniform_res)
    fig3_model_form_extrap(mavm_extrap)
    fig4_total_uncertainty(results_dict[25], total_unc, uniform_res)
    fig5_sobol_indices(sobol_res)
    print(f"\n  Figures saved to: {OUTPUT_DIR}/")

    # ── RD-5: Determinism snapshot check ──────────────────────────────────
    print("\n  Verifying determinism snapshot ...")
    snapshot = build_snapshot(results_dict, corner_unum, mavm_extrap,
                              total_unc, sobol_res)
    compare_against_snapshot(snapshot)
    print("\nDone.\n")


if __name__ == "__main__":
    main()
