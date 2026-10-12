"""
Unified Intelligent Analytics Query Engine.
Coordinates the complete 8-stage pipeline from natural language to verified execution,
confidence scoring, transparent explanation, and feedback calibration.
"""
import logging
from typing import Dict, List, Optional, Any
import pandas as pd

from query_engine.config import (
    SALES_DATA_PATH, TARGETS_DATA_PATH, DATA_DICTIONARY_PATH,
    FEEDBACK_LOG_PATH, NL_QUERIES_PATH, DEFAULT_ENGINE_MODE
)
from query_engine.data_loader import DataLoader
from query_engine.schema_catalog import SchemaCatalog
from query_engine.feedback_loop import FeedbackManager
from query_engine.nlp.ai_translator import AITranslator
from query_engine.codegen.pandas_generator import PandasGenerator
from query_engine.codegen.sql_generator import SQLGenerator
from query_engine.executor.pandas_runner import PandasRunner
from query_engine.executor.sql_runner import SQLRunner
from query_engine.scoring.confidence import ConfidenceScorer
from query_engine.explainer.explanation import QueryExplainer

logger = logging.getLogger(__name__)


class IntelligentAnalyticsEngine:
    """Production-grade natural language to analytics query engine."""

    def __init__(
        self,
        sales_path: str = SALES_DATA_PATH,
        targets_path: str = TARGETS_DATA_PATH,
        dict_path: str = DATA_DICTIONARY_PATH,
        feedback_path: str = FEEDBACK_LOG_PATH
    ):
        logger.info("Initializing Intelligent Analytics Query Engine...")
        self.schema_catalog = SchemaCatalog(dict_path)
        self.feedback_manager = FeedbackManager(feedback_path)
        
        # Load and prepare datasets
        self.sales_df = DataLoader.prepare_sales_dataset(sales_path)
        self.targets_df = DataLoader.prepare_targets_dataset(targets_path)

        # Components
        self.translator = AITranslator(self.schema_catalog, self.feedback_manager)
        self.pandas_generator = PandasGenerator()
        self.sql_generator = SQLGenerator()
        self.pandas_runner = PandasRunner(self.sales_df, self.targets_df)
        self.sql_runner = SQLRunner(self.sales_df, self.targets_df)
        self.confidence_scorer = ConfidenceScorer(self.schema_catalog)
        self.explainer = QueryExplainer(self.schema_catalog)

    def process_query(self, query: str, mode: str = DEFAULT_ENGINE_MODE) -> Dict[str, Any]:
        """
        Executes the 8-stage intelligent query processing cycle for a single natural language query.
        Returns a dictionary adhering to the exact evaluation schema:
        {
            "query": "...",
            "generated_logic": "...",
            "result": "...",
            "confidence_score": 0.0,
            "explanation": "..."
        }
        """
        # Stage 1: Understand Natural Language & Map Business Terms
        plan = self.translator.translate(query)

        # Stage 2: Generate Executable Logic (Pandas / SQL)
        if mode == "sql":
            generated_logic = self.sql_generator.generate(plan)
            # Stage 3: Execute and Return Results
            success, result_data, err_msg = self.sql_runner.execute(generated_logic)
        else:
            generated_logic = self.pandas_generator.generate(plan)
            # Stage 3: Execute and Return Results
            success, result_data, err_msg = self.pandas_runner.execute(generated_logic)

        # Syntax check indicator
        syntax_valid = (err_msg is None) or ("Syntax" not in str(err_msg))

        # Stage 4: Confidence Scoring
        has_data = bool(result_data is not None and result_data != [] and result_data != {})
        confidence = self.confidence_scorer.calculate(
            plan=plan,
            syntax_valid=syntax_valid,
            execution_success=success,
            result_has_data=has_data,
            feedback_hint=plan.metadata.get("feedback_hint")
        )

        # Stage 5: Explainable AI
        explanation = self.explainer.explain(plan, mode=mode)
        if not success and err_msg:
            explanation += f" Execution warning: {err_msg}"

        # Stage 6 & Expected Output Formatting
        return {
            "query": query,
            "generated_logic": generated_logic,
            "result": result_data if success else f"Error: {err_msg}",
            "confidence_score": confidence,
            "explanation": explanation
        }

    def evaluate_suite(self, suite_path: str = NL_QUERIES_PATH, mode: str = DEFAULT_ENGINE_MODE) -> List[Dict[str, Any]]:
        """Processes an entire test suite from JSON file (e.g., nl_queries.json)."""
        suite_data = DataLoader.load_json(suite_path)
        results = []
        for item in suite_data:
            q_text = item.get("query", "")
            out = self.process_query(q_text, mode=mode)
            results.append(out)
        return results

    def add_feedback(
        self,
        query: str,
        generated_logic: str,
        user_rating: int,
        corrected_logic: str = "",
        notes: str = ""
    ) -> str:
        """Records feedback to feedback_log.csv for dynamic engine calibration."""
        return self.feedback_manager.record_feedback(
            query=query,
            generated_logic=generated_logic,
            user_rating=user_rating,
            corrected_logic=corrected_logic,
            notes=notes
        )
