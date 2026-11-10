"""Mean-variance (Markowitz) portfolio from sample estimates -- price-only signals.

At each weekly decision date d the model sees only the last `lookback` daily returns
up to and including d, and solves

    maximize    mu' w  -  (lam / 2) * w' Sigma w
    subject to  sum(w) = 1,   0 <= w_i <= w_max

    mu    = sample mean of daily returns   * 252   (annualized expected return)
    Sigma = sample covariance of returns   * 252   (annualized covariance)
    lam   = risk aversion: 0 -> put as much as allowed into the highest-mean ETFs,
            larger -> high-variance ETFs (and correlated groups) are penalized more
    w_max = diversification cap (at least ceil(1 / w_max) ETFs are held)

Long-only and fully invested: there is no separate cash position. T-bill ETFs in the
universe (SGOV, BIL, JPST, ...) serve as the cash-like asset if the model wants low risk.

Solvers: Gurobi QP (default, solve_mean_variance_gurobi) or our own numpy implementation
of accelerated projected gradient (FISTA, solve_mean_variance), described below.

    solve(mu, Sigma, lam, w_max):
        if lam == 0: fill w_max into the assets in decreasing mu order        # exact LP solution
        L <- lam * largest eigenvalue of Sigma                                # Lipschitz constant
        w <- y <- uniform weights;  t <- 1
        repeat until ||w_new - w||_inf < tol or max_iter:
            grad   <- lam * Sigma y - mu                                       # O(n^2)
            w_new  <- PROJECT(y - grad / L)                                    # O(n log(1/eps))
            if grad . (w_new - w) > 0: t <- 1, y <- w <- w_new, continue       # adaptive restart
            t_new  <- (1 + sqrt(1 + 4 t^2)) / 2
            y      <- w_new + ((t - 1) / t_new) (w_new - w)
            w, t   <- w_new, t_new
        return w

    PROJECT(v):  Euclidean projection onto {0 <= w <= w_max, sum w = 1}
        find tau by bisection such that sum_i clip(v_i - tau, 0, w_max) = 1
        return clip(v - tau, 0, w_max)

Complexity per decision (n assets, T = lookback days, K iterations):
    estimation  O(T n^2)   eigenvalue O(n^3)   optimization O(K (n^2 + n log(1/eps)))
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


# ------------------------------------------------------------------ estimation
def sample_estimates(window: pd.DataFrame):
    """Annualized sample mean vector and covariance matrix of daily returns."""
    mu = window.mean().to_numpy() * TRADING_DAYS
    sigma = np.cov(window.to_numpy(), rowvar=False, ddof=1) * TRADING_DAYS
    return mu, np.atleast_2d(sigma)


# ------------------------------------------------------------------ optimization
def project_capped_simplex(v, w_max, tol=1e-12, max_iter=200):
    """Euclidean projection of v onto {w : 0 <= w <= w_max, sum(w) = 1} (bisection on tau)."""
    lo, hi = v.min() - w_max, v.max()  # sum = n*w_max >= 1 at lo, sum = 0 at hi
    for _ in range(max_iter):
        tau = (lo + hi) / 2
        s = np.clip(v - tau, 0.0, w_max).sum()
        if abs(s - 1.0) < tol or hi - lo < 1e-15:
            break
        lo, hi = (tau, hi) if s > 1.0 else (lo, tau)
    return np.clip(v - tau, 0.0, w_max)


def greedy_max_return(mu, w_max):
    """lam = 0: the problem is linear, so fill the highest-mean assets up to the cap."""
    w = np.zeros_like(mu)
    left = 1.0
    for i in np.argsort(-mu):
        w[i] = min(w_max, left)
        left -= w[i]
        if left <= 0:
            break
    return w


def solve_mean_variance(mu, sigma, lam, w_max, tol=1e-9, max_iter=10_000):
    """Return (weights, iterations) for max mu'w - lam/2 w'Sigma w on the capped simplex."""
    n = len(mu)
    if n * w_max < 1 - 1e-12:
        raise ValueError(f"w_max={w_max} is infeasible for {n} assets (need n * w_max >= 1)")
    if lam == 0:
        return greedy_max_return(mu, w_max), 0

    L = lam * np.linalg.eigvalsh(sigma)[-1]
    if L <= 0:  # zero-variance window: only the mean matters
        return greedy_max_return(mu, w_max), 0

    w = y = np.full(n, 1.0 / n)
    t = 1.0
    for k in range(1, max_iter + 1):
        grad = lam * (sigma @ y) - mu
        w_new = project_capped_simplex(y - grad / L, w_max)
        if np.abs(w_new - w).max() < tol:
            return w_new, k
        if grad @ (w_new - w) > 0:  # momentum points uphill -> restart (O'Donoghue & Candes, 2015)
            t, y, w = 1.0, w_new, w_new
            continue
        t_new = (1 + np.sqrt(1 + 4 * t * t)) / 2
        y = w_new + ((t - 1) / t_new) * (w_new - w)
        w, t = w_new, t_new
    return w, max_iter


def solve_mean_variance_gurobi(mu, sigma, lam, w_max):
    """Same problem solved with Gurobi's QP solver (reference / cross-check for our own solver).

    Returns (weights, barrier iterations), like solve_mean_variance.
    """
    import gurobipy as gp  # optional dependency: only needed when this solver is used
    from gurobipy import GRB

    n = len(mu)
    sigma = (sigma + sigma.T) / 2  # exact symmetry, so Gurobi accepts the quadratic term
    with gp.Env(params={"OutputFlag": 0}) as env, gp.Model("markowitz", env=env) as m:
        w = m.addVars(n, lb=0.0, ub=w_max, name="w")
        m.addConstr(w.sum() == 1, name="budget")

        ret = gp.LinExpr(mu.tolist(), [w[i] for i in range(n)])          # mu' w
        i, j = np.triu_indices(n)                                         # w' Sigma w, upper triangle
        coef = np.where(i == j, 1.0, 2.0) * sigma[i, j]
        risk = gp.QuadExpr()
        risk.addTerms(coef.tolist(), [w[a] for a in i], [w[b] for b in j])
        m.setObjective(ret - (lam / 2) * risk, GRB.MAXIMIZE)

        m.optimize()
        if m.Status != GRB.OPTIMAL:
            raise RuntimeError(f"Gurobi status {m.Status}")
        x = np.array([w[k].X for k in range(n)])
        return np.clip(x, 0.0, w_max), m.BarIterCount


# ------------------------------------------------------------------ strategy
SOLVERS = {"gurobi": solve_mean_variance_gurobi, "fista": solve_mean_variance}


class MeanVariance:
    """Weekly strategy: history (returns up to the decision date) -> target weights.

    solver: "gurobi" (default, Gurobi QP) or "fista" (our own projected-gradient solver).
    """

    def __init__(self, lookback=126, lam=10.0, w_max=0.20, solver="gurobi"):
        if solver not in SOLVERS:
            raise ValueError(f"solver must be one of {list(SOLVERS)}, got {solver!r}")
        self.lookback, self.lam, self.w_max, self.solver = lookback, lam, w_max, solver
        self.name = f"Mean-variance (lookback={lookback}d, lambda={lam:g}, w_max={w_max:.0%})"

    def __call__(self, history: pd.DataFrame) -> pd.Series:
        window = history.tail(self.lookback)
        eligible = window.columns[window.notna().all()]  # full history in the window
        mu, sigma = sample_estimates(window[eligible])
        w, _ = SOLVERS[self.solver](mu, sigma, self.lam, max(self.w_max, 1 / len(eligible)))
        w[w < 1e-6] = 0.0  # drop numerical dust, then renormalize
        return pd.Series(w / w.sum(), index=eligible).reindex(history.columns, fill_value=0.0)

    def diagnostics(self, history: pd.DataFrame) -> pd.DataFrame:
        """Annualized expected return / volatility of every eligible ETF at this decision."""
        window = history.tail(self.lookback)
        window = window.loc[:, window.notna().all()]
        mu, sigma = sample_estimates(window)
        return pd.DataFrame({"exp_return_ann": mu, "vol_ann": np.sqrt(np.diag(sigma))}, index=window.columns)
