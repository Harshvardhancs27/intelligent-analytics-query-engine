"""
Configuration settings and paths for Intelligent Analytics Query Engine.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Data file paths
SALES_DATA_PATH = os.environ.get("SALES_DATA_PATH", str(BASE_DIR / "sales_data.csv"))
TARGETS_DATA_PATH = os.environ.get("TARGETS_DATA_PATH", str(BASE_DIR / "targets.csv"))
DATA_DICTIONARY_PATH = os.environ.get("DATA_DICTIONARY_PATH", str(BASE_DIR / "data_dictionary.json"))
NL_QUERIES_PATH = os.environ.get("NL_QUERIES_PATH", str(BASE_DIR / "nl_queries.json"))
FEEDBACK_LOG_PATH = os.environ.get("FEEDBACK_LOG_PATH", str(BASE_DIR / "feedback_log.csv"))
OUTPUT_RESULTS_PATH = os.environ.get("OUTPUT_RESULTS_PATH", str(BASE_DIR / "output_results.json"))

# Execution settings
DEFAULT_ENGINE_MODE = os.environ.get("ENGINE_MODE", "pandas")  # 'pandas' or 'sql'
EXECUTION_TIMEOUT_SECONDS = 10

# Security Sandbox settings
ALLOWED_MODULES = {"pd", "pandas", "np", "numpy", "math", "datetime"}
BANNED_BUILTINS = {
    "__import__", "eval", "exec", "compile", "open", "file", 
    "input", "raw_input", "globals", "locals", "vars", "dir", 
    "getattr", "setattr", "delattr", "hasattr", "breakpoint", 
    "exit", "quit", "help"
}
BANNED_ATTRIBUTES = {
    "__subclasses__", "__bases__", "__class__", "__code__", 
    "__globals__", "__builtins__", "__import__"
}
