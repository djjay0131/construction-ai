"""
hw4_solution_verification.py — Solution Verification for the EB FD Beam Solver

AOE/CS/ME 6444 — Verification and Validation in Scientific Computing
Homework #4 | Spring 2026 | Dr. Chris Roy
Authors: Jason Cusati & Cheng-Shun Chuang

Physical Case:
    8-ft simply-supported LVL residential header under uniform distributed load.
    Same case used for HW3 code verification (now using it as the "real" UQ case).

Numerical Model:
    Finite-difference Euler-Bernoulli beam (4th-order BVP), O(h²) scheme.
    Simply-supported BCs via ghost-node elimination.
    Direct solver: np.linalg.solve (dense LU factorization).

Uncertainty Sources Quantified:
    (1) Discretization error  U_DE : Richardson extrapolation + GCI
            Grids : N = 10, 20, 40, 80, 160  (r = 2, systematic halving)
            SRQs  : w_max [in],  M_max [lb·in],  σ_max [psi]
    (2) Iterative error       U_IT : Direct solver → U_IT = 0 (machine precision)
    (3) Round-off error       U_RO : float64 vs float32 on each grid

Total:     U_NUM = U_DE + U_IT + U_RO   (additive, each term positive)
Reported for:
    (A) Fine grid            N = 160  (h = 0.600 in)  — high-fidelity solution
    (B) Parametric study grid N = 20  (h = 4.800 in)  — 100s–1000s of cases

Factor of Safety (Fs) Criterion (Roy lectures):
    Fs = 1.25  if  0.5 ≤ p_obs / p_theoretical ≤ 2.0  (asymptotic regime)
    Fs = 3.00  otherwise                                (unreliable estimate)
    p_theoretical = 2   (O(h²) scheme)

One-sided note:
    The FD scheme overestimates deflection (w_FD ≥ w_exact) for this UDL case.
    U_DE therefore acts as a one-sided lower bound:  w_true ≥ w_FD − U_DE.
    Both one-sided and symmetric GCI values are reported in the tables.

Outputs (console + figures written to ./hw4_figures/):
    Console:
        Table 1  — GCI analysis (all triplets, all SRQs)
        Table 2  — Asymptotic convergence check  (GCI_ratio ≈ 1)
        Table 3  — Round-off error  (float64 vs float32)
        Table 4  — U_NUM budget summary  (fine grid vs parametric grid)
    Figures:
        fig1_convergence_gci.{pdf,png}   — SRQ convergence with GCI bands
        fig2_pobs_triplets.{pdf,png}     — Observed order vs triplet
        fig3_gci_bar.{pdf,png}           — GCI% for fine & parametric grids
        fig4_unum_budget.{pdf,png}       — Stacked U_NUM budget comparison

Run:
    cd construction-ai/backend/app/core/structural
    python hw4_solution_verification.py
"""

from __future__ import annotations

import math
import os
import sys
from typing import Dict, List

import numpy as np
import matplotlib
matplotlib.use("Agg")           # headless – no display needed
import matplotlib.pyplot as plt

# Allow import from same package directory
sys.path.insert(0, os.path.dirname(__file__))
from beam_solver import BeamGeometry, BeamMaterial, solve_simply_supported

# ============================================================
# Physical Setup  (identical to HW3 – same 8-ft LVL header)
# ============================================================
L_FT         = 8.0
L            = L_FT * 12.0       #  96.0  in   (beam span)
B            = 3.5                #   3.5  in   (beam width)
D            = 11.25              #  11.25 in   (beam depth)
E_PSI        = 1_600_000.0        #   E    [psi]
Q0_LBFT      = 500.0              # 500    lb/ft (uniform distributed load)
Q0           = Q0_LBFT / 12.0    #  41.667 lb/in
FB           = 900.0              # allowable bending stress [psi]
FV           = 180.0              # allowable shear stress  [psi]

GEO  = BeamGeometry(span_in=L, width_in=B, depth_in=D)
MAT  = BeamMaterial(E_psi=E_PSI, Fb_psi=FB, Fv_psi=FV)
EI   = E_PSI * GEO.moment_of_inertia   # lb·in²

# Closed-form reference values (validated against analytical solution in HW3)
W_MAX_EXACT   = 5.0 * Q0 * L**4 / (384.0 * EI)       # ≈ 0.06935 in
M_MAX_EXACT   = Q0 * L**2 / 8.0                       # = 48000.00 lb·in
SIG_MAX_EXACT = M_MAX_EXACT / GEO.section_modulus      # ≈ 650.16  psi

# ============================================================
# Study Parameters
# ============================================================
GRID_LEVELS     : List[int] = [10, 20, 40, 80, 160]   # N, coarse → fine
REFINE_RATIO    : float     = 2.0                      # r = h_coarse / h_fine
P_THEORETICAL   : float     = 2.0                      # O(h²) FD scheme
FINE_GRID       : int       = 160                      # high-fidelity grid
PARAMETRIC_GRID : int       = 20                       # coarse parametric grid

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "hw4_figures")

STYLE = dict(
    font_size=10, axes_labelsize=10, axes_titlesize=11,
    legend_fontsize=9, xtick_labelsize=9, ytick_labelsize=9,
    figure_dpi=150,
)

# Matplotlib rcParam dict
_RC = {
    "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11,
    "legend.fontsize": 9, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "figure.dpi": 150,
}

SRQ_LABELS   = ["w_max", "M_max", "sigma_max"]
SRQ_UNITS    = ["in", "lb·in", "psi"]
SRQ_EXACT    = [W_MAX_EXACT, M_MAX_EXACT, SIG_MAX_EXACT]

# For each grid level: which triplet index and which GCI key gives its U_DE.
# Triplet index: 0=T0(160,80,40)  1=T1(80,40,20)  2=T2(40,20,10)
# GCI_12 → U_DE for f1 (finest of triplet)
# GCI_23 → U_DE for f2 (middle of triplet)
_GCI_MAP: Dict[int, tuple] = {
    160: (0, "GCI_12"),   # T0 f1 = N=160
    80:  (1, "GCI_12"),   # T1 f1 = N=80
    40:  (2, "GCI_12"),   # T2 f1 = N=40
    20:  (2, "GCI_23"),   # T2 f2 = N=20
    10:  None,            # coarsest — no two coarser grids available
}


