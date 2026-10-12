"""
Multi-factor Confidence Scoring Rubric (0.0 to 1.0).
Evaluates schema alignment, syntax validity, translation certainty, execution status, and feedback history.
"""
from typing import Dict, Any, Optional
from query_engine.nlp.intent_model import QueryPlan
from query_engine.schema_catalog import SchemaCatalog


class ConfidenceScorer:
    """Computes transparent, multi-dimensional confidence score for natural language query execution."""

    def __init__(self, schema_catalog: SchemaCatalog):
        self.catalog = schema_catalog

    def calculate(
        self,
        plan: QueryPlan,
        syntax_valid: bool,
        execution_success: bool,
        result_has_data: bool,
        feedback_hint: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculates holistic confidence score:
        - Schema alignment: 30%
        - Syntax validity: 25%
        - Translation certainty: 25%
        - Execution status: 20%
        - Feedback adjustment: +/- 10%
        """
        # 1. Schema Alignment Score (0.0 - 1.0)
        target_cols = list(plan.metrics) + list(plan.dimensions)
        for f in plan.filters:
            target_cols.append(f.column)
        
        valid_cols = [c for c in target_cols if c in self.catalog.sales_columns or c in self.catalog.targets_columns or c in self.catalog.metrics]
        schema_score = len(valid_cols) / max(len(target_cols), 1)

        # 2. Syntax Validity Score (0.0 or 1.0)
        syntax_score = 1.0 if syntax_valid else 0.0

        # 3. Translation Certainty Score (0.0 - 1.0)
        # Based on whether key intents and entities were cleanly recognized
        certainty_score = 0.95
        if not plan.metrics:
            certainty_score -= 0.15
        if plan.intent_type.value == "RAW_SCAN":
            certainty_score -= 0.30

        # 4. Execution Score (0.0 - 1.0)
        if execution_success:
            # Check edge case: YoY growth on single-year dataset produces baseline NaN
            if plan.intent_type.value == "TIME_SERIES_GROWTH":
                execution_score = 0.90  # Legitimate data boundary edge-case
            elif result_has_data:
                execution_score = 1.0
            else:
                execution_score = 0.85
        else:
            execution_score = 0.0

        # Weighted Base Score
        base_score = (
            0.30 * schema_score +
            0.25 * syntax_score +
            0.25 * certainty_score +
            0.20 * execution_score
        )

        # 5. Feedback Loop Adjustment
        if feedback_hint:
            user_rating = feedback_hint.get("user_rating", 0)
            if user_rating >= 4:
                base_score += 0.05  # Positive boost from verified analyst review
            elif user_rating > 0 and user_rating <= 2:
                base_score -= 0.10  # Caution penalty

        # Clip between 0.0 and 1.0
        final_score = max(0.0, min(1.0, round(base_score, 2)))
        return final_score
