"""
AI Translation Engine: Translates natural language into structured semantic QueryPlan.
Supports local semantic reasoning compiler, feedback incorporation, and external LLM bridging.
"""
import os
import re
import logging
from typing import Dict, List, Optional, Any
from query_engine.nlp.intent_model import (
    QueryPlan, IntentType, FilterCondition
)
from query_engine.nlp.tokenizer import EntityExtractor
from query_engine.schema_catalog import SchemaCatalog
from query_engine.feedback_loop import FeedbackManager

logger = logging.getLogger(__name__)


class AITranslator:
    """Semantic AI Engine that resolves natural language into a canonical execution plan."""

    def __init__(self, schema_catalog: SchemaCatalog, feedback_mgr: Optional[FeedbackManager] = None):
        self.catalog = schema_catalog
        self.extractor = EntityExtractor(schema_catalog)
        self.feedback_mgr = feedback_mgr

    def translate(self, query: str) -> QueryPlan:
        """Translates a natural language query into a robust QueryPlan."""
        clean_query = query.strip()
        lower = clean_query.lower()

        # Check feedback loop for prior verified corrections or hints
        feedback_hint = None
        if self.feedback_mgr:
            feedback_hint = self.feedback_mgr.lookup_query_feedback(clean_query)

        # 1. Extract base linguistic entities
        metrics = self.extractor.extract_metrics(clean_query)
        dimensions = self.extractor.extract_dimensions(clean_query)
        filters = self.extractor.extract_filters(clean_query)
        time_filter = self.extractor.extract_time_filters(clean_query)
        limit = self.extractor.extract_limit(clean_query)

        # 2. Pattern & Intent Classification
        
        # Pattern A: Nested Multi-Level (e.g. "Revenue of top 3 customers per region")
        if re.search(r"\b(?:revenue|sales|profit|orders)\s+of\s+top\s+(\d+)\s+([a-zA-Z_]+)\s+(?:per|in\s+each|by)\s+([a-zA-Z_]+)\b", lower):
            m = re.search(r"\b(?:revenue|sales|profit|orders)\s+of\s+top\s+(\d+)\s+([a-zA-Z_]+)\s+(?:per|in\s+each|by)\s+([a-zA-Z_]+)\b", lower)
            n_val = int(m.group(1))
            inner_ent = self.catalog.resolve_term(m.group(2))
            outer_ent = self.catalog.resolve_term(m.group(3))
            
            # Map terms like 'customers' -> 'customer_id'
            if inner_ent in {"customers", "customer"}:
                inner_ent = "customer_id"
            if outer_ent in {"regions", "region"}:
                outer_ent = "region"

            return QueryPlan(
                raw_query=clean_query,
                intent_type=IntentType.NESTED_GROUP_RANK_AGG,
                metrics=metrics or ["revenue"],
                dimensions=[outer_ent],
                limit=n_val,
                nested_spec={
                    "inner_dimension": inner_ent,
                    "outer_dimension": outer_ent,
                    "inner_rank_limit": n_val,
                    "aggregation": "sum"
                },
                metadata={"feedback_hint": feedback_hint}
            )

        # Pattern B: Window Partition Rank (e.g. "Top product in each region", "highest item per city")
        if (re.search(r"\b(?:top|highest|best|leading|first)\s+(?:product|item|customer|category)\b", lower) and 
            re.search(r"\b(?:in each|per|by each)\s+([a-zA-Z_]+)\b", lower)):
            part_match = re.search(r"\b(?:in each|per|by each)\s+([a-zA-Z_]+)\b", lower)
            partition_col = self.catalog.resolve_term(part_match.group(1))
            if partition_col in {"region", "regions"}:
                partition_col = "region"
            elif partition_col in {"city", "cities"}:
                partition_col = "city"
            
            # Determine ranked entity
            ranked_entity = "product_name"
            if "customer" in lower:
                ranked_entity = "customer_id"
            elif "category" in lower:
                ranked_entity = "product_category"

            return QueryPlan(
                raw_query=clean_query,
                intent_type=IntentType.WINDOW_PARTITION_RANK,
                metrics=metrics or ["revenue"],
                dimensions=[partition_col, ranked_entity],
                partition_by=partition_col,
                order_by=metrics[0] if metrics else "revenue",
                order_desc=True,
                limit=limit or 1,
                metadata={"feedback_hint": feedback_hint}
            )

        # Pattern C: Target Comparison (e.g. "Which region missed its target in Feb?", "beat target")
        if "target" in lower or "goal" in lower:
            comp_op = "<" if any(w in lower for w in ["miss", "missed", "below", "behind", "fail", "under"]) else ">="
            target_dim = "region" if ("region" in lower or "regions" in lower) else "region"
            return QueryPlan(
                raw_query=clean_query,
                intent_type=IntentType.TARGET_COMPARISON,
                metrics=["revenue"],
                dimensions=[target_dim],
                time_filter=time_filter,
                comparison_target="target_revenue",
                comparison_operator=comp_op,
                metadata={"feedback_hint": feedback_hint}
            )

        # Pattern D: Contribution Percentage (e.g. "Sales contribution % by category", "share of revenue")
        if any(term in lower for term in ["contribution", "%", "percent", "percentage", "share"]):
            dim = dimensions[0] if dimensions else "product_category"
            return QueryPlan(
                raw_query=clean_query,
                intent_type=IntentType.CONTRIBUTION_PERCENTAGE,
                metrics=metrics or ["revenue"],
                dimensions=[dim],
                metadata={"feedback_hint": feedback_hint}
            )

        # Pattern E: Time Series YoY / Growth (e.g. "YoY growth in revenue", "year over year sales growth")
        if any(term in lower for term in ["yoy", "year over year", "growth", "growth rate"]):
            return QueryPlan(
                raw_query=clean_query,
                intent_type=IntentType.TIME_SERIES_GROWTH,
                metrics=metrics or ["revenue"],
                dimensions=["year"],
                metadata={"feedback_hint": feedback_hint}
            )

        # Pattern F: Top N Group Ranking (e.g. "Top 2 cities by profit", "Top 5 products by revenue")
        if limit is not None and dimensions:
            return QueryPlan(
                raw_query=clean_query,
                intent_type=IntentType.GROUP_TOP_N,
                metrics=metrics or ["revenue"],
                dimensions=dimensions,
                filters=filters,
                time_filter=time_filter,
                order_by=metrics[0] if metrics else "revenue",
                order_desc=not any(w in lower for w in ["bottom", "lowest", "least", "worst"]),
                limit=limit,
                metadata={"feedback_hint": feedback_hint}
            )

        # Pattern G: Group Aggregation (e.g. "Average order value by region", "Total sales by category")
        if dimensions:
            metric = metrics[0] if metrics else "revenue"
            agg_func = "mean" if "average" in lower or "avg" in lower or metric == "avg_order_value" else "sum"
            return QueryPlan(
                raw_query=clean_query,
                intent_type=IntentType.GROUP_AGGREGATION,
                metrics=[metric],
                dimensions=dimensions,
                filters=filters,
                time_filter=time_filter,
                agg_funcs=[agg_func],
                metadata={"feedback_hint": feedback_hint}
            )

        # Pattern H: Single Aggregate (e.g. "Total sales in India for March")
        metric = metrics[0] if metrics else "revenue"
        agg_func = "sum"
        if "average" in lower or "avg" in lower or "mean" in lower:
            agg_func = "mean"
        elif "count" in lower or "number of" in lower:
            agg_func = "count"

        return QueryPlan(
            raw_query=clean_query,
            intent_type=IntentType.AGGREGATION,
            metrics=[metric],
            dimensions=[],
            filters=filters,
            time_filter=time_filter,
            agg_funcs=[agg_func],
            metadata={"feedback_hint": feedback_hint}
        )