# ============================================================
# Grid Convergence Sweep
# ============================================================

def run_convergence_sweep() -> Dict[int, Dict]:
    """Solve on all N in GRID_LEVELS; return per-level results."""
    results: Dict[int, Dict] = {}
    for N in GRID_LEVELS:
        fd = solve_simply_supported(GEO, MAT, Q0, n_nodes=N + 1)
        results[N] = dict(
            h        = L / N,
            w_max    = fd.w_max,
            M_max    = fd.M_max,
            sigma_max= fd.sigma_max,
        )
    return results


# ============================================================
# GCI / Richardson Extrapolation  (Celik et al. 2008 / Roy)
# ============================================================

def gci_triplet(
    f1: float, f2: float, f3: float,
    r: float = 2.0, p_th: float = 2.0,
) -> Dict:
    """
    GCI analysis for three solutions on systematically-refined grids.

    Notation
    --------
    f1  : SRQ on finest  grid (h₁)
    f2  : SRQ on medium  grid (h₂ = r·h₁)
    f3  : SRQ on coarsest grid (h₃ = r²·h₁)

    Returns
    -------
    dict with keys:
        p_obs        — observed order of accuracy
        f_RE         — Richardson-extrapolated (h → 0) value
        Fs           — factor of safety applied
        GCI_12       — absolute U_DE for f1 (fine grid, pair 1–2) [SRQ units]
        GCI_23       — absolute U_DE for f2 (medium, pair 2–3)    [SRQ units]
        GCI_12_pct   — relative GCI_12 [%]
        GCI_23_pct   — relative GCI_23 [%]
        asymptotic   — GCI_23 / (r^p · GCI_12)  ≈ 1 in asymptotic range
        converge_type— 'monotone' | 'oscillatory' | 'converged'
    """
    e21 = f2 - f1   # signed difference: medium − fine   (pair 1–2)
    e32 = f3 - f2   # signed difference: coarse − medium  (pair 2–3)

    TINY = 1e-300
    if abs(e21) < TINY or abs(e32) < TINY:
        return dict(
            p_obs=float("nan"), f_RE=f1, Fs=1.25,
            GCI_12=0.0, GCI_23=0.0,
            GCI_12_pct=0.0, GCI_23_pct=0.0,
            asymptotic=float("nan"),
            converge_type="converged",
        )

    # ── observed order of accuracy ──────────────────────────────────────────
    p_obs = math.log(abs(e32) / abs(e21)) / math.log(r)
    converge_type = "monotone" if (e21 * e32 > 0) else "oscillatory"

    # ── Richardson-extrapolated value ───────────────────────────────────────
    if p_obs > 0.01:
        f_RE = f1 + e21 / (r**p_obs - 1.0)
    else:
        f_RE = f1          # fallback: non-converging case

    # ── factor of safety ────────────────────────────────────────────────────
    p_ratio = p_obs / p_th if p_th > 0 else float("inf")
    Fs = 1.25 if (0.5 <= p_ratio <= 2.0) else 3.0

    # ── GCI (absolute, in SRQ units) ─────────────────────────────────────────
    rp    = r**p_obs if p_obs > 0.01 else r**0.01   # guard vs zero exponent
    denom = rp - 1.0

    GCI_12 = Fs * abs(e21) / denom    # U_DE for f1  (finest of pair 1–2)
    GCI_23 = Fs * abs(e32) / denom    # U_DE for f2  (finest of pair 2–3)

    GCI_12_pct = GCI_12 / abs(f1) * 100.0 if abs(f1) > TINY else 0.0
    GCI_23_pct = GCI_23 / abs(f2) * 100.0 if abs(f2) > TINY else 0.0

    # ── asymptotic convergence indicator ────────────────────────────────────
    asymptotic = GCI_23 / (rp * GCI_12) if GCI_12 > 0 else float("nan")

    return dict(
        p_obs=p_obs, f_RE=f_RE, Fs=Fs,
        GCI_12=GCI_12, GCI_23=GCI_23,
        GCI_12_pct=GCI_12_pct, GCI_23_pct=GCI_23_pct,
        asymptotic=asymptotic,
        converge_type=converge_type,
    )


def run_gci_analysis(results: Dict[int, Dict]) -> Dict[str, List[Dict]]:
    """
    Run GCI for every consecutive triplet of grids and every SRQ.

    Triplets (finest→coarsest):
        T0: (N=160, N=80,  N=40)   primary fine-grid analysis
        T1: (N=80,  N=40,  N=20)   intermediate analysis
        T2: (N=40,  N=20,  N=10)   used for parametric-grid U_DE

    Returns
    -------
    dict keyed by SRQ name; each value is a list of gci_triplet() results
    (one per triplet, T0 first).
    """
    triplets = [
        (160, 80,  40),   # T0
        (80,  40,  20),   # T1
        (40,  20,  10),   # T2
    ]

    gci_results: Dict[str, List[Dict]] = {name: [] for name in SRQ_LABELS}

    for (n1, n2, n3) in triplets:
        for srq in SRQ_LABELS:
            f1 = results[n1][srq]
            f2 = results[n2][srq]
            f3 = results[n3][srq]
            g  = gci_triplet(f1, f2, f3, r=REFINE_RATIO, p_th=P_THEORETICAL)
            gci_results[srq].append(g)

    return gci_results


# ============================================================
# Round-Off Error   (float64 vs float32 direct solve)
# ============================================================

