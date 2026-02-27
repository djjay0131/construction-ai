"""
hw3_verification.py — Code Verification for the Euler-Bernoulli FD Beam Solver

AOE/CS/ME 6444 — Verification and Validation in Scientific Computing
Homework #3 | Spring 2026 | Dr. Chris Roy
Authors: Jason Cusati & Cheng-Shun Chuang

Approach: Option 2 — Exact Solution
    w_exact(x) = q0/(24*EI) * (x^4 - 2*L*x^3 + L^3*x)

Outputs:
    - Convergence table (console)
    - SRQ table (console)
    - hw3_figures/fig1_convergence_loglog.{pdf,png}
    - hw3_figures/fig2_local_error_N160.{pdf,png}
    - hw3_figures/fig3_srq_convergence.{pdf,png}

Run:
    cd construction-ai/backend/app/core/structural
    python hw3_verification.py
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")           # headless — no display required
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Allow import from same directory
sys.path.insert(0, os.path.dirname(__file__))
from beam_solver import (
    BeamGeometry,
    BeamMaterial,
    solve_simply_supported,
    exact_simply_supported,
)

# ---------------------------------------------------------------------------
# Test case: 8-ft LVL residential header (inch-pound units)
# ---------------------------------------------------------------------------
L_FT    = 8.0
L       = L_FT * 12.0          # 96.0 in
B       = 3.5                   # in
D       = 11.25                 # in
E_PSI   = 1_600_000.0           # psi
Q0_LBFT = 500.0                 # lb/ft
Q0      = Q0_LBFT / 12.0       # 41.6667 lb/in
FB      = 900.0                 # allowable bending [psi]
FV      = 180.0                 # allowable shear [psi]

GEO  = BeamGeometry(span_in=L, width_in=B, depth_in=D)
MAT  = BeamMaterial(E_psi=E_PSI, Fb_psi=FB, Fv_psi=FV)
EI   = E_PSI * GEO.moment_of_inertia

# Exact SRQ values
W_MAX_EXACT   = 5.0 * Q0 * L**4 / (384.0 * EI)   # 0.06935026 in
M_MAX_EXACT   = Q0 * L**2 / 8.0                   # 48000.00 lb·in
SIG_MAX_EXACT = M_MAX_EXACT / GEO.section_modulus  # 650.1587 psi

GRID_LEVELS = [10, 20, 40, 80, 160]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "hw3_figures")

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def l2_norm(h: float, diff: np.ndarray) -> float:
    """Discrete L2 norm: sqrt(h * sum(diff^2)) — approximates ||e||_L2 integral."""
    return math.sqrt(h * np.sum(diff**2))


def linf_norm(diff: np.ndarray) -> float:
    """Discrete L-infinity norm: max|diff|."""
    return float(np.max(np.abs(diff)))


def p_hat(e_coarse: float, e_fine: float) -> float:
    """Observed order of accuracy for halved grid spacing."""
    return math.log(e_coarse / e_fine) / math.log(2.0)


# ---------------------------------------------------------------------------
# Grid convergence sweep
# ---------------------------------------------------------------------------

def run_convergence_sweep() -> dict:
    """Solve on all grid levels; return dict of results."""
    results = {}
    for N in GRID_LEVELS:
        n_nodes = N + 1
        h = L / N

        # FD solution
        fd = solve_simply_supported(GEO, MAT, Q0, n_nodes=n_nodes)
        w_h = fd.w

        # Exact solution at same grid points
        x_nodes, w_ex = exact_simply_supported(GEO, MAT, Q0, n_nodes=n_nodes)

        diff = w_h - w_ex
        e_l2   = l2_norm(h, diff)
        e_linf = linf_norm(diff)

        # SRQ errors (relative, percent)
        e_wmax  = abs(fd.w_max - W_MAX_EXACT)  / W_MAX_EXACT  * 100.0
        e_Mmax  = abs(fd.M_max - M_MAX_EXACT)  / M_MAX_EXACT  * 100.0
        e_sigma = abs(fd.sigma_max - SIG_MAX_EXACT) / SIG_MAX_EXACT * 100.0

        results[N] = dict(
            h=h, x=x_nodes, w_h=w_h, w_ex=w_ex, diff=diff,
            e_l2=e_l2, e_linf=e_linf,
            e_wmax=e_wmax, e_Mmax=e_Mmax, e_sigma=e_sigma,
            fd=fd,
        )
    return results


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_convergence_table(results: dict) -> None:
    hdr = f"{'N':>5}  {'h [in]':>9}  {'e_L2 [in]':>13}  {'e_Linf [in]':>13}  {'p_L2':>7}  {'p_Linf':>7}"
    print("\n" + "="*len(hdr))
    print("Grid Convergence — Euler-Bernoulli FD Beam Solver (Option 2: Exact Solution)")
    print("="*len(hdr))
    print(hdr)
    print("-"*len(hdr))

    prev_l2 = prev_linf = None
    for N in GRID_LEVELS:
        r = results[N]
        if prev_l2 is not None:
            p_l2   = f"{p_hat(prev_l2,   r['e_l2']):7.3f}"
            p_linf = f"{p_hat(prev_linf, r['e_linf']):7.3f}"
        else:
            p_l2 = p_linf = "    ---"
        print(f"{N:>5}  {r['h']:>9.4f}  {r['e_l2']:>13.6e}  {r['e_linf']:>13.6e}  {p_l2}  {p_linf}")
        prev_l2, prev_linf = r['e_l2'], r['e_linf']

    print("="*len(hdr))


def print_srq_table(results: dict) -> None:
    print("\n--- SRQ Convergence ---")
    print(f"{'SRQ':<18}  {'Exact':>14}  {'N=10':>12}  {'N=160':>12}  {'Err@N160':>10}")
    print("-"*72)

    r10  = results[10]
    r160 = results[160]

    rows = [
        ("w_max [in]",    W_MAX_EXACT,   r10['fd'].w_max,   r160['fd'].w_max,   r160['e_wmax'],  "%"),
        ("M_max [lb·in]", M_MAX_EXACT,   r10['fd'].M_max,   r160['fd'].M_max,   r160['e_Mmax'],  "%"),
        ("sigma_max [psi]", SIG_MAX_EXACT, r10['fd'].sigma_max, r160['fd'].sigma_max, r160['e_sigma'], "%"),
    ]
    for label, exact, v10, v160, err, unit in rows:
        print(f"{label:<18}  {exact:>14.6g}  {v10:>12.6g}  {v160:>12.6g}  {err:>9.4f}{unit}")

    print(f"\nExact values: w_max={W_MAX_EXACT:.8f} in, "
          f"M_max={M_MAX_EXACT:.2f} lb·in, sigma_max={SIG_MAX_EXACT:.4f} psi")


def print_roundoff_table(results: dict) -> None:
    print("\n--- Round-Off Analysis (condition number of interior K block) ---")
    print(f"{'N':>5}  {'h [in]':>9}  {'kappa(K)':>12}  {'eps*kappa':>12}  {'roundoff [in]':>14}  {'trunc [in]':>12}")
    print("-"*75)
    for N in GRID_LEVELS:
        r = results[N]
        # Rebuild K interior block, compute condition number
        h = r['h']
        h4 = h**4
        size = N + 1
        K = np.zeros((size, size))
        K[0, 0] = 1.0
        K[1, 1] = 5.0 * EI / h4; K[1, 2] = -4.0 * EI / h4; K[1, 3] = 1.0 * EI / h4
        for i in range(2, N - 1):
            K[i, i-2] = 1.0*EI/h4; K[i, i-1] = -4.0*EI/h4
            K[i, i]   = 6.0*EI/h4; K[i, i+1] = -4.0*EI/h4; K[i, i+2] = 1.0*EI/h4
        K[N-1, N-3] = 1.0*EI/h4; K[N-1, N-2] = -4.0*EI/h4; K[N-1, N-1] = 5.0*EI/h4
        K[N, N] = 1.0
        K_int = K[1:N, 1:N]
        kappa = np.linalg.cond(K_int)
        eps = np.finfo(float).eps
        roundoff = eps * kappa * W_MAX_EXACT
        trunc = r['e_linf']
        print(f"{N:>5}  {h:>9.4f}  {kappa:>12.3e}  {eps*kappa:>12.3e}  {roundoff:>14.3e}  {trunc:>12.3e}")
    print("-"*75)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

STYLE = {
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.dpi": 150,
}

def save_fig(fig: plt.Figure, stem: str) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for ext in ("pdf", "png"):
        path = os.path.join(OUTPUT_DIR, f"{stem}.{ext}")
        fig.savefig(path, bbox_inches="tight", dpi=300)
    print(f"  saved {stem}.{{pdf,png}}")


def fig1_convergence_loglog(results: dict) -> None:
    """Log-log plot of L2 and Linf error norms vs h."""
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(5, 4))

        h_vals  = np.array([results[N]["h"]      for N in GRID_LEVELS])
        e_l2    = np.array([results[N]["e_l2"]   for N in GRID_LEVELS])
        e_linf  = np.array([results[N]["e_linf"] for N in GRID_LEVELS])

        ax.loglog(h_vals, e_l2,   "bo-", label=r"$L_2$ norm",      ms=6, lw=1.5)
        ax.loglog(h_vals, e_linf, "rs--", label=r"$L_\infty$ norm", ms=6, lw=1.5)

        # Reference slope-2 line anchored at coarsest grid (L2)
        C = e_l2[0] / h_vals[0]**2
        h_ref = np.array([h_vals[0], h_vals[-1]])
        ax.loglog(h_ref, C * h_ref**2, "k--", lw=1.2, label="Slope 2 reference")

        ax.set_xlabel(r"Grid Spacing $h$ [in]")
        ax.set_ylabel("Error Norm [in]")
        ax.set_title("Grid Convergence: FD Euler–Bernoulli Beam Solver")
        ax.legend(loc="upper left")
        ax.grid(True, which="both", color="gray", alpha=0.3, lw=0.5)
        ax.invert_xaxis()   # coarse → fine left to right in spirit

        fig.tight_layout()
        save_fig(fig, "fig1_convergence_loglog")
        plt.close(fig)


def fig2_local_error_N160(results: dict) -> None:
    """Local pointwise error e(x) = w_h - w_exact at N=160."""
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(5, 3.5))

        r   = results[160]
        x   = r["x"]
        err = r["diff"]

        ax.plot(x, err, "b-", lw=1.5, label=r"$e_i = w_h - w_\mathrm{exact}$")

        # Mark maximum
        idx_max = np.argmax(np.abs(err))
        ax.plot(x[idx_max], err[idx_max], "r*", ms=10, zorder=5)
        ax.annotate(f"max = {err[idx_max]:.2e} in",
                    xy=(x[idx_max], err[idx_max]),
                    xytext=(x[idx_max] - 18, err[idx_max] * 0.65),
                    fontsize=8,
                    arrowprops=dict(arrowstyle="->", color="red", lw=0.8))

        ax.axhline(0, color="gray", lw=0.6, ls=":")
        ax.set_xlabel(r"Position $x$ [in]")
        ax.set_ylabel(r"Pointwise Error $w_h - w_\mathrm{exact}$ [in]")
        ax.set_title(r"Local Discretization Error at $N = 160$")
        ax.set_xlim(0, L)
        ax.grid(True, color="gray", alpha=0.3, lw=0.5)
        ax.legend(loc="upper right")

        fig.tight_layout()
        save_fig(fig, "fig2_local_error_N160")
        plt.close(fig)


def fig3_srq_convergence(results: dict) -> None:
    """SRQ relative error (w_max %) vs h, log-log."""
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(5, 3.5))

        h_vals  = np.array([results[N]["h"]      for N in GRID_LEVELS])
        e_wmax  = np.array([results[N]["e_wmax"] for N in GRID_LEVELS])

        ax.loglog(h_vals, e_wmax, "bo-", label=r"$e_{w_\mathrm{max}}$ [%]", ms=6, lw=1.5)

        # Reference slope-2 anchored at coarsest
        C = e_wmax[0] / h_vals[0]**2
        h_ref = np.array([h_vals[0], h_vals[-1]])
        ax.loglog(h_ref, C * h_ref**2, "k--", lw=1.2, label="Slope 2 reference")

        ax.text(0.55, 0.12,
                r"$M_\mathrm{max},\,\sigma_\mathrm{max}$: machine precision",
                transform=ax.transAxes, fontsize=8, color="gray")

        ax.set_xlabel(r"Grid Spacing $h$ [in]")
        ax.set_ylabel(r"SRQ Relative Error [\%]")
        ax.set_title(r"SRQ Convergence: $w_\mathrm{max}$ Relative Error")
        ax.legend(loc="upper left")
        ax.grid(True, which="both", color="gray", alpha=0.3, lw=0.5)
        ax.invert_xaxis()

        fig.tight_layout()
        save_fig(fig, "fig3_srq_convergence")
        plt.close(fig)


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

def verify_convergence_rates(results: dict) -> None:
    prev_l2 = prev_linf = prev_wmax = None
    for N in GRID_LEVELS:
        r = results[N]
        if prev_l2 is not None:
            p_l2   = p_hat(prev_l2,   r["e_l2"])
            p_linf = p_hat(prev_linf, r["e_linf"])
            p_wmax = p_hat(prev_wmax, r["e_wmax"])
            assert 1.95 < p_l2   < 2.05, f"p_L2={p_l2:.3f} out of [1.95,2.05] at N={N}"
            assert 1.95 < p_linf < 2.05, f"p_Linf={p_linf:.3f} out of [1.95,2.05] at N={N}"
            assert 1.95 < p_wmax < 2.05, f"p_wmax={p_wmax:.3f} out of [1.95,2.05] at N={N}"
        prev_l2, prev_linf, prev_wmax = r["e_l2"], r["e_linf"], r["e_wmax"]
    print("\nAll convergence rate assertions passed (p_hat in [1.95, 2.05]).")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\nTest case: {L_FT}-ft LVL header, b={B} in, d={D} in, "
          f"E={E_PSI:,} psi, q0={Q0_LBFT:.0f} lb/ft")
    print(f"EI = {EI:.4e} lb·in², L = {L:.1f} in")
    print(f"Exact: w_max = {W_MAX_EXACT:.8f} in, "
          f"M_max = {M_MAX_EXACT:.2f} lb·in, "
          f"sigma_max = {SIG_MAX_EXACT:.4f} psi")

    results = run_convergence_sweep()

    print_convergence_table(results)
    print_srq_table(results)
    print_roundoff_table(results)
    verify_convergence_rates(results)

    print("\nGenerating figures ...")
    fig1_convergence_loglog(results)
    fig2_local_error_N160(results)
    fig3_srq_convergence(results)
    print(f"Figures saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
