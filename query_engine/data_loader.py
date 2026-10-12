"""
Robust Data Loader for handling heterogeneous data sources,
including UTF-8 BOM, quoted CSV rows, Excel-escaped JSON, and NA region preservation.
"""
import csv
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class DataLoader:
    """Production-grade data ingestion utility with auto-detection for formatting anomalies."""

    @staticmethod
    def clean_text_content(content: str) -> str:
        """
        Unescapes content if the file was exported with CSV row wrappers
        (e.g., each line enclosed in outer quotes with double-escaped internal quotes).
        """
        if not content:
            return ""
        try:
            reader = csv.reader(io.StringIO(content))
            rows = [r for r in reader if r]
            if rows and all(len(r) == 1 for r in rows):
                # Check if unescaped lines contain structure (delimiters or brackets)
                sample = "\n".join(r[0] for r in rows[:10])
                if any(delim in sample for delim in [",", "{", "[", ":", "\""]):
                    return "\n".join(r[0] for r in rows)
        except Exception as e:
            logger.debug(f"CSV unwrapping fallback ignored: {e}")
        return content

    @classmethod
    def load_json(cls, file_path: str) -> Any:
        """Loads JSON file safely handling BOM and CSV-escaped formatting."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found at: {file_path}")

        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            cleaned = cls.clean_text_content(raw)
            return json.loads(cleaned)

    @classmethod
    def load_csv(cls, file_path: str, keep_na_strings: bool = True) -> pd.DataFrame:
        """
        Loads CSV file cleanly.
        Crucial: keep_na_strings=True prevents the 'NA' region (North America)
        from being converted to NaN!
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found at: {file_path}")

        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()

        cleaned = cls.clean_text_content(raw)
        
        # Parse CSV with pandas
        # keep_default_na=False ensures 'NA' remains string 'NA' (North America)
        df = pd.read_csv(
            io.StringIO(cleaned),
            keep_default_na=not keep_na_strings,
            na_values=["", "null", "NULL", "None"] if keep_na_strings else None
        )
        # Strip potential whitespace in string columns
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].astype(str).str.strip()

        return df

    @classmethod
    def prepare_sales_dataset(cls, file_path: str) -> pd.DataFrame:
        """Loads sales data and ensures standard derived metrics (revenue, month, year) are added."""
        df = cls.load_csv(file_path, keep_na_strings=True)

        # Convert numeric types
        numeric_cols = ["quantity", "unit_price", "discount", "shipping_cost", "profit"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Precompute revenue if formula components are present: quantity * unit_price * (1 - discount)
        if "quantity" in df.columns and "unit_price" in df.columns:
            discount = df["discount"] if "discount" in df.columns else 0.0
            df["revenue"] = (df["quantity"] * df["unit_price"] * (1.0 - discount)).round(4)

        # Add time helpers if order_date exists
        if "order_date" in df.columns:
            order_dt = pd.to_datetime(df["order_date"], errors="coerce")
            df["month"] = order_dt.dt.strftime("%Y-%m")
            df["year"] = order_dt.dt.year.astype("Int64").astype(str)

        return df

    @classmethod
    def prepare_targets_dataset(cls, file_path: str) -> pd.DataFrame:
        """Loads targets dataset with numeric conversion and preserved NA region."""
        df = cls.load_csv(file_path, keep_na_strings=True)
        if "target_revenue" in df.columns:
            df["target_revenue"] = pd.to_numeric(df["target_revenue"], errors="coerce").fillna(0)
        return df