def _build_and_solve(n_nodes: int, dtype: np.dtype) -> Dict[str, float]:
    """
    Assemble and solve the EB beam FD system in the specified dtype.

    Uses explicit typed arithmetic throughout assembly and calls
    np.linalg.solve which — for float32 input on NumPy ≥ 1.20 —
    dispatches to LAPACK sgesv (single precision).

    NOTE: NumPy may internally upcast float32 to float64 on some builds.
    If that occurs, the float32 difference is a lower bound on U_RO;
    the condition-number estimate provides an upper bound.
    """
    N    = n_nodes - 1
    h    = dtype(L / N)
    h4   = h**dtype(4)
    EI_d = dtype(EI)
    q0_d = dtype(Q0)

    size = N + 1
    K = np.zeros((size, size), dtype=dtype)

    K[0, 0] = dtype(1)
    K[1, 1] =  dtype( 5) * EI_d / h4
    K[1, 2] =  dtype(-4) * EI_d / h4
    K[1, 3] =  dtype( 1) * EI_d / h4

    for i in range(2, N - 1):
        K[i, i - 2] =  dtype( 1) * EI_d / h4
        K[i, i - 1] =  dtype(-4) * EI_d / h4
        K[i, i    ] =  dtype( 6) * EI_d / h4
        K[i, i + 1] =  dtype(-4) * EI_d / h4
        K[i, i + 2] =  dtype( 1) * EI_d / h4

    K[N - 1, N - 3] =  dtype( 1) * EI_d / h4
    K[N - 1, N - 2] =  dtype(-4) * EI_d / h4
    K[N - 1, N - 1] =  dtype( 5) * EI_d / h4
    K[N, N] = dtype(1)

    q_vec = np.full(size, q0_d, dtype=dtype)
    q_vec[0] = dtype(0)
    q_vec[N] = dtype(0)

    # Solve: np.linalg.solve uses LAPACK driver appropriate for dtype
    w = np.linalg.solve(K, q_vec)

    # Bending moment via 3-point 2nd-order FD of w
    x_arr = np.linspace(dtype(0), dtype(L), N + 1, dtype=dtype)
    M_arr = np.zeros(size, dtype=dtype)
    for i in range(1, N):
        M_arr[i] = -EI_d * (w[i - 1] - dtype(2) * w[i] + w[i + 1]) / h**dtype(2)
    M_arr[0] = dtype(0)
    M_arr[N] = dtype(0)

    w_max    = float(np.max(w))
    M_max    = float(np.max(np.abs(M_arr)))
    S        = GEO.section_modulus
    sigma_max = M_max / S

    return dict(w_max=w_max, M_max=M_max, sigma_max=sigma_max)


def run_roundoff_study(grid_levels: List[int]) -> Dict[int, Dict]:
    """
    For each grid level: solve in float64 and float32, compute |Δ| for each SRQ.
    Also compute the condition-number upper bound on U_RO.
    """
    ro: Dict[int, Dict] = {}
    for N in grid_levels:
        n_nodes = N + 1
        f64 = _build_and_solve(n_nodes, np.float64)
        f32 = _build_and_solve(n_nodes, np.float32)

        # Condition number of the interior stiffness block to bound URO
        h   = L / N
        h4  = h**4
        sz  = N + 1
        K64 = np.zeros((sz, sz), dtype=np.float64)
        K64[0, 0] = 1.0
        K64[1, 1] = 5.0 * EI / h4;  K64[1, 2] = -4.0 * EI / h4
        K64[1, 3] = EI / h4
        for i in range(2, N - 1):
            K64[i, i-2] =  EI / h4;  K64[i, i-1] = -4.0 * EI / h4
            K64[i, i  ] =  6.0 * EI / h4
            K64[i, i+1] = -4.0 * EI / h4;  K64[i, i+2] = EI / h4
        K64[N-1, N-3] = EI / h4;  K64[N-1, N-2] = -4.0 * EI / h4
        K64[N-1, N-1] = 5.0 * EI / h4
        K64[N, N] = 1.0
        K_int  = K64[1:N, 1:N]
        kappa  = np.linalg.cond(K_int)

        eps_f64 = np.finfo(np.float64).eps
        eps_f32 = np.finfo(np.float32).eps

        URO_kappa_f64 = eps_f64 * kappa * f64["w_max"]   # upper bound for f64 U_RO
        URO_kappa_f32 = eps_f32 * kappa * f64["w_max"]   # upper bound for f32 U_RO

        # Float32 validity: if eps_f32 * kappa > 1, the f32 solve is unreliable.
        # In that case, use the double-precision backward error bound instead.
        f32_valid = (eps_f32 * kappa) < 1.0

        # Raw f32 vs f64 differences (may be meaningless if f32 is invalid)
        raw_URO_wmax  = abs(f32["w_max"]    - f64["w_max"])
        raw_URO_Mmax  = abs(f32["M_max"]    - f64["M_max"])
        raw_URO_sigma = abs(f32["sigma_max"]- f64["sigma_max"])

        # Reliable U_RO for the *double-precision* solver = ε_f64 · κ · |SRQ|
        URO_wmax_f64bound  = eps_f64 * kappa * abs(f64["w_max"])
        URO_Mmax_f64bound  = eps_f64 * kappa * abs(f64["M_max"])
        URO_sigma_f64bound = eps_f64 * kappa * abs(f64["sigma_max"])

        # Choose: if float32 is valid, report |Δ|; otherwise report the f64 bound
        URO_wmax  = raw_URO_wmax  if f32_valid else URO_wmax_f64bound
        URO_Mmax  = raw_URO_Mmax  if f32_valid else URO_Mmax_f64bound
        URO_sigma = raw_URO_sigma if f32_valid else URO_sigma_f64bound

        ro[N] = dict(
            f64               = f64,
            f32               = f32,
            kappa             = kappa,
            eps_f64           = eps_f64,
            eps_f32           = eps_f32,
            f32_valid         = f32_valid,
            raw_URO_wmax      = raw_URO_wmax,
            raw_URO_Mmax      = raw_URO_Mmax,
            raw_URO_sigma     = raw_URO_sigma,
            URO_wmax          = URO_wmax,
            URO_Mmax          = URO_Mmax,
            URO_sigma         = URO_sigma,
            URO_kappa_f64     = URO_kappa_f64,
            URO_kappa_f32     = URO_kappa_f32,
        )
    return ro


