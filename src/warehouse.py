"""Warehouse abstraction: one SQL surface over two backends.

- Demo mode: local SQLite file (stdlib sqlite3 via pandas for bulk loads).
- Live mode: real Snowflake via snowflake-connector-python.

Deliberate portability choice: InvoiceDate is stored as TEXT/VARCHAR in the
'YYYY-MM-DD HH:MM:SS' format in BOTH backends, and all generated SQL uses
only functions that exist in both dialects (SUBSTR, SUM, COUNT, AVG,
GROUP BY, ORDER BY, LIMIT). That keeps one SQL generation path, tested in
demo mode, and the same SQL runs unchanged against Snowflake in live mode.
"""
from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from typing import Any, Optional

import pandas as pd

TABLE_NAME = "RETAIL_TRANSACTIONS"
LOG_TABLE_NAME = "QUERY_LOG"

# Column order is the contract for ingest and for generated SQL.
COLUMNS = ["INVOICE", "STOCKCODE", "DESCRIPTION", "QUANTITY",
           "INVOICEDATE", "PRICE", "CUSTOMERID", "COUNTRY"]

SQLITE_RETAIL_DDL = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    INVOICE TEXT,
    STOCKCODE TEXT,
    DESCRIPTION TEXT,
    QUANTITY INTEGER,
    INVOICEDATE TEXT,
    PRICE REAL,
    CUSTOMERID REAL,
    COUNTRY TEXT
)"""

SNOWFLAKE_RETAIL_DDL = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    INVOICE VARCHAR,
    STOCKCODE VARCHAR,
    DESCRIPTION VARCHAR,
    QUANTITY NUMBER,
    INVOICEDATE VARCHAR,
    PRICE FLOAT,
    CUSTOMERID FLOAT,
    COUNTRY VARCHAR
)"""

SQLITE_LOG_DDL = f"""CREATE TABLE IF NOT EXISTS {LOG_TABLE_NAME} (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    TS TEXT,
    MODE TEXT,
    QUESTION TEXT,
    SQL_TEXT TEXT,
    SUCCESS INTEGER,
    LATENCY_MS REAL,
    ERROR TEXT
)"""

SNOWFLAKE_LOG_DDL = f"""CREATE TABLE IF NOT EXISTS {LOG_TABLE_NAME} (
    ID NUMBER AUTOINCREMENT,
    TS VARCHAR,
    MODE VARCHAR,
    QUESTION VARCHAR,
    SQL_TEXT VARCHAR,
    SUCCESS NUMBER,
    LATENCY_MS FLOAT,
    ERROR VARCHAR
)"""


class Warehouse(ABC):
    """Minimal interface the copilot, ingest, and monitoring layers use."""

    name: str = "base"

    @abstractmethod
    def execute(self, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Run a read query. Returns (column names, rows)."""

    @abstractmethod
    def execute_write(self, sql: str, params: Optional[tuple] = None) -> None:
        """Run a write statement (DDL / INSERT)."""

    @abstractmethod
    def create_tables(self) -> None:
        """Create the retail and query-log tables if they do not exist."""

    @abstractmethod
    def drop_table(self, table: str) -> None:
        ...

    @abstractmethod
    def load_dataframe(self, df: pd.DataFrame, table: str) -> int:
        """Bulk-load a dataframe into a table. Returns rows loaded."""

    @abstractmethod
    def row_count(self, table: str) -> int:
        ...

    @abstractmethod
    def close(self) -> None:
        ...


class SQLiteWarehouse(Warehouse):
    name = "sqlite"

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")

    def execute(self, sql: str):
        cur = self._conn.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        return cols, cur.fetchall()

    def execute_write(self, sql: str, params: Optional[tuple] = None) -> None:
        if params is None:
            self._conn.execute(sql)
        else:
            self._conn.execute(sql, params)
        self._conn.commit()

    def create_tables(self) -> None:
        self.execute_write(SQLITE_RETAIL_DDL)
        self.execute_write(SQLITE_LOG_DDL)

    def drop_table(self, table: str) -> None:
        self.execute_write(f"DROP TABLE IF EXISTS {table}")

    def load_dataframe(self, df: pd.DataFrame, table: str) -> int:
        # chunksize=1000 with method="multi" keeps each INSERT under
        # SQLite's variable limit (8 columns x 1000 rows = 8000 vars).
        df.to_sql(table, self._conn, if_exists="append", index=False,
                  chunksize=1000, method="multi")
        self._conn.commit()
        return len(df)

    def row_count(self, table: str) -> int:
        _, rows = self.execute(f"SELECT COUNT(*) FROM {table}")
        return int(rows[0][0])

    def close(self) -> None:
        self._conn.close()


class SnowflakeWarehouse(Warehouse):
    name = "snowflake"

    def __init__(self, cfg):
        import snowflake.connector

        connect_kwargs: dict[str, Any] = {
            "account": cfg.account,
            "user": cfg.user,
            "password": cfg.password,
            "warehouse": cfg.warehouse,
            "database": cfg.database,
            "schema": cfg.schema,
        }
        if cfg.role:
            connect_kwargs["role"] = cfg.role
        self._conn = snowflake.connector.connect(**connect_kwargs)

    def execute(self, sql: str):
        cur = self._conn.cursor()
        try:
            cur.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            return cols, cur.fetchall()
        finally:
            cur.close()

    def execute_write(self, sql: str, params: Optional[tuple] = None) -> None:
        cur = self._conn.cursor()
        try:
            cur.execute(sql, params or ())
        finally:
            cur.close()

    def create_tables(self) -> None:
        self.execute_write(SNOWFLAKE_RETAIL_DDL)
        self.execute_write(SNOWFLAKE_LOG_DDL)

    def drop_table(self, table: str) -> None:
        self.execute_write(f"DROP TABLE IF EXISTS {table}")

    def load_dataframe(self, df: pd.DataFrame, table: str) -> int:
        from snowflake.connector.pandas_tools import write_pandas

        success, nchunks, nrows, _ = write_pandas(
            self._conn, df, table, auto_create_table=False, overwrite=False)
        if not success:
            raise RuntimeError(f"write_pandas failed for {table}")
        return int(nrows)

    def row_count(self, table: str) -> int:
        _, rows = self.execute(f"SELECT COUNT(*) FROM {table}")
        return int(rows[0][0])

    def close(self) -> None:
        self._conn.close()


def build_warehouse(cfg) -> Warehouse:
    """Build the warehouse for the resolved mode ('live' or 'demo')."""
    if cfg.resolve_mode() == "live":
        return SnowflakeWarehouse(cfg.snowflake)
    return SQLiteWarehouse(cfg.db_path)
