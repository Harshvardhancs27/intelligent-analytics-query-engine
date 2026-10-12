"""
Feedback Loop Integration for Intelligent Analytics Query Engine.
Reads, analyzes, and applies feedback from feedback_log.csv to calibrate confidence and refine logic.
"""
import os
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

from query_engine.config import FEEDBACK_LOG_PATH

logger = logging.getLogger(__name__)


class FeedbackManager:
    """Manages historical feedback ingestion, similarity lookup, and active learning adjustments."""

    def __init__(self, log_path: str = FEEDBACK_LOG_PATH):
        self.log_path = Path(log_path)
        self.feedback_df: Optional[pd.DataFrame] = None
        self._ensure_log_initialized()
        self.reload()

    def _ensure_log_initialized(self) -> None:
        """Initializes feedback_log.csv with header if it doesn't exist."""
        if not self.log_path.exists():
            headers = [
                "feedback_id", "timestamp", "query", "generated_logic",
                "user_rating", "corrected_logic", "notes"
            ]
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                # Seed an example feedback entry demonstrating learning from prior adjustments
                writer.writerow([
                    "FB-001",
                    datetime.now().isoformat(),
                    "Total sales in India for March",
                    "df[(df['country'] == 'India') & (df['month'] == '2024-03')]['revenue'].sum()",
                    "5",
                    "",
                    "Accurate mapping of sales->revenue and March->2024-03 verified by analyst"
                ])
                writer.writerow([
                    "FB-002",
                    datetime.now().isoformat(),
                    "Which region missed target in February",
                    "merged[merged['revenue'] < merged['target_revenue']]",
                    "5",
                    "JOIN targets on region and filter month='2024-02'",
                    "Ensure left join targets with sales and compare revenue < target_revenue"
                ])

    def reload(self) -> None:
        """Reloads the feedback dataframe from disk."""
        if self.log_path.exists():
            try:
                self.feedback_df = pd.read_csv(self.log_path, keep_default_na=False)
            except Exception as e:
                logger.warning(f"Could not load feedback log: {e}")
                self.feedback_df = pd.DataFrame()
        else:
            self.feedback_df = pd.DataFrame()

    @staticmethod
    def _calculate_query_similarity(q1: str, q2: str) -> float:
        """Calculates token-based Jaccard similarity between two natural language queries."""
        tokens1 = set(q1.lower().replace("?", "").replace(",", "").split())
        tokens2 = set(q2.lower().replace("?", "").replace(",", "").split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        return len(intersection) / len(union)

    def lookup_query_feedback(self, query: str, threshold: float = 0.65) -> Optional[Dict[str, Any]]:
        """
        Finds the closest matching historical feedback entry for a query.
        Returns match metadata, corrected logic (if any), and confidence adjustments.
        """
        if self.feedback_df is None or self.feedback_df.empty:
            return None

        best_match = None
        best_sim = 0.0

        for _, row in self.feedback_df.iterrows():
            past_query = str(row.get("query", ""))
            sim = self._calculate_query_similarity(query, past_query)
            if sim > best_sim:
                best_sim = sim
                best_match = row

        if best_match is not None and best_sim >= threshold:
            rating_val = 0
            try:
                rating_val = int(best_match.get("user_rating", 0))
            except (ValueError, TypeError):
                pass

            return {
                "matched_query": best_match.get("query"),
                "similarity": round(best_sim, 3),
                "user_rating": rating_val,
                "corrected_logic": best_match.get("corrected_logic", "").strip(),
                "historical_logic": best_match.get("generated_logic", "").strip(),
                "notes": best_match.get("notes", ""),
                "has_correction": bool(best_match.get("corrected_logic", "").strip())
            }

        return None

    def record_feedback(
        self,
        query: str,
        generated_logic: str,
        user_rating: int,
        corrected_logic: str = "",
        notes: str = ""
    ) -> str:
        """Appends new user feedback to feedback_log.csv."""
        feedback_id = f"FB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        new_row = [
            feedback_id,
            datetime.now().isoformat(),
            query,
            generated_logic,
            str(user_rating),
            corrected_logic,
            notes
        ]
        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(new_row)
        self.reload()
        return feedback_id
