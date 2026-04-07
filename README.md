# Cross-ISO Power Spread Analyzer

**An institutional-grade quantitative trading platform for identifying, forecasting, and executing spread trading opportunities across all major North American electricity markets.**

Built for energy traders, quantitative analysts, and power market researchers who need real-time intelligence on inter-ISO price dislocations — backed by machine learning forecasting, Hidden Markov regime detection, and robust risk management.

---

## Why This Exists

North American electricity is fragmented across 8 Independent System Operators, each with distinct generation mixes, weather exposures, demand profiles, and regulatory frameworks. These structural differences create persistent spread patterns that occasionally deviate from equilibrium:

- **ERCOT** (Texas) — energy-only market, extreme summer heat spikes, high wind penetration
- **PJM** (Mid-Atlantic) — capacity market, gas/coal/nuclear mix, winter-peaking
- **CAISO** (California) — solar-heavy duck curve, steep evening ramps, wildfire risk
- **MISO** (Midwest) — wind-rich, coal-transitioning, spring shoulder weakness
- **NYISO** (New York) — congestion-driven, dual-zone (upstate hydro vs NYC gas)
- **ISO-NE** (New England) — gas-constrained winters, LNG dependency, capacity scarcity
- **SPP** (Southwest) — wind capital of the US, negative price events, low base prices
- **IESO** (Ontario) — hydro/nuclear baseload, low volatility, carbon-priced

When the spread between any two markets overshoots its statistical equilibrium, this platform detects it, forecasts its trajectory, sizes the position, and manages the risk — from signal to execution.

---

## Platform Capabilities

### Data Intelligence

- **Multi-source data pipeline** pulling real-time and historical LMP data from ERCOT public APIs, CAISO OASIS, and EIA Open Data v2, with Open-Meteo weather integration (temperature, wind, solar radiation, humidity)
- **5-minute granularity** support for intraday trading signals — captures price spikes and ramp events that hourly data misses entirely
- **LMP component decomposition** into energy, congestion, and loss components — enabling targeted congestion/FTR analysis on the transmission paths that actually drive spread dislocations
- **Natural gas price integration** for spark spread analysis (gas-to-power heat rate modeling), capturing the fundamental marginal cost driver across gas-fired ISOs
- **Renewable generation forecasts** — solar irradiance and wind speed predictions feed directly into CAISO duck curve and SPP/ERCOT wind depression models
- **Intelligent synthetic fallback** using calibrated Ornstein-Uhlenbeck processes with ISO-specific effects (CAISO duck curve, ERCOT heat spikes, SPP wind depression, Poisson price spikes) when live APIs are unavailable
- **DuckDB-powered SQL analytics** for fast aggregation — daily spreads with on/off-peak breakdowns, hourly load shapes with percentile bands, weather-price joins with lagged features

### Quantitative Analysis Engine

- **Cointegration testing** (Engle-Granger two-step) — confirms whether an ISO pair has a stationary, mean-reverting spread worth trading
- **Ornstein-Uhlenbeck half-life estimation** — measures how fast a spread deviation decays back to equilibrium (shorter = more tradeable)
- **Hurst exponent** via Rescaled Range analysis — H < 0.5 confirms mean-reversion, H > 0.5 flags trending regimes where momentum strategies dominate
- **Augmented Dickey-Fuller stationarity testing** — validates that spreads aren't drifting into non-stationary territory
- **Weather-price correlation analysis** — quantifies the V-shaped temperature demand response (heating below 18C, cooling above 24C), wind/solar merit-order effects, and lagged weather signals up to 48 hours ahead
- **Seasonality decomposition** — hourly load shape curves, monthly seasonal patterns, weekday/weekend discounts, peak/off-peak ratio tracking
- **All 28 ISO pair correlations** rendered as a dynamic heatmap — instantly identify which pairs are converging, diverging, or decorrelating

### ML Forecasting & Regime Intelligence

- **Machine learning spread forecasting** using LSTM and Transformer architectures trained on engineered features (lagged prices, weather, temporal encodings, rolling statistics) to predict next-hour and next-day spread movements
- **Hidden Markov Model regime detection** classifying market conditions into low-volatility, normal, and high-volatility states — with full transition probability matrices showing how likely the market is to shift regimes
- **Dynamic regime-adjusted strategy parameters** — entry/exit z-scores, lookback windows, and position sizes automatically adapt based on the current detected volatility regime, tightening stops in high-vol and widening entries in low-vol
- **Walk-forward model validation** ensuring all forecasting performance is measured strictly out-of-sample — no lookahead bias, no overfitting to history

### Trading Strategy Engine

