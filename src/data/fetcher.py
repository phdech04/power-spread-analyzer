"""
Fetches hourly LMP data from public ISO APIs.
Falls back to synthetic generation if API unavailable.
"""

import os
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import yaml

logger = logging.getLogger(__name__)


class ISODataFetcher:
    def __init__(self, config_path: str = "config/settings.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.cache_dir = Path(self.config["data"]["cache_dir"])
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, iso: str, start: str, end: str) -> str:
        raw = f"{iso}_{start}_{end}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _load_cache(self, iso: str, start: str, end: str) -> pd.DataFrame | None:
        key = self._cache_key(iso, start, end)
        path = self.cache_dir / f"{key}.parquet"
        if path.exists():
            logger.info(f"Loading cached data for {iso}")
            return pd.read_parquet(path)
        return None

    def _save_cache(self, df: pd.DataFrame, iso: str, start: str, end: str):
        key = self._cache_key(iso, start, end)
        path = self.cache_dir / f"{key}.parquet"
        df.to_parquet(path, index=False)

    # ── Real API Fetchers ──────────────────────────────────────────────

    def fetch_ercot(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch ERCOT DAM Settlement Point Prices from public reports.
        ERCOT publishes historical DAM SPPs as downloadable CSVs at:
        https://www.ercot.com/mp/data-products/data-product-details?id=NP4-190-CD

        For the API approach, we use the ERCOT public API (no key required for
        historical DAM data).
        """
        node = self.config["isos"]["ERCOT"]["node"]
        url = "https://www.ercot.com/api/1/services/read/dashboards/dam-settlement-point-prices"

        try:
            params = {
                "deliveryDateFrom": start_date,
                "deliveryDateTo": end_date,
                "settlementPoint": node,
            }
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            rows = []
            for record in data.get("data", []):
                rows.append({
                    "timestamp": pd.Timestamp(record["deliveryDate"]) + pd.Timedelta(hours=int(record.get("deliveryHour", 1)) - 1),
                    "iso": "ERCOT",
                    "node": node,
                    "lmp": float(record.get("settlementPointPrice", 0)),
                    "energy_component": float(record.get("settlementPointPrice", 0)),
                    "congestion_component": 0.0,
                    "loss_component": 0.0,
                })

            if not rows:
                raise ValueError("No ERCOT data returned")

            return pd.DataFrame(rows)

        except Exception as e:
            logger.warning(f"ERCOT API failed: {e}, trying EIA fallback")
            return self.fetch_eia("ERCOT", start_date, end_date)

    def fetch_caiso(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch CAISO LMP data from OASIS API (public, no key required).
        http://oasis.caiso.com/mrioasis/logon.do
        """
        node = self.config["isos"]["CAISO"]["node"]
        url = "http://oasis.caiso.com/oasisapi/SingleZip"

        try:
            params = {
                "queryname": "PRC_LMP",
                "startdatetime": f"{start_date}T07:00-0000",
                "enddatetime": f"{end_date}T07:00-0000",
                "market_run_id": "DAM",
                "node": node,
                "resultformat": 6,  # CSV
            }
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()

            import io
            import zipfile
            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = z.namelist()[0]
            df = pd.read_csv(z.open(csv_name))

            result = pd.DataFrame({
                "timestamp": pd.to_datetime(df["INTERVALSTARTTIME_GMT"]),
                "iso": "CAISO",
                "node": node,
                "lmp": df["MW"].astype(float),
                "energy_component": df.get("LMP_ENE", df["MW"]).astype(float),
                "congestion_component": df.get("LMP_CONG", 0.0),
                "loss_component": df.get("LMP_LOSS", 0.0),
            })
            return result

        except Exception as e:
            logger.warning(f"CAISO OASIS failed: {e}, trying EIA fallback")
            return self.fetch_eia("CAISO", start_date, end_date)

    def fetch_eia(self, iso: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch wholesale electricity prices from EIA Open Data API v2.
        Requires free API key (set EIA_API_KEY env var).
        Covers all major ISOs with hourly demand and price data.
        """
        api_key = os.getenv("EIA_API_KEY")
        if not api_key:
            raise ValueError("EIA_API_KEY environment variable not set")

        iso_mapping = {
            "ERCOT": "TEX",
            "PJM": "PJM",
            "CAISO": "CAL",
            "MISO": "MIDW",
            "NYISO": "NY",
            "ISO-NE": "NE",
            "SPP": "SW",
            "IESO": "ONT",
        }

        base_url = self.config["data"]["eia_api_base"]
        eia_region = iso_mapping.get(iso, iso)

        url = f"{base_url}/daily-region-data/data/"
        params = {
            "api_key": api_key,
            "frequency": "hourly",
            "data[0]": "value",
            "facets[respondent][]": eia_region,
            "start": start_date,
            "end": end_date,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
        }

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        rows = []
        node = self.config["isos"][iso]["node"]
        for record in data.get("response", {}).get("data", []):
            rows.append({
                "timestamp": pd.Timestamp(record["period"]),
                "iso": iso,
                "node": node,
                "lmp": float(record.get("value", 0)),
                "energy_component": float(record.get("value", 0)),
                "congestion_component": 0.0,
                "loss_component": 0.0,
            })

        if not rows:
            raise ValueError(f"No EIA data returned for {iso}")

        return pd.DataFrame(rows)

    # ── Synthetic Fallback ─────────────────────────────────────────────

    def generate_synthetic(self, iso: str, days: int = 365) -> pd.DataFrame:
        """
        Realistic synthetic data when APIs unavailable.
        Models: base load, solar duck curve, heat/cold spikes,
        weekend effects, regime shifts, random spikes.

        Uses Ornstein-Uhlenbeck process for mean-reverting prices:
            dX = theta * (mu - X) * dt + sigma * dW
        """
        np.random.seed(hash(iso) % (2**31))
        iso_config = self.config["isos"][iso]
        base_price = iso_config["base_price"]
        volatility = iso_config["volatility"]
        tz = iso_config["timezone"]

        hours = days * 24
        timestamps = pd.date_range(
            end=pd.Timestamp.now(tz="UTC").normalize(),
            periods=hours,
            freq="h",
            tz="UTC",
        )

        # OU process parameters
        theta = 0.15  # mean-reversion speed
        mu = base_price
        sigma = volatility * 0.01 * base_price
        dt = 1.0 / 24.0

        prices = np.zeros(hours)
        prices[0] = mu
        noise = np.random.randn(hours)

        for t in range(1, hours):
            prices[t] = (
                prices[t - 1]
                + theta * (mu - prices[t - 1]) * dt
                + sigma * np.sqrt(dt) * noise[t]
            )

        # Diurnal pattern (24h cycle)
        hour_of_day = np.array([ts.hour for ts in timestamps])
        diurnal = 8 * np.sin(np.pi * (hour_of_day - 6) / 16)
        diurnal = np.where((hour_of_day >= 6) & (hour_of_day <= 22), diurnal, -3)

        # Seasonal pattern (365d cycle)
        day_of_year = np.array([ts.timetuple().tm_yday for ts in timestamps])
        seasonal = 10 * np.sin(2 * np.pi * (day_of_year - 30) / 365)

        # Weekend discount
        day_of_week = np.array([ts.weekday() for ts in timestamps])
        weekend = np.where(day_of_week >= 5, -5, 0)

        # ISO-specific effects
        iso_effect = np.zeros(hours)
        if iso == "CAISO":
            # Duck curve: solar depression midday
            solar_dip = np.where(
                (hour_of_day >= 10) & (hour_of_day <= 15),
                -12 * np.sin(np.pi * (hour_of_day - 10) / 5),
                0,
            )
            # Evening ramp
            evening_ramp = np.where(
                (hour_of_day >= 17) & (hour_of_day <= 21),
                15 * np.sin(np.pi * (hour_of_day - 17) / 4),
                0,
            )
            iso_effect = solar_dip + evening_ramp

        elif iso == "ERCOT":
            # Summer heat spikes
            summer_heat = np.where(
                (day_of_year >= 150) & (day_of_year <= 250) & (hour_of_day >= 14) & (hour_of_day <= 18),
                20 * np.random.rand(hours),
                0,
            )
            iso_effect = summer_heat

        elif iso in ("SPP", "MISO"):
            # Wind depression during windy hours
            wind_effect = np.where(
                (hour_of_day >= 22) | (hour_of_day <= 6),
                -4 * np.random.rand(hours),
                0,
            )
            iso_effect = wind_effect

        # Random price spikes (Poisson process)
        spike_prob = 0.003
        spikes = np.where(
            np.random.rand(hours) < spike_prob,
            np.random.exponential(scale=50, size=hours),
            0,
        )

        # Combine all components
        lmp = prices + diurnal + seasonal + weekend + iso_effect + spikes
        lmp = np.maximum(lmp, -10)  # floor at -$10/MWh (negative prices happen)

        # Decompose into components (approximate)
        energy = lmp * 0.85
        congestion = lmp * 0.10
        loss = lmp * 0.05

        df = pd.DataFrame({
            "timestamp": timestamps,
            "iso": iso,
            "node": iso_config["node"],
            "lmp": np.round(lmp, 2),
            "energy_component": np.round(energy, 2),
            "congestion_component": np.round(congestion, 2),
            "loss_component": np.round(loss, 2),
        })

        return df

    # ── Main Fetch Interface ───────────────────────────────────────────

    def fetch(self, iso: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Try real data first, fall back to synthetic."""
        # Check cache
        cached = self._load_cache(iso, start_date, end_date)
        if cached is not None:
            return cached

        df = None

        # Try real APIs
        try:
            if iso == "ERCOT":
                df = self.fetch_ercot(start_date, end_date)
            elif iso == "CAISO":
                df = self.fetch_caiso(start_date, end_date)
            else:
                df = self.fetch_eia(iso, start_date, end_date)

            logger.info(f"Fetched real data for {iso}: {len(df)} rows")

        except Exception as e:
            logger.warning(f"Real data fetch failed for {iso}: {e}")
            logger.info(f"Generating synthetic data for {iso}")
            start_dt = pd.Timestamp(start_date)
            end_dt = pd.Timestamp(end_date)
            days = (end_dt - start_dt).days
            df = self.generate_synthetic(iso, days=max(days, 30))

        # Cache the result
        self._save_cache(df, iso, start_date, end_date)
        return df

    def fetch_all(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch data for all configured ISOs and concatenate."""
        frames = []
        for iso in self.config["isos"]:
            df = self.fetch(iso, start_date, end_date)
            frames.append(df)
        return pd.concat(frames, ignore_index=True)

    def generate_synthetic_5min(self, iso: str, days: int = 30) -> pd.DataFrame:
        """
        Generate 5-minute granularity synthetic data for intraday analysis.
        Captures price spikes and ramp events that hourly data misses.
        """
        np.random.seed(hash(f"5min_{iso}") % (2**31))
        iso_config = self.config["isos"][iso]
        base_price = iso_config["base_price"]
        volatility = iso_config["volatility"]

        intervals = days * 24 * 12  # 12 five-minute intervals per hour
        timestamps = pd.date_range(
            end=pd.Timestamp.now(tz="UTC").normalize(),
            periods=intervals,
            freq="5min",
            tz="UTC",
        )

        # OU process at 5-min resolution
        theta = 0.15
        mu = base_price
        sigma = volatility * 0.01 * base_price
        dt = 1.0 / (24 * 12)

        prices = np.zeros(intervals)
        prices[0] = mu
        noise = np.random.randn(intervals)

        for t in range(1, intervals):
            prices[t] = (
                prices[t - 1]
                + theta * (mu - prices[t - 1]) * dt
                + sigma * np.sqrt(dt) * noise[t]
            )

        # Diurnal pattern
        hour_frac = np.array([ts.hour + ts.minute / 60 for ts in timestamps])
        diurnal = 8 * np.sin(np.pi * (hour_frac - 6) / 16)
        diurnal = np.where((hour_frac >= 6) & (hour_frac <= 22), diurnal, -3)

        # Intraday volatility spikes (ramp events)
        spike_prob = 0.001
        spikes = np.where(
            np.random.rand(intervals) < spike_prob,
            np.random.exponential(scale=30, size=intervals),
            0,
        )

        # 5-min ramp events (sharp price moves over 15-30 min)
        ramp_prob = 0.0005
        for i in range(intervals):
            if np.random.rand() < ramp_prob:
                ramp_len = np.random.randint(3, 7)  # 15-35 min ramp
                ramp_mag = np.random.randn() * 15
                end = min(i + ramp_len, intervals)
                prices[i:end] += np.linspace(0, ramp_mag, end - i)

        lmp = prices + diurnal + spikes
        lmp = np.maximum(lmp, -10)

        df = pd.DataFrame({
            "timestamp": timestamps,
            "iso": iso,
            "node": iso_config["node"],
            "lmp": np.round(lmp, 2),
            "energy_component": np.round(lmp * 0.85, 2),
            "congestion_component": np.round(lmp * 0.10, 2),
            "loss_component": np.round(lmp * 0.05, 2),
        })

        return df

    def fetch_5min(self, iso: str, days: int = 30) -> pd.DataFrame:
        """Fetch or generate 5-minute granularity data."""
        cache_key = self._cache_key(iso, f"5min_{days}", "5min")
        cached = self._load_cache(iso, f"5min_{days}", "5min")
        if cached is not None:
            return cached
        df = self.generate_synthetic_5min(iso, days=days)
        self._save_cache(df, iso, f"5min_{days}", "5min")
        return df
