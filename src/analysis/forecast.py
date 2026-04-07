"""
ML-based spread forecasting using LSTM and Transformer architectures.
Predicts next-hour and next-day spread movements with walk-forward validation.
"""

import logging
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available — ML forecasting will use sklearn fallback")

try:
    from sklearn.ensemble import GradientBoostingRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# ── PyTorch Models ────────────────────────────────────────────────────

if TORCH_AVAILABLE:
    class LSTMForecaster(nn.Module):
        """2-layer LSTM for spread time series prediction."""

        def __init__(self, input_size: int, hidden_size: int = 64,
                     num_layers: int = 2, dropout: float = 0.2):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size, hidden_size, num_layers,
                batch_first=True, dropout=dropout
            )
            self.fc = nn.Sequential(
                nn.Linear(hidden_size, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, 1),
            )

        def forward(self, x):
            lstm_out, _ = self.lstm(x)
            return self.fc(lstm_out[:, -1, :])

    class TransformerForecaster(nn.Module):
        """Transformer encoder for spread prediction with positional encoding."""

        def __init__(self, input_size: int, d_model: int = 64,
                     nhead: int = 4, num_layers: int = 2, dropout: float = 0.2):
            super().__init__()
            self.input_proj = nn.Linear(input_size, d_model)
            self.pos_encoding = nn.Parameter(torch.randn(1, 500, d_model) * 0.1)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model, nhead=nhead,
                dim_feedforward=d_model * 4, dropout=dropout,
                batch_first=True
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers)
            self.fc = nn.Sequential(
                nn.Linear(d_model, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, 1),
            )

        def forward(self, x):
            seq_len = x.size(1)
            x = self.input_proj(x) + self.pos_encoding[:, :seq_len, :]
            x = self.encoder(x)
            return self.fc(x[:, -1, :])


# ── Feature Engineering ───────────────────────────────────────────────

