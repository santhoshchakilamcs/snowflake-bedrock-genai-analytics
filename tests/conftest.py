"""Shared fixtures for the test suite (demo mode, tiny local data)."""
from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.warehouse import SQLiteWarehouse  # noqa: E402

TINY_ROWS = [
    ("1001", "A001", "RED WIDGET", 10, "2010-06-01 10:00:00", 2.50, 1.0,
     "United Kingdom"),
    ("1001", "A002", "BLUE WIDGET", 5, "2010-06-01 10:00:00", 3.00, 1.0,
     "United Kingdom"),
    ("1002", "A001", "RED WIDGET", 4, "2010-06-02 11:00:00", 2.50, 2.0,
     "Germany"),
    ("1003", "A003", "GREEN GADGET", 2, "2011-01-15 09:00:00", 10.00, 1.0,
     "United Kingdom"),
    ("1004", "A002", "BLUE WIDGET", -1, "2011-02-01 12:00:00", 3.00, 3.0,
     "France"),
    ("1005", "A001", "RED WIDGET", 7, "2011-12-20 15:00:00", 2.50, 2.0,
     "Germany"),
]

TINY_COLUMNS = ["INVOICE", "STOCKCODE", "DESCRIPTION", "QUANTITY",
                "INVOICEDATE", "PRICE", "CUSTOMERID", "COUNTRY"]

COUNTRIES = ["United Kingdom", "Germany", "France", "Netherlands",
             "Australia", "Spain", "Italy", "Belgium", "Switzerland",
             "Portugal", "USA", "Canada", "Japan"]


@pytest.fixture
def tiny_warehouse(tmp_path):
    wh = SQLiteWarehouse(str(tmp_path / "test.db"))
    wh.create_tables()
    df = pd.DataFrame(TINY_ROWS, columns=TINY_COLUMNS)
    wh.load_dataframe(df, "RETAIL_TRANSACTIONS")
    yield wh
    wh.close()


@pytest.fixture
def tiny_df():
    return pd.DataFrame(TINY_ROWS, columns=TINY_COLUMNS)