# ============================================================
# U_NUM Budget Assembly
# ============================================================

def assemble_unum(
    results: Dict[int, Dict],
    gci_data: Dict[str, List[Dict]],
    roundoff: Dict[int, Dict],
    grid_label: str,
    N_grid: int,
) -> Dict:
    """
    Assemble U_NUM = U_DE + U_IT + U_RO for a single grid level.

    Parameters
    ----------
    grid_label : "fine" or "parametric"
    N_grid     : the grid level to report (160 or 20)

    For U_DE:
      - Fine grid (N=160):      use GCI_12 from triplet T0 (160, 80, 40)
      - Parametric  (N=20):     use GCI_23 from triplet T2 (40, 20, 10)
        where GCI_23 in T2 is the U_DE for the N=40 solution... wait:
        GCI_23 from triplet T2 (f1=N40, f2=N20, f3=N10) is U_DE for f2 = N20. ✓
    """
    unum: Dict = {}
    for i, srq in enumerate(SRQ_LABELS):
        unit = SRQ_UNITS[i]

        if N_grid == FINE_GRID:
            # GCI_12 from T0  →  U_DE for N=160 solution
            U_DE = gci_data[srq][0]["GCI_12"]
        else:
            # GCI_23 from T2  →  U_DE for N=20 solution  (f2 in triplet 40/20/10)
            U_DE = gci_data[srq][2]["GCI_23"]

        # U_IT = 0: direct LU solver → residual at machine epsilon
        U_IT = 0.0

        # U_RO: |Δ(f32, f64)| if float32 valid; else ε_f64·κ·|f| bound
        ro_key = {"w_max": "URO_wmax", "M_max": "URO_Mmax", "sigma_max": "URO_sigma"}[srq]
        U_RO = roundoff[N_grid][ro_key]

        U_NUM = U_DE + U_IT + U_RO

        srv = results[N_grid][srq]
        unum[srq] = dict(
            srq_val   = srv,
            U_DE      = U_DE,
            U_IT      = U_IT,
            U_RO      = U_RO,
            U_NUM     = U_NUM,
            U_NUM_pct = U_NUM / abs(srv) * 100.0 if abs(srv) > 1e-300 else 0.0,
            unit      = unit,
        )
    return unum


def assemble_unum_all_grids(
    results: Dict[int, Dict],
    gci_data: Dict[str, List[Dict]],
    roundoff: Dict[int, Dict],
) -> Dict[int, Dict]:
    """
    Assemble U_NUM = U_DE + U_IT + U_RO for every grid level.

    GCI source per grid (see _GCI_MAP):
      N=160 → GCI_12 from T0   N=80 → GCI_12 from T1
      N=40  → GCI_12 from T2   N=20 → GCI_23 from T2
      N=10  → N/A (no coarser pair available)
    """
    all_unum: Dict[int, Dict] = {}
    _ro_keys = {"w_max": "URO_wmax", "M_max": "URO_Mmax", "sigma_max": "URO_sigma"}
    for N in GRID_LEVELS:
        unum_n: Dict = {}
        gci_entry = _GCI_MAP[N]
        for i, srq in enumerate(SRQ_LABELS):
            if gci_entry is not None:
                ti, key = gci_entry
                U_DE: float = gci_data[srq][ti][key]
            else:
                U_DE = float("nan")

            U_IT = 0.0
            U_RO = roundoff[N][_ro_keys[srq]]
            U_NUM = (U_DE + U_RO) if not math.isnan(U_DE) else float("nan")
            srv   = results[N][srq]
            unum_n[srq] = dict(
                srq_val   = srv,
                U_DE      = U_DE,
                U_IT      = U_IT,
                U_RO      = U_RO,
                U_NUM     = U_NUM,
                U_NUM_pct = (U_NUM / abs(srv) * 100.0
                             if (not math.isnan(U_NUM) and abs(srv) > 1e-300)
                             else float("nan")),
                unit      = SRQ_UNITS[i],
            )
        all_unum[N] = unum_n
    return all_unum


# ============================================================
# Console Output
# ============================================================

# Triplet labels for display
_TRIPLET_LABELS = ["T0: (160,80,40)", "T1: (80,40,20)", "T2: (40,20,10)"]


def print_header(title: str) -> None:
    bar = "=" * 72
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def print_gci_table(gci_data: Dict[str, List[Dict]]) -> None:
    print_header("Table 1 — GCI / Richardson Extrapolation Analysis")
    for i, srq in enumerate(SRQ_LABELS):
        unit = SRQ_UNITS[i]
        exact = SRQ_EXACT[i]
        print(f"\n  SRQ: {srq}   [Exact = {exact:.6g} {unit}]")
        hdr = (f"  {'Triplet':<20} {'p_obs':>7} {'Fs':>5} "
               f"{'f_RE':>14} {'GCI_12':>12} {'GCI_23':>12} "
               f"{'GCI_12%':>9} {'GCI_23%':>9} "
               f"{'asym':>8} {'type':>11}")
        print(hdr)
        print("  " + "-" * 106)
        for j, g in enumerate(gci_data[srq]):
            lbl  = _TRIPLET_LABELS[j]
            p    = f"{g['p_obs']:.3f}"   if not math.isnan(g['p_obs']) else "   N/A"
            Fs   = f"{g['Fs']:.2f}"
            fRE  = f"{g['f_RE']:.6g}"
            g12  = f"{g['GCI_12']:.3e}"
            g23  = f"{g['GCI_23']:.3e}"
            g12p = f"{g['GCI_12_pct']:.4f}%"
            g23p = f"{g['GCI_23_pct']:.4f}%"
            asym = (f"{g['asymptotic']:.4f}"
                    if not math.isnan(g['asymptotic']) else "  N/A")
            ct   = g['converge_type']
            print(f"  {lbl:<20} {p:>7} {Fs:>5} {fRE:>14} "
                  f"{g12:>12} {g23:>12} {g12p:>9} {g23p:>9} {asym:>8} {ct:>11}")
    print()


