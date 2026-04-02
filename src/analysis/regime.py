"""
HMM-based regime detection for power prices.
Identifies low-volatility, normal, and high-volatility/spike regimes.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    logger.warning("hmmlearn not available — regime detection will use fallback")


class RegimeDetector:
    def fit(self, returns: pd.Series, n_regimes: int = 3) -> dict:
        """
        Detect price regimes using Hidden Markov Model.
        Regimes: low-vol (calm), normal, high-vol (spike/stress).

        Falls back to quantile-based detection if hmmlearn unavailable.
        """
        returns = returns.dropna()

        if HMM_AVAILABLE:
            return self._fit_hmm(returns, n_regimes)
        return self._fit_quantile(returns, n_regimes)

    def _fit_hmm(self, returns: pd.Series, n_regimes: int) -> dict:
        model = GaussianHMM(
            n_components=n_regimes,
            covariance_type="full",
            n_iter=100,
            random_state=42,
        )
        X = returns.values.reshape(-1, 1)
        model.fit(X)
        states = model.predict(X)

        # Sort regimes by variance (low-vol first)
        variances = model.covars_.flatten()
        sort_idx = np.argsort(variances)
        state_map = {old: new for new, old in enumerate(sort_idx)}
        states = np.array([state_map[s] for s in states])

        regime_names = {0: "low_volatility", 1: "normal", 2: "high_volatility"}
        if n_regimes > 3:
            for i in range(3, n_regimes):
                regime_names[i] = f"regime_{i}"

        return {
            "states": states,
            "means": model.means_.flatten()[sort_idx],
            "variances": variances[sort_idx],
            "transition_matrix": model.transmat_[sort_idx][:, sort_idx],
            "regime_names": regime_names,
            "method": "hmm",
        }

    def _fit_quantile(self, returns: pd.Series, n_regimes: int) -> dict:
        """Fallback: classify regimes by rolling volatility quantiles."""
        rolling_vol = returns.rolling(24).std()
        quantiles = np.linspace(0, 1, n_regimes + 1)
        thresholds = rolling_vol.quantile(quantiles).values

        states = np.zeros(len(returns), dtype=int)
        for i in range(1, n_regimes):
            states[rolling_vol.values > thresholds[i]] = i

        regime_names = {0: "low_volatility", 1: "normal", 2: "high_volatility"}

        means = []
        variances = []
        for s in range(n_regimes):
            mask = states == s
            if mask.sum() > 0:
                means.append(float(returns.values[mask].mean()))
                variances.append(float(returns.values[mask].var()))
            else:
                means.append(0.0)
                variances.append(0.0)

        return {
            "states": states,
            "means": np.array(means),
            "variances": np.array(variances),
            "transition_matrix": self._estimate_transition(states, n_regimes),
            "regime_names": regime_names,
            "method": "quantile_fallback",
        }

    def _estimate_transition(self, states: np.ndarray, n_regimes: int) -> np.ndarray:
        """Estimate transition matrix from state sequence."""
        trans = np.zeros((n_regimes, n_regimes))
        for i in range(len(states) - 1):
            trans[states[i], states[i + 1]] += 1

        # Normalize rows
        row_sums = trans.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        return trans / row_sums

    def regime_summary(self, returns: pd.Series, result: dict) -> pd.DataFrame:
        """Summary statistics per regime."""
        returns = returns.dropna().values
        rows = []
        for state_id, name in result["regime_names"].items():
            mask = result["states"] == state_id
            if mask.sum() == 0:
                continue
            regime_returns = returns[mask]
            rows.append({
                "regime": name,
                "count": int(mask.sum()),
                "pct_time": float(mask.sum() / len(mask)),
                "mean_return": float(regime_returns.mean()),
                "volatility": float(regime_returns.std()),
                "min": float(regime_returns.min()),
                "max": float(regime_returns.max()),
            })
        return pd.DataFrame(rows)
