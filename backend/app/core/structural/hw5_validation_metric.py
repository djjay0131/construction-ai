"""
hw5_validation_metric.py — Validation Metric for the EB FD Beam Solver

AOE/CS/ME 6444 — Verification and Validation in Scientific Computing
Homework #5 | Spring 2026 | Dr. Chris Roy
Authors: Jason Cusati & Cheng-Shun Chuang

Physical Case:
    8-ft simply-supported LVL residential header under uniform distributed load.
    Same physical case as HW3 (code verification) and HW4 (solution verification).

Aleatory Uncertain Input:
    Elastic modulus E ~ N(µ = 1,600,000 psi, σ = 160,000 psi)
    CoV = 10 % — physically representative of LVL manufacturing variability.

SRQ (System Response Quantity):
    w_max — peak mid-span deflection [in]
    Chosen because HW4 confirmed p_obs ≈ 2.00 (asymptotic, F_s = 1.25, U_NUM < 0.28%).
    M_max / σ_max are noise-dominated and excluded from the UQ study.

Simulation Grid:
    N = 20 (h = 4.800 in) — the parametric-study grid validated in HW4.
    U_NUM(w_max, N=20) = 0.0625 % — negligible relative to input uncertainty.

Experimental Data:
    Option #2 — Synthetic data generated from:
        E_minus = µ − σ = 1,440,000 psi  →  w_max(E_minus) = β (larger)
        E_plus  = µ + σ = 1,760,000 psi  →  w_max(E_plus)  = α (smaller)
        α = min SRQ,  β = max SRQ

    Dataset 1  (5 points):  SRQ = α + χ₁(β − α)
        χ₁ = [0.55, 0.95, 1.0, 1.1, 1.5]

    Dataset 2  (10 points):  SRQ = α + χ₂(β − α)
        χ₂ = [0.1, 0.4, 0.6, 0.75, 0.8, 0.9, 0.91, 0.97, 1.3, 1.6]

Simulation Sampling:
    Latin Hypercube Sampling (LHS) from N(µ_E, σ_E).
    Sample sizes: 10, 25, 100.
    Random seed fixed at 42 for reproducibility.

Validation Metrics:
    AVM  = ∫|F_sim(y) − F_exp(y)| dy   (unsigned, always ≥ 0)
    MAVM = ∫[F_sim(y) − F_exp(y)] dy   (signed; > 0 → simulation under-predicts)

    Both computed exactly as the area between two step functions evaluated on
    the union of all data/sample points.

Outputs:
    Console:
        Table 1 — Synthetic experimental datasets (α, β, all SRQ values)
        Table 2 — LHS sample statistics for each sample size
        Table 3 — AVM / MAVM results for both datasets × 3 sample sizes
    Figures  (written to ./hw5_figures/):
        fig1_datasets.{pdf,png}          — Experimental EDFs for both datasets
        fig2_cdf_dataset1.{pdf,png}      — CDF comparison, Dataset 1 (1×3 grid)
        fig3_cdf_dataset2.{pdf,png}      — CDF comparison, Dataset 2 (1×3 grid)
        fig4_avm_mavm_bar.{pdf,png}      — AVM & MAVM summary bar charts

Run:
    cd construction-ai/backend/app/core/structural
    python hw5_validation_metric.py
"""

from __future__ import annotations

import math
import os
import sys
from typing import Dict, List, Tuple

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.special import ndtri          # inverse normal CDF  (probit)
from scipy.stats import norm as sp_norm  # normal distribution utilities

sys.path.insert(0, os.path.dirname(__file__))
from beam_solver import BeamGeometry, BeamMaterial, solve_simply_supported

# ============================================================
# Physical Setup  (identical to HW3 / HW4)
# ============================================================
L_FT     = 8.0
L        = L_FT * 12.0       # 96.0 in
B        = 3.5                # 3.5 in (width)
D        = 11.25              # 11.25 in (depth)
E_NOM    = 1_600_000.0        # nominal E [psi]
Q0_LBFT  = 500.0              # 500 lb/ft
Q0       = Q0_LBFT / 12.0    # 41.6667 lb/in
FB       = 900.0              # allowable bending stress [psi]
FV       = 180.0              # allowable shear stress [psi]

GEO  = BeamGeometry(span_in=L, width_in=B, depth_in=D)
I    = GEO.moment_of_inertia  # 415.2832 in^4