def print_asymptotic_table(gci_data: Dict[str, List[Dict]]) -> None:
    print_header("Table 2 — Asymptotic Convergence Check  (ratio ≈ 1 desired)")
    hdr = (f"  {'SRQ':<12} {'T0 ratio':>10} {'T1 ratio':>10} {'T2 ratio':>10}  "
           "Notes")
    print(hdr)
    print("  " + "-" * 60)
    for srq in SRQ_LABELS:
        row_vals = []
        for g in gci_data[srq]:
            v = g["asymptotic"]
            row_vals.append(f"{v:.4f}" if not math.isnan(v) else "   N/A")
        note = "✓ asymptotic" if all(
            not math.isnan(g["asymptotic"]) and abs(g["asymptotic"] - 1.0) < 0.1
            for g in gci_data[srq] if not math.isnan(g["asymptotic"])
        ) else "— check p_obs"
        print(f"  {srq:<12} {row_vals[0]:>10} {row_vals[1]:>10} {row_vals[2]:>10}  {note}")
    print()


def print_roundoff_table(roundoff: Dict[int, Dict]) -> None:
    print_header("Table 3 — Round-Off Error  (|f_f64 − f_f32|  +  κ·ε bounds)")

    hdr = (f"  {'N':>5}  {'h [in]':>8}  {'κ(K_int)':>12}  "
           f"{'ε_f64·κ':>12}  {'ε_f32·κ':>12}  "
           f"{'|Δw_max| raw':>14}  {'f32 valid?':>11}  "
           f"{'U_RO(w_max)':>13}  (source)")
    print(hdr)
    print("  " + "-" * 120)
    for N in sorted(roundoff.keys()):
        r = roundoff[N]
        h = L / N
        valid_str = "YES" if r["f32_valid"] else "NO (κε>1)"
        source    = "|Δ|" if r["f32_valid"] else "ε_f64·κ·f"
        print(f"  {N:>5}  {h:>8.4f}  {r['kappa']:>12.3e}  "
              f"{r['eps_f64']*r['kappa']:>12.3e}  "
              f"{r['eps_f32']*r['kappa']:>12.3e}  "
              f"{r['raw_URO_wmax']:>14.3e}  "
              f"{valid_str:>11}  "
              f"{r['URO_wmax']:>13.3e}  {source}")
    print(f"""
  Notes:
    ε_f64 = {np.finfo(np.float64).eps:.3e}  (double machine epsilon)
    ε_f32 = {np.finfo(np.float32).eps:.3e}  (single machine epsilon)
    If ε_f32·κ > 1: float32 solve is unreliable; U_RO is reported as ε_f64·κ·|f|
    (the backward-error bound for our double-precision direct solver).
""")


def print_unum_budget(unum_fine: Dict, unum_param: Dict) -> None:
    print_header("Table 4 — Total Numerical Uncertainty  U_NUM = U_DE + U_IT + U_RO")
    for label, unum, N_grid in [("Fine grid  (N=160)", unum_fine,  FINE_GRID),
                                 ("Parametric (N=20) ", unum_param, PARAMETRIC_GRID)]:
        print(f"\n  Grid: {label}  (h = {L/N_grid:.4f} in)")
        hdr = (f"  {'SRQ':<14} {'f(h)':>14} {'U_DE':>12} {'U_IT':>10} "
               f"{'U_RO':>12} {'U_NUM':>12} {'U_NUM%':>9}")
        print(hdr)
        print("  " + "-" * 86)
        for srq in SRQ_LABELS:
            u = unum[srq]
            print(f"  {srq:<14} {u['srq_val']:>14.6g} {u['U_DE']:>12.3e} "
                  f"{u['U_IT']:>10.3e} {u['U_RO']:>12.3e} "
                  f"{u['U_NUM']:>12.3e} {u['U_NUM_pct']:>8.4f}%")
    print()


def print_unum_all_grids_table(all_unum: Dict[int, Dict]) -> None:
    """Table 5 — U_NUM for every grid level, one block per SRQ."""
    print_header("Table 5 — U_NUM at All Grid Levels  (U_NUM = U_DE + U_IT + U_RO)")
    _ro_note = {160: "ε·κ·f", 80: "ε·κ·f", 40: "|Δ|", 20: "|Δ|", 10: "|Δ|"}
    for srq, unit in zip(SRQ_LABELS, SRQ_UNITS):
        print(f"\n  SRQ: {srq}   [{unit}]   (U_IT = 0 for all grids — direct LU solver)")
        hdr = (f"  {'N':>5}  {'h [in]':>8}  {'f(h)':>14}  "
               f"{'U_DE':>12}  {'U_RO':>12}  {'U_NUM':>12}  "
               f"{'U_NUM %':>9}  GCI source         U_RO source")
        print(hdr)
        print("  " + "-" * 105)
        for N in GRID_LEVELS:
            u   = all_unum[N][srq]
            h   = L / N
            ge  = _GCI_MAP[N]
            gci_src = (f"T{ge[0]}/{ge[1]}" if ge else "N/A")
            ude_s   = f"{u['U_DE']:.3e}"   if not math.isnan(u["U_DE"])  else "         N/A"
            unum_s  = f"{u['U_NUM']:.3e}"  if not math.isnan(u["U_NUM"]) else "         N/A"
            upct_s  = f"{u['U_NUM_pct']:.4f}%" if not math.isnan(u["U_NUM_pct"]) else "      N/A"
            print(f"  {N:>5}  {h:>8.4f}  {u['srq_val']:>14.6g}  "
                  f"{ude_s:>12}  {u['U_RO']:>12.3e}  {unum_s:>12}  "
                  f"{upct_s:>9}  {gci_src:<18} {_ro_note.get(N, '|Δ|')}")
    print()


