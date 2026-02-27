"""
Finite-difference Euler-Bernoulli beam solver for residential wood header/beam assessment.

Governing equation (prismatic, uniform EI):
    EI * w'''' = q(x),   x in (0, L)

Sign convention: w positive downward (gravity direction).
    M(x) = -EI * w''
    V(x) = -EI * w'''

Discretization: 5-point central difference, O(h^2).
Simply-supported BCs enforced via ghost points.
Banded LU solve (scipy.linalg.solve_banded).
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BeamGeometry:
    """Cross-section and span of a rectangular wood member (inch units)."""
    span_in: float        # L  [in]
    width_in: float       # b  [in]
    depth_in: float       # d  [in]

    @property
    def area(self) -> float:
        return self.width_in * self.depth_in

    @property
    def moment_of_inertia(self) -> float:
        return self.width_in * self.depth_in ** 3 / 12.0

    @property
    def section_modulus(self) -> float:
        return self.moment_of_inertia / (self.depth_in / 2.0)


@dataclass
class BeamMaterial:
    """Structural wood material properties (inch-pound units)."""
    E_psi: float     # modulus of elasticity [psi = lb/in^2]
    Fb_psi: float    # allowable bending stress [psi]
    Fv_psi: float    # allowable shear stress [psi]


@dataclass
class BeamSolveResult:
    """Outputs of a single deterministic beam solve."""
    x: np.ndarray           # node positions [in]
    w: np.ndarray           # deflection field, positive downward [in]
    M: np.ndarray           # bending moment field [lb·in]
    V: np.ndarray           # shear force field [lb]
    w_max: float            # peak deflection [in]
    sigma_max: float        # peak bending stress [psi]
    tau_max: float          # peak shear stress [psi]
    deflection_ratio: float # w_max / L  (dimensionless)
    passes_bending: bool
    passes_shear: bool
    passes_deflection: bool

    @property
    def is_acceptable(self) -> bool:
        return self.passes_bending and self.passes_shear and self.passes_deflection


@dataclass
class MCResult:
    """Outputs of a Monte Carlo uncertainty quantification run."""
    p_fail: float           # estimated probability of failure
    w_max_samples: np.ndarray
    sigma_max_samples: np.ndarray
    tau_max_samples: np.ndarray
    n_samples: int


# ---------------------------------------------------------------------------
# Deterministic solver
# ---------------------------------------------------------------------------

def solve_simply_supported(
    geometry: BeamGeometry,
    material: BeamMaterial,
    q0_lb_per_in: float,
    n_nodes: int = 200,
) -> BeamSolveResult:
    """
    Solve the simply-supported Euler-Bernoulli beam BVP for uniform load q0.

    Parameters
    ----------
    geometry    : beam geometry (inch units)
    material    : wood material properties (inch-pound units)
    q0_lb_per_in: uniformly distributed load [lb/in]
    n_nodes     : number of grid points N+1 (N intervals)

    Returns
    -------
    BeamSolveResult with deflection, moment, shear, and acceptance flags.
    """
    L = geometry.span_in
    EI = material.E_psi * geometry.moment_of_inertia

    N = n_nodes - 1          # number of intervals
    h = L / N
    h4 = h ** 4

    # Node positions
    x = np.linspace(0.0, L, N + 1)

    # Build full stiffness matrix K (dense; (N+1) x (N+1), 5-diagonal).
    # Using np.linalg.solve — sufficient for typical N <= 500.
    size = N + 1
    K = np.zeros((size, size))

    # Row 0: Dirichlet w_0 = 0
    K[0, 0] = 1.0

    # Row 1: modified near-boundary stencil (ghost point w_{-1} = -w_1)
    #   (EI/h^4)(5*w_1 - 4*w_2 + w_3) = q_1
    K[1, 1] = 5.0 * EI / h4
    K[1, 2] = -4.0 * EI / h4
    K[1, 3] = 1.0 * EI / h4

    # Interior rows i = 2 .. N-2: standard 5-point stencil
    #   (EI/h^4)(w_{i-2} - 4*w_{i-1} + 6*w_i - 4*w_{i+1} + w_{i+2}) = q_i
    for i in range(2, N - 1):
        K[i, i - 2] = 1.0 * EI / h4
        K[i, i - 1] = -4.0 * EI / h4
        K[i, i]     = 6.0 * EI / h4
        K[i, i + 1] = -4.0 * EI / h4
        K[i, i + 2] = 1.0 * EI / h4

    # Row N-1: modified near-boundary stencil (ghost point w_{N+1} = -w_{N-1})
    #   (EI/h^4)(w_{N-3} - 4*w_{N-2} + 5*w_{N-1}) = q_{N-1}
    K[N - 1, N - 3] = 1.0 * EI / h4
    K[N - 1, N - 2] = -4.0 * EI / h4
    K[N - 1, N - 1] = 5.0 * EI / h4

    # Row N: Dirichlet w_N = 0
    K[N, N] = 1.0

    # Load vector
    q = np.full(size, q0_lb_per_in)
    q[0] = 0.0   # Dirichlet rows — RHS = 0
    q[N] = 0.0

    # Solve K w = q  (direct dense solve; O(N^3) but N<=500 is negligible)
    w = np.linalg.solve(K, q)

    # Derived quantities via central differences
    # M(x) = -EI * w''   (downward-positive convention)
    # V(x) = -EI * w'''
    M = np.zeros(size)
    V = np.zeros(size)

    for i in range(1, N):
        w_pp = (w[i - 1] - 2.0 * w[i] + w[i + 1]) / h ** 2
        M[i] = -EI * w_pp

    # Simply-supported: zero moment at ends
    M[0] = 0.0
    M[N] = 0.0

    # Shear from V = dM/dx using numpy's central-difference gradient
    V = np.gradient(M, x)

    # Stress resultants
    w_max = float(np.max(w))
    M_max = float(np.max(np.abs(M)))
    V_max = float(np.max(np.abs(V)))

    sigma_max = M_max / geometry.section_modulus
    tau_max = 1.5 * V_max / geometry.area

    defl_limit = L / 240.0

    return BeamSolveResult(
        x=x,
        w=w,
        M=M,
        V=V,
        w_max=w_max,
        sigma_max=sigma_max,
        tau_max=tau_max,
        deflection_ratio=w_max / L,
        passes_bending=sigma_max <= material.Fb_psi,
        passes_shear=tau_max <= material.Fv_psi,
        passes_deflection=w_max <= defl_limit,
    )


# ---------------------------------------------------------------------------
# Analytical solution (verification benchmark)
# ---------------------------------------------------------------------------

def exact_simply_supported(
    geometry: BeamGeometry,
    material: BeamMaterial,
    q0_lb_per_in: float,
    n_nodes: int = 200,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Exact closed-form solution for simply-supported beam under uniform load.

        w(x) = q0 / (24 EI) * (x^4 - 2*L*x^3 + L^3*x)

    Returns (x, w_exact).
    """
    L = geometry.span_in
    EI = material.E_psi * geometry.moment_of_inertia
    x = np.linspace(0.0, L, n_nodes)
    w = q0_lb_per_in / (24.0 * EI) * (x ** 4 - 2.0 * L * x ** 3 + L ** 3 * x)
    return x, w


