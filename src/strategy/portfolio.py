"""
Multi-pair portfolio optimization using Markowitz mean-variance framework.
Trades multiple ISO spreads simultaneously with correlation-aware sizing.
"""

import logging
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

logger = logging.getLogger(__name__)

ISOS = ["ERCOT", "PJM", "CAISO", "MISO", "NYISO", "ISO-NE", "SPP", "IESO"]


class PortfolioOptimizer:
    """Markowitz portfolio optimization for spread trading."""

    def __init__(self, fetcher, analyzer):
        self.fetcher = fetcher
        self.analyzer = analyzer

    def get_all_pairs(self) -> list:
        """Return all 28 unique ISO pairs."""
        return [f"{a}-{b}" for a, b in combinations(ISOS, 2)]

    def compute_spread_returns(self, days: int = 365) -> pd.DataFrame:
        """
        Compute daily spread returns for all 28 pairs.
        Returns DataFrame: index=date, columns=pair names, values=daily spread changes.
        """
        end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

        # Fetch all ISO data
        iso_data = {}
        for iso in ISOS:
            try:
                df = self.fetcher.fetch(iso, start_date, end_date)
                daily = df.set_index("timestamp").resample("D")["lmp"].mean()
                iso_data[iso] = daily
            except Exception as e:
                logger.warning(f"Failed to fetch {iso}: {e}")

        # Compute spread returns for all pairs
        spreads = {}
        for iso_a, iso_b in combinations(ISOS, 2):
            if iso_a not in iso_data or iso_b not in iso_data:
                continue
            pair = f"{iso_a}-{iso_b}"
            spread = iso_data[iso_a] - iso_data[iso_b]
            spreads[pair] = spread.diff()  # daily change

        if not spreads:
            return pd.DataFrame()

        return pd.DataFrame(spreads).dropna()

    def correlation_matrix(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        """Correlation matrix of all spread returns."""
        return returns_df.corr()

    def covariance_matrix(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        """Annualized covariance matrix."""
        return returns_df.cov() * 252

    def optimize(
        self,
        returns_df: pd.DataFrame,
        target: str = "max_sharpe",
        max_weight: float = 0.30,
        risk_free_rate: float = 0.05,
    ) -> dict:
        """
        Mean-variance portfolio optimization.

        target: 'max_sharpe', 'min_variance', or 'target_return'
        max_weight: maximum allocation per pair (default 30%)
        """
        n = returns_df.shape[1]
        pairs = returns_df.columns.tolist()

        # Annualized statistics
        mu = returns_df.mean().values * 252
        cov = returns_df.cov().values * 252

        def portfolio_return(w):
            return w @ mu

        def portfolio_vol(w):
            return np.sqrt(w @ cov @ w)

        def neg_sharpe(w):
            ret = portfolio_return(w)
            vol = portfolio_vol(w)
            if vol == 0:
                return 0
            return -(ret - risk_free_rate) / vol

        # Constraints: weights sum to 1, each between -max and +max (long/short)
        constraints = [{"type": "eq", "fun": lambda w: np.sum(np.abs(w)) - 1}]
        bounds = [(-max_weight, max_weight)] * n
        w0 = np.ones(n) / n

        if target == "max_sharpe":
            result = minimize(neg_sharpe, w0, bounds=bounds, constraints=constraints,
                            method="SLSQP", options={"maxiter": 1000})
        elif target == "min_variance":
            result = minimize(portfolio_vol, w0, bounds=bounds, constraints=constraints,
                            method="SLSQP", options={"maxiter": 1000})
        else:
            result = minimize(neg_sharpe, w0, bounds=bounds, constraints=constraints,
                            method="SLSQP", options={"maxiter": 1000})

        weights = result.x
        port_ret = float(portfolio_return(weights))
        port_vol = float(portfolio_vol(weights))
        port_sharpe = float((port_ret - risk_free_rate) / port_vol) if port_vol > 0 else 0

        # Build allocation
        allocations = []
        for i, pair in enumerate(pairs):
            if abs(weights[i]) > 0.001:
                allocations.append({
                    "pair": pair,
                    "weight": round(float(weights[i]), 4),
                    "direction": "long" if weights[i] > 0 else "short",
                    "contribution_return": round(float(weights[i] * mu[i]), 4),
                })

        allocations.sort(key=lambda x: abs(x["weight"]), reverse=True)

        return {
            "target": target,
            "portfolio_return": round(port_ret, 4),
            "portfolio_volatility": round(port_vol, 4),
            "portfolio_sharpe": round(port_sharpe, 3),
            "n_active_pairs": sum(1 for a in allocations if abs(a["weight"]) > 0.001),
            "allocations": allocations,
            "optimization_success": result.success,
        }

    def efficient_frontier(
        self, returns_df: pd.DataFrame, n_points: int = 20, max_weight: float = 0.30
    ) -> list:
        """Compute points along the efficient frontier."""
        mu = returns_df.mean().values * 252
        min_ret = mu.min()
        max_ret = mu.max()
        target_returns = np.linspace(min_ret, max_ret, n_points)

        n = returns_df.shape[1]
        cov = returns_df.cov().values * 252

        frontier = []
        for target_ret in target_returns:
            constraints = [
                {"type": "eq", "fun": lambda w: np.sum(np.abs(w)) - 1},
                {"type": "eq", "fun": lambda w, tr=target_ret: w @ mu - tr},
            ]
            bounds = [(-max_weight, max_weight)] * n
            w0 = np.ones(n) / n

            try:
                result = minimize(
                    lambda w: np.sqrt(w @ cov @ w), w0,
                    bounds=bounds, constraints=constraints,
                    method="SLSQP", options={"maxiter": 500}
                )
                if result.success:
                    vol = float(np.sqrt(result.x @ cov @ result.x))
                    ret = float(result.x @ mu)
                    frontier.append({
                        "return": round(ret, 4),
                        "volatility": round(vol, 4),
                        "sharpe": round((ret - 0.05) / vol, 3) if vol > 0 else 0,
                    })
            except Exception:
                continue

        return frontier

    def pair_statistics(self, returns_df: pd.DataFrame) -> list:
        """Summary statistics for each pair."""
        stats = []
        for pair in returns_df.columns:
            r = returns_df[pair]
            ann_ret = float(r.mean() * 252)
            ann_vol = float(r.std() * np.sqrt(252))
            sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
            stats.append({
                "pair": pair,
                "annual_return": round(ann_ret, 4),
                "annual_volatility": round(ann_vol, 4),
                "sharpe": round(sharpe, 3),
                "skew": round(float(r.skew()), 3),
                "kurtosis": round(float(r.kurtosis()), 3),
            })
        stats.sort(key=lambda x: x["sharpe"], reverse=True)
        return stats