class SpreadFeatureBuilder:
    """Build ML features from spread and price data."""

    def __init__(self, lookback: int = 168):
        self.lookback = lookback
        self.scaler = StandardScaler()

    def build_features(self, spread_df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer features from spread data.
        Input: DataFrame with columns [trade_date, price_a, price_b, spread]
        """
        df = spread_df.copy()

        # Lagged spreads
        for lag in [1, 2, 3, 5, 7, 14, 21]:
            df[f"spread_lag_{lag}"] = df["spread"].shift(lag)

        # Rolling statistics
        for window in [5, 10, 20, 60]:
            df[f"spread_ma_{window}"] = df["spread"].rolling(window).mean()
            df[f"spread_std_{window}"] = df["spread"].rolling(window).std()

        # Z-score
        ma20 = df["spread"].rolling(20).mean()
        std20 = df["spread"].rolling(20).std()
        df["zscore"] = (df["spread"] - ma20) / std20.replace(0, np.nan)

        # Momentum
        df["spread_change_1d"] = df["spread"].diff(1)
        df["spread_change_5d"] = df["spread"].diff(5)
        df["spread_return_1d"] = df["spread"].pct_change(1)

        # Volatility
        df["realized_vol_5d"] = df["spread"].rolling(5).std()
        df["realized_vol_20d"] = df["spread"].rolling(20).std()
        df["vol_ratio"] = df["realized_vol_5d"] / df["realized_vol_20d"].replace(0, np.nan)

        # Price features
        df["price_a_ma5"] = df["price_a"].rolling(5).mean()
        df["price_b_ma5"] = df["price_b"].rolling(5).mean()
        df["price_a_change"] = df["price_a"].diff(1)
        df["price_b_change"] = df["price_b"].diff(1)

        # Temporal (cyclical encoding)
        if "trade_date" in df.columns:
            dates = pd.to_datetime(df["trade_date"])
            df["day_of_week_sin"] = np.sin(2 * np.pi * dates.dt.dayofweek / 7)
            df["day_of_week_cos"] = np.cos(2 * np.pi * dates.dt.dayofweek / 7)
            df["month_sin"] = np.sin(2 * np.pi * dates.dt.month / 12)
            df["month_cos"] = np.cos(2 * np.pi * dates.dt.month / 12)

        return df

    def prepare_sequences(
        self, df: pd.DataFrame, target_col: str = "spread",
        horizon: int = 1, feature_cols: list = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Create supervised learning sequences for time series."""
        if feature_cols is None:
            feature_cols = [c for c in df.columns if c not in
                          ["trade_date", "spread", "price_a", "price_b"]]

        # Target: future spread change
        df = df.copy()
        df["target"] = df[target_col].shift(-horizon) - df[target_col]

        # Drop NaN
        df = df.dropna(subset=feature_cols + ["target"])

        X = df[feature_cols].values
        y = df["target"].values

        return X, y


# ── Forecast Engine ───────────────────────────────────────────────────

class SpreadForecaster:
    """
    Main forecasting engine with walk-forward validation.
    Uses PyTorch LSTM/Transformer when available, falls back to GBM.
    """

    def __init__(self, model_type: str = "lstm", lookback: int = 30):
        self.model_type = model_type
        self.lookback = lookback
        self.feature_builder = SpreadFeatureBuilder(lookback)
        self.model = None
        self.scaler = StandardScaler()

    def _create_sequences(self, X: np.ndarray, y: np.ndarray,
                          seq_len: int) -> Tuple[np.ndarray, np.ndarray]:
        """Create sliding window sequences for LSTM/Transformer."""
        Xs, ys = [], []
        for i in range(seq_len, len(X)):
            Xs.append(X[i - seq_len:i])
            ys.append(y[i])
        return np.array(Xs), np.array(ys)

    def train_and_predict(
        self,
        spread_df: pd.DataFrame,
        train_ratio: float = 0.7,
        horizon: int = 1,
        epochs: int = 50,
    ) -> dict:
        """
        Train model and generate predictions with walk-forward validation.
        Returns predictions, metrics, and feature importances.
        """
        # Build features
        featured = self.feature_builder.build_features(spread_df)
        feature_cols = [c for c in featured.columns if c not in
                       ["trade_date", "spread", "price_a", "price_b"]]

        X, y = self.feature_builder.prepare_sequences(
            featured, horizon=horizon, feature_cols=feature_cols
        )

        if len(X) < 60:
            return {"error": "Insufficient data for forecasting (need 60+ days)"}

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        split = int(len(X_scaled) * train_ratio)
        X_train, X_test = X_scaled[:split], X_scaled[split:]
        y_train, y_test = y[:split], y[split:]

        if TORCH_AVAILABLE and self.model_type in ("lstm", "transformer"):
            predictions = self._train_pytorch(
                X_train, y_train, X_test, y_test,
                epochs=epochs, feature_cols=feature_cols
            )
        else:
            predictions = self._train_sklearn(X_train, y_train, X_test, feature_cols)

        # Metrics
        rmse = float(np.sqrt(mean_squared_error(y_test[:len(predictions)], predictions)))
        mae = float(mean_absolute_error(y_test[:len(predictions)], predictions))

        # Direction accuracy
        actual_dir = np.sign(y_test[:len(predictions)])
        pred_dir = np.sign(predictions)
        direction_accuracy = float(np.mean(actual_dir == pred_dir))

        # Build result with dates
        test_dates = featured["trade_date"].iloc[-len(y_test):].values
        actual_spreads = featured["spread"].iloc[-len(y_test):].values

        forecast_data = []
        for i in range(min(len(predictions), len(test_dates))):
            date = test_dates[i]
            forecast_data.append({
                "date": str(date)[:10] if hasattr(date, '__str__') else str(date),
                "actual_spread": round(float(actual_spreads[i]), 2),
                "predicted_change": round(float(predictions[i]), 3),
                "actual_change": round(float(y_test[i]), 3),
                "forecast_spread": round(float(actual_spreads[i] + predictions[i]), 2),
            })

        return {
            "model_type": self.model_type if TORCH_AVAILABLE else "gradient_boosting",
            "horizon": horizon,
            "metrics": {
                "rmse": rmse,
                "mae": mae,
                "direction_accuracy": direction_accuracy,
                "n_train": split,
                "n_test": len(predictions),
            },
            "forecasts": forecast_data,
            "feature_names": feature_cols,
        }

    def _train_pytorch(self, X_train, y_train, X_test, y_test,
                       epochs: int, feature_cols: list) -> np.ndarray:
        """Train LSTM or Transformer model."""
        seq_len = min(self.lookback, len(X_train) // 3)
        X_train_seq, y_train_seq = self._create_sequences(X_train, y_train, seq_len)
        X_test_seq, y_test_seq = self._create_sequences(X_test, y_test, seq_len)

        if len(X_train_seq) == 0 or len(X_test_seq) == 0:
            return self._train_sklearn(
                X_train, y_train, X_test, feature_cols
            )

        X_t = torch.FloatTensor(X_train_seq)
        y_t = torch.FloatTensor(y_train_seq).unsqueeze(1)
        X_v = torch.FloatTensor(X_test_seq)

        input_size = X_train_seq.shape[2]

        if self.model_type == "transformer":
            model = TransformerForecaster(input_size)
        else:
            model = LSTMForecaster(input_size)

        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        criterion = nn.MSELoss()

        # Training loop
        model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            output = model(X_t)
            loss = criterion(output, y_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        # Predict
        model.eval()
        with torch.no_grad():
            predictions = model(X_v).numpy().flatten()

        self.model = model
        return predictions

    def _train_sklearn(self, X_train, y_train, X_test,
                       feature_cols: list) -> np.ndarray:
        """Fallback: Gradient Boosting Regressor."""
        model = GradientBoostingRegressor(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, random_state=42
        )
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)
        self.model = model
        self.feature_importances = dict(zip(feature_cols, model.feature_importances_))
        return predictions

    def walk_forward_forecast(
        self, spread_df: pd.DataFrame, train_window: int = 180,
        test_window: int = 30, horizon: int = 1
    ) -> dict:
        """Walk-forward out-of-sample forecasting."""
        featured = self.feature_builder.build_features(spread_df)
        feature_cols = [c for c in featured.columns if c not in
                       ["trade_date", "spread", "price_a", "price_b"]]

        X, y = self.feature_builder.prepare_sequences(
            featured, horizon=horizon, feature_cols=feature_cols
        )
        X_scaled = self.scaler.fit_transform(X)

        all_preds = []
        all_actuals = []
        fold_results = []
        start = 0

        while start + train_window + test_window <= len(X_scaled):
            train_end = start + train_window
            test_end = min(train_end + test_window, len(X_scaled))

            X_tr = X_scaled[start:train_end]
            y_tr = y[start:train_end]
            X_te = X_scaled[train_end:test_end]
            y_te = y[train_end:test_end]

            model = GradientBoostingRegressor(
                n_estimators=150, max_depth=4, learning_rate=0.05,
                subsample=0.8, random_state=42
            )
            model.fit(X_tr, y_tr)
            preds = model.predict(X_te)

            rmse = float(np.sqrt(mean_squared_error(y_te, preds)))
            dir_acc = float(np.mean(np.sign(y_te) == np.sign(preds)))

            fold_results.append({
                "fold": len(fold_results),
                "train_start": start,
                "test_start": train_end,
                "rmse": rmse,
                "direction_accuracy": dir_acc,
            })

            all_preds.extend(preds.tolist())
            all_actuals.extend(y_te.tolist())
            start += test_window

        if not all_preds:
            return {"error": "Insufficient data for walk-forward"}

        overall_rmse = float(np.sqrt(mean_squared_error(all_actuals, all_preds)))
        overall_dir_acc = float(np.mean(
            np.sign(np.array(all_actuals)) == np.sign(np.array(all_preds))
        ))

        return {
            "overall_metrics": {
                "rmse": overall_rmse,
                "direction_accuracy": overall_dir_acc,
                "n_folds": len(fold_results),
                "total_predictions": len(all_preds),
            },
            "fold_results": fold_results,
        }
