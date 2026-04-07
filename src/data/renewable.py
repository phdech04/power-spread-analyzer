"""
Renewable generation forecast integration.
Solar irradiance and wind speed forecasts feed into price impact models.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Installed renewable capacity by ISO (approximate GW)
RENEWABLE_CAPACITY = {
    "ERCOT": {"wind_gw": 37, "solar_gw": 18},
    "CAISO": {"wind_gw": 6, "solar_gw": 20},
    "SPP": {"wind_gw": 32, "solar_gw": 8},
    "MISO": {"wind_gw": 28, "solar_gw": 6},
    "PJM": {"wind_gw": 4, "solar_gw": 5},
    "NYISO": {"wind_gw": 2, "solar_gw": 3},
    "ISO-NE": {"wind_gw": 1.5, "solar_gw": 5},
    "IESO": {"wind_gw": 5, "solar_gw": 1},
}


class RenewableFetcher:
    """Generates renewable generation forecasts and computes price impacts."""

    def __init__(self):
        self.capacity = RENEWABLE_CAPACITY

    def forecast_generation(
        self, iso: str, weather_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Estimate renewable generation from weather data.
        Wind: power curve approximation from wind speed.
        Solar: irradiance-based capacity factor.
        """
        df = weather_df.copy()
        cap = self.capacity.get(iso, {"wind_gw": 1, "solar_gw": 1})

        # Wind power curve (simplified cubic)
        # Cut-in: 3 m/s, rated: 12 m/s, cut-out: 25 m/s
        wind_speed = df["wind_speed"].values
        wind_cf = np.where(
            wind_speed < 3, 0,
            np.where(
                wind_speed < 12,
                (wind_speed - 3) ** 3 / (12 - 3) ** 3,
                np.where(wind_speed < 25, 1.0, 0)
            )
        )
        # Account for wake effects and availability (~85%)
        wind_cf *= 0.85
        df["wind_generation_gw"] = np.round(wind_cf * cap["wind_gw"], 3)
        df["wind_capacity_factor"] = np.round(wind_cf, 3)

        # Solar: proportional to irradiance with panel efficiency
        solar = df["solar_radiation"].values
        max_irradiance = 1000  # W/m2
        solar_cf = np.minimum(solar / max_irradiance, 1.0) * 0.20  # 20% panel efficiency
        solar_cf = np.maximum(solar_cf, 0)
        df["solar_generation_gw"] = np.round(solar_cf * cap["solar_gw"], 3)
        df["solar_capacity_factor"] = np.round(solar_cf, 3)

        df["total_renewable_gw"] = df["wind_generation_gw"] + df["solar_generation_gw"]
        df["renewable_penetration_pct"] = np.round(
            df["total_renewable_gw"] / (cap["wind_gw"] + cap["solar_gw"]) * 100, 1
        )

        return df

    def price_impact_model(
        self, price_df: pd.DataFrame, renewable_df: pd.DataFrame, iso: str
    ) -> pd.DataFrame:
        """
        Estimate renewable generation's impact on prices.
        Merit-order effect: more renewables -> lower marginal cost -> lower prices.
        """
        # Merge on timestamp
        price_df = price_df.copy()
        renewable_df = renewable_df.copy()
        price_df["timestamp"] = pd.to_datetime(price_df["timestamp"]).dt.floor("h")
        renewable_df["timestamp"] = pd.to_datetime(renewable_df["timestamp"]).dt.floor("h")

        merged = pd.merge(
            price_df[["timestamp", "lmp"]],
            renewable_df[["timestamp", "wind_generation_gw", "solar_generation_gw", "total_renewable_gw"]],
            on="timestamp", how="inner"
        )

        if len(merged) < 50:
            return merged

        # Compute marginal price impact per GW of renewables
        from scipy import stats
        slope, intercept, r_val, p_val, std_err = stats.linregress(
            merged["total_renewable_gw"], merged["lmp"]
        )

        merged["predicted_price_impact"] = slope * merged["total_renewable_gw"]
        merged["residual_price"] = merged["lmp"] - merged["predicted_price_impact"]

        merged.attrs["impact_model"] = {
            "slope_per_gw": round(float(slope), 2),
            "intercept": round(float(intercept), 2),
            "r_squared": round(float(r_val ** 2), 4),
            "p_value": round(float(p_val), 6),
            "iso": iso,
        }

        return merged

    def duck_curve_analysis(self, renewable_df: pd.DataFrame, iso: str = "CAISO") -> pd.DataFrame:
        """
        Analyze the duck curve: midday solar depression + evening ramp.
        Returns hourly average net load shape.
        """
        df = renewable_df.copy()
        df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour

        hourly = df.groupby("hour").agg({
            "solar_generation_gw": "mean",
            "wind_generation_gw": "mean",
            "total_renewable_gw": "mean",
        }).reset_index()

        # Assume base load of ~30 GW for CAISO
        base_load_map = {
            "CAISO": 30, "ERCOT": 45, "PJM": 60, "MISO": 50,
            "SPP": 25, "NYISO": 20, "ISO-NE": 15, "IESO": 18,
        }
        base_load = base_load_map.get(iso, 30)

        # Simple load shape (peaked at 17h)
        hourly["estimated_load_gw"] = base_load * (
            0.7 + 0.3 * np.sin(np.pi * (hourly["hour"].values - 5) / 14)
        )
        hourly["net_load_gw"] = hourly["estimated_load_gw"] - hourly["total_renewable_gw"]
        hourly["solar_reduction_pct"] = (
            hourly["solar_generation_gw"] / hourly["estimated_load_gw"] * 100
        ).round(1)

        # Ramp rate: evening pickup
        hourly["net_load_change"] = hourly["net_load_gw"].diff()
        hourly["iso"] = iso

        return hourly

    def forecast_summary(self, renewable_df: pd.DataFrame, iso: str) -> dict:
        """Summary statistics for renewable generation."""
        df = renewable_df
        cap = self.capacity.get(iso, {"wind_gw": 1, "solar_gw": 1})
        total_cap = cap["wind_gw"] + cap["solar_gw"]

        return {
            "iso": iso,
            "wind_capacity_gw": cap["wind_gw"],
            "solar_capacity_gw": cap["solar_gw"],
            "avg_wind_generation_gw": round(float(df["wind_generation_gw"].mean()), 2),
            "avg_solar_generation_gw": round(float(df["solar_generation_gw"].mean()), 2),
            "avg_total_renewable_gw": round(float(df["total_renewable_gw"].mean()), 2),
            "max_renewable_gw": round(float(df["total_renewable_gw"].max()), 2),
            "avg_wind_cf": round(float(df["wind_capacity_factor"].mean()), 3),
            "avg_solar_cf": round(float(df["solar_capacity_factor"].mean()), 3),
            "peak_renewable_pct": round(float(df["renewable_penetration_pct"].max()), 1),
        }