# Closed-form reference (w_max = 5 q L^4 / 384 EI); used for checks only
EI_NOM        = E_NOM * I
W_MAX_EXACT   = 5.0 * Q0 * L**4 / (384.0 * EI_NOM)   # ≈ 0.06935 in

# ============================================================
# Aleatory Uncertain Input:  E ~ N(µ_E, σ_E)
# ============================================================
MU_E    = 1_600_000.0   # [psi]  same as nominal
SIGMA_E = 160_000.0     # [psi]  10 % CoV — representative LVL variability

# Parametric grid (validated in HW4: U_NUM = 0.0625 % for w_max at N=20)
N_GRID  = 20

# ============================================================
# Synthetic Experimental Data  (Option #2)
# ============================================================
CHI_1 = np.array([0.55, 0.95, 1.0, 1.1, 1.5])
CHI_2 = np.array([0.1, 0.4, 0.6, 0.75, 0.8, 0.9, 0.91, 0.97, 1.3, 1.6])

SAMPLE_SIZES = [10, 25, 100]
LHS_SEED     = 42

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "hw5_figures")

# ── Matplotlib style (consistent with HW4) ─────────────────────────────────
_RC = {
    "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11,
    "legend.fontsize": 9, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "figure.dpi": 150,
}


# ============================================================
# Helper: deterministic beam solve for a given E
# ============================================================

def w_max_for_E(E_psi: float) -> float:
    """Return w_max [in] from the FD solver at N_GRID nodes for elastic modulus E."""
    mat = BeamMaterial(E_psi=E_psi, Fb_psi=FB, Fv_psi=FV)
    result = solve_simply_supported(GEO, mat, Q0, n_nodes=N_GRID + 1)
    return result.w_max


# ============================================================
# Latin Hypercube Sampling from N(µ, σ)
# ============================================================

def lhs_normal(mu: float, sigma: float, n: int, seed: int = 42) -> np.ndarray:
    """
    Draw n Latin Hypercube samples from N(mu, sigma).

    Each of n equal-probability strata in [0, 1] is sampled once
    (uniformly within the stratum), then the inverse-normal CDF is applied.

    Parameters
    ----------
    mu, sigma : distribution parameters
    n         : number of samples
    seed      : random seed for reproducibility

    Returns
    -------
    1-D array of n samples from N(mu, sigma)
    """
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)                          # random permutation of strata
    u    = (perm + rng.uniform(0.0, 1.0, n)) / n      # one uniform draw per stratum
    u    = np.clip(u, 1e-12, 1.0 - 1e-12)             # guard against ndtri edge cases
    return mu + sigma * ndtri(u)                       # inverse normal CDF


# ============================================================
# Synthetic Experimental Data Generation
# ============================================================

def build_synthetic_datasets() -> Dict:
    """
    Compute α, β, and both synthetic experimental datasets.

    Returns
    -------
    dict with keys:
        E_minus, E_plus  : E = µ ± σ
        w_minus, w_plus  : w_max at E_minus, E_plus [in]
        alpha, beta      : min, max SRQ
        delta            : β − α
        exp1, exp2       : SRQ arrays for Dataset 1 and 2
    """
    E_minus = MU_E - SIGMA_E   # 1,440,000 psi  → larger deflection
    E_plus  = MU_E + SIGMA_E   # 1,760,000 psi  → smaller deflection

    w_minus = w_max_for_E(E_minus)   # β (larger)
    w_plus  = w_max_for_E(E_plus)    # α (smaller)

    alpha = min(w_minus, w_plus)
    beta  = max(w_minus, w_plus)
    delta = beta - alpha

    exp1 = alpha + CHI_1 * delta
    exp2 = alpha + CHI_2 * delta

    return dict(
        E_minus=E_minus, E_plus=E_plus,
        w_minus=w_minus, w_plus=w_plus,
        alpha=alpha, beta=beta, delta=delta,
        exp1=exp1, exp2=exp2,
    )


# ============================================================
# AVM / MAVM Computation
# ============================================================