- **Mean-reversion strategy** (primary) — enters when the rolling z-score exceeds entry thresholds (default +/- 1.5 sigma), exits on reversion toward zero (+/- 0.3 sigma), with hard stops at +/- 3.0 sigma for regime breaks
- **Momentum strategy** (secondary) — fast/slow moving average crossover on the spread captures trending regimes that mean-reversion misses
- **Multi-pair portfolio optimization** — trades multiple ISO spreads simultaneously with Markowitz mean-variance optimization, correlation-aware position sizing, and portfolio-level risk constraints across all 28 possible pairs
- **Event-driven backtesting engine** with realistic P&L simulation — position-level tracking, configurable transaction costs ($0.05/MWh default), and MW-denominated position sizing
- **Walk-forward validation** — 60-day train / 30-day test rolling windows, reporting only out-of-sample metrics (Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor)
- **Parameter optimization** via grid search with walk-forward scoring — prevents overfitting by evaluating every parameter combination on unseen data
- **Sensitivity analysis** — varies individual parameters while holding others constant to map the performance surface and identify fragile vs robust configurations

### Risk Management Framework

- **Value-at-Risk** (historical and parametric) at 95% and 99% confidence — quantifies the daily loss threshold under normal conditions
- **Conditional VaR / Expected Shortfall** — averages the worst-case tail losses beyond VaR, critical for fat-tailed power markets where kurtosis routinely exceeds 3
- **Maximum drawdown tracking** with peak-to-trough measurement, percentage decline, and duration in periods
- **Monte Carlo simulation** — generates 10,000+ scenario paths using bootstrapped returns and regime-conditional volatility to stress-test strategy robustness far beyond the 4 fixed historical scenarios
- **Historical stress testing** with 4 calibrated extreme scenarios:
  - *2021 Texas Freeze* — ERCOT prices at $9,000/MWh for 96 hours, 50x price multiplier
  - *2020 COVID Demand Drop* — 30% demand collapse across all ISOs for 720 hours
  - *Pacific NW Heat Dome* — CAISO 5x, SPP 3x price multipliers for 168 hours
  - *Polar Vortex* — PJM 8x, NYISO 10x, ISO-NE 12x, MISO 6x for 120 hours
- **Position sizing** via Kelly criterion (theoretically optimal), half-Kelly (variance-reduced), and fixed-fractional (risk 2% per trade, size inversely proportional to stop distance)
- **Custom scenario builder** — define arbitrary spread shocks, price multipliers, and durations to model emerging risks

### Real-Time Operations

- **WebSocket streaming** for live price feeds — pushes real-time LMP updates, spread calculations, and z-score signals to connected clients as market data arrives
- **Threshold-based alerting** — configurable notifications via email, Slack, or SMS when z-scores cross entry/exit/stop thresholds, regime changes are detected, or stress limits are breached
- **Persistent trade journal** — logs every entry, exit, and position change with full attribution (strategy, regime state, weather conditions, time-of-day) for post-trade analysis and strategy refinement
- **Live PnL tracking** with real-time equity curves, running drawdown monitoring, and intraday performance attribution

### Visualization & Dashboards

- **React SPA** (Vite + Recharts) — production-ready frontend with dark theme, responsive layout, and 8+ interactive tabs covering market overview, spread analysis, weather correlation, backtesting, risk, portfolio, forecasting, and alerting
- **Streamlit dashboard** — rapid exploration interface with 5 analysis tabs, interactive parameter sliders, Plotly charts, and 1-hour data caching for iterative research
- **Correlation heatmap** — all 28 ISO pair correlations visualized as a dynamic matrix with divergence highlighting
- **Transmission constraint map** — geographic visualization of congested inter-ISO paths overlaid on actual ISO boundary maps, color-coded by congestion severity
- **Regulatory event calendar** — FERC filings, capacity auction dates, planned outage schedules, and compliance deadlines overlaid on price charts for event-driven context
- **Options & implied volatility surface** — realized vs implied volatility comparison for spread options, enabling traders to identify mispriced volatility
- **5 Jupyter notebooks** — step-by-step analysis walkthroughs from data exploration through spread analysis, weather correlation, backtesting, and risk assessment

---

## Architecture

