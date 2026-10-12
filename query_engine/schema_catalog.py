"""
Schema Catalog & Ontology Manager for Intelligent Analytics Query Engine.
Interprets metadata, maps synonyms, registers dimensions & metrics, and validates schema alignment.
"""
from typing import Dict, List, Optional, Any, Set
import logging
from query_engine.data_loader import DataLoader
from query_engine.config import DATA_DICTIONARY_PATH

logger = logging.getLogger(__name__)


class SchemaCatalog:
    """Central ontological catalog providing business-to-technical metadata mapping."""

    def __init__(self, data_dict_path: str = DATA_DICTIONARY_PATH):
        self.data_dict_path = data_dict_path
        self.raw_dict = DataLoader.load_json(data_dict_path)
        
        self.metrics: Dict[str, str] = self.raw_dict.get("metrics", {})
        self.dimensions: List[str] = self.raw_dict.get("dimensions", [])
        self.synonyms: Dict[str, str] = self.raw_dict.get("synonyms", {})
        self.time_mappings: Dict[str, str] = self.raw_dict.get("time_mappings", {})
        
        # Extended synonyms for natural business terminology
        self._extended_synonyms: Dict[str, str] = {
            "sales": "revenue",
            "sale": "revenue",
            "turnover": "revenue",
            "income": "revenue",
            "earnings": "profit",
            "net profit": "profit",
            "margin": "profit",
            "orders": "orders",
            "order count": "orders",
            "volume": "quantity",
            "units": "quantity",
            "aov": "avg_order_value",
            "average order value": "avg_order_value",
            "avg order value": "avg_order_value",
            "customer": "customer_id",
            "client": "customer_id",
            "buyer": "customer_id",
            "product": "product_name",
            "item": "product_name",
            "category": "product_category",
            "subcategory": "product_subcategory",
            "segment": "customer_segment",
            "date": "order_date",
            "target": "target_revenue",
            "target revenue": "target_revenue",
            "goal": "target_revenue"
        }
        # Merge dictionary synonyms with extended synonyms
        for k, v in self.synonyms.items():
            self._extended_synonyms[k.lower()] = v.lower()

        # Registered known columns across sales and targets tables
        self.sales_columns: Set[str] = {
            "order_id", "order_date", "region", "country", "city",
            "customer_id", "customer_segment", "product_category",
            "product_subcategory", "product_name", "quantity",
            "unit_price", "discount", "shipping_cost", "profit",
            "revenue", "month", "year"
        }
        self.targets_columns: Set[str] = {
            "region", "month", "target_revenue"
        }

    def resolve_term(self, term: str) -> str:
        """Resolves colloquial synonyms to canonical technical field names."""
        clean = term.strip().lower()
        if clean in self._extended_synonyms:
            return self._extended_synonyms[clean]
        return clean

    def is_metric(self, name: str) -> bool:
        """Checks if a term is a metric or resolves to one."""
        resolved = self.resolve_term(name)
        return resolved in self.metrics or resolved in {"profit", "quantity", "discount", "shipping_cost", "revenue", "orders", "avg_order_value"}

    def is_dimension(self, name: str) -> bool:
        """Checks if a term is a dimension or resolves to one."""
        resolved = self.resolve_term(name)
        return resolved in self.dimensions or resolved in {"customer_id", "product_name", "month", "year"}

    def get_metric_formula(self, metric: str) -> str:
        """Returns the formula for a metric as defined in data dictionary."""
        resolved = self.resolve_term(metric)
        return self.metrics.get(resolved, resolved)

    def validate_columns(self, columns: List[str], table: str = "sales") -> Dict[str, Any]:
        """Validates a list of columns against the schema for confidence scoring."""
        valid_set = self.sales_columns if table == "sales" else self.targets_columns
        valid_cols = [c for c in columns if c in valid_set]
        missing_cols = [c for c in columns if c not in valid_set]
        alignment_score = len(valid_cols) / max(len(columns), 1)
        return {
            "valid_columns": valid_cols,
            "missing_columns": missing_cols,
            "alignment_score": alignment_score
        }