# ---------------------------------------------------------------------------
# Monte Carlo UQ
# ---------------------------------------------------------------------------

def monte_carlo_assessment(
    geometry: BeamGeometry,
    material: BeamMaterial,
    trib_width_ft_bounds: tuple[float, float],
    q_roof_mean_psf: float,
    q_roof_std_psf: float,
    q_floor_mean_psf: float,
    q_floor_std_psf: float,
    E_mean_psi: float,
    E_std_psi: float,
    n_mc: int = 10_000,
    n_nodes: int = 100,
    rng: np.random.Generator | None = None,
) -> MCResult:
    """
    Monte Carlo uncertainty quantification for beam structural assessment.

    Random variables:
        T_w ~ Uniform(trib_width_ft_bounds)   [ft]
        q_roof ~ N(q_roof_mean_psf, q_roof_std_psf^2)  [psf]
        q_floor ~ N(q_floor_mean_psf, q_floor_std_psf^2)  [psf]
        E ~ N(E_mean_psi, E_std_psi^2)  [psi]

    Failure criterion (any one triggers failure):
        sigma_max > Fb  OR  tau_max > Fv  OR  w_max > L/240

    Parameters
    ----------
    geometry               : nominal beam geometry
    material               : nominal material with allowable stresses
    trib_width_ft_bounds   : (min, max) tributary width [ft]
    q_roof_mean_psf        : mean roof load [psf]
    q_roof_std_psf         : std dev of roof load [psf]
    q_floor_mean_psf       : mean floor load [psf]
    q_floor_std_psf        : std dev of floor load [psf]
    E_mean_psi             : mean modulus of elasticity [psi]
    E_std_psi              : std dev of modulus [psi]
    n_mc                   : number of Monte Carlo samples
    n_nodes                : FD grid size per solve
    rng                    : optional numpy Generator for reproducibility

    Returns
    -------
    MCResult with p_fail and sample arrays.
    """
    if rng is None:
        rng = np.random.default_rng()

    tw_min, tw_max = trib_width_ft_bounds

    # Sample all inputs at once
    T_w = rng.uniform(tw_min, tw_max, n_mc)                       # [ft]
    q_roof = rng.normal(q_roof_mean_psf, q_roof_std_psf, n_mc)    # [psf]
    q_floor = rng.normal(q_floor_mean_psf, q_floor_std_psf, n_mc) # [psf]
    E_samples = rng.normal(E_mean_psi, E_std_psi, n_mc)           # [psi]

    # Clamp to physically meaningful values
    q_roof = np.maximum(q_roof, 0.0)
    q_floor = np.maximum(q_floor, 0.0)
    E_samples = np.maximum(E_samples, 1e5)

    w_max_arr = np.zeros(n_mc)
    sigma_max_arr = np.zeros(n_mc)
    tau_max_arr = np.zeros(n_mc)
    failures = np.zeros(n_mc, dtype=bool)

    L = geometry.span_in

    for j in range(n_mc):
        # q0 [lb/ft] = (q_roof + q_floor) * T_w;  convert to lb/in
        q0_lb_per_ft = (q_roof[j] + q_floor[j]) * T_w[j]
        q0_lb_per_in = q0_lb_per_ft / 12.0

        mat_j = BeamMaterial(
            E_psi=E_samples[j],
            Fb_psi=material.Fb_psi,
            Fv_psi=material.Fv_psi,
        )

        result = solve_simply_supported(geometry, mat_j, q0_lb_per_in, n_nodes)

        w_max_arr[j] = result.w_max
        sigma_max_arr[j] = result.sigma_max
        tau_max_arr[j] = result.tau_max

        failures[j] = (
            result.sigma_max > material.Fb_psi
            or result.tau_max > material.Fv_psi
            or result.w_max > L / 240.0
        )

    p_fail = float(np.mean(failures))

    return MCResult(
        p_fail=p_fail,
        w_max_samples=w_max_arr,
        sigma_max_samples=sigma_max_arr,
        tau_max_samples=tau_max_arr,
        n_samples=n_mc,
    )
