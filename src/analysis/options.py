"""
Options and implied volatility analysis for power spreads.
Compares realized vs implied volatility and estimates spread option prices.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq


class VolatilitySurface:
    """Realized and implied volatility analysis for spread options."""

    def realized_vol(
        self, spreads: pd.Series, windows: list = None
    ) -> pd.DataFrame:
        """
        Compute realized volatility at multiple time horizons.
        Annualized using sqrt(252) convention.
        """
        if windows is None:
            windows = [5, 10, 20, 60, 120, 252]

        results = []
        returns = spreads.pct_change().dropna()

        for w in windows:
            if len(returns) < w:
                continue
            rolling_vol = returns.rolling(w).std() * np.sqrt(252)
            current = rolling_vol.iloc[-1] if len(rolling_vol) > 0 else np.nan
            avg = rolling_vol.mean()
            results.append({
                "window": w,
                "window_label": f"{w}d",
                "current_vol": round(float(current), 4) if not np.isnan(current) else None,
                "avg_vol": round(float(avg), 4) if not np.isnan(avg) else None,
                "min_vol": round(float(rolling_vol.min()), 4),
                "max_vol": round(float(rolling_vol.max()), 4),
                "vol_of_vol": round(float(rolling_vol.std()), 4),
            })

        return pd.DataFrame(results)

    def vol_term_structure(self, spreads: pd.Series) -> list:
        """Volatility term structure from short to long horizon."""
        returns = spreads.pct_change().dropna()
        horizons = [5, 10, 20, 40, 60, 90, 120, 180, 252]
        structure = []

        for h in horizons:
            if len(returns) < h:
                break
            vol = float(returns.iloc[-h:].std() * np.sqrt(252))
            structure.append({
                "days": h,
                "annualized_vol": round(vol, 4),
            })

        return structure

    def vol_cone(self, spreads: pd.Series, window: int = 20) -> dict:
        """
        Volatility cone: percentile bands of realized vol over time.
        Shows if current vol is historically high/low.
        """
        returns = spreads.pct_change().dropna()
        rolling_vol = returns.rolling(window).std() * np.sqrt(252)
        rolling_vol = rolling_vol.dropna()

        current = float(rolling_vol.iloc[-1])

        return {
            "window": window,
            "current": round(current, 4),
            "percentile": round(float((rolling_vol < current).mean() * 100), 1),
            "p5": round(float(rolling_vol.quantile(0.05)), 4),
            "p25": round(float(rolling_vol.quantile(0.25)), 4),
            "p50": round(float(rolling_vol.quantile(0.50)), 4),
            "p75": round(float(rolling_vol.quantile(0.75)), 4),
            "p95": round(float(rolling_vol.quantile(0.95)), 4),
            "mean": round(float(rolling_vol.mean()), 4),
        }

    def implied_vol_estimate(
        self, spread: float, strike: float, days_to_expiry: int,
        risk_free_rate: float = 0.05, option_price: float = None,
    ) -> dict:
        """
        Black-76 implied volatility for spread options.
        If option_price given, backs out IV. Otherwise estimates from realized.
        """
        T = days_to_expiry / 365.0
        if T <= 0:
            return {"error": "Expiry must be in the future"}

        if option_price is not None and option_price > 0:
            # Solve for IV using Brent's method
            try:
                iv = brentq(
                    lambda sigma: self._black76_call(spread, strike, T, risk_free_rate, sigma) - option_price,
                    0.01, 5.0
                )
            except ValueError:
                iv = None
        else:
            iv = None

        return {
            "spread": spread,
            "strike": strike,
            "days_to_expiry": days_to_expiry,
            "implied_vol": round(float(iv), 4) if iv else None,
            "option_price": option_price,
        }

    def _black76_call(self, F: float, K: float, T: float, r: float, sigma: float) -> float:
        """Black-76 call price for futures/spread options."""
        if F <= 0 or K <= 0 or sigma <= 0 or T <= 0:
            return max(F - K, 0) * np.exp(-r * T) if F > 0 and K > 0 else 0.0
        d1 = (np.log(F / K) + 0.5 * sigma ** 2 * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        return np.exp(-r * T) * (F * norm.cdf(d1) - K * norm.cdf(d2))

    def option_chain(
        self, current_spread: float, realized_vol: float,
        days_to_expiry: int = 30, risk_free_rate: float = 0.05,
        n_strikes: int = 11,
    ) -> list:
        """
        Generate theoretical option chain around current spread.
        Uses realized vol as proxy for IV.
        """
        T = days_to_expiry / 365.0
        strike_range = realized_vol * current_spread * np.sqrt(T) * 2
        strikes = np.linspace(
            current_spread - strike_range,
            current_spread + strike_range,
            n_strikes,
        )

        # Use absolute spread for option pricing (spreads can be negative)
        F = abs(current_spread) if current_spread != 0 else 1.0

        chain = []
        for K in strikes:
            if K <= 0:
                continue
            call = self._black76_call(F, K, T, risk_free_rate, realized_vol)
            put = call - np.exp(-risk_free_rate * T) * (F - K)  # put-call parity

            if F > 0 and K > 0 and realized_vol > 0:
                d1 = (np.log(F / K) + 0.5 * realized_vol ** 2 * T) / (realized_vol * np.sqrt(T))
                delta = float(norm.cdf(d1))
            else:
                delta = 0.5

            chain.append({
                "strike": round(float(K), 2),
                "call_price": round(float(max(call, 0)), 4),
                "put_price": round(float(max(put, 0)), 4),
                "delta": round(float(delta), 4),
                "moneyness": round(float(current_spread / K), 4),
            })

        return chain

    def vol_summary(self, spreads: pd.Series) -> dict:
        """Complete volatility analysis summary."""
        rv = self.realized_vol(spreads)
        cone = self.vol_cone(spreads)
        term = self.vol_term_structure(spreads)

        return {
            "realized_vol_table": rv.to_dict(orient="records"),
            "vol_cone": cone,
            "term_structure": term,
            "current_20d_vol": cone["current"],
            "vol_percentile": cone["percentile"],
        }
