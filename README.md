# Cross-ISO Power Spread Analyzer

Quantitative analysis tool for identifying and backtesting spread trading opportunities across North American electricity markets (CAISO, PJM, ERCOT, MISO, NYISO, ISO-NE, SPP, IESO).

## Features

- **Data Pipeline**: Real-time data from public ISO APIs (ERCOT, CAISO, EIA) + Open-Meteo weather, with synthetic fallback
- **SQL Analytics**: DuckDB-powered queries for daily spreads, hourly shapes, and weather-price joins
- **Spread Analysis**: Cointegration testing, Ornstein-Uhlenbeck half-life, Hurst exponent, rolling z-scores
- **Weather Correlation**: V-shaped temperature response, wind/solar impact, lagged weather signals
- **Regime Detection**: HMM-based volatility regime classification (low-vol, normal, spike)
- **Strategy Engine**: Mean-reversion (z-score) and momentum (MA crossover) strategies
- **Backtesting**: Event-driven backtest with walk-forward validation, parameter optimization
- **Risk Management**: Historical/parametric VaR, CVaR, stress testing (Texas freeze, COVID, heat dome), Kelly criterion position sizing
- **Dashboards**: Streamlit interactive dashboard + React frontend with FastAPI backend

## Quick Start

```bash
# Clone and install
git clone <repo-url>
cd power-spread-analyzer
pip install -r requirements.txt

# Run Streamlit dashboard
streamlit run src/visualization/dashboard.py

# Or run FastAPI + React
uvicorn src.api.app:app --reload --port 8000
cd frontend && npm install && npm run dev
```

## Project Structure

```
src/
├── data/          # Fetchers (ISO APIs, weather), processor, DuckDB integration
├── analysis/      # Spreads, correlation, regime detection, seasonality
├── strategy/      # Mean reversion, momentum, backtest engine, optimizer
├── risk/          # VaR/CVaR, stress testing, position sizing
├── visualization/ # Streamlit dashboard
└── api/           # FastAPI backend
sql/               # DuckDB schema and analysis queries
notebooks/         # 5 analysis notebooks (exploration → risk)
frontend/          # React dashboard (Vite + Recharts)
tests/             # Unit tests
```

## Data Sources

- **EIA Open Data API** — wholesale electricity prices (free API key)
- **ERCOT** — public DAM settlement point prices
- **CAISO OASIS** — public LMP data
- **Open-Meteo** — historical hourly weather (free, no key)
- **Synthetic fallback** — OU process with realistic diurnal/seasonal patterns

## Built With

Python, Pandas, NumPy, DuckDB, Scikit-learn, hmmlearn, Statsmodels, Plotly, Streamlit, FastAPI, React, Recharts
