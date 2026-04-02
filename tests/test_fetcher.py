import pytest
import pandas as pd
from src.data.fetcher import ISODataFetcher


class TestISODataFetcher:
    @pytest.fixture
    def fetcher(self):
        return ISODataFetcher()

    def test_synthetic_returns_dataframe(self, fetcher):
        df = fetcher.generate_synthetic("ERCOT", days=30)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 30 * 24

    def test_synthetic_has_required_columns(self, fetcher):
        df = fetcher.generate_synthetic("PJM", days=10)
        required = ["timestamp", "iso", "node", "lmp",
                     "energy_component", "congestion_component", "loss_component"]
        for col in required:
            assert col in df.columns

    def test_synthetic_prices_reasonable(self, fetcher):
        df = fetcher.generate_synthetic("CAISO", days=60)
        assert df["lmp"].mean() > 0
        assert df["lmp"].mean() < 200
        assert df["lmp"].min() >= -10

    def test_synthetic_different_per_iso(self, fetcher):
        ercot = fetcher.generate_synthetic("ERCOT", days=30)
        pjm = fetcher.generate_synthetic("PJM", days=30)
        assert not ercot["lmp"].equals(pjm["lmp"])

    def test_all_isos_generate(self, fetcher):
        for iso in fetcher.config["isos"]:
            df = fetcher.generate_synthetic(iso, days=7)
            assert len(df) > 0
            assert df["iso"].iloc[0] == iso
