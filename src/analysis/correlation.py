"""
Weather-price correlation engine.
Analyzes how temperature, wind, and solar radiation drive power prices.
"""

import numpy as np
import pandas as pd
from scipy import stats


class WeatherCorrelation:
    def pearson_by_iso(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """Compute temperature vs price correlation per ISO."""
        results = []
        for iso, group in merged_df.groupby("iso"):
            clean = group[["lmp", "temp_c"]].dropna()
            if len(clean) < 10:
                continue
            r, p = stats.pearsonr(clean["temp_c"], clean["lmp"])
            results.append({
                "iso": iso,
                "pearson_r": r,
                "p_value": p,
                "n_obs": len(clean),
                "significant": p < 0.05,
            })
        return pd.DataFrame(results)

    def nonlinear_temp_response(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Power demand is V-shaped vs temperature:
        - Below ~18°C: heating demand increases price
        - Above ~24°C: cooling demand increases price
        - 18-24°C: comfortable, low demand (the "valley")

        Bins temperature and computes average price per bin.
        """
        results = []
        for iso, group in df.groupby("iso"):
            clean = group[["temp_c", "lmp"]].dropna()
            if len(clean) < 50:
                continue

            bins = np.arange(
                clean["temp_c"].min() - 1,
                clean["temp_c"].max() + 2,
                2,
            )
            clean = clean.copy()
            clean["temp_bin"] = pd.cut(clean["temp_c"], bins=bins)

            binned = clean.groupby("temp_bin", observed=True)["lmp"].agg(
                ["mean", "std", "count"]
            ).reset_index()
            binned["iso"] = iso
            binned["temp_mid"] = binned["temp_bin"].apply(lambda x: x.mid)
            results.append(binned)

        if not results:
            return pd.DataFrame()
        return pd.concat(results, ignore_index=True)

    def wind_solar_impact(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Quantify renewable generation's impact on prices.
        High wind → lower prices in ERCOT/SPP (wind generation)
        High solar → lower midday prices in CAISO (duck curve)
        """
        results = []
        for iso, group in df.groupby("iso"):
            clean = group[["lmp", "wind_speed", "solar_radiation"]].dropna()
            if len(clean) < 10:
                continue

            row = {"iso": iso}

            # Wind correlation
            r_wind, p_wind = stats.pearsonr(clean["wind_speed"], clean["lmp"])
            row["wind_price_corr"] = r_wind
            row["wind_p_value"] = p_wind

            # Solar correlation
            daytime = clean[clean["solar_radiation"] > 0]
            if len(daytime) > 10:
                r_solar, p_solar = stats.pearsonr(
                    daytime["solar_radiation"], daytime["lmp"]
                )
                row["solar_price_corr"] = r_solar
                row["solar_p_value"] = p_solar
            else:
                row["solar_price_corr"] = np.nan
                row["solar_p_value"] = np.nan

            results.append(row)

        return pd.DataFrame(results)

    def lagged_weather_signal(
        self, df: pd.DataFrame, max_lag: int = 48
    ) -> pd.DataFrame:
        """
        Test if weather N hours ago predicts current price.
        Useful for forecasting: weather forecasts lead price.
        Returns correlation at each lag.
        """
        results = []
        for iso, group in df.groupby("iso"):
            clean = group[["temp_c", "lmp"]].dropna().reset_index(drop=True)
            if len(clean) < max_lag + 50:
                continue

            for lag in range(0, max_lag + 1):
                temp_lagged = clean["temp_c"].shift(lag)
                valid = clean["lmp"].notna() & temp_lagged.notna()
                if valid.sum() < 10:
                    continue
                r, p = stats.pearsonr(
                    temp_lagged[valid], clean["lmp"][valid]
                )
                results.append({
                    "iso": iso,
                    "lag_hours": lag,
                    "pearson_r": r,
                    "p_value": p,
                })

        return pd.DataFrame(results)

    def compute_all(self, df: pd.DataFrame) -> dict:
        """Run all correlation analyses."""
        return {
            "pearson_by_iso": self.pearson_by_iso(df),
            "temp_response": self.nonlinear_temp_response(df),
            "renewable_impact": self.wind_solar_impact(df),
            "lagged_signal": self.lagged_weather_signal(df),
        }
