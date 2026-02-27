/*
 * beam_solver.cpp — Euler-Bernoulli beam FD solver (C++ port of beam_solver.py)
 *
 * Governing equation (prismatic, uniform EI):
 *   EI * w'''' = q(x),   x in (0, L)
 *
 * Sign convention: w positive downward.
 *   M(x) = -EI * w''
 *   V(x) = -EI * w'''
 *
 * Discretization: 5-point central difference stencil, O(h^2).
 * Simply-supported BCs via ghost points.
 * Direct Gaussian elimination with partial pivoting (no external dependencies).
 *
 * Build:
 *   g++ -O2 -std=c++17 -o beam_solver beam_solver.cpp
 *
 * Usage:
 *   ./beam_solver [span_ft] [width_in] [depth_in] [E_psi] [q0_lb_per_ft] [N]
 *   ./beam_solver                         # uses default 8-ft LVL header
 */

#include <algorithm>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

// ---------------------------------------------------------------------------
// Dense matrix Gaussian elimination with partial pivoting  (O(n^3))
// Solves A x = b in-place; returns false if singular.
// ---------------------------------------------------------------------------
static bool gauss_solve(std::vector<std::vector<double>>& A,
                        std::vector<double>& b,
                        std::vector<double>& x)
{
    int n = static_cast<int>(A.size());
    // Forward elimination
    for (int col = 0; col < n; ++col) {
        // Partial pivot
        int pivot = col;
        for (int row = col + 1; row < n; ++row)
            if (std::abs(A[row][col]) > std::abs(A[pivot][col]))
                pivot = row;
        std::swap(A[col], A[pivot]);
        std::swap(b[col], b[pivot]);

        if (std::abs(A[col][col]) < 1e-300) return false;

        double inv = 1.0 / A[col][col];
        for (int row = col + 1; row < n; ++row) {
            double factor = A[row][col] * inv;
            for (int k = col; k < n; ++k)
                A[row][k] -= factor * A[col][k];
            b[row] -= factor * b[col];
        }
    }
    // Back substitution
    x.resize(n);
    for (int row = n - 1; row >= 0; --row) {
        double sum = b[row];
        for (int k = row + 1; k < n; ++k)
            sum -= A[row][k] * x[k];
        x[row] = sum / A[row][row];
    }
    return true;
}

// ---------------------------------------------------------------------------
// Beam solve result
// ---------------------------------------------------------------------------
struct BeamResult {
    std::vector<double> x;   // node positions [in]
    std::vector<double> w;   // deflection [in], positive downward
    std::vector<double> M;   // bending moment [lb·in]
    double w_max;
    double M_max;
    double sigma_max;
    double tau_max;
    bool passes_bending;
    bool passes_shear;
    bool passes_deflection;
};

// ---------------------------------------------------------------------------
// Analytical exact solution (verification benchmark)
//   w_exact(x) = q0 / (24*EI) * (x^4 - 2*L*x^3 + L^3*x)
// ---------------------------------------------------------------------------
static double w_exact(double xv, double L, double EI, double q0)
{
    return q0 / (24.0 * EI) * (xv*xv*xv*xv - 2.0*L*xv*xv*xv + L*L*L*xv);
}

