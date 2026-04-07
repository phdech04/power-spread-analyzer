# Methodology

## Why Spread Trading Between ISOs Works

North American electricity markets are operated by Independent System Operators (ISOs), each with distinct characteristics:

- **Different weather exposure**: ERCOT (Houston heat) vs ISO-NE (Boston cold) means demand shocks hit at different times
- **Different generation mix**: CAISO (solar-heavy) vs PJM (gas/coal/nuclear) creates structural price shape differences
- **Transmission constraints**: Physical congestion between regions means prices can diverge significantly
- **Different regulatory frameworks**: ERCOT's energy-only market vs PJM's capacity market affects base price levels
- **Different fuel dependencies**: ISO-NE's winter gas constraints vs SPP's wind surplus create seasonal basis differentials
- **Renewable penetration asymmetry**: CAISO's duck curve and SPP's wind depression create predictable intraday spread patterns

These structural differences create persistent spread patterns that occasionally deviate from equilibrium — creating trading opportunities.

## Statistical Framework

### Cointegration

Two price series are cointegrated if their linear combination is stationary, even though individual series are non-stationary. We use the **Engle-Granger two-step test**:

1. Regress price_A on price_B
2. Test residuals for stationarity (ADF test)
3. If residuals are stationary (p < 0.05), the pair is cointegrated

Cointegrated pairs have a meaningful "equilibrium spread" that the market tends to revert to.

### Ornstein-Uhlenbeck Process

We model spread mean-reversion as an OU process:

```
dS = theta(mu - S)dt + sigma * dW
```

Where:
- `S` = current spread
- `theta` = mean-reversion speed
- `mu` = long-run mean spread
- `sigma` = volatility
- `dW` = Wiener process increment

**Half-life** = ln(2) / theta — the time for a deviation to decay by 50%. Estimated via OLS regression of spread changes on lagged spreads.

### Hurst Exponent

The Hurst exponent (H) via Rescaled Range (R/S) analysis characterizes the series:
- H < 0.5: Mean-reverting (our target)
- H = 0.5: Random walk (no edge)
- H > 0.5: Trending (momentum opportunity)

## Weather as a Price Driver

Power demand is fundamentally weather-driven:

### Temperature Response (V-Shaped)
- **Below 18C**: Heating demand increases — higher prices
- **18-24C**: Comfort zone — low demand, low prices
- **Above 24C**: Cooling demand increases — higher prices

We quantify this with Cooling Degree Days (CDD) and Heating Degree Days (HDD):
- CDD = max(0, T - 18C)
- HDD = max(0, 18C - T)

### Renewable Impact
- **Wind**: Negative price correlation in ERCOT and SPP (high wind penetration)
- **Solar**: Creates the CAISO "duck curve" — midday price depression followed by steep evening ramp
- **Lagged signal**: Weather forecasts lead prices by 24-48 hours, creating forecasting value

## Natural Gas as the Marginal Fuel

In most ISOs, natural gas sets the marginal price 40-70% of hours. The **spark spread** (power price minus gas cost at a given heat rate) is the fundamental profitability signal for gas generators:

```
Spark Spread = Power Price - (Gas Price x Heat Rate)
```

Typical heat rates: 7-10 MMBtu/MWh depending on unit efficiency.

We integrate Henry Hub spot and regional gas hub prices to:
- Decompose power price movements into gas-driven vs non-gas components
- Identify when spark spreads compress (indicating generator margin stress)
- Forecast power price moves from gas price leading indicators

## Congestion & FTR Analysis

Locational Marginal Prices decompose into three components:

```
LMP = Energy Component + Congestion Component + Loss Component
```

The **congestion component** reflects transmission constraints and is where significant inter-ISO spread alpha resides. We analyze:
- Congestion component trends and seasonality per node
- Financial Transmission Rights (FTR) fair value estimation
- Constraint activation frequency and price impact
- Geographic mapping of persistently congested paths

## ML Forecasting

### Feature Engineering

The ML pipeline builds on the statistical features:
- **Lagged prices**: 1h, 24h, 168h (1 week) lags for both ISOs
- **Rolling statistics**: 24h mean, std, skewness of spreads
- **Weather features**: Temperature deviation from 30-day mean, CDD/HDD, wind speed, solar radiation
- **Temporal encodings**: Hour-of-day (cyclical), day-of-week, month, is_peak, is_weekend
- **Regime state**: Current HMM-detected volatility regime (one-hot encoded)
- **Gas prices**: Current and lagged natural gas hub prices

### Model Architecture

**LSTM (Long Short-Term Memory)**:
- Captures sequential dependencies in spread time series
- 2-layer LSTM with 64 hidden units, dropout 0.2
- Lookback window: 168 hours (1 week)
- Predicts: next-hour and next-day spread level

**Transformer Encoder**:
- Self-attention mechanism identifies relevant historical patterns regardless of distance
- 4-head attention, 2 encoder layers, positional encoding
- Better at capturing regime-change dynamics than LSTM

### Validation Protocol