```
                          Real-Time Layer
                    ┌──────────────────────┐
                    │  WebSocket Server     │
                    │  ├─ Live LMP feeds    │
                    │  ├─ Signal streaming  │
                    │  └─ Alert dispatch    │
                    └──────────┬───────────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │                    FastAPI Backend                    │
    │  /api/prices  /api/spread  /api/backtest  /api/risk  │
    │  /api/forecast  /api/portfolio  /api/alerts          │
    │  /api/gas  /api/congestion  /api/montecarlo          │
    └──────────────────────────┬───────────────────────────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │                  Analysis Engine                      │
    │                                                       │
    │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
    │  │ Spread       │  │ ML Forecast  │  │ Regime     │  │
    │  │ Analyzer     │  │ (LSTM/Tfmr)  │  │ Detector   │  │
    │  │ Cointegration│  │ Next-hour    │  │ HMM 3-state│  │
    │  │ Half-life    │  │ Next-day     │  │ Transition  │  │
    │  │ Hurst        │  │ Walk-forward │  │ matrices    │  │
    │  └─────────────┘  └──────────────┘  └────────────┘  │
    │                                                       │
    │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
    │  │ Weather      │  │ Congestion   │  │ Gas/Spark  │  │
    │  │ Correlation  │  │ FTR Analysis │  │ Spread     │  │
    │  │ V-shape temp │  │ Path pricing │  │ Heat rate  │  │
    │  │ Wind/Solar   │  │ Constraint   │  │ Hub prices │  │
    │  │ Lagged 48h   │  │ mapping      │  │ Basis diff │  │
    │  └─────────────┘  └──────────────┘  └────────────┘  │
    └──────────────────────────┬───────────────────────────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │                Strategy & Risk Layer                  │
    │                                                       │
    │  ┌──────────────┐  ┌─────────────┐  ┌────────────┐  │
    │  │ Mean Reversion│  │ Portfolio   │  │ Risk       │  │
    │  │ Momentum      │  │ Optimizer   │  │ VaR / CVaR │  │
    │  │ Regime-       │  │ Markowitz   │  │ Monte Carlo│  │
    │  │ adaptive      │  │ Multi-pair  │  │ Stress Test│  │
    │  │ ML-enhanced   │  │ Correlation │  │ Kelly Size │  │
    │  └──────────────┘  └─────────────┘  └────────────┘  │
    └──────────────────────────┬───────────────────────────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │                   Data Pipeline                       │
    │                                                       │
    │  ISO APIs ──→ ISODataFetcher ──→ DataProcessor       │
    │  Open-Meteo ─→ WeatherFetcher    (feature eng.)      │
    │  Gas hubs ───→ GasFetcher     ──→ DuckDB / Parquet   │
    │  Renewables ─→ RenewableFetcher                      │
    │                                                       │
    │  5-min + hourly + daily granularity                   │
    │  Parquet cache │ MD5 dedup │ UTC alignment            │
    └──────────────────────────────────────────────────────┘
```

---

## Project Structure

```
src/
├── data/                # Data acquisition & processing
│   ├── fetcher.py       #   ISO LMP fetcher (ERCOT, CAISO, EIA APIs + synthetic)
│   ├── weather.py       #   Open-Meteo weather data (temp, wind, solar, humidity)
│   ├── gas.py           #   Natural gas hub prices (Henry Hub, regional basis)
│   ├── renewable.py     #   Solar/wind generation forecasts
│   ├── processor.py     #   Feature engineering pipeline (temporal, weather, lagged)
│   └── db.py            #   DuckDB wrapper for SQL analytics
│
├── analysis/            # Quantitative analysis modules
│   ├── spreads.py       #   Cointegration, OU half-life, Hurst, ADF, z-score
│   ├── correlation.py   #   Weather-price correlation (V-shape, wind, solar, lags)
│   ├── regime.py        #   HMM volatility regime detection (3-state)
│   ├── seasonality.py   #   Hourly, monthly, weekday, peak/off-peak decomposition
│   ├── congestion.py    #   LMP congestion component & FTR analysis
│   └── forecast.py      #   ML spread forecasting (LSTM, Transformer)
│
├── strategy/            # Trading strategies & execution
│   ├── mean_reversion.py#   Z-score mean-reversion with regime-adaptive params
│   ├── momentum.py      #   MA crossover trend-following
│   ├── portfolio.py     #   Multi-pair Markowitz optimization
│   ├── backtest.py      #   Event-driven backtester + walk-forward validation
│   └── optimize.py      #   Grid search parameter optimization
│
├── risk/                # Risk analytics & position management
│   ├── var.py           #   VaR, CVaR, max drawdown, rolling risk
│   ├── stress.py        #   Historical stress scenarios (4 calibrated events)
│   ├── montecarlo.py    #   Monte Carlo simulation (10,000+ paths)
│   ├── position.py      #   Kelly criterion, half-Kelly, fixed-fractional sizing
│   └── journal.py       #   Persistent trade journal with attribution
│
├── realtime/            # Real-time operations
│   ├── streaming.py     #   WebSocket server for live price feeds & signals
│   └── alerts.py        #   Threshold alerting (email, Slack, SMS)
│
├── visualization/       # Dashboards
│   └── dashboard.py     #   Streamlit interactive dashboard (5+ tabs)
│
└── api/                 # REST + WebSocket backend
    └── app.py           #   FastAPI with 10+ endpoints

frontend/                # React SPA (Vite + Recharts)
├── src/
│   ├── App.jsx          #   Main app, 8+ tabs, dark theme
│   ├── components/      #   MarketOverview, SpreadChart, BacktestPanel,
│   │                    #   RiskDashboard, WeatherCorrelation, Portfolio,
│   │                    #   ForecastPanel, CorrelationHeatmap, AlertManager,
│   │                    #   CongestionMap, GasSpread, MonteCarloView,
│   │                    #   EventCalendar, VolSurface
│   └── utils/
│       └── api.js       #   Axios API client (15+ endpoints)

sql/                     # DuckDB schemas & analytics queries
notebooks/               # 5 Jupyter analysis notebooks
tests/                   # Unit tests (25+ across all modules)
config/
└── settings.yaml        # ISO configs, weather locations, strategy params
```