// ---------------------------------------------------------------------------
// Simply-supported beam solver for uniform load q0 [lb/in]
// ---------------------------------------------------------------------------
BeamResult solve_simply_supported(double L,       // span [in]
                                   double b,       // width [in]
                                   double d,       // depth [in]
                                   double E,       // modulus [psi]
                                   double Fb,      // allowable bending [psi]
                                   double Fv,      // allowable shear [psi]
                                   double q0,      // load [lb/in]
                                   int    n_nodes)
{
    int N    = n_nodes - 1;
    double h = L / N;
    double h4 = h * h * h * h;
    double I  = b * d * d * d / 12.0;
    double EI = E * I;

    int size = N + 1;

    // Build K (dense)
    std::vector<std::vector<double>> K(size, std::vector<double>(size, 0.0));
    std::vector<double> rhs(size, q0);
    rhs[0] = 0.0;
    rhs[N] = 0.0;

    // Row 0: Dirichlet w_0 = 0
    K[0][0] = 1.0;

    // Row 1: modified stencil (ghost point w_{-1} = -w_1)
    K[1][1] =  5.0 * EI / h4;
    K[1][2] = -4.0 * EI / h4;
    K[1][3] =  1.0 * EI / h4;

    // Rows 2 .. N-2: standard 5-point stencil
    for (int i = 2; i <= N - 2; ++i) {
        K[i][i-2] =  1.0 * EI / h4;
        K[i][i-1] = -4.0 * EI / h4;
        K[i][i  ] =  6.0 * EI / h4;
        K[i][i+1] = -4.0 * EI / h4;
        K[i][i+2] =  1.0 * EI / h4;
    }

    // Row N-1: modified stencil (ghost point w_{N+1} = -w_{N-1})
    K[N-1][N-3] =  1.0 * EI / h4;
    K[N-1][N-2] = -4.0 * EI / h4;
    K[N-1][N-1] =  5.0 * EI / h4;

    // Row N: Dirichlet w_N = 0
    K[N][N] = 1.0;

    // Solve
    std::vector<double> w;
    bool ok = gauss_solve(K, rhs, w);
    assert(ok && "Stiffness matrix is singular");

    // Node positions
    std::vector<double> xv(size);
    for (int i = 0; i < size; ++i) xv[i] = i * h;

    // Bending moment: M = -EI * w''  (central difference)
    std::vector<double> Mv(size, 0.0);
    for (int i = 1; i < N; ++i) {
        double w_pp = (w[i-1] - 2.0*w[i] + w[i+1]) / (h * h);
        Mv[i] = -EI * w_pp;
    }
    Mv[0] = 0.0;
    Mv[N] = 0.0;

    // Shear: V = dM/dx via central difference gradient
    // (using numpy-equivalent: one-sided at ends, central in interior)
    std::vector<double> Vv(size, 0.0);
    Vv[0] = (Mv[1] - Mv[0]) / h;
    for (int i = 1; i < N; ++i)
        Vv[i] = (Mv[i+1] - Mv[i-1]) / (2.0 * h);
    Vv[N] = (Mv[N] - Mv[N-1]) / h;

    // Stress resultants
    double w_max = *std::max_element(w.begin(), w.end());
    double M_max = 0.0, V_max = 0.0;
    for (int i = 0; i < size; ++i) {
        M_max = std::max(M_max, std::abs(Mv[i]));
        V_max = std::max(V_max, std::abs(Vv[i]));
    }

    double area         = b * d;
    double section_mod  = I / (d / 2.0);
    double sigma_max    = M_max / section_mod;
    double tau_max      = 1.5 * V_max / area;
    double defl_limit   = L / 240.0;

    BeamResult res;
    res.x    = xv;
    res.w    = w;
    res.M    = Mv;
    res.w_max = w_max;
    res.M_max = M_max;
    res.sigma_max = sigma_max;
    res.tau_max   = tau_max;
    res.passes_bending    = sigma_max <= Fb;
    res.passes_shear      = tau_max   <= Fv;
    res.passes_deflection = w_max     <= defl_limit;
    return res;
}