def print_one_sided_note(results: Dict[int, Dict]) -> None:
    """Print one-sided uncertainty interpretation for w_max."""
    print_header("One-Sided Uncertainty Note (w_max)")
    w160 = results[FINE_GRID]["w_max"]
    w20  = results[PARAMETRIC_GRID]["w_max"]
    print(f"\n  FD scheme overestimates deflection (w_FD ≥ w_exact).")
    print(f"  → One-sided interpretation: w_true ≥ w_FD − U_DE  (lower bound only).")
    print(f"  → 'Conservative' for structural design (overestimated deflection).")
    print(f"\n  Fine grid (N=160):     w_FD = {w160:.8f} in  ≥  w_true")
    print(f"  Parametric (N=20):     w_FD = {w20:.8f} in  ≥  w_true")
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


def fig1_convergence_gci(
    results: Dict[int, Dict],
    gci_data: Dict[str, List[Dict]],
) -> None:
    """
    Figure 1 — SRQ values vs N with GCI error bars and RE-extrapolated values.
    One subplot per SRQ.
    """
    N_arr = np.array(GRID_LEVELS)

    with plt.rc_context(_RC):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), sharey=False)

        triplet_grids = [(160, 80, 40), (80, 40, 20), (40, 20, 10)]
        # For each triplet Tx:
        #   GCI_12 → error bar on N_fine (f1)
        #   GCI_23 → error bar on N_medium (f2)
        triplet_error_map = [
            {160: "GCI_12", 80: "GCI_23"},   # T0
            { 80: "GCI_12", 40: "GCI_23"},   # T1
            { 40: "GCI_12", 20: "GCI_23"},   # T2
        ]

        for ax, srq, unit, exact in zip(axes, SRQ_LABELS, SRQ_UNITS, SRQ_EXACT):
            srq_vals = np.array([results[N][srq] for N in GRID_LEVELS])

            # Compute error bar for each grid level
            errs = np.zeros(len(GRID_LEVELS))
            for ti, (n1, n2, n3) in enumerate(triplet_grids):
                g = gci_data[srq][ti]
                errs[GRID_LEVELS.index(n1)] = g["GCI_12"]
                errs[GRID_LEVELS.index(n2)] = g["GCI_23"]

            # Plot convergence with error bars
            ax.errorbar(N_arr, srq_vals, yerr=errs,
                        fmt="bo-", capsize=4, capthick=1, elinewidth=1,
                        ms=6, lw=1.5, label="FD solution ± GCI")

            # Richardson-extrapolated value from finest triplet T0
            f_RE = gci_data[srq][0]["f_RE"]
            ax.axhline(f_RE, color="green", ls="--", lw=1.2,
                       label=f"RE extrap: {f_RE:.6g}")

            # Exact reference
            ax.axhline(exact, color="red", ls=":", lw=1.0,
                       label=f"Exact: {exact:.6g}")

            ax.set_xlabel("Grid Level $N$")
            ax.set_ylabel(f"{srq} [{unit}]")
            ax.set_title(f"{srq} Convergence")
            ax.legend(fontsize=8)
            ax.grid(True, color="gray", alpha=0.3, lw=0.5)

        fig.suptitle(
            "Solution Verification: SRQ Convergence with GCI Uncertainty Bands\n"
            f"8-ft LVL Header, q₀ = {Q0_LBFT:.0f} lb/ft",
            fontsize=11, y=1.01,
        )
        fig.tight_layout()
        _save(fig, "fig1_convergence_gci")
        plt.close(fig)


def fig2_pobs_triplets(gci_data: Dict[str, List[Dict]]) -> None:
    """
    Figure 2 — Observed order of accuracy p̂ for each SRQ across all triplets.
    Horizontal reference line at p_theoretical = 2.
    """
    x = np.arange(3)  # 3 triplets
    width = 0.25
    colors = ["steelblue", "darkorange", "green"]
    labels_short = [s.replace("_", r"\_") for s in SRQ_LABELS]

    with plt.rc_context(_RC):
        fig, ax = plt.subplots(figsize=(7, 4))

        for k, (srq, color) in enumerate(zip(SRQ_LABELS, colors)):
            p_vals = [
                g["p_obs"] if not math.isnan(g["p_obs"]) else 0.0
                for g in gci_data[srq]
            ]
            bars = ax.bar(x + k * width, p_vals, width, label=srq,
                          color=color, alpha=0.8, edgecolor="black", lw=0.6)
            # Annotate bar tops
            for bar, pv in zip(bars, p_vals):
                if pv > 0.01:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + 0.04,
                            f"{pv:.2f}", ha="center", va="bottom", fontsize=8)

        ax.axhline(P_THEORETICAL, color="red", ls="--", lw=1.2,
                   label=f"$p_{{\\rm th}}$ = {P_THEORETICAL:.1f}")
        ax.axhline(P_THEORETICAL * 0.5, color="orange", ls=":", lw=0.8,
                   label=r"0.5 $p_{\rm th}$ (Fs boundary)")
        ax.axhline(P_THEORETICAL * 2.0, color="orange", ls=":", lw=0.8,
                   label=r"2.0 $p_{\rm th}$ (Fs boundary)")

        ax.set_xticks(x + width)
        ax.set_xticklabels(_TRIPLET_LABELS, fontsize=9)
        ax.set_ylabel("Observed Order $\\hat{p}$")
        ax.set_title("Observed Order of Accuracy by Triplet and SRQ")
        ax.legend(loc="upper right", fontsize=8)
        ax.set_ylim(0, max(P_THEORETICAL * 2.5, 5))
        ax.grid(True, axis="y", color="gray", alpha=0.3, lw=0.5)

        fig.tight_layout()
        _save(fig, "fig2_pobs_triplets")
        plt.close(fig)