def compute_avm_mavm(
    sim_samples: np.ndarray,
    exp_data: np.ndarray,
) -> Dict[str, float]:
    """
    Compute the Area Validation Metric (AVM) and Modified AVM (MAVM).

    Both are computed exactly as the area between two step (empirical)
    distribution functions evaluated at every data/sample point.

    AVM  = ∫ |F_sim(y) − F_exp(y)| dy  (unsigned, L1 distance between CDFs)
    MAVM = ∫ [F_sim(y) − F_exp(y)] dy  (signed Wasserstein-type metric)

    Sign convention for MAVM:
        MAVM > 0  →  F_sim generally above F_exp  →  simulation assigns more
                     probability below any given value  →  simulation
                     UNDER-PREDICTS deflection (unconservative for deflection
                     limit state)
        MAVM < 0  →  simulation OVER-PREDICTS deflection (conservative)

    Algorithm:
        Build the union of all jump points; on each interval the two CDFs are
        both constant. Integrate piecewise.

    Parameters
    ----------
    sim_samples : 1-D array of simulation SRQ values (LHS realisations)
    exp_data    : 1-D array of experimental/synthetic SRQ values

    Returns
    -------
    dict with keys: avm, mavm, n_sim, n_exp
    """
    n_sim = len(sim_samples)
    n_exp = len(exp_data)

    # Union of all jump points (both distributions)
    points = np.sort(np.unique(np.concatenate([sim_samples, exp_data])))

    avm  = 0.0
    mavm = 0.0

    for k in range(len(points) - 1):
        x_left  = points[k]
        x_right = points[k + 1]
        width   = x_right - x_left

        # Right-continuous CDF: F(y) = P(X ≤ y)
        f_sim = np.sum(sim_samples <= x_left) / n_sim
        f_exp = np.sum(exp_data    <= x_left) / n_exp

        diff  = f_sim - f_exp
        avm  += width * abs(diff)
        mavm += width * diff

    return dict(avm=avm, mavm=mavm, n_sim=n_sim, n_exp=n_exp)


# ============================================================
# Run Full Validation Study
# ============================================================

def run_validation_study(datasets: Dict) -> Dict:
    """
    For each LHS sample size, propagate E uncertainty, then compute
    AVM/MAVM against both experimental datasets.

    Returns nested dict:
        results[n_samples]["dataset1" | "dataset2"] = avm_mavm_dict
        results[n_samples]["E_samples"]             = array of E values
        results[n_samples]["w_samples"]             = array of w_max values
    """
    results: Dict = {}

    for n_sim in SAMPLE_SIZES:
        E_samples = lhs_normal(MU_E, SIGMA_E, n_sim, seed=LHS_SEED)
        w_samples = np.array([w_max_for_E(E) for E in E_samples])

        ds1 = compute_avm_mavm(w_samples, datasets["exp1"])
        ds2 = compute_avm_mavm(w_samples, datasets["exp2"])

        results[n_sim] = dict(
            E_samples=E_samples,
            w_samples=w_samples,
            dataset1=ds1,
            dataset2=ds2,
        )
        print(f"    LHS n={n_sim:>3d}:  E_mean={np.mean(E_samples):.1f}  "
              f"w_mean={np.mean(w_samples):.6f} in  "
              f"AVM1={ds1['avm']:.5f}  AVM2={ds2['avm']:.5f}")

    return results


# ============================================================
# Console Output
# ============================================================

def print_header(title: str) -> None:
    bar = "=" * 72
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def print_dataset_table(datasets: Dict) -> None:
    print_header("Table 1 — Synthetic Experimental Datasets")

    print(f"\n  Aleatory input:  E ~ N(µ = {MU_E:.0f} psi,  σ = {SIGMA_E:.0f} psi)"
          f"  [CoV = {SIGMA_E/MU_E*100:.0f}%]")
    print(f"\n  E at µ−σ = {datasets['E_minus']:.0f} psi  →  w_max = {datasets['w_minus']:.7f} in  (β = max SRQ)")
    print(f"  E at µ+σ = {datasets['E_plus']:.0f} psi  →  w_max = {datasets['w_plus']:.7f} in  (α = min SRQ)")
    print(f"\n  α = {datasets['alpha']:.7f} in")
    print(f"  β = {datasets['beta']:.7f} in")
    print(f"  β − α = {datasets['delta']:.7f} in\n")

    print("  Dataset 1  (χ₁ = [0.55, 0.95, 1.0, 1.1, 1.5]):")
    print(f"  {'#':>3}  {'χ₁':>8}  {'SRQ = α + χ(β−α)  [in]':>28}")
    print("  " + "-" * 44)
    for i, (chi, srq) in enumerate(zip(CHI_1, datasets["exp1"])):
        print(f"  {i+1:>3}  {chi:>8.3f}  {srq:>28.7f}")

    print(f"\n  Dataset 2  (χ₂ = [0.1, 0.4, 0.6, 0.75, 0.8, 0.9, 0.91, 0.97, 1.3, 1.6]):")
    print(f"  {'#':>3}  {'χ₂':>8}  {'SRQ = α + χ(β−α)  [in]':>28}")
    print("  " + "-" * 44)
    for i, (chi, srq) in enumerate(zip(CHI_2, datasets["exp2"])):
        print(f"  {i+1:>3}  {chi:>8.3f}  {srq:>28.7f}")
    print()


