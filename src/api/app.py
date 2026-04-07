"""
FastAPI backend serving analysis results to the React frontend.
Run with: uvicorn src.api.app:app --reload --port 8000
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
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
        v = float(obj)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(obj, np.ndarray):
        return sanitize(obj.tolist())
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


from src.data.fetcher import ISODataFetcher
from src.data.weather import WeatherFetcher
from src.data.processor import DataProcessor
from src.data.gas import GasFetcher
from src.data.renewable import RenewableFetcher
from src.analysis.spreads import SpreadAnalyzer
from src.analysis.correlation import WeatherCorrelation
from src.analysis.seasonality import SeasonalityAnalyzer
from src.analysis.regime import RegimeDetector
from src.analysis.congestion import CongestionAnalyzer
from src.analysis.forecast import SpreadForecaster
from src.analysis.transmission import TransmissionMapper
from src.analysis.options import VolatilitySurface
from src.analysis.calendar import EventCalendar
from src.strategy.mean_reversion import MeanReversionStrategy
from src.strategy.momentum import MomentumStrategy
from src.strategy.regime_adaptive import RegimeAdaptiveStrategy
from src.strategy.portfolio import PortfolioOptimizer
from src.strategy.backtest import BacktestEngine
from src.risk.var import RiskMetrics
from src.risk.stress import StressTest
from src.risk.montecarlo import MonteCarloSimulator
from src.risk.journal import TradeJournal
from src.realtime.streaming import ConnectionManager, PriceStreamSimulator
from src.realtime.alerts import AlertManager

app = FastAPI(title="Power Spread Analyzer API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = str(Path(__file__).resolve().parent.parent.parent / "config" / "settings.yaml")
fetcher = ISODataFetcher(config_path=CONFIG_PATH)
weather_fetcher = WeatherFetcher(config_path=CONFIG_PATH)
analyzer = SpreadAnalyzer()
engine = BacktestEngine()
gas_fetcher = GasFetcher()
renewable_fetcher = RenewableFetcher()
congestion_analyzer = CongestionAnalyzer()
transmission_mapper = TransmissionMapper()
vol_surface = VolatilitySurface()
event_calendar = EventCalendar()
trade_journal = TradeJournal()
alert_manager = AlertManager()
mc_simulator = MonteCarloSimulator()

# WebSocket streaming
import yaml
with open(CONFIG_PATH) as f:
    _config = yaml.safe_load(f)
ws_manager = ConnectionManager()
price_simulator = PriceStreamSimulator(_config)

ISOS = ["ERCOT", "PJM", "CAISO", "MISO", "NYISO", "ISO-NE", "SPP", "IESO"]


def _fetch_pair(iso_a, iso_b, days):
    """Helper to fetch data for a pair."""
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    df_a = fetcher.fetch(iso_a, start_date, end_date)
    df_b = fetcher.fetch(iso_b, start_date, end_date)
    return df_a, df_b, start_date, end_date


# ── Original Endpoints ─────────────────────────────────────────────────

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
    df_a, df_b, _, _ = _fetch_pair(iso_a, iso_b, days)
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
    df_a, df_b, _, _ = _fetch_pair(iso_a, iso_b, days)
    spread_df = analyzer.compute_spread(df_a, df_b)
    spreads = spread_df["spread"]

    if strategy == "mean_reversion":
        strat = MeanReversionStrategy(lookback=lookback, entry_z=entry_z, exit_z=exit_z, stop_loss_z=stop_z)
    elif strategy == "regime_adaptive":
        strat = RegimeAdaptiveStrategy(lookback=lookback)
    else:
        strat = MomentumStrategy(fast_window=5, slow_window=lookback)

    signals = strat.generate_signals(spreads)
    result = engine.run(signals)

    response = {
        "metrics": result["metrics"],
        "equity_curve": [round(v, 2) for v in result["equity_curve"].tolist()],
        "n_trades": result["metrics"]["n_trades"],
        "strategy": strategy,
    }

    # Add regime info if using regime-adaptive
    if strategy == "regime_adaptive" and hasattr(strat, "get_regime_summary"):
        response["regime_summary"] = sanitize(strat.get_regime_summary(signals))

    return sanitize(response)


@app.get("/api/risk")
def get_risk(iso_a: str = "ERCOT", iso_b: str = "PJM", days: int = 365):
    df_a, df_b, _, _ = _fetch_pair(iso_a, iso_b, days)
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


# ── NEW: ML Forecasting ───────────────────────────────────────────────

@app.get("/api/forecast")
def get_forecast(
    iso_a: str = "ERCOT", iso_b: str = "PJM", days: int = 365,
    model: str = "lstm", horizon: int = 1,
):
    df_a, df_b, _, _ = _fetch_pair(iso_a, iso_b, days)
    spread_df = analyzer.compute_spread(df_a, df_b)

    forecaster = SpreadForecaster(model_type=model)
    result = forecaster.train_and_predict(spread_df, horizon=horizon)

    return sanitize(result)


# ── NEW: Portfolio Optimization ────────────────────────────────────────

@app.get("/api/portfolio")
def get_portfolio(
    days: int = 365, target: str = "max_sharpe", max_weight: float = 0.30,
):
    optimizer = PortfolioOptimizer(fetcher, analyzer)
    returns_df = optimizer.compute_spread_returns(days=days)

    if returns_df.empty:
        return {"error": "Could not compute spread returns"}

    result = optimizer.optimize(returns_df, target=target, max_weight=max_weight)
    result["correlation_matrix"] = sanitize(
        optimizer.correlation_matrix(returns_df).round(3).to_dict()
    )
    result["pair_stats"] = sanitize(optimizer.pair_statistics(returns_df))

    return sanitize(result)


@app.get("/api/portfolio/frontier")
def get_frontier(days: int = 365):
    optimizer = PortfolioOptimizer(fetcher, analyzer)
    returns_df = optimizer.compute_spread_returns(days=days)

    if returns_df.empty:
        return {"error": "Could not compute spread returns"}

    frontier = optimizer.efficient_frontier(returns_df)
    return sanitize({"frontier": frontier})


# ── NEW: Correlation Matrix ────────────────────────────────────────────

@app.get("/api/correlation")
def get_correlation(days: int = 365):
    optimizer = PortfolioOptimizer(fetcher, analyzer)
    returns_df = optimizer.compute_spread_returns(days=days)

    if returns_df.empty:
        return {"error": "Could not compute correlations"}

    corr = optimizer.correlation_matrix(returns_df)
    pairs = corr.columns.tolist()

    # Build heatmap data
    heatmap = []
    for i, p1 in enumerate(pairs):
        for j, p2 in enumerate(pairs):
            heatmap.append({
                "x": p1, "y": p2,
                "value": round(float(corr.iloc[i, j]), 3),
            })

    return sanitize({
        "pairs": pairs,
        "heatmap": heatmap,
        "matrix": corr.round(3).to_dict(),
    })


# ── NEW: Congestion/FTR ───────────────────────────────────────────────

@app.get("/api/congestion")
def get_congestion(iso_a: str = "ERCOT", iso_b: str = "PJM", days: int = 365):
    df_a, df_b, _, _ = _fetch_pair(iso_a, iso_b, days)

    cong_spread = congestion_analyzer.congestion_spread(df_a, df_b)
    ftr = congestion_analyzer.ftr_valuation(cong_spread)
    summary_a = congestion_analyzer.congestion_summary(df_a)
    summary_b = congestion_analyzer.congestion_summary(df_b)

    return sanitize({
        "congestion_spread": [
            {
                "date": row["trade_date"].isoformat() if hasattr(row["trade_date"], "isoformat") else str(row["trade_date"]),
                "total_spread": round(row["total_spread"], 2),
                "congestion_spread": round(row["congestion_spread"], 2),
                "energy_spread": round(row["energy_spread"], 2),
                "congestion_pct": round(row["congestion_contribution_pct"], 1),
            }
            for _, row in cong_spread.iterrows()
        ],
        "ftr_valuation": ftr,
        "summary_a": summary_a.to_dict(orient="records") if not summary_a.empty else [],
        "summary_b": summary_b.to_dict(orient="records") if not summary_b.empty else [],
    })


# ── NEW: Natural Gas / Spark Spread ───────────────────────────────────

@app.get("/api/gas")
def get_gas(iso: str = "ERCOT", days: int = 365):
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

    gas = gas_fetcher.fetch_henry_hub(start_date, end_date)
    power = fetcher.fetch(iso, start_date, end_date)
    spark = gas_fetcher.compute_spark_spread(power, gas, iso)
    summary = gas_fetcher.spark_spread_summary(spark)

    return sanitize({
        "iso": iso,
        "spark_spread": [
            {
                "date": row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"]),
                "power_price": round(row["power_price"], 2),
                "gas_price": round(row["gas_price"], 3),
                "fuel_cost": round(row["fuel_cost"], 2),
                "spark_spread": round(row["spark_spread"], 2),
            }
            for _, row in spark.iterrows()
        ],
        "summary": summary,
        "heat_rate": gas_fetcher.hub_mapping.get(iso, {}).get("heat_rate", 8.0),
        "gas_hub": gas_fetcher.hub_mapping.get(iso, {}).get("hub", "Henry Hub"),
    })


# ── NEW: Renewable Generation ─────────────────────────────────────────

@app.get("/api/renewables")
def get_renewables(iso: str = "CAISO", days: int = 90):
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

    weather = weather_fetcher.fetch_for_iso(iso, start_date, end_date)
    gen = renewable_fetcher.forecast_generation(iso, weather)
    duck = renewable_fetcher.duck_curve_analysis(gen, iso)
    summary = renewable_fetcher.forecast_summary(gen, iso)

    return sanitize({
        "iso": iso,
        "summary": summary,
        "duck_curve": duck.to_dict(orient="records"),
        "hourly_avg": gen.groupby(gen["timestamp"].dt.hour).agg({
            "wind_generation_gw": "mean",
            "solar_generation_gw": "mean",
            "total_renewable_gw": "mean",
        }).round(3).reset_index().rename(columns={"timestamp": "hour"}).to_dict(orient="records"),
    })


# ── NEW: Monte Carlo ──────────────────────────────────────────────────

@app.get("/api/montecarlo")
def get_montecarlo(
    iso_a: str = "ERCOT", iso_b: str = "PJM", days: int = 365,
    n_simulations: int = 5000, horizon: int = 252,
):
    df_a, df_b, _, _ = _fetch_pair(iso_a, iso_b, days)
    spread_df = analyzer.compute_spread(df_a, df_b)

    strat = MeanReversionStrategy()
    signals = strat.generate_signals(spread_df["spread"])
    bt = engine.run(signals)
    returns = bt["daily_pnl"][1:] / 100_000

    sim = MonteCarloSimulator(n_simulations=min(n_simulations, 10000), horizon_days=horizon)
    result = sim.simulate(returns)

    return sanitize(result)


# ── NEW: Transmission Map ─────────────────────────────────────────────

@app.get("/api/transmission")
def get_transmission():
    return sanitize({
        "interfaces": transmission_mapper.get_interfaces(),
        "iso_nodes": transmission_mapper.get_iso_nodes(),
        "flows": transmission_mapper.simulate_flows(),
    })


# ── NEW: Options / Volatility ─────────────────────────────────────────

@app.get("/api/volatility")
def get_volatility(iso_a: str = "ERCOT", iso_b: str = "PJM", days: int = 365):
    df_a, df_b, _, _ = _fetch_pair(iso_a, iso_b, days)
    spread_df = analyzer.compute_spread(df_a, df_b)
    spreads = spread_df["spread"]

    vol_data = vol_surface.vol_summary(spreads)
    current_spread = float(spreads.iloc[-1])

    # Get current realized vol for option pricing
    rv = vol_surface.realized_vol(spreads)
    current_vol = rv[rv["window"] == 20]["current_vol"].values
    current_vol = float(current_vol[0]) if len(current_vol) > 0 and current_vol[0] is not None else 0.3

    chain = vol_surface.option_chain(current_spread, current_vol, days_to_expiry=30)

    return sanitize({
        **vol_data,
        "current_spread": round(current_spread, 2),
        "option_chain": chain,
    })


# ── NEW: Event Calendar ───────────────────────────────────────────────

@app.get("/api/events")
def get_events(
    iso: str = None, category: str = None, days: int = 180,
):
    events = event_calendar.get_upcoming(days=days, iso=iso)
    if category:
        events = [e for e in events if e["category"] == category]
    categories = event_calendar.get_categories()

    return sanitize({
        "events": events,
        "categories": categories,
    })


@app.get("/api/events/pair")
def get_pair_events(iso_a: str = "ERCOT", iso_b: str = "PJM", days: int = 90):
    return sanitize({
        "events": event_calendar.events_for_pair(iso_a, iso_b, days=days),
    })


# ── NEW: Trade Journal ────────────────────────────────────────────────

@app.get("/api/journal")
def get_journal():
    return sanitize({
        "trades": trade_journal.get_all_trades(),
        "summary": trade_journal.summary(),
        "open_count": len(trade_journal.get_open_trades()),
    })


# ── NEW: Alerts ────────────────────────────────────────────────────────

@app.get("/api/alerts")
def get_alerts(limit: int = 50):
    return sanitize({
        "rules": alert_manager.get_rules(),
        "history": alert_manager.get_history(limit=limit),
    })


# ── NEW: WebSocket Streaming ──────────────────────────────────────────

@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """Stream live price updates to connected clients."""
    await ws_manager.connect(websocket, "prices")
    try:
        # Send initial snapshot
        await websocket.send_json({
            "type": "snapshot",
            "data": price_simulator.get_snapshot(),
        })

        while True:
            # Wait for client messages (pair subscriptions) or tick
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=2.0)
                # Client can send subscription: {"subscribe": "ERCOT-PJM"}
                if "subscribe" in data:
                    room = data["subscribe"]
                    await ws_manager.connect(websocket, room)
            except asyncio.TimeoutError:
                pass

            # Generate tick
            updates = price_simulator.tick()
            await websocket.send_json({
                "type": "tick",
                "data": sanitize(updates),
            })

            # Check alerts
            for iso, update in updates.items():
                alert_manager.check_alerts({
                    "price": update["lmp"],
                    "iso": iso,
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "prices")


@app.websocket("/ws/spread")
async def websocket_spread(
    websocket: WebSocket, iso_a: str = "ERCOT", iso_b: str = "PJM"
):
    """Stream live spread + z-score + signals for a pair."""
    room = f"{iso_a}-{iso_b}"
    await ws_manager.connect(websocket, room)
    try:
        while True:
            # Tick prices
            price_simulator.tick()

            # Compute live spread
            spread_data = price_simulator.compute_live_spread(iso_a, iso_b)

            # Check spread alerts
            alerts = alert_manager.check_alerts({
                "zscore": spread_data["zscore"],
                "spread": spread_data["spread"],
                "pair": f"{iso_a}-{iso_b}",
                "iso_a": iso_a,
                "iso_b": iso_b,
            })

            await websocket.send_json(sanitize({
                "type": "spread_tick",
                "data": spread_data,
                "alerts": alerts,
            }))

            await asyncio.sleep(2)  # 2-second tick interval

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, room)