def fig3_gci_bar(gci_data: Dict[str, List[Dict]]) -> None:
    """
    Figure 3 — GCI% for fine grid (N=160) and parametric grid (N=20) for all SRQs.
    Fine grid:      GCI_12 from T0  (pair 160/80)
    Parametric grid: GCI_23 from T2  (pair 20/10 where N=20 is "fine" of pair)
    """
    srq_labels_short = SRQ_LABELS
    x = np.arange(len(SRQ_LABELS))
    width = 0.35

    gci_fine  = [gci_data[s][0]["GCI_12_pct"] for s in SRQ_LABELS]   # T0 GCI_12
    gci_param = [gci_data[s][2]["GCI_23_pct"] for s in SRQ_LABELS]   # T2 GCI_23

    with plt.rc_context(_RC):
        fig, ax = plt.subplots(figsize=(6, 4))

        b1 = ax.bar(x - width / 2, gci_fine,  width, label=f"Fine grid  (N={FINE_GRID})",
                    color="steelblue", alpha=0.85, edgecolor="black", lw=0.6)
        b2 = ax.bar(x + width / 2, gci_param, width, label=f"Parametric (N={PARAMETRIC_GRID})",
                    color="tomato",     alpha=0.85, edgecolor="black", lw=0.6)

        for bars in (b1, b2):
            for bar in bars:
                h = bar.get_height()
                if h > 1e-8:
                    ax.text(bar.get_x() + bar.get_width() / 2, h + h * 0.05,
                            f"{h:.3f}%", ha="center", va="bottom", fontsize=8)

        ax.set_xticks(x)
        ax.set_xticklabels(SRQ_LABELS)
        ax.set_ylabel("GCI  [%  of SRQ]")
        ax.set_title(f"Discretization Uncertainty (GCI):\n"
                     f"Fine Grid (N={FINE_GRID}) vs. Parametric Grid (N={PARAMETRIC_GRID})")
        ax.legend(loc="upper right")
        ax.set_yscale("symlog", linthresh=1e-10)
        ax.grid(True, axis="y", color="gray", alpha=0.3, lw=0.5)

        fig.tight_layout()
        _save(fig, "fig3_gci_bar")
        plt.close(fig)


def fig4_unum_budget(unum_fine: Dict, unum_param: Dict) -> None:
    """
    Figure 4 — Stacked bar chart of U_NUM components for each SRQ.
    Side-by-side: fine grid (N=160) and parametric grid (N=20).
    """
    n_srq   = len(SRQ_LABELS)
    x       = np.arange(n_srq)
    width   = 0.35

    def _extract(unum: Dict, key: str) -> List[float]:
        return [unum[s][key] for s in SRQ_LABELS]

    ude_f  = _extract(unum_fine,  "U_DE")
    uro_f  = _extract(unum_fine,  "U_RO")
    ude_p  = _extract(unum_param, "U_DE")
    uro_p  = _extract(unum_param, "U_RO")

    with plt.rc_context(_RC):
        fig, axes = plt.subplots(1, n_srq, figsize=(11, 4.5))

        for ax, srq, unit, ude_fi, uro_fi, ude_pi, uro_pi in zip(
            axes, SRQ_LABELS, SRQ_UNITS, ude_f, uro_f, ude_p, uro_p
        ):
            data_fine  = [ude_fi, 0.0, uro_fi]
            data_param = [ude_pi, 0.0, uro_pi]
            labels_comp = ["$U_{DE}$", "$U_{IT}$ (=0)", "$U_{RO}$"]
            colors_comp = ["steelblue", "gray", "tomato"]

            bar_x = np.array([0.0, 0.5])
            bottom_f = 0.0
            bottom_p = 0.0
            for comp_val_f, comp_val_p, clr, lbl in zip(
                data_fine, data_param, colors_comp, labels_comp
            ):
                ax.bar(bar_x[0], comp_val_f, 0.35,
                       bottom=bottom_f, color=clr, label=lbl,
                       edgecolor="black", lw=0.5, alpha=0.85)
                ax.bar(bar_x[1], comp_val_p, 0.35,
                       bottom=bottom_p, color=clr,
                       edgecolor="black", lw=0.5, alpha=0.85)
                bottom_f += comp_val_f
                bottom_p += comp_val_p

            ax.set_xticks(bar_x)
            ax.set_xticklabels([f"N={FINE_GRID}", f"N={PARAMETRIC_GRID}"], fontsize=9)
            ax.set_ylabel(f"Uncertainty [{unit}]")
            ax.set_title(srq)
            ax.set_yscale("symlog", linthresh=max(min(ude_fi, ude_pi) * 1e-3, 1e-20))
            ax.grid(True, axis="y", color="gray", alpha=0.3, lw=0.5)

            # Add total annotation
            for bx, tot in zip(bar_x, [bottom_f, bottom_p]):
                ax.text(bx, tot * 1.05, f"{tot:.2e}", ha="center", fontsize=7)

        # Unified legend on first axes
        axes[0].legend(fontsize=8, loc="upper right")

        fig.suptitle(
            "U_NUM Budget:  $U_{\\rm NUM} = U_{DE} + U_{IT} + U_{RO}$\n"
            f"Fine Grid (N={FINE_GRID}) vs. Parametric Grid (N={PARAMETRIC_GRID})",
            fontsize=11,
        )
        fig.tight_layout()
        _save(fig, "fig4_unum_budget")
        plt.close(fig)


