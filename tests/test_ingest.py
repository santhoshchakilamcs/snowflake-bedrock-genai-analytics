"""Tests for ingest helpers (no network, no real warehouse)."""
import pandas as pd

from src.config import AppConfig
from src.ingest import clean, resolve_source


def test_clean_normalizes_columns_and_dates():
    raw = pd.DataFrame([{
        "Invoice": 536365, "StockCode": "85123A",
        "Description": "WHITE HANGING HEART T-LIGHT HOLDER",
        "Quantity": 6, "InvoiceDate": "2010-12-01 08:26:00",
        "Price": 2.55, "Customer ID": 17850.0, "Country": "United Kingdom",
    }])
    df = clean(raw)
    assert list(df.columns) == ["INVOICE", "STOCKCODE", "DESCRIPTION",
                                "QUANTITY", "INVOICEDATE", "PRICE",
                                "CUSTOMERID", "COUNTRY"]
    assert df.iloc[0]["INVOICEDATE"] == "2010-12-01 08:26:00"
    assert df.iloc[0]["QUANTITY"] == 6
    assert df.iloc[0]["CUSTOMERID"] == 17850.0


def test_clean_is_idempotent():
    """clean() must accept its own output (the cached CSV round-trip)."""
    raw = pd.DataFrame([{
        "Invoice": 536365, "StockCode": "85123A",
        "Description": "WHITE HANGING HEART T-LIGHT HOLDER",
        "Quantity": 6, "InvoiceDate": "2010-12-01 08:26:00",
        "Price": 2.55, "Customer ID": 17850.0, "Country": "United Kingdom",
    }])
    once = clean(raw)
    twice = clean(once)
    assert list(twice.columns) == list(once.columns)
    assert twice.iloc[0]["INVOICEDATE"] == "2010-12-01 08:26:00"
    assert twice.iloc[0]["COUNTRY"] == "United Kingdom"
    assert twice.iloc[0]["QUANTITY"] == 6


def test_resolve_source_prefers_data_path(tmp_path):
    csv = tmp_path / "sample.csv"
    csv.write_text("Invoice,StockCode\n1,A\n")
    cfg = AppConfig.from_env()
    cfg.data_path = str(csv)
    path, kind = resolve_source(cfg)
    assert path == str(csv)
    assert kind == "csv"
