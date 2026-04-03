"""
FastAPI backend serving analysis results to the React frontend.
Run with: uvicorn src.api.app:app --reload --port 8000
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd


def sanitize(obj):
    """Recursively convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

from src.data.fetcher import ISODataFetcher
from src.data.weather import WeatherFetcher
from src.data.processor import DataProcessor
from src.analysis.spreads import SpreadAnalyzer
from src.analysis.correlation import WeatherCorrelation
from src.analysis.seasonality import SeasonalityAnalyzer
from src.analysis.regime import RegimeDetector
from src.strategy.mean_reversion import MeanReversionStrategy
from src.strategy.momentum import MomentumStrategy
from src.strategy.backtest import BacktestEngine
from src.risk.var import RiskMetrics
from src.risk.stress import StressTest

app = FastAPI(title="Power Spread Analyzer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = str(Path(__file__).resolve().parent.parent.parent / "config" / "settings.yaml")
fetcher = ISODataFetcher(config_path=CONFIG_PATH)
analyzer = SpreadAnalyzer()
engine = BacktestEngine()

ISOS = ["ERCOT", "PJM", "CAISO", "MISO", "NYISO", "ISO-NE", "SPP", "IESO"]


@app.get("/api/isos")
def get_isos():
    return {"isos": ISOS}


@app.get("/api/prices")
def get_prices(iso: str = "ERCOT", days: int = 365):
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    df = fetcher.fetch(iso, start_date, end_date)
    daily = df.set_index("timestamp").resample("D")["lmp"].mean().reset_index()
    return {
        "iso": iso,
        "data": [
            {"date": row["timestamp"].isoformat(), "lmp": round(row["lmp"], 2)}
            for _, row in daily.iterrows()
        ],
    }


@app.get("/api/spread")
def get_spread(iso_a: str = "ERCOT", iso_b: str = "PJM", days: int = 365):
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

    df_a = fetcher.fetch(iso_a, start_date, end_date)
    df_b = fetcher.fetch(iso_b, start_date, end_date)
    spread_df = analyzer.compute_spread(df_a, df_b)
    zscore = analyzer.rolling_zscore(spread_df["spread"]).fillna(0)

    return {
        "iso_a": iso_a,
        "iso_b": iso_b,
        "data": [
            {
                "date": row["trade_date"].isoformat() if hasattr(row["trade_date"], "isoformat") else str(row["trade_date"]),
                "price_a": round(row["price_a"], 2),
                "price_b": round(row["price_b"], 2),
                "spread": round(row["spread"], 2),
                "zscore": round(zscore.iloc[i], 3),
            }
            for i, (_, row) in enumerate(spread_df.iterrows())
        ],
        "stats": sanitize(analyzer.spread_summary(spread_df["spread"])),
    }


@app.get("/api/backtest")
def run_backtest(
    iso_a: str = "ERCOT",
    iso_b: str = "PJM",
    days: int = 365,
    strategy: str = "mean_reversion",
    lookback: int = 20,
    entry_z: float = 1.5,
    exit_z: float = 0.3,
    stop_z: float = 3.0,
):
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

    df_a = fetcher.fetch(iso_a, start_date, end_date)
    df_b = fetcher.fetch(iso_b, start_date, end_date)
    spread_df = analyzer.compute_spread(df_a, df_b)
    spreads = spread_df["spread"]

    if strategy == "mean_reversion":
        strat = MeanReversionStrategy(lookback=lookback, entry_z=entry_z, exit_z=exit_z, stop_loss_z=stop_z)
    else:
        strat = MomentumStrategy(fast_window=5, slow_window=lookback)

    signals = strat.generate_signals(spreads)
    result = engine.run(signals)

    return {
        "metrics": result["metrics"],
        "equity_curve": [round(v, 2) for v in result["equity_curve"].tolist()],
        "n_trades": result["metrics"]["n_trades"],
    }


@app.get("/api/risk")
def get_risk(iso_a: str = "ERCOT", iso_b: str = "PJM", days: int = 365):
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

    df_a = fetcher.fetch(iso_a, start_date, end_date)
    df_b = fetcher.fetch(iso_b, start_date, end_date)
    spread_df = analyzer.compute_spread(df_a, df_b)

    strat = MeanReversionStrategy()
    signals = strat.generate_signals(spread_df["spread"])
    bt = engine.run(signals)

    risk = RiskMetrics()
    returns = bt["daily_pnl"][1:] / 100_000
    report = risk.risk_report(returns, bt["equity_curve"])

    stress = StressTest()
    positions = {f"{iso_a}-{iso_b}": 1}
    stress_results = stress.run_all_scenarios(positions)

    return sanitize({
        "risk_report": report,
        "stress_tests": stress_results.to_dict(orient="records"),
    })