---

## Quick Start

```bash
# Clone and install
git clone <repo-url>
cd power-spread-analyzer
pip install -r requirements.txt

# Run Streamlit dashboard (exploration & research)
streamlit run src/visualization/dashboard.py

# Run FastAPI + React (production interface)
uvicorn src.api.app:app --reload --port 8000
cd frontend && npm install && npm run dev
```

---

## Data Sources

| Source | Data | Access |
|--------|------|--------|
| **EIA Open Data API** | Wholesale electricity prices (all ISOs) | Free API key |
| **ERCOT** | DAM settlement point prices | Public, no key |
| **CAISO OASIS** | Locational marginal prices | Public, no key |
| **Open-Meteo** | Historical + forecast hourly weather | Free, no key |
| **EIA Natural Gas** | Henry Hub + regional hub spot prices | Free API key |
| **Synthetic Fallback** | Calibrated OU process with ISO-specific effects | Built-in |

---

## Statistical & ML Framework

### Spread Stationarity Pipeline
```
Price_A, Price_B
    → Engle-Granger Cointegration Test (p < 0.05?)
    → ADF Stationarity Test on spread residuals
    → OU Half-Life estimation (ln(2) / |θ|)
    → Hurst Exponent via R/S analysis (H < 0.5?)
    → Rolling Z-Score (20-day window)
    → Signal Generation
```

### ML Forecasting Pipeline
```
Features [lagged_prices, weather, temporal, rolling_stats, regime_state]
    → Train/Val/Test split (walk-forward, no lookahead)
    → LSTM / Transformer encoder
    → Predict: next-hour spread, next-day spread
    → Confidence intervals via MC dropout
    → Signal: combine statistical z-score + ML forecast
```

### Regime-Adaptive Strategy
```
Returns → HMM fit (3 Gaussian states)
    → Classify: low_vol / normal / high_vol
    → Transition matrix: P(regime_t+1 | regime_t)
    → Adjust parameters:
        low_vol:  entry_z=2.0, stop_z=3.5, full size
        normal:   entry_z=1.5, stop_z=3.0, full size
        high_vol: entry_z=1.0, stop_z=2.0, half size
```

### Portfolio Optimization
```
28 ISO pairs → Covariance matrix of spread returns
    → Markowitz mean-variance optimization
    → Constraints: max 30% per pair, long/short balanced
    → Efficient frontier: target Sharpe > 1.5
    → Rebalance: weekly or on regime change
```

---

## Risk Controls

| Metric | Method | Purpose |
|--------|--------|---------|
| **VaR 95/99%** | Historical percentile + parametric Gaussian | Daily loss threshold |
| **CVaR / ES** | Tail average beyond VaR | Fat-tail risk (kurtosis > 3) |
| **Max Drawdown** | Peak-to-trough equity decline | Capital preservation |
| **Monte Carlo** | 10,000 bootstrapped paths, regime-conditional | Robustness testing |
| **Stress Scenarios** | 4 calibrated historical events | Extreme loss estimation |
| **Kelly Sizing** | f* = (pb - q) / b, half-Kelly practical | Position sizing |
| **Regime Stops** | HMM state change triggers position review | Adaptive protection |

---

## Built With

**Core**: Python, Pandas, NumPy, SciPy, Statsmodels, Scikit-learn, hmmlearn

**ML**: PyTorch (LSTM, Transformer), walk-forward cross-validation

**Data**: DuckDB, PyArrow/Parquet, Requests, Open-Meteo API, EIA API

**Backend**: FastAPI, Uvicorn, WebSockets

**Frontend**: React 18, Vite, Recharts, Axios

**Visualization**: Streamlit, Plotly

**Testing**: Pytest

---

## License

MIT