def print_lhs_table(results: Dict) -> None:
    print_header("Table 2 — LHS Sample Statistics (E and w_max)")
    hdr = (f"  {'n_sim':>6}  {'E_mean [psi]':>14}  {'E_std [psi]':>12}  "
           f"{'w_mean [in]':>12}  {'w_std [in]':>11}  "
           f"{'w_min [in]':>11}  {'w_max [in]':>11}")
    print(hdr)
    print("  " + "-" * 86)
    for n_sim, res in sorted(results.items()):
        E = res["E_samples"]
        w = res["w_samples"]
        print(f"  {n_sim:>6}  {np.mean(E):>14.1f}  {np.std(E):>12.1f}  "
              f"{np.mean(w):>12.7f}  {np.std(w):>11.7f}  "
              f"{np.min(w):>11.7f}  {np.max(w):>11.7f}")
    print()


def print_avm_table(results: Dict) -> None:
    print_header("Table 3 — AVM / MAVM Results")

    for ds_key, ds_label in [("dataset1", "Dataset 1 (5 pts)"),
                              ("dataset2", "Dataset 2 (10 pts)")]:
        print(f"\n  {ds_label}")
        hdr = (f"  {'n_sim':>6}  {'AVM [in]':>12}  {'MAVM [in]':>12}  "
               f"{'|MAVM/AVM|':>12}  Interpretation")
        print(hdr)
        print("  " + "-" * 76)
        for n_sim, res in sorted(results.items()):
            m = res[ds_key]
            avm  = m["avm"]
            mavm = m["mavm"]
            ratio = abs(mavm) / avm if avm > 1e-15 else float("nan")
            interp = "sim under-predicts (unconservative)" if mavm > 0 else "sim over-predicts (conservative)"
            print(f"  {n_sim:>6}  {avm:>12.6f}  {mavm:>12.6f}  {ratio:>12.4f}  {interp}")
    print()


# ============================================================
# Empirical CDF / EDF utilities
# ============================================================

