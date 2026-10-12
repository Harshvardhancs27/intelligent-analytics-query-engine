"""
Pandas Execution Runner: Executes generated analytics code against DataFrames in a safe environment.
"""
import ast
import logging
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
import pandas as pd

from query_engine.executor.sandbox import SandboxValidator

logger = logging.getLogger(__name__)


class PandasRunner:
    """Safe runner for Pandas analytical code blocks."""

    def __init__(self, sales_df: pd.DataFrame, targets_df: pd.DataFrame):
        self.sales_df = sales_df
        self.targets_df = targets_df

    @staticmethod
    def format_result(raw_result: Any) -> Any:
        """Serializes Pandas/Numpy outputs into clean JSON-compatible Python primitives."""
        if isinstance(raw_result, (np.integer, int)):
            return int(raw_result)
        elif isinstance(raw_result, (np.floating, float)):
            if np.isnan(raw_result):
                return None
            return round(float(raw_result), 4)
        elif isinstance(raw_result, pd.Series):
            # Check for YoY pct_change or single series
            clean_dict = {}
            for k, v in raw_result.items():
                if pd.isna(v):
                    clean_dict[str(k)] = "Baseline / N/A (no prior period in dataset)"
                else:
                    clean_dict[str(k)] = round(float(v), 4)
            return clean_dict
        elif isinstance(raw_result, pd.DataFrame):
            # Replace NaNs for JSON safety and round floats
            records = raw_result.replace({np.nan: None}).to_dict(orient="records")
            formatted = []
            for row in records:
                clean_row = {}
                for k, v in row.items():
                    if isinstance(v, (np.floating, float)):
                        clean_row[k] = round(float(v), 2)
                    elif isinstance(v, (np.integer, int)):
                        clean_row[k] = int(v)
                    else:
                        clean_row[k] = v
                formatted.append(clean_row)
            return formatted
        elif isinstance(raw_result, list):
            return raw_result
        return str(raw_result)

    def execute(self, code_str: str) -> Tuple[bool, Any, Optional[str]]:
        """
        Executes code safely against datasets.
        Returns: (success: bool, result: Any, error_message: Optional[str])
        """
        # 1. AST Sandbox Security Check
        try:
            SandboxValidator.validate_code(code_str)
        except Exception as sec_err:
            logger.error(f"Sandbox security check failed: {sec_err}")
            return False, None, f"Security Violation: {str(sec_err)}"

        # 2. Setup execution context
        # Provide working copies to avoid in-place data mutations
        exec_globals = {
            "pd": pd,
            "np": np,
            "__builtins__": {
                "round": round, "len": len, "max": max, "min": min, "sum": sum,
                "range": range, "int": int, "float": float, "str": str, "dict": dict,
                "list": list, "set": set, "bool": bool
            }
        }
        exec_locals = {
            "df": self.sales_df.copy(),
            "targets": self.targets_df.copy()
        }

        # 3. Execution
        try:
            # If code is a single expression, evaluate it
            tree = ast.parse(code_str)
            if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr):
                raw_res = eval(code_str, exec_globals, exec_locals)
            else:
                # Multi-statement code: execute block
                # If the last statement is an expression, rewrite to capture it
                if isinstance(tree.body[-1], ast.Expr):
                    last_expr = ast.unparse(tree.body[-1].value) if hasattr(ast, "unparse") else None
                    code_lines = code_str.strip().split("\n")
                    exec_code = "\n".join(code_lines[:-1]) + f"\n__final_result__ = {code_lines[-1]}"
                    exec(exec_code, exec_globals, exec_locals)
                    raw_res = exec_locals.get("__final_result__")
                else:
                    exec(code_str, exec_globals, exec_locals)
                    # Find likely output variables
                    candidates = ["result", "merged", "top_n", "cat_sales", "yearly_rev", "q8", "prod_agg"]
                    raw_res = None
                    for c in candidates:
                        if c in exec_locals:
                            raw_res = exec_locals[c]
                            break

            formatted = self.format_result(raw_res)
            return True, formatted, None

        except Exception as exec_err:
            logger.error(f"Error during Pandas execution: {exec_err}")
            return False, None, str(exec_err)
