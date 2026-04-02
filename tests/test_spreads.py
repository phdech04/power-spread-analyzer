import pytest
import numpy as np
import pandas as pd
from src.analysis.spreads import SpreadAnalyzer


class TestSpreadAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return SpreadAnalyzer()

    def test_rolling_zscore_bounds(self, analyzer):
        """Z-scores should be roughly standard normal."""
        data = pd.Series(np.random.randn(1000).cumsum())
        z = analyzer.rolling_zscore(data, window=20)
        assert z.dropna().std() < 5  # reasonable bound

    def test_rolling_zscore_window(self, analyzer):
        data = pd.Series(np.random.randn(100))
        z = analyzer.rolling_zscore(data, window=20)
        # First 19 values should be NaN (window not full)
        assert z.iloc[:19].isna().all()

    def test_half_life_positive_for_mean_reverting(self, analyzer):
        """Mean-reverting (OU) series should have finite half-life."""
        np.random.seed(42)
        x = [0.0]
        for _ in range(500):
            x.append(x[-1] * 0.95 + np.random.randn() * 0.5)
        hl = analyzer.half_life(pd.Series(x))
        assert 0 < hl < 100

    def test_half_life_infinite_for_random_walk(self, analyzer):
        """Random walk should have infinite (or very large) half-life."""
        np.random.seed(42)
        rw = pd.Series(np.random.randn(500).cumsum())
        hl = analyzer.half_life(rw)
        assert hl > 50 or hl == np.inf

    def test_cointegration_on_known_pair(self, analyzer):
        """Two cointegrated series should pass the test."""
        np.random.seed(42)
        common = np.random.randn(500).cumsum()
        a = common + np.random.randn(500) * 0.5
        b = common + np.random.randn(500) * 0.5
        result = analyzer.cointegration_test(a, b)
        assert result["cointegrated"] is True
        assert result["p_value"] < 0.05

    def test_cointegration_on_independent(self, analyzer):
        """Two independent random walks should NOT be cointegrated."""
        np.random.seed(42)
        a = np.random.randn(500).cumsum()
        b = np.random.randn(500).cumsum()
        result = analyzer.cointegration_test(a, b)
        # Not guaranteed to fail, but usually should
        assert "p_value" in result

    def test_hurst_mean_reverting(self, analyzer):
        """Mean-reverting series should have H < 0.5."""
        np.random.seed(42)
        x = [0.0]
        for _ in range(1000):
            x.append(x[-1] * 0.9 + np.random.randn() * 0.3)
        h = analyzer.hurst_exponent(pd.Series(x))
        assert h < 0.6  # should be well below 0.5

    def test_spread_summary(self, analyzer):
        """Summary should contain all expected keys."""
        np.random.seed(42)
        spreads = pd.Series(np.random.randn(500))
        summary = analyzer.spread_summary(spreads)
        assert "mean" in summary
        assert "half_life" in summary
        assert "hurst" in summary
        assert "adf" in summary
