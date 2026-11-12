"""Ingestion: UCI Online Retail II -> warehouse table RETAIL_TRANSACTIONS.

Source resolution, in order:
1. DATA_PATH env var (xlsx or csv).
2. data/online_retail_II.xlsx in the project (downloaded on first run).
3. data/online_retail.csv in the project.
4. Download the xlsx from UCI and save it to data/.

The xlsx has two sheets (Year 2009-2010, Year 2010-2011); both are loaded
and concatenated: 1,067,371 rows, Dec 2009 - Dec 2011. The parsed CSV is
cached in data/ so repeat runs are fast. No data files are committed to
the repo (see .gitignore); the app downloads or regenerates them on
first run.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

UCI_URL = ("https://archive.ics.uci.edu/ml/machine-learning-databases/"
           "00502/online_retail_II.xlsx")

SOURCE_COLUMNS = ["Invoice", "StockCode", "Description", "Quantity",
                  "InvoiceDate", "Price", "Customer ID", "Country"]
TARGET_COLUMNS = ["INVOICE", "STOCKCODE", "DESCRIPTION", "QUANTITY",
                  "INVOICEDATE", "PRICE", "CUSTOMERID", "COUNTRY"]


def resolve_source(cfg) -> tuple[str, str]:
    """Return (path, kind) for the dataset; downloads the xlsx if needed."""
    data_dir = os.path.join(cfg.project_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    if cfg.data_path:
        path = cfg.data_path
        kind = "xlsx" if path.lower().endswith((".xlsx", ".xls")) else "csv"
        return path, kind
    xlsx = os.path.join(data_dir, "online_retail_II.xlsx")
    csv = os.path.join(data_dir, "online_retail.csv")
    cached = os.path.join(data_dir, "online_retail_ii.csv")
    if os.path.exists(cached):
        return cached, "csv"
    if os.path.exists(xlsx):
        return xlsx, "xlsx"
    if os.path.exists(csv):
        return csv, "csv"
    print(f"Downloading UCI Online Retail II from {UCI_URL} ...")
    import requests

    resp = requests.get(UCI_URL, timeout=300)
    resp.raise_for_status()
    with open(xlsx, "wb") as fh:
        fh.write(resp.content)
    print(f"Saved {xlsx} ({len(resp.content):,} bytes)")
    return xlsx, "xlsx"


def load_source(path: str, kind: str) -> pd.DataFrame:
    if kind == "xlsx":
        xls = pd.ExcelFile(path)
        frames = []
        for sheet in xls.sheet_names:
            part = pd.read_excel(xls, sheet_name=sheet)
            frames.append(part)
            print(f"  sheet {sheet!r}: {len(part):,} rows")
        df = pd.concat(frames, ignore_index=True)
    else:
        df = pd.read_csv(path)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize to the TARGET_COLUMNS schema. Idempotent: accepts both
    the raw UCI column names and an already-cleaned frame (the cached CSV
    is written post-clean, so re-reads must not re-rename)."""
    if set(TARGET_COLUMNS).issubset(set(df.columns)):
        df = df[TARGET_COLUMNS].copy()
    else:
        rename = dict(zip(SOURCE_COLUMNS, TARGET_COLUMNS))
        keep = [c for c in SOURCE_COLUMNS if c in df.columns]
        df = df[keep].rename(columns=rename).copy()
        for col in TARGET_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[TARGET_COLUMNS]
    df["INVOICEDATE"] = pd.to_datetime(
        df["INVOICEDATE"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    df["QUANTITY"] = pd.to_numeric(df["QUANTITY"], errors="coerce")
    df["PRICE"] = pd.to_numeric(df["PRICE"], errors="coerce")
    df["CUSTOMERID"] = pd.to_numeric(df["CUSTOMERID"], errors="coerce")
    df["INVOICE"] = df["INVOICE"].astype(str)
    df["STOCKCODE"] = df["STOCKCODE"].astype(str)
    return df


def ingest(cfg, warehouse=None) -> dict:
    """Load the dataset into the warehouse. Returns a stats dict."""
    from .warehouse import TABLE_NAME, build_warehouse

    wh = warehouse or build_warehouse(cfg)
    wh.create_tables()
    path, kind = resolve_source(cfg)
    print(f"Loading source: {path} ({kind})")
    raw = load_source(path, kind)
    df = clean(raw)
    # Cache the parsed CSV for fast repeat runs.
    cached = os.path.join(cfg.project_root, "data", "online_retail_ii.csv")
    if kind == "xlsx" and not os.path.exists(cached):
        df.to_csv(cached, index=False)
        print(f"Cached parsed CSV at {cached}")
    wh.drop_table(TABLE_NAME)
    wh.create_tables()
    n = wh.load_dataframe(df, TABLE_NAME)
    stats = {
        "rows": n,
        "date_min": str(df["INVOICEDATE"].min()),
        "date_max": str(df["INVOICEDATE"].max()),
        "countries": int(df["COUNTRY"].nunique()),
        "customers": int(df["CUSTOMERID"].nunique()),
        "products": int(df["STOCKCODE"].nunique()),
        "mode": cfg.resolve_mode(),
    }
    print(f"Ingested {n:,} rows into {TABLE_NAME} "
          f"({stats['date_min']} -> {stats['date_max']}, "
          f"{stats['countries']} countries, "
          f"{stats['customers']:,} customers, "
          f"{stats['products']:,} products)")
    return stats


def main() -> None:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from .config import AppConfig
    from .warehouse import build_warehouse

    cfg = AppConfig.from_env()
    wh = build_warehouse(cfg)
    try:
        ingest(cfg, wh)
    finally:
        wh.close()


if __name__ == "__main__":
    main()