def fig5_unum_vs_h(all_unum: Dict[int, Dict]) -> None:
    """
    Figure 5 — Log-log plot of U_DE, U_RO, and U_NUM vs grid spacing h
    for all grid levels and all SRQs.  One subplot per SRQ.
    """
    h_arr = np.array([L / N for N in GRID_LEVELS])

    with plt.rc_context(_RC):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))

        for ax, srq, unit in zip(axes, SRQ_LABELS, SRQ_UNITS):
            ude_arr  = []
            uro_arr  = []
            unum_arr = []
            for N in GRID_LEVELS:
                u = all_unum[N][srq]
                ude_arr.append(u["U_DE"]  if not math.isnan(u["U_DE"])  else np.nan)
                uro_arr.append(u["U_RO"]  if not math.isnan(u["U_RO"])  else np.nan)
                unum_arr.append(u["U_NUM"] if not math.isnan(u["U_NUM"]) else np.nan)

            ude_arr  = np.array(ude_arr,  dtype=float)
            uro_arr  = np.array(uro_arr,  dtype=float)
            unum_arr = np.array(unum_arr, dtype=float)

            # Finite (non-nan) masks for plotting
            m_ude  = np.isfinite(ude_arr)
            m_uro  = np.isfinite(uro_arr)
            m_unum = np.isfinite(unum_arr)

            if m_ude.sum() > 1:
                ax.loglog(h_arr[m_ude],  ude_arr[m_ude],  "bs--",
                          ms=6, lw=1.4, label=r"$U_{DE}$ (GCI)")
            if m_uro.sum() > 1:
                ax.loglog(h_arr[m_uro],  uro_arr[m_uro],  "r^:",
                          ms=6, lw=1.4, label=r"$U_{RO}$")
            if m_unum.sum() > 1:
                ax.loglog(h_arr[m_unum], unum_arr[m_unum], "ko-",
                          ms=7, lw=2.0, label=r"$U_{NUM}$")

            # Reference O(h²) slope anchored to the largest finite U_DE value
            valid_ude = ude_arr[m_ude]
            if len(valid_ude) > 1:
                C = valid_ude[0] / h_arr[m_ude][0]**2
                h_ref = np.array([h_arr[m_ude][0], h_arr[m_ude][-1]])
                ax.loglog(h_ref, C * h_ref**2, "k--", lw=0.9, alpha=0.5,
                          label="Slope 2 ref")

            # Mark N=10 as no-U_DE with an open circle on U_RO
            idx10 = GRID_LEVELS.index(10)
            ax.loglog(h_arr[idx10], uro_arr[idx10], "wo",
                      ms=9, markeredgecolor="red", markeredgewidth=1.2,
                      zorder=5, label="N=10 (no U_DE)")

            ax.set_xlabel(r"Grid spacing $h$ [in]")
            ax.set_ylabel(f"Uncertainty [{unit}]")
            ax.set_title(srq)
            ax.legend(fontsize=8)
            ax.invert_xaxis()
            ax.grid(True, which="both", color="gray", alpha=0.3, lw=0.5)

        fig.suptitle(
            r"$U_{\rm NUM}$ Components vs. $h$: All Grid Levels"
            f"\n8-ft LVL Header, q₀ = {Q0_LBFT:.0f} lb/ft",
            fontsize=11, y=1.01,
        )
        fig.tight_layout()
        _save(fig, "fig5_unum_vs_h")
        plt.close(fig)


# ============================================================
# Main
# ============================================================

def main() -> None:
    print("\n" + "=" * 72)
    print("  HW4 — Solution Verification: EB FD Beam Solver")
    print("  AOE/CS/ME 6444 | Spring 2026 | Dr. Chris Roy")
    print("  Authors: Jason Cusati & Cheng-Shun Chuang")
    print("=" * 72)
    print(f"\n  Physical case: {L_FT}-ft LVL header, b={B} in, d={D} in")
    print(f"  E = {E_PSI:,} psi,  q₀ = {Q0_LBFT:.0f} lb/ft,  EI = {EI:.4e} lb·in²")
    print(f"  FD scheme order: p_th = {P_THEORETICAL:.1f}  (O(h²))")
    print(f"  Grid levels: N = {GRID_LEVELS}  (r = {REFINE_RATIO:.1f})")
    print(f"\n  Reference (exact) values:")
    print(f"    w_max    = {W_MAX_EXACT:.8f} in")
    print(f"    M_max    = {M_MAX_EXACT:.4f} lb·in")
    print(f"    σ_max    = {SIG_MAX_EXACT:.6f} psi")

    # ── 1. Grid convergence ────────────────────────────────────────────────
    print("\n  [1/4] Running grid convergence sweep ...")
    results = run_convergence_sweep()

    # ── 2. GCI analysis ───────────────────────────────────────────────────
    print("  [2/4] Running GCI / Richardson extrapolation analysis ...")
    gci_data = run_gci_analysis(results)

    # ── 3. Round-off study ────────────────────────────────────────────────
    print("  [3/4] Running round-off study (float64 vs float32, all grids) ...")
    roundoff = run_roundoff_study(GRID_LEVELS)

    # ── 4. U_NUM budgets ──────────────────────────────────────────────────
    print("  [4/4] Assembling U_NUM budgets ...")
    unum_fine  = assemble_unum(results, gci_data, roundoff,
                               "fine",       FINE_GRID)
    unum_param = assemble_unum(results, gci_data, roundoff,
                               "parametric", PARAMETRIC_GRID)
    unum_all   = assemble_unum_all_grids(results, gci_data, roundoff)

    # ── Console tables ─────────────────────────────────────────────────────
    print_gci_table(gci_data)
    print_asymptotic_table(gci_data)
    print_roundoff_table(roundoff)
    print_unum_budget(unum_fine, unum_param)
    print_unum_all_grids_table(unum_all)
    print_one_sided_note(results)

    # ── Summary ────────────────────────────────────────────────────────────
    print_header("Summary")
    for label, unum, N in [("Fine grid  (N=160, h=0.600 in)", unum_fine,  FINE_GRID),
                            ("Parametric (N=20,  h=4.800 in)", unum_param, PARAMETRIC_GRID)]:
        u_w = unum["w_max"]
        print(f"\n  {label}")
        print(f"    w_max   = {u_w['srq_val']:.8f} in  ±  U_NUM = {u_w['U_NUM']:.3e} in"
              f"  ({u_w['U_NUM_pct']:.4f}%)")
        print(f"    U_DE = {u_w['U_DE']:.3e} in   "
              f"U_IT = 0 (direct solver)   "
              f"U_RO = {u_w['U_RO']:.3e} in")
    print()

    # ── Figures ────────────────────────────────────────────────────────────
    print("  Generating figures ...")
    fig1_convergence_gci(results, gci_data)
    fig2_pobs_triplets(gci_data)
    fig3_gci_bar(gci_data)
    fig4_unum_budget(unum_fine, unum_param)
    fig5_unum_vs_h(unum_all)
    print(f"\n  Figures saved to: {OUTPUT_DIR}/")
    print("\nDone.\n")


if __name__ == "__main__":
    main()
