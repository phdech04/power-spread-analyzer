"""
Monte Carlo simulation for strategy robustness testing.
Generates 10,000+ scenario paths using block bootstrap
and regime-conditional volatility scaling.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MonteCarloSimulator:
    """Monte Carlo simulation engine for spread portfolio risk assessment."""

    def __init__(self, n_simulations: int = 10000, horizon_days: int = 252):
        self.n_simulations = n_simulations
        self.horizon_days = horizon_days

    def block_bootstrap(
        self, returns: np.ndarray, block_size: int = 10
    ) -> np.ndarray:
        """
        Block bootstrap to preserve autocorrelation structure.
        Draws blocks of consecutive returns and concatenates.
        """
        n = len(returns)
        n_blocks = (self.horizon_days // block_size) + 1
        path = np.zeros(self.horizon_days)

        idx = 0
        for _ in range(n_blocks):
            start = np.random.randint(0, max(1, n - block_size))
            block = returns[start:start + block_size]
            end = min(idx + len(block), self.horizon_days)
            path[idx:end] = block[:end - idx]
            idx = end
            if idx >= self.horizon_days:
                break

        return path

    def simulate(
        self,
        returns: pd.Series,
        initial_equity: float = 100_000,
        regime_states: np.ndarray = None,
        regime_vol_multipliers: dict = None,
    ) -> dict:
        """
        Run Monte Carlo simulation.

        Args:
            returns: Historical daily returns series
            initial_equity: Starting capital
            regime_states: Array of regime labels per return (0,1,2)
            regime_vol_multipliers: {regime_id: vol_multiplier}

        Returns:
            Distribution of terminal wealth, drawdowns, and statistics.
        """
        returns_arr = returns.dropna().values
        if len(returns_arr) < 30:
            return {"error": "Insufficient data for Monte Carlo (need 30+ returns)"}

        terminal_values = np.zeros(self.n_simulations)
        max_drawdowns = np.zeros(self.n_simulations)
        paths = np.zeros((self.n_simulations, self.horizon_days))

        for i in range(self.n_simulations):
            # Block bootstrap path
            sim_returns = self.block_bootstrap(returns_arr)

            # Regime-conditional volatility scaling
            if regime_states is not None and regime_vol_multipliers:
                regime_seq = np.random.choice(regime_states, size=self.horizon_days)
                for regime_id, mult in regime_vol_multipliers.items():
                    mask = regime_seq == regime_id
                    sim_returns[mask] *= mult

            # Build equity path
            equity = initial_equity * np.cumprod(1 + sim_returns)
            paths[i] = equity
            terminal_values[i] = equity[-1]

            # Max drawdown
            peak = np.maximum.accumulate(equity)
            dd = (equity - peak) / peak
            max_drawdowns[i] = dd.min()

        # Compute percentile paths
        percentiles = {}
        for p in [5, 25, 50, 75, 95]:
            percentiles[f"p{p}"] = np.percentile(paths, p, axis=0).tolist()

        # Statistics
        terminal_return = (terminal_values - initial_equity) / initial_equity

        return {
            "n_simulations": self.n_simulations,
            "horizon_days": self.horizon_days,
            "initial_equity": initial_equity,
            "statistics": {
                "mean_terminal": round(float(terminal_values.mean()), 2),
                "median_terminal": round(float(np.median(terminal_values)), 2),
                "std_terminal": round(float(terminal_values.std()), 2),
                "p5_terminal": round(float(np.percentile(terminal_values, 5)), 2),
                "p25_terminal": round(float(np.percentile(terminal_values, 25)), 2),
                "p75_terminal": round(float(np.percentile(terminal_values, 75)), 2),
                "p95_terminal": round(float(np.percentile(terminal_values, 95)), 2),
                "mean_return": round(float(terminal_return.mean() * 100), 2),
                "prob_loss": round(float((terminal_values < initial_equity).mean() * 100), 1),
                "prob_20pct_drawdown": round(float((max_drawdowns < -0.20).mean() * 100), 1),
                "avg_max_drawdown": round(float(max_drawdowns.mean() * 100), 1),
                "worst_drawdown": round(float(max_drawdowns.min() * 100), 1),
            },
            "percentile_paths": percentiles,
            "terminal_distribution": {
                "values": np.percentile(terminal_values, np.arange(0, 101, 5)).tolist(),
                "percentiles": list(range(0, 101, 5)),
            },
        }

    def var_from_simulation(
        self, returns: pd.Series, confidence: float = 0.95
    ) -> dict:
        """Compute VaR and CVaR from Monte Carlo paths."""
        result = self.simulate(returns, n_simulations=self.n_simulations)
        if "error" in result:
            return result

        terminal = np.array(result["terminal_distribution"]["values"])
        # Use terminal returns for VaR
        returns_dist = (terminal - result["initial_equity"]) / result["initial_equity"]

        var_idx = int((1 - confidence) * len(returns_dist))
        var = float(returns_dist[var_idx])
        cvar = float(returns_dist[:var_idx + 1].mean()) if var_idx > 0 else var

        return {
            "mc_var": round(var * 100, 2),
            "mc_cvar": round(cvar * 100, 2),
            "confidence": confidence,
            "n_simulations": self.n_simulations,
        }
