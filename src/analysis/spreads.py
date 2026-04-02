"""
Spread computation, rolling statistics, cointegration testing,
and mean-reversion metrics for cross-ISO power spreads.
"""

import numpy as np
import pandas as pd
from numpy.linalg import lstsq
from statsmodels.tsa.stattools import coint, adfuller


class SpreadAnalyzer:
    def compute_spread(self, df_a: pd.DataFrame, df_b: pd.DataFrame) -> pd.DataFrame:
        """
        Daily average LMP spread between two ISOs.
        Returns DataFrame with trade_date, price_a, price_b, spread.
        """
        daily_a = (
            df_a.set_index("timestamp")
            .resample("D")["lmp"]
            .mean()
            .rename("price_a")
        )
        daily_b = (
            df_b.set_index("timestamp")
            .resample("D")["lmp"]
            .mean()
            .rename("price_b")
        )
        combined = pd.concat([daily_a, daily_b], axis=1).dropna()
        combined["spread"] = combined["price_a"] - combined["price_b"]
        combined.index.name = "trade_date"
        return combined.reset_index()

    def rolling_zscore(self, spreads: pd.Series, window: int = 20) -> pd.Series:
        """Z-score of current spread vs rolling window."""
        mean = spreads.rolling(window).mean()
        std = spreads.rolling(window).std()
        return (spreads - mean) / std

    def half_life(self, spreads: pd.Series) -> float:
        """
        Ornstein-Uhlenbeck half-life estimation.
        Key metric: how fast does the spread mean-revert?
        Shorter half-life = better mean-reversion candidate.

        Regression: delta(spread) = theta * spread_lag + intercept
        Half-life = -ln(2) / theta
        """
        spreads = spreads.dropna()
        lag = spreads.shift(1).iloc[1:]
        delta = spreads.diff().iloc[1:]

        # Remove NaN
        mask = lag.notna() & delta.notna()
        lag = lag[mask].values
        delta = delta[mask].values

        X = np.column_stack([lag, np.ones(len(lag))])
        theta = lstsq(X, delta, rcond=None)[0][0]

        if theta >= 0:
            return np.inf  # not mean-reverting
        return -np.log(2) / theta

    def cointegration_test(
        self, series_a: np.ndarray, series_b: np.ndarray
    ) -> dict:
        """
        Engle-Granger cointegration test.
        If cointegrated, the spread is stationary = tradeable.
        """
        stat, pvalue, crit_values = coint(series_a, series_b)
        return {
            "test_stat": float(stat),
            "p_value": float(pvalue),
            "critical_values": {
                "1%": float(crit_values[0]),
                "5%": float(crit_values[1]),
                "10%": float(crit_values[2]),
            },
            "cointegrated": pvalue < 0.05,
        }

    def adf_test(self, series: pd.Series) -> dict:
        """Augmented Dickey-Fuller test for stationarity."""
        result = adfuller(series.dropna(), autolag="AIC")
        return {
            "test_stat": float(result[0]),
            "p_value": float(result[1]),
            "lags_used": int(result[2]),
            "n_obs": int(result[3]),
            "critical_values": {k: float(v) for k, v in result[4].items()},
            "stationary": result[1] < 0.05,
        }

    def hurst_exponent(self, series: pd.Series, max_lag: int = 100) -> float:
        """
        Hurst exponent via R/S analysis.
        H < 0.5: mean-reverting
        H = 0.5: random walk
        H > 0.5: trending
        """
        series = series.dropna().values
        n = len(series)
        if n < max_lag * 2:
            max_lag = n // 4

        lags = range(2, max_lag)
        rs = []

        for lag in lags:
            subseries = [series[i:i + lag] for i in range(0, n - lag, lag)]
            rs_vals = []
            for ss in subseries:
                if len(ss) < 2:
                    continue
                mean_ss = np.mean(ss)
                deviations = np.cumsum(ss - mean_ss)
                r = np.max(deviations) - np.min(deviations)
                s = np.std(ss, ddof=1)
                if s > 0:
                    rs_vals.append(r / s)
            if rs_vals:
                rs.append(np.mean(rs_vals))
            else:
                rs.append(np.nan)

        rs = np.array(rs)
        lags = np.array(list(lags))
        valid = ~np.isnan(rs) & (rs > 0)

        if valid.sum() < 2:
            return 0.5

        log_lags = np.log(lags[valid])
        log_rs = np.log(rs[valid])
        X = np.column_stack([log_lags, np.ones(len(log_lags))])
        hurst = lstsq(X, log_rs, rcond=None)[0][0]

        return float(hurst)

    def spread_summary(self, spreads: pd.Series) -> dict:
        """Comprehensive summary statistics for a spread series."""
        spreads = spreads.dropna()
        return {
            "mean": float(spreads.mean()),
            "std": float(spreads.std()),
            "min": float(spreads.min()),
            "max": float(spreads.max()),
            "skew": float(spreads.skew()),
            "kurtosis": float(spreads.kurtosis()),
            "half_life": self.half_life(spreads),
            "hurst": self.hurst_exponent(spreads),
            "adf": self.adf_test(spreads),
        }
