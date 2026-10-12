"""
SQL Execution Runner: Executes generated SQL queries against an in-memory SQLite relational database.
"""
import sqlite3
import logging
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


class SQLRunner:
    """In-memory SQLite execution engine for generated ANSI SQL queries."""

    def __init__(self, sales_df: pd.DataFrame, targets_df: pd.DataFrame):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_database(sales_df, targets_df)

    def _init_database(self, sales_df: pd.DataFrame, targets_df: pd.DataFrame) -> None:
        """Loads DataFrames into SQLite tables."""
        sales_df.to_sql("sales_data", self.conn, index=False, if_exists="replace")
        targets_df.to_sql("targets", self.conn, index=False, if_exists="replace")

    def execute(self, sql_query: str) -> Tuple[bool, Any, Optional[str]]:
        """
        Executes SQL query against SQLite database.
        Returns: (success: bool, result: Any, error_message: Optional[str])
        """
        # Read-only check: block destructive commands
        banned_sql = {"drop", "delete", "insert", "update", "alter", "attach", "detach", "vacuum"}
        first_token = sql_query.strip().split()[0].lower() if sql_query.strip() else ""
        if first_token in banned_sql or any(f" {b} " in sql_query.lower() for b in ["drop table", "delete from"]):
            return False, None, "Destructive SQL statements are blocked by security policy."

        try:
            cursor = self.conn.cursor()
            cursor.execute(sql_query)
            rows = cursor.fetchall()

            if not rows:
                return True, [], None

            # Convert rows to dicts
            result = [dict(row) for row in rows]
            
            # If single row with single value, unwrap to scalar
            if len(result) == 1 and len(result[0]) == 1:
                val = list(result[0].values())[0]
                if isinstance(val, float):
                    val = round(val, 4)
                return True, val, None

            # Clean float values
            cleaned = []
            for r in result:
                clean_r = {}
                for k, v in r.items():
                    if isinstance(v, float):
                        clean_r[k] = round(v, 2)
                    else:
                        clean_r[k] = v
                cleaned.append(clean_r)

            return True, cleaned, None

        except Exception as e:
            logger.error(f"Error executing SQL: {e}")
            return False, None, str(e)