def ecdf(data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return (x, F) arrays for plotting the empirical CDF as a step function."""
    x = np.sort(data)
    F = np.arange(1, len(x) + 1) / len(x)
    # Prepend a point at x - epsilon so the step starts at 0
    x = np.concatenate([[x[0] - 1e-12], x])
    F = np.concatenate([[0.0], F])
    return x, F


# ============================================================
# Figure Generation
# ============================================================

def _save(fig: plt.Figure, stem: str) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for ext in ("pdf", "png"):
        path = os.path.join(OUTPUT_DIR, f"{stem}.{ext}")
        fig.savefig(path, bbox_inches="tight", dpi=300)
    print(f"    saved  {stem}.{{pdf,png}}")


def fig1_datasets(datasets: Dict) -> None:
    """Figure 1 — EDF of both experimental datasets with α and β markers."""
    alpha = datasets["alpha"]
    beta  = datasets["beta"]
    delta = datasets["delta"]

    with plt.rc_context(_RC):
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))

        for ax, chi, exp_data, ds_label, n_pts in [
            (axes[0], CHI_1, datasets["exp1"], "Dataset 1", 5),
            (axes[1], CHI_2, datasets["exp2"], "Dataset 2", 10),
        ]:
            x, F = ecdf(exp_data)
            ax.step(x * 1000, F, where="post", color="navy", lw=2,
                    label=f"Experimental EDF ({n_pts} pts)")

            # Mark individual data points
            ax.scatter(np.sort(exp_data) * 1000,
                       np.arange(1, n_pts + 1) / n_pts,
                       s=40, zorder=5, color="navy")

            # α and β lines
            ax.axvline(alpha * 1000, color="green",  ls="--", lw=1.2, label=f"α (E₊, {alpha*1000:.2f} ×10⁻³ in)")
            ax.axvline(beta  * 1000, color="orange", ls="--", lw=1.2, label=f"β (E₋, {beta*1000:.2f} ×10⁻³ in)")

            ax.set_xlabel("$w_{\\mathrm{max}}$ [10$^{-3}$ in]")
            ax.set_ylabel("Cumulative probability")
            ax.set_title(f"{ds_label}: Synthetic Experimental EDF")
            ax.legend(fontsize=8)
            ax.set_ylim(-0.05, 1.10)
            ax.grid(True, ls=":", alpha=0.5)

        fig.suptitle("Synthetic Experimental Datasets\n"
                     r"$E \sim \mathcal{N}(\mu_E=1{,}600{,}000\ \mathrm{psi},\ "
                     r"\sigma_E=160{,}000\ \mathrm{psi})$  [CoV = 10\%]",
                     y=1.01)
        fig.tight_layout()
        _save(fig, "fig1_datasets")
        plt.close(fig)


def _cdf_comparison_figure(
    datasets: Dict,
    results: Dict,
    ds_key: str,
    ds_label: str,
    stem: str,
) -> None:
    """
    One row of 3 subplots: simulation CDF vs experimental EDF for each sample size.
    Shaded area = AVM (|F_sim − F_exp|).
    """
    exp_data = datasets[ds_key.replace("dataset", "exp")]   # "exp1" or "exp2"

    x_exp, F_exp_step = ecdf(exp_data)

    with plt.rc_context(_RC):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), sharey=True)

        for ax, n_sim in zip(axes, SAMPLE_SIZES):
            w_sim = results[n_sim]["w_samples"]
            m     = results[n_sim][ds_key]
            avm   = m["avm"]
            mavm  = m["mavm"]

            x_sim, F_sim_step = ecdf(w_sim)

            # Build a fine union of all jump points for shading
            all_pts = np.sort(np.unique(np.concatenate([
                np.sort(w_sim), np.sort(exp_data)
            ])))
            # Add small padding on left/right
            pad = (all_pts[-1] - all_pts[0]) * 0.05
            x_fill = np.sort(np.concatenate([
                [all_pts[0] - pad], all_pts - 1e-15, all_pts + 1e-15,
                [all_pts[-1] + pad]
            ]))

            F_s = np.array([np.sum(w_sim    <= y) / len(w_sim)    for y in x_fill])
            F_e = np.array([np.sum(exp_data <= y) / len(exp_data) for y in x_fill])

            # Fill AVM regions
            ax.fill_between(x_fill * 1000, F_s, F_e,
                            where=(F_s >= F_e), alpha=0.30, color="steelblue",
                            label="Sim above Exp")
            ax.fill_between(x_fill * 1000, F_s, F_e,
                            where=(F_s <  F_e), alpha=0.30, color="tomato",
                            label="Exp above Sim")

            # Plot CDFs
            ax.step(x_exp * 1000, F_exp_step, where="post",
                    color="navy", lw=2.0, label="Exp EDF")
            ax.step(x_sim * 1000, F_sim_step, where="post",
                    color="steelblue", lw=1.5, ls="--", label=f"Sim CDF (n={n_sim})")

            sign_str = ">" if mavm > 0 else "<"
            ax.set_title(
                f"$n_{{\\mathrm{{sim}}}}={n_sim}$\n"
                f"AVM $={avm*1000:.4f}\\times10^{{-3}}$~in\n"
                f"MAVM $={mavm*1000:+.4f}\\times10^{{-3}}$~in"
            )
            ax.set_xlabel("$w_{\\mathrm{max}}$ [10$^{-3}$ in]")
            if ax is axes[0]:
                ax.set_ylabel("Cumulative probability")
            ax.set_ylim(-0.05, 1.10)
            ax.grid(True, ls=":", alpha=0.5)
            ax.legend(fontsize=7.5, loc="upper left")

        fig.suptitle(
            f"Simulation CDF vs Experimental EDF — {ds_label}\n"
            r"$E \sim \mathcal{N}(1{,}600{,}000,\ 160{,}000^2)$ psi  |  "
            r"$w_{\max}$  [in]  |  Grid $N=20$   (HW4: $U_{\mathrm{NUM}}=0.0625\%$)",
            y=1.01, fontsize=10,
        )
        fig.tight_layout()
        _save(fig, stem)
        plt.close(fig)


def fig2_cdf_dataset1(datasets: Dict, results: Dict) -> None:
    _cdf_comparison_figure(
        datasets, results, "dataset1", "Dataset 1 (5 experimental points)",
        "fig2_cdf_dataset1"
    )


def fig3_cdf_dataset2(datasets: Dict, results: Dict) -> None:
    _cdf_comparison_figure(
        datasets, results, "dataset2", "Dataset 2 (10 experimental points)",
        "fig3_cdf_dataset2"
    )


def fig4_avm_mavm_bar(results: Dict) -> None:
    """Figure 4 — Bar charts of AVM and MAVM for all cases."""
    n_sims = SAMPLE_SIZES
    x = np.arange(len(n_sims))
    width = 0.35

    with plt.rc_context(_RC):
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

        for ax, metric, ylabel, title in [
            (axes[0], "avm",  "AVM [in]",  "Area Validation Metric (AVM)"),
            (axes[1], "mavm", "MAVM [in]", "Modified AVM (MAVM)"),
        ]:
            vals1 = np.array([results[n][f"dataset1"][metric] for n in n_sims])
            vals2 = np.array([results[n][f"dataset2"][metric] for n in n_sims])

            bars1 = ax.bar(x - width/2, vals1 * 1000, width, label="Dataset 1",
                           color="steelblue", alpha=0.85, edgecolor="k", lw=0.6)
            bars2 = ax.bar(x + width/2, vals2 * 1000, width, label="Dataset 2",
                           color="tomato",    alpha=0.85, edgecolor="k", lw=0.6)

            # Value labels
            for bar in bars1:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2, h + 0.005,
                        f"{h:.3f}", ha="center", va="bottom", fontsize=7.5)
            for bar in bars2:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2, h + 0.005,
                        f"{h:.3f}", ha="center", va="bottom", fontsize=7.5)

            if metric == "mavm":
                ax.axhline(0, color="k", lw=0.8, ls="--")
                ax.annotate("← over-predicts", xy=(0.01, 0.15), xycoords="axes fraction",
                            fontsize=8, color="gray")
                ax.annotate("under-predicts →", xy=(0.01, 0.80), xycoords="axes fraction",
                            fontsize=8, color="gray")

            ax.set_xticks(x)
            ax.set_xticklabels([f"$n={n}$" for n in n_sims])
            ax.set_xlabel("LHS sample size ($n_{\\mathrm{sim}}$)")
            ax.set_ylabel(f"{ylabel} $[\\times 10^{{-3}}\\,\\mathrm{{in}}]$")
            ax.set_title(title)
            ax.legend()
            ax.grid(True, axis="y", ls=":", alpha=0.5)

        fig.suptitle(
            "AVM and MAVM Summary — Both Datasets × All Sample Sizes\n"
            r"$w_{\max}$  SRQ  |  $E \sim \mathcal{N}(1{,}600{,}000,\ 160{,}000^2)$ psi"
        )
        fig.tight_layout()
        _save(fig, "fig4_avm_mavm_bar")
        plt.close(fig)


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("\n" + "=" * 72)
    print("  HW5 — Validation Metric  |  EB Beam Solver  |  Spring 2026")
    print("  Authors: Jason Cusati & Cheng-Shun Chuang")
    print("=" * 72)

    # 1. Build synthetic experimental datasets
    print("\n[1/4] Building synthetic experimental datasets …")
    datasets = build_synthetic_datasets()
    print_dataset_table(datasets)

    # 2. Run LHS + model propagation
    print("\n[2/4] Running LHS sampling and model propagation …")
    results = run_validation_study(datasets)
    print_lhs_table(results)

    # 3. Compute and display AVM/MAVM
    print("\n[3/4] AVM / MAVM Results:")
    print_avm_table(results)

    # 4. Generate figures
    print("\n[4/4] Generating figures …")
    fig1_datasets(datasets)
    fig2_cdf_dataset1(datasets, results)
    fig3_cdf_dataset2(datasets, results)
    fig4_avm_mavm_bar(results)

    print(f"\n  All figures saved to: {OUTPUT_DIR}")
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
