"""
Natural gas price integration for spark spread analysis.
Fetches Henry Hub and regional hub prices, computes gas-to-power heat rate spreads.
"""

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Gas hub to ISO mapping (which gas hub prices the marginal generator in each ISO)
GAS_HUB_MAPPING = {
    "ERCOT": {"hub": "Houston Ship Channel", "heat_rate": 7.5},
    "PJM": {"hub": "Tetco M-3", "heat_rate": 8.0},
    "CAISO": {"hub": "SoCal Citygate", "heat_rate": 7.8},
    "MISO": {"hub": "Chicago Citygate", "heat_rate": 8.2},
    "NYISO": {"hub": "Transco Zone 6 NY", "heat_rate": 9.0},
    "ISO-NE": {"hub": "Algonquin Citygate", "heat_rate": 9.5},
    "SPP": {"hub": "Panhandle Eastern", "heat_rate": 8.0},
    "IESO": {"hub": "Dawn Ontario", "heat_rate": 8.5},
}


class GasFetcher:
    """Fetches natural gas prices and computes spark spreads."""

    def __init__(self):
        self.hub_mapping = GAS_HUB_MAPPING

    def fetch_henry_hub(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch Henry Hub natural gas prices.
        Falls back to synthetic if EIA API key not available.
        """
        try:
            import os
            api_key = os.getenv("EIA_API_KEY")
            if api_key:
                url = "https://api.eia.gov/v2/natural-gas/pri/fut/data/"
                params = {
                    "api_key": api_key,
                    "frequency": "daily",
                    "data[0]": "value",
                    "start": start_date,
                    "end": end_date,
                }
                resp = requests.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                rows = []
                for r in data.get("response", {}).get("data", []):
                    rows.append({
                        "date": pd.Timestamp(r["period"]),
                        "gas_price": float(r["value"]),
                    })
                if rows:
                    return pd.DataFrame(rows)
        except Exception as e:
            logger.warning(f"EIA gas fetch failed: {e}")

        return self._generate_synthetic_gas(start_date, end_date)

    def _generate_synthetic_gas(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Synthetic gas prices using OU process with seasonal patterns."""
        np.random.seed(42)
        dates = pd.date_range(start_date, end_date, freq="D")
        n = len(dates)

        # OU process around $3.50/MMBtu
        base = 3.50
        theta = 0.05
        sigma = 0.15
        prices = np.zeros(n)
        prices[0] = base

        for i in range(1, n):
            prices[i] = prices[i-1] + theta * (base - prices[i-1]) + sigma * np.random.randn()

        # Winter premium (Nov-Mar)
        month = dates.month
        winter = np.where((month >= 11) | (month <= 3), 1.0, 0)
        prices += winter

        # Summer AC premium (Jul-Aug)
        summer = np.where((month >= 7) & (month <= 8), 0.3, 0)
        prices += summer

        prices = np.maximum(prices, 1.0)

        return pd.DataFrame({
            "date": dates,
            "gas_price": np.round(prices, 3),
            "hub": "Henry Hub",
        })

    def fetch_regional_basis(self, iso: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Regional gas hub basis differential vs Henry Hub.
        Synthetic: models pipeline constraints and regional supply/demand.
        """
        np.random.seed(hash(iso) % (2**31))
        dates = pd.date_range(start_date, end_date, freq="D")
        n = len(dates)

        # Base basis differentials by region
        basis_map = {
            "ERCOT": 0.10,
            "PJM": 0.40,
            "CAISO": 0.80,
            "MISO": 0.15,
            "NYISO": 1.20,
            "ISO-NE": 2.50,  # Algonquin premium in winter
            "SPP": -0.10,
            "IESO": 0.30,
        }

        base_basis = basis_map.get(iso, 0.20)
        basis = base_basis + np.random.randn(n) * 0.15

        # ISO-NE winter premium (pipeline constraints)
        if iso == "ISO-NE":
            month = dates.month
            winter = np.where((month >= 12) | (month <= 2), 5.0 + np.random.rand(n) * 3, 0)
            basis += winter

        return pd.DataFrame({
            "date": dates,
            "basis": np.round(basis, 3),
            "iso": iso,
            "hub": self.hub_mapping[iso]["hub"],
        })

    def compute_spark_spread(
        self, power_prices: pd.DataFrame, gas_prices: pd.DataFrame, iso: str
    ) -> pd.DataFrame:
        """
        Spark spread = Power Price - (Gas Price * Heat Rate)
        Measures gas-fired generator profitability.
        """
        heat_rate = self.hub_mapping.get(iso, {}).get("heat_rate", 8.0)

        # Align to daily
        if "timestamp" in power_prices.columns:
            daily_power = (
                power_prices.set_index("timestamp")
                .resample("D")["lmp"].mean()
                .reset_index()
                .rename(columns={"timestamp": "date", "lmp": "power_price"})
            )
        else:
            daily_power = power_prices.rename(columns={"lmp": "power_price"})

        daily_power["date"] = pd.to_datetime(daily_power["date"]).dt.tz_localize(None).dt.normalize()
        gas_prices = gas_prices.copy()
        gas_prices["date"] = pd.to_datetime(gas_prices["date"]).dt.tz_localize(None).dt.normalize()

        merged = pd.merge(daily_power, gas_prices[["date", "gas_price"]], on="date", how="inner")
        merged["heat_rate"] = heat_rate
        merged["fuel_cost"] = merged["gas_price"] * heat_rate
        merged["spark_spread"] = merged["power_price"] - merged["fuel_cost"]
        merged["iso"] = iso

        return merged

    def spark_spread_summary(self, spark_df: pd.DataFrame) -> dict:
        """Summary statistics for spark spread."""
        ss = spark_df["spark_spread"].dropna()
        return {
            "mean": round(float(ss.mean()), 2),
            "std": round(float(ss.std()), 2),
            "min": round(float(ss.min()), 2),
            "max": round(float(ss.max()), 2),
            "pct_positive": round(float((ss > 0).mean() * 100), 1),
            "avg_when_positive": round(float(ss[ss > 0].mean()), 2) if (ss > 0).any() else 0,
            "avg_when_negative": round(float(ss[ss < 0].mean()), 2) if (ss < 0).any() else 0,
        }
