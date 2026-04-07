"""
Streamlit dashboard for Cross-ISO Power Spread Analyzer.
Run with: streamlit run src/visualization/dashboard.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
from src.risk.position import PositionSizer
from src.risk.montecarlo import MonteCarloSimulator

# ── Page Config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Power Spread Analyzer",
    page_icon="⚡",
    layout="wide",
)

st.title("Cross-ISO Power Spread Analyzer")

# ── Sidebar ──────────────────────────────────────────────────────────
st.sidebar.header("Configuration")

CONFIG_PATH = str(Path(__file__).resolve().parent.parent.parent / "config" / "settings.yaml")

ISOS = ["ERCOT", "PJM", "CAISO", "MISO", "NYISO", "ISO-NE", "SPP", "IESO"]

iso_a = st.sidebar.selectbox("Market A", ISOS, index=0)
iso_b = st.sidebar.selectbox("Market B", ISOS, index=1)

days = st.sidebar.slider("Lookback (days)", 30, 730, 365)

st.sidebar.subheader("Strategy Parameters")
lookback = st.sidebar.slider("Rolling Window", 5, 60, 20)
entry_z = st.sidebar.slider("Entry Z-Score", 0.5, 3.0, 1.5, 0.1)
exit_z = st.sidebar.slider("Exit Z-Score", 0.0, 1.5, 0.3, 0.1)
stop_z = st.sidebar.slider("Stop Loss Z-Score", 2.0, 5.0, 3.0, 0.1)


# ── Data Loading ─────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data(iso_a, iso_b, days):
    fetcher = ISODataFetcher(config_path=CONFIG_PATH)
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

    df_a = fetcher.fetch(iso_a, start_date, end_date)
    df_b = fetcher.fetch(iso_b, start_date, end_date)
    return df_a, df_b, start_date, end_date


@st.cache_data(ttl=3600)
def load_weather(days):
    weather = WeatherFetcher(config_path=CONFIG_PATH)
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    return weather.fetch_all(start_date, end_date)


df_a, df_b, start_date, end_date = load_data(iso_a, iso_b, days)

analyzer = SpreadAnalyzer()
spread_df = analyzer.compute_spread(df_a, df_b)
spreads = spread_df["spread"]

# ── Tabs ─────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13 = st.tabs([
    "Overview", "Spreads", "Forecast", "Portfolio",
    "Backtest", "Risk", "Monte Carlo", "Congestion",
    "Gas/Spark", "Renewables", "Volatility", "Correlation",
    "Events",
])

# ── Tab 1: Market Overview ───────────────────────────────────────────
with tab1:
    st.header("Market Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"{iso_a} Avg Price", f"${df_a['lmp'].mean():.2f}/MWh")
    col2.metric(f"{iso_b} Avg Price", f"${df_b['lmp'].mean():.2f}/MWh")
    col3.metric(f"{iso_a} Volatility", f"${df_a['lmp'].std():.2f}")
    col4.metric(f"{iso_b} Volatility", f"${df_b['lmp'].std():.2f}")

    # Daily prices
    daily_a = df_a.set_index("timestamp").resample("D")["lmp"].mean().reset_index()
    daily_a["iso"] = iso_a
    daily_b = df_b.set_index("timestamp").resample("D")["lmp"].mean().reset_index()
    daily_b["iso"] = iso_b
    daily_both = pd.concat([daily_a, daily_b])

    fig = px.line(daily_both, x="timestamp", y="lmp", color="iso",
                  title="Daily Average LMP", labels={"lmp": "$/MWh"})
    st.plotly_chart(fig, use_container_width=True)

    # Hourly shape
    df_a_copy = df_a.copy()
    df_b_copy = df_b.copy()
    df_a_copy["hour"] = df_a_copy["timestamp"].dt.hour
    df_b_copy["hour"] = df_b_copy["timestamp"].dt.hour
    df_a_copy["iso"] = iso_a
    df_b_copy["iso"] = iso_b
    hourly = pd.concat([df_a_copy, df_b_copy])
    hourly_avg = hourly.groupby(["hour", "iso"])["lmp"].mean().reset_index()

    fig2 = px.line(hourly_avg, x="hour", y="lmp", color="iso",
                   title="Avg Hourly Price Shape", labels={"lmp": "$/MWh"})
    st.plotly_chart(fig2, use_container_width=True)

# ── Tab 2: Spread Analysis ──────────────────────────────────────────
with tab2:
    st.header(f"Spread Analysis: {iso_a} vs {iso_b}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mean Spread", f"${spreads.mean():.2f}")
    col2.metric("Spread Vol", f"${spreads.std():.2f}")

    hl = analyzer.half_life(spreads)
    col3.metric("Half-Life", f"{hl:.1f} days")

    hurst = analyzer.hurst_exponent(spreads)
    col4.metric("Hurst Exponent", f"{hurst:.3f}")

    zscore = analyzer.rolling_zscore(spreads, window=lookback)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=["Spread", "Z-Score"])
    fig.add_trace(go.Scatter(x=spread_df["trade_date"], y=spreads,
                             name="Spread"), row=1, col=1)
    fig.add_hline(y=spreads.mean(), line_dash="dash", row=1, col=1)

    fig.add_trace(go.Scatter(x=spread_df["trade_date"], y=zscore,
                             name="Z-Score"), row=2, col=1)
    fig.add_hline(y=entry_z, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=-entry_z, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=0, line_dash="dash", row=2, col=1)

    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

    coint = analyzer.cointegration_test(
        spread_df["price_a"].values, spread_df["price_b"].values
    )
    st.subheader("Cointegration Test")
    st.json(coint)

# ── Tab 3: ML Forecast ──────────────────────────────────────────────
with tab3:
    st.header("ML Spread Forecasting")

    model_type = st.selectbox("Model", ["gradient_boosting", "lstm", "transformer"])
    horizon = st.selectbox("Forecast Horizon", [1, 5, 10], format_func=lambda x: f"{x}-Day")

    if st.button("Run Forecast"):
        with st.spinner("Training model..."):
            forecaster = SpreadForecaster(model_type=model_type)
            result = forecaster.train_and_predict(spread_df, horizon=horizon)

        if "error" in result:
            st.error(result["error"])
        else:
            m = result["metrics"]
            col1, col2, col3 = st.columns(3)
            col1.metric("Direction Accuracy", f"{m['direction_accuracy']:.1%}")
            col2.metric("RMSE", f"{m['rmse']:.4f}")
            col3.metric("MAE", f"{m['mae']:.4f}")

            st.caption(f"Model: {result['model_type']} | Train: {m['n_train']} | Test: {m['n_test']}")

            fc = pd.DataFrame(result["forecasts"])
            if len(fc) > 0:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=fc["date"], y=fc["actual_spread"],
                                         name="Actual", line=dict(color="#00d4ff")))
                fig.add_trace(go.Scatter(x=fc["date"], y=fc["forecast_spread"],
                                         name="Forecast", line=dict(color="#845ef7", dash="dash")))
                fig.update_layout(title="Actual vs Forecast Spread", height=400)
                st.plotly_chart(fig, use_container_width=True)

                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=fc["date"], y=fc["actual_change"],
                                          name="Actual Change", line=dict(color="#51cf66")))
                fig2.add_trace(go.Scatter(x=fc["date"], y=fc["predicted_change"],
                                          name="Predicted Change", line=dict(color="#ff6b6b", dash="dash")))
                fig2.add_hline(y=0, line_dash="dash", line_color="gray")
                fig2.update_layout(title="Predicted vs Actual Changes", height=350)
                st.plotly_chart(fig2, use_container_width=True)

# ── Tab 4: Portfolio Optimization ────────────────────────────────────
with tab4:
    st.header("Multi-Pair Portfolio Optimization")

    target = st.selectbox("Optimization Target", ["max_sharpe", "min_variance"])
    max_weight = st.slider("Max Weight per Pair", 0.05, 0.50, 0.30, 0.05)

    if st.button("Optimize Portfolio"):
        with st.spinner("Optimizing across 28 pairs..."):
            fetcher = ISODataFetcher(config_path=CONFIG_PATH)
            optimizer = PortfolioOptimizer(fetcher, analyzer)
            returns_df = optimizer.compute_spread_returns(days=days)

        if returns_df.empty:
            st.error("Could not compute spread returns")
        else:
            result = optimizer.optimize(returns_df, target=target, max_weight=max_weight)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Portfolio Return", f"{result['portfolio_return']*100:.1f}%")
            col2.metric("Portfolio Vol", f"{result['portfolio_volatility']*100:.1f}%")
            col3.metric("Sharpe Ratio", f"{result['portfolio_sharpe']:.3f}")
            col4.metric("Active Pairs", result['n_active_pairs'])

            # Allocations
            allocs = pd.DataFrame(result["allocations"])
            if len(allocs) > 0:
                allocs = allocs[allocs["weight"].abs() > 0.005]
                fig = px.bar(allocs, x="weight", y="pair", orientation="h",
                             color="direction", color_discrete_map={"long": "#51cf66", "short": "#ff6b6b"},
                             title="Optimal Allocations")
                fig.update_layout(height=max(400, len(allocs) * 30))
                st.plotly_chart(fig, use_container_width=True)

            # Correlation heatmap
            corr = optimizer.correlation_matrix(returns_df)
            fig2 = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdYlGn",
                             title="Spread Return Correlation Matrix")
            fig2.update_layout(height=600)
            st.plotly_chart(fig2, use_container_width=True)

            # Pair stats
            stats = pd.DataFrame(optimizer.pair_statistics(returns_df))
            st.subheader("Top Pairs by Sharpe")
            st.dataframe(stats.head(15), use_container_width=True)

# ── Tab 5: Backtest ──────────────────────────────────────────────────
with tab5:
    st.header("Strategy Backtest")

    strategy_type = st.selectbox("Strategy", ["Mean Reversion", "Momentum", "Regime Adaptive"])

    if strategy_type == "Mean Reversion":
        strategy = MeanReversionStrategy(
            lookback=lookback, entry_z=entry_z,
            exit_z=exit_z, stop_loss_z=stop_z,
        )
    elif strategy_type == "Regime Adaptive":
        strategy = RegimeAdaptiveStrategy(lookback=lookback)
    else:
        fast = st.number_input("Fast Window", value=5)
        slow = st.number_input("Slow Window", value=20)
        strategy = MomentumStrategy(fast_window=fast, slow_window=slow)

    signals = strategy.generate_signals(spreads)
    engine = BacktestEngine()
    bt_result = engine.run(signals)

    m = bt_result["metrics"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Return", f"{m['total_return_pct']:.1f}%")
    col2.metric("Sharpe Ratio", f"{m['sharpe_ratio']:.2f}")
    col3.metric("Max Drawdown", f"{m['max_drawdown_pct']:.1f}%")
    col4.metric("Win Rate", f"{m['win_rate']:.1%}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Trades", m["n_trades"])
    col6.metric("Profit Factor", f"{m['profit_factor']:.2f}")
    col7.metric("Sortino", f"{m['sortino_ratio']:.2f}")
    col8.metric("Calmar", f"{m['calmar_ratio']:.2f}")

    # Regime summary for adaptive strategy
    if strategy_type == "Regime Adaptive" and hasattr(strategy, "get_regime_summary"):
        rs = strategy.get_regime_summary(signals)
        st.subheader("Regime Summary")
        col1, col2 = st.columns(2)
        col1.metric("Current Regime", rs["current_regime"])
        col2.metric("Current Entry Z", f"{rs['current_entry_z']:.2f}")
        st.json(rs["regime_pct"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=bt_result["equity_curve"], name="Equity",
                             fill="tozeroy"))
    fig.update_layout(title="Equity Curve", yaxis_title="$", height=400)
    st.plotly_chart(fig, use_container_width=True)

    if bt_result["trade_pnl"]:
        fig2 = px.histogram(x=bt_result["trade_pnl"], nbins=30,
                            title="Trade P&L Distribution",
                            labels={"x": "P&L ($)"})
        st.plotly_chart(fig2, use_container_width=True)

# ── Tab 6: Risk ──────────────────────────────────────────────────────
with tab6:
    st.header("Risk Analysis")

    risk = RiskMetrics()
    returns = bt_result["daily_pnl"][1:] / 100_000

    report = risk.risk_report(returns, bt_result["equity_curve"])

    col1, col2, col3 = st.columns(3)
    col1.metric("VaR 95%", f"{report['historical_var_95']:.4f}")
    col2.metric("CVaR 95%", f"{report['cvar_95']:.4f}")
    col3.metric("Annual Vol", f"{report['volatility_annual']:.4f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("Skewness", f"{report['skewness']:.3f}")
    col5.metric("Kurtosis", f"{report['kurtosis']:.3f}")
    col6.metric("Worst Day", f"{report['worst_day']:.4f}")

    # Stress testing
    st.subheader("Stress Scenarios")
    stress = StressTest()
    positions = {f"{iso_a}-{iso_b}": 1}
    stress_results = stress.run_all_scenarios(positions)
    st.dataframe(stress_results, use_container_width=True)

    # Position sizing
    st.subheader("Position Sizing")
    sizer = PositionSizer()
    sizing = sizer.optimal_size(
        capital=100_000,
        win_rate=m["win_rate"],
        avg_win=m["avg_win"],
        avg_loss=m["avg_loss"],
        max_risk_pct=0.02,
        stop_distance=5.0,
    )
    st.json(sizing)

# ── Tab 7: Monte Carlo ──────────────────────────────────────────────
with tab7:
    st.header("Monte Carlo Simulation")

    n_sims = st.selectbox("Simulations", [1000, 5000, 10000], index=1)
    mc_horizon = st.selectbox("Horizon (days)", [126, 252, 504], index=1,
                               format_func=lambda x: f"{x} ({x//252}y)" if x >= 252 else f"{x} (~6m)")

    if st.button("Run Monte Carlo"):
        with st.spinner(f"Running {n_sims:,} simulations..."):
            sim = MonteCarloSimulator(n_simulations=n_sims, horizon_days=mc_horizon)
            mc_result = sim.simulate(returns)

        if "error" in mc_result:
            st.error(mc_result["error"])
        else:
            stats = mc_result["statistics"]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Mean Terminal", f"${stats['mean_terminal']:,.0f}")
            col2.metric("Prob of Loss", f"{stats['prob_loss']:.1f}%")
            col3.metric("Avg Max DD", f"{stats['avg_max_drawdown']:.1f}%")
            col4.metric("P(20%+ DD)", f"{stats['prob_20pct_drawdown']:.1f}%")

            col5, col6, col7, col8, col9 = st.columns(5)
            col5.metric("P5", f"${stats['p5_terminal']:,.0f}")
            col6.metric("P25", f"${stats['p25_terminal']:,.0f}")
            col7.metric("Median", f"${stats['median_terminal']:,.0f}")
            col8.metric("P75", f"${stats['p75_terminal']:,.0f}")
            col9.metric("P95", f"${stats['p95_terminal']:,.0f}")

            # Percentile fan chart
            paths = mc_result["percentile_paths"]
            fig = go.Figure()
            x_days = list(range(0, mc_horizon, max(1, mc_horizon // 200)))
            for pname, color, fill in [
                ("p95", "#51cf66", None), ("p75", "#8ce99a", "tonexty"),
                ("p50", "#00d4ff", None), ("p25", "#ffa8a8", "tonexty"),
                ("p5", "#ff6b6b", None),
            ]:
                y_vals = [paths[pname][i] for i in x_days if i < len(paths[pname])]
                fig.add_trace(go.Scatter(
                    x=x_days[:len(y_vals)], y=y_vals,
                    name=pname.upper(), line=dict(color=color),
                    fill=fill, fillcolor=color.replace(")", ",0.1)").replace("rgb", "rgba") if fill else None,
                ))
            fig.update_layout(title="Equity Path Percentile Bands", height=450,
                              xaxis_title="Trading Days", yaxis_title="$")
            st.plotly_chart(fig, use_container_width=True)

# ── Tab 8: Congestion / FTR ─────────────────────────────────────────
with tab8:
    st.header(f"Congestion Analysis: {iso_a} vs {iso_b}")

    cong = CongestionAnalyzer()
    cong_spread = cong.congestion_spread(df_a, df_b)
    ftr = cong.ftr_valuation(cong_spread)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Daily Cong. Spread", f"${ftr['avg_daily_congestion_spread']:.2f}")
    col2.metric("Annual FTR Value", f"${ftr['annual_ftr_value_est']:,.0f}")
    col3.metric("Monthly FTR Value", f"${ftr['avg_monthly_ftr_value']:,.0f}")
    col4.metric("Positive Days", f"{ftr['positive_days_pct']:.0f}%")

    # Spread decomposition
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cong_spread["trade_date"], y=cong_spread["energy_spread"],
                             name="Energy Spread", fill="tozeroy",
                             line=dict(color="#00d4ff")))
    fig.add_trace(go.Scatter(x=cong_spread["trade_date"], y=cong_spread["congestion_spread"],
                             name="Congestion Spread", fill="tozeroy",
                             line=dict(color="#845ef7")))
    fig.update_layout(title="Spread Decomposition: Energy vs Congestion", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # Congestion contribution %
    fig2 = px.line(cong_spread, x="trade_date", y="congestion_contribution_pct",
                   title="Congestion Contribution to Total Spread (%)")
    fig2.update_layout(height=300)
    st.plotly_chart(fig2, use_container_width=True)

    # Summary tables
    summary_a = cong.congestion_summary(df_a)
    summary_b = cong.congestion_summary(df_b)
    if not summary_a.empty:
        st.subheader(f"{iso_a} Congestion Summary")
        st.dataframe(summary_a, use_container_width=True)
    if not summary_b.empty:
        st.subheader(f"{iso_b} Congestion Summary")
        st.dataframe(summary_b, use_container_width=True)

# ── Tab 9: Gas / Spark Spread ───────────────────────────────────────
with tab9:
    st.header(f"Natural Gas & Spark Spread: {iso_a}")

    gas_fetcher = GasFetcher()
    gas_info = gas_fetcher.hub_mapping.get(iso_a, {})
    st.caption(f"Gas Hub: **{gas_info.get('hub', 'N/A')}** | Heat Rate: **{gas_info.get('heat_rate', 8.0)} MMBtu/MWh**")

    gas_prices = gas_fetcher.fetch_henry_hub(start_date, end_date)
    spark_df = gas_fetcher.compute_spark_spread(df_a, gas_prices, iso_a)
    summary = gas_fetcher.spark_spread_summary(spark_df)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Spark Spread", f"${summary['mean']:.2f}")
    col2.metric("Spark Spread Vol", f"${summary['std']:.2f}")
    col3.metric("Positive Days", f"{summary['pct_positive']:.0f}%")
    col4.metric("Avg When Positive", f"${summary['avg_when_positive']:.2f}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=spark_df["date"], y=spark_df["spark_spread"],
                             name="Spark Spread", line=dict(color="#51cf66")))
    fig.add_trace(go.Scatter(x=spark_df["date"], y=spark_df["power_price"],
                             name="Power Price", line=dict(color="#00d4ff", width=1)))
    fig.add_trace(go.Scatter(x=spark_df["date"], y=spark_df["fuel_cost"],
                             name="Fuel Cost", line=dict(color="#ff6b6b", width=1)))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(title="Spark Spread (Power - Fuel Cost)", height=400)
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.line(spark_df, x="date", y="gas_price", title="Natural Gas Price ($/MMBtu)")
    fig2.update_layout(height=250)
    st.plotly_chart(fig2, use_container_width=True)

# ── Tab 10: Renewables ──────────────────────────────────────────────
with tab10:
    st.header(f"Renewable Generation: {iso_a}")

    renewable_fetcher = RenewableFetcher()
    weather_fetcher = WeatherFetcher(config_path=CONFIG_PATH)

    re_days = min(days, 90)
    re_end = pd.Timestamp.now().strftime("%Y-%m-%d")
    re_start = (pd.Timestamp.now() - pd.Timedelta(days=re_days)).strftime("%Y-%m-%d")
    weather_iso = weather_fetcher.fetch_for_iso(iso_a, re_start, re_end)
    gen_df = renewable_fetcher.forecast_generation(iso_a, weather_iso)
    summary = renewable_fetcher.forecast_summary(gen_df, iso_a)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Wind Capacity", f"{summary['wind_capacity_gw']} GW")
    col2.metric("Solar Capacity", f"{summary['solar_capacity_gw']} GW")
    col3.metric("Avg Wind CF", f"{summary['avg_wind_cf']:.1%}")
    col4.metric("Peak Renewable %", f"{summary['peak_renewable_pct']:.0f}%")

    # Hourly generation profile
    hourly_gen = gen_df.groupby(gen_df["timestamp"].dt.hour).agg({
        "wind_generation_gw": "mean",
        "solar_generation_gw": "mean",
    }).reset_index()
    hourly_gen.rename(columns={"timestamp": "hour"}, inplace=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=hourly_gen["hour"], y=hourly_gen["solar_generation_gw"],
                         name="Solar", marker_color="#fcc419"))
    fig.add_trace(go.Bar(x=hourly_gen["hour"], y=hourly_gen["wind_generation_gw"],
                         name="Wind", marker_color="#00d4ff"))
    fig.update_layout(title="Avg Hourly Generation Profile", barmode="stack", height=350,
                      xaxis_title="Hour of Day", yaxis_title="GW")
    st.plotly_chart(fig, use_container_width=True)

    # Duck curve
    duck = renewable_fetcher.duck_curve_analysis(gen_df, iso_a)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=duck["hour"], y=duck["estimated_load_gw"],
                              name="Gross Load", line=dict(dash="dash", color="gray")))
    fig2.add_trace(go.Scatter(x=duck["hour"], y=duck["net_load_gw"],
                              name="Net Load", line=dict(color="#ff6b6b", width=2)))
    fig2.add_trace(go.Scatter(x=duck["hour"], y=duck["total_renewable_gw"],
                              name="Renewable Gen", line=dict(color="#51cf66", width=2)))
    fig2.update_layout(title="Duck Curve — Net Load Shape", height=350,
                       xaxis_title="Hour", yaxis_title="GW")
    st.plotly_chart(fig2, use_container_width=True)

# ── Tab 11: Volatility / Options ─────────────────────────────────────
with tab11:
    st.header(f"Volatility Analysis: {iso_a}-{iso_b}")

    vol = VolatilitySurface()
    vol_data = vol.vol_summary(spreads)
    cone = vol_data["vol_cone"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Current 20d Vol", f"{cone['current']:.1%}")
    col2.metric("Vol Percentile", f"{cone['percentile']:.0f}th")
    col3.metric("Current Spread", f"${float(spreads.iloc[-1]):.2f}")

    # Term structure
    term = vol_data["term_structure"]
    if term:
        term_df = pd.DataFrame(term)
        fig = px.line(term_df, x="days", y="annualized_vol",
                      title="Volatility Term Structure", markers=True)
        fig.update_layout(height=300, yaxis_tickformat=".1%")
        st.plotly_chart(fig, use_container_width=True)

    # Vol cone
    st.subheader("Volatility Cone")
    cone_df = pd.DataFrame([{
        "Metric": k.upper(), "Value": f"{v:.1%}" if isinstance(v, float) and v < 5 else str(v)
    } for k, v in cone.items()])
    st.dataframe(cone_df, use_container_width=True)

    # Realized vol table
    rv_df = pd.DataFrame(vol_data["realized_vol_table"])
    if len(rv_df) > 0:
        st.subheader("Realized Volatility by Window")
        st.dataframe(rv_df, use_container_width=True)

    # Option chain
    current_spread = abs(float(spreads.iloc[-1])) if float(spreads.iloc[-1]) != 0 else 1.0
    rv_table = vol_data["realized_vol_table"]
    current_vol = 0.3
    for r in rv_table:
        if r["window"] == 20 and r.get("current_vol") is not None:
            current_vol = r["current_vol"]

    chain = vol.option_chain(current_spread, current_vol, days_to_expiry=30)
    if chain:
        st.subheader("Theoretical Option Chain (30-Day Expiry)")
        st.dataframe(pd.DataFrame(chain), use_container_width=True)

# ── Tab 12: Correlation Heatmap ──────────────────────────────────────
with tab12:
    st.header("Spread Return Correlation Matrix")

    if st.button("Compute Correlations (28 pairs)"):
        with st.spinner("Computing spread returns for all pairs..."):
            fetcher = ISODataFetcher(config_path=CONFIG_PATH)
            optimizer = PortfolioOptimizer(fetcher, analyzer)
            returns_df = optimizer.compute_spread_returns(days=days)

        if returns_df.empty:
            st.error("Could not compute correlations")
        else:
            corr = optimizer.correlation_matrix(returns_df)
            fig = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdYlGn",
                            title=f"Correlation Matrix ({len(corr.columns)} pairs)",
                            aspect="auto")
            fig.update_layout(height=700)
            st.plotly_chart(fig, use_container_width=True)

# ── Tab 13: Events Calendar ─────────────────────────────────────────
with tab13:
    st.header("Regulatory & Market Events")

    calendar = EventCalendar()
    categories = calendar.get_categories()

    col1, col2 = st.columns(2)
    filter_cat = col1.selectbox("Category", ["All"] + categories)
    event_days = col2.slider("Lookahead (days)", 30, 365, 180)

    cat_arg = None if filter_cat == "All" else filter_cat

    # Events for the selected pair
    pair_events = calendar.events_for_pair(iso_a, iso_b, days=event_days)
    if cat_arg:
        pair_events = [e for e in pair_events if e["category"] == cat_arg]

    st.subheader(f"Events Affecting {iso_a} / {iso_b} ({len(pair_events)})")
    if pair_events:
        events_df = pd.DataFrame(pair_events)
        display_cols = ["date", "end_date", "title", "category", "impact", "description"]
        available = [c for c in display_cols if c in events_df.columns]
        st.dataframe(events_df[available], use_container_width=True)
    else:
        st.info("No events in this period.")

    # All events
    all_events = calendar.get_upcoming(days=event_days)
    if cat_arg:
        all_events = [e for e in all_events if e["category"] == cat_arg]

    other = [e for e in all_events if e not in pair_events]
    if other:
        st.subheader(f"Other Market Events ({len(other)})")
        other_df = pd.DataFrame(other)
        available = [c for c in display_cols if c in other_df.columns]
        st.dataframe(other_df[available], use_container_width=True)