All ML models use strict walk-forward validation:
1. Expanding or rolling training window (minimum 90 days)
2. Validation window: 30 days (hyperparameter tuning)
3. Test window: 30 days (performance reporting)
4. No information leakage — features computed only from past data
5. Performance measured on aggregate out-of-sample predictions

## Trading Strategies

### Mean Reversion (Primary)

1. Compute rolling Z-score of spread: `z = (S - mu_rolling) / sigma_rolling`
2. **Enter**: Long when z < -1.5, Short when z > +1.5
3. **Exit**: When z crosses back through +/- 0.3
4. **Stop loss**: When |z| > 3.0 (potential regime break)

### Momentum (Secondary)

Moving average crossover on spread (fast 5-day vs slow 20-day) captures regime shifts that mean-reversion misses.

### Regime-Adaptive Parameters

The static z-score thresholds above are defaults. In production, the HMM regime detector dynamically adjusts:

| Regime | Entry Z | Exit Z | Stop Z | Position Size |
|--------|---------|--------|--------|---------------|
| Low Volatility | 2.0 | 0.5 | 3.5 | 100% |
| Normal | 1.5 | 0.3 | 3.0 | 100% |
| High Volatility | 1.0 | 0.2 | 2.0 | 50% |

**Rationale**: In low-vol regimes, spreads rarely hit entry thresholds, so we widen them but can afford larger positions. In high-vol regimes, spreads move fast — we enter earlier but size smaller to limit tail risk.

### ML-Enhanced Signals

When ML forecasting is active, signals combine statistical and predictive components:

```
Combined Signal = w1 * z_score_signal + w2 * ml_forecast_signal
```

Weights are determined by recent out-of-sample forecast accuracy, with ML weight increasing when forecast Sharpe > statistical Sharpe.

### Multi-Pair Portfolio

Rather than trading one pair in isolation, the portfolio optimizer:
1. Computes the covariance matrix of all 28 pair spread returns
2. Runs Markowitz mean-variance optimization with constraints (max 30% per pair)
3. Produces optimal weights targeting maximum Sharpe ratio on the efficient frontier
4. Rebalances weekly or when a regime change is detected
5. Enforces portfolio-level VaR limits across all positions simultaneously

### Walk-Forward Validation

To avoid overfitting:
1. Train on 60-day rolling window
2. Test on next 30 days (out-of-sample)
3. Roll forward and repeat
4. Report only out-of-sample metrics

This is critical — in-sample Sharpe ratios are meaningless for production trading.

## Risk Management

### Value-at-Risk (VaR)

- **Historical VaR**: Sort returns, take the (1-alpha) percentile
- **Parametric VaR**: Assume Gaussian, compute from mean/std
- **CVaR (Expected Shortfall)**: Average of losses beyond VaR — captures tail risk better

Power markets have fat tails (kurtosis > 3), so CVaR is more informative than VaR.

### Monte Carlo Simulation

Beyond the 4 fixed stress scenarios, we run 10,000+ Monte Carlo simulations:

1. Bootstrap daily returns from historical data (preserving autocorrelation via block bootstrap)
2. Apply regime-conditional volatility scaling (high-vol periods produce fatter tails)
3. Simulate portfolio equity paths over 1-year horizon
4. Compute distribution of terminal wealth, max drawdown, and worst-case scenarios
5. Report: P5/P25/P50/P75/P95 of terminal equity, probability of >20% drawdown, expected recovery time

This provides a much richer picture of strategy robustness than point estimates.

### Stress Testing

We model four historical/hypothetical scenarios:
1. **2021 Texas Freeze**: ERCOT prices hit $9,000/MWh for 4 days
2. **COVID Demand Drop**: 30% demand decline across all ISOs
3. **Heat Dome**: Pacific NW extreme temps affecting CAISO/SPP
4. **Polar Vortex**: Extreme cold in eastern ISOs (2014-style)

Plus custom scenarios defined by the user with arbitrary spread shocks, price multipliers, and durations.

### Position Sizing

- **Kelly Criterion**: f* = (p*b - q) / b — theoretically optimal but aggressive
- **Half-Kelly**: More practical, reduces variance of outcomes
- **Fixed Fractional**: Risk 2% of capital per trade, size inversely proportional to stop distance

## Real-Time Operations

### WebSocket Streaming

Live market data flows through a WebSocket server that:
- Receives price updates from ISO APIs (polling at maximum available frequency)
- Computes real-time spread, z-score, and ML forecast for subscribed pairs
- Pushes updates to all connected frontend clients
- Maintains a rolling buffer for on-the-fly indicator computation

### Alerting System

Configurable threshold alerts trigger on:
- Z-score crossing entry/exit/stop levels
- Regime change detected by HMM
- VaR limit breach at portfolio level
- Stress scenario threshold exceeded
- ML forecast divergence from statistical signal

Delivery channels: email, Slack webhook, SMS (via configurable providers).

### Trade Journal

Every trade is logged with full context:
- Entry/exit timestamps and prices
- Strategy that generated the signal (mean-reversion, momentum, ML)
- Regime state at entry and exit
- Weather conditions at entry
- Realized P&L and contribution to portfolio
- Attribution: how much of the P&L came from spread reversion vs regime shift vs weather event