// ---------------------------------------------------------------------------
// main — benchmark + verification
// ---------------------------------------------------------------------------
int main(int argc, char* argv[])
{
    // Defaults: 8-ft LVL header, Douglas Fir-Larch, q0 = 500 lb/ft
    double span_ft  = (argc > 1) ? atof(argv[1]) : 8.0;
    double width_in = (argc > 2) ? atof(argv[2]) : 3.5;
    double depth_in = (argc > 3) ? atof(argv[3]) : 11.25;
    double E_psi    = (argc > 4) ? atof(argv[4]) : 1600000.0;
    double q0_lbft  = (argc > 5) ? atof(argv[5]) : 500.0;
    int    n_nodes  = (argc > 6) ? atoi(argv[6]) : 200;

    double L        = span_ft * 12.0;            // [in]
    double q0       = q0_lbft / 12.0;            // [lb/in]
    double Fb       = 900.0;                     // [psi]
    double Fv       = 180.0;                     // [psi]

    printf("=== Euler-Bernoulli Beam Solver (C++) ===\n");
    printf("Span: %.1f ft (%.1f in), b=%.2f in, d=%.2f in\n",
           span_ft, L, width_in, depth_in);
    printf("E = %.0f psi, q0 = %.1f lb/ft, N = %d nodes\n\n",
           E_psi, q0_lbft, n_nodes);

    // --- Timed solve ---
    auto t0 = std::chrono::high_resolution_clock::now();
    BeamResult res = solve_simply_supported(
        L, width_in, depth_in, E_psi, Fb, Fv, q0, n_nodes);
    auto t1 = std::chrono::high_resolution_clock::now();
    double elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    // --- Analytical benchmark ---
    double I       = width_in * depth_in * depth_in * depth_in / 12.0;
    double EI      = E_psi * I;
    double w_exact_max = 5.0 * q0 * L*L*L*L / (384.0 * EI);
    double M_exact_max = q0 * L * L / 8.0;

    double w_err = std::abs(res.w_max - w_exact_max) / w_exact_max * 100.0;
    double M_err = std::abs(res.M_max - M_exact_max) / M_exact_max * 100.0;

    printf("--- Results ---\n");
    printf("w_max     = %.6f in  (exact: %.6f in,  err: %.4f%%)\n",
           res.w_max, w_exact_max, w_err);
    printf("M_max     = %.2f lb·in  (exact: %.2f lb·in,  err: %.4f%%)\n",
           res.M_max, M_exact_max, M_err);
    printf("sigma_max = %.1f psi  (Fb = %.0f psi)  %s\n",
           res.sigma_max, Fb, res.passes_bending ? "PASS" : "FAIL");
    printf("tau_max   = %.2f psi  (Fv = %.0f psi)  %s\n",
           res.tau_max, Fv, res.passes_shear ? "PASS" : "FAIL");
    printf("w/L       = 1/%.0f  (limit L/240)  %s\n",
           L / res.w_max, res.passes_deflection ? "PASS" : "FAIL");
    printf("Acceptable: %s\n\n", (res.passes_bending && res.passes_shear && res.passes_deflection) ? "YES" : "NO");
    printf("Solve time: %.3f ms  (N=%d)\n", elapsed_ms, n_nodes);

    // --- Grid convergence summary ---
    printf("\n--- Grid Convergence (Linf error vs exact) ---\n");
    printf("%6s  %10s  %10s  %8s\n", "N", "h [in]", "Linf_err [in]", "p_hat");
    int grids[] = {10, 20, 40, 80, 160};
    double prev_err = 0.0;
    for (int ig = 0; ig < 5; ++ig) {
        int Ng = grids[ig];
        BeamResult rg = solve_simply_supported(
            L, width_in, depth_in, E_psi, Fb, Fv, q0, Ng + 1);
        double hg = L / Ng;
        // Linf vs exact at each node
        double linf = 0.0;
        for (int i = 0; i <= Ng; ++i) {
            double xi = i * hg;
            double we = w_exact(xi, L, EI, q0);
            linf = std::max(linf, std::abs(rg.w[i] - we));
        }
        double p_hat = (ig > 0 && prev_err > 0.0)
                       ? std::log(prev_err / linf) / std::log(2.0)
                       : 0.0;
        if (ig == 0)
            printf("%6d  %10.4f  %13.6e  %8s\n", Ng, hg, linf, "  ---");
        else
            printf("%6d  %10.4f  %13.6e  %8.3f\n", Ng, hg, linf, p_hat);
        prev_err = linf;
    }

    return 0;
}
