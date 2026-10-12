"""
Comprehensive Automated Test Suite for Intelligent Analytics Query Engine.
Tests all 8 benchmark queries, dual-mode execution (Pandas/SQL), AST security sandbox,
feedback loop integration, and unseen query generalization.
"""
import unittest
import json
from pathlib import Path
import pandas as pd

from query_engine.config import (
    SALES_DATA_PATH, TARGETS_DATA_PATH, DATA_DICTIONARY_PATH, FEEDBACK_LOG_PATH
)
from query_engine.data_loader import DataLoader
from query_engine.schema_catalog import SchemaCatalog
from query_engine.feedback_loop import FeedbackManager
from query_engine.engine import IntelligentAnalyticsEngine
from query_engine.executor.sandbox import SandboxValidator, SecurityViolationError


class TestDataLoaderAndSchema(unittest.TestCase):
    """Tests data ingestion and schema resolution."""

    def test_sales_data_loading_and_na_preservation(self):
        df = DataLoader.prepare_sales_dataset(SALES_DATA_PATH)
        self.assertEqual(len(df), 10)
        self.assertIn("revenue", df.columns)
        self.assertIn("NA", df["region"].unique(), "Region 'NA' must not be converted to NaN!")
        self.assertEqual(df["revenue"].sum(), 6134.4)

    def test_targets_data_loading(self):
        targets = DataLoader.prepare_targets_dataset(TARGETS_DATA_PATH)
        self.assertEqual(len(targets), 9)
        self.assertIn("NA", targets["region"].unique())
        self.assertTrue(all(targets["target_revenue"] > 0))

    def test_schema_catalog_synonyms(self):
        catalog = SchemaCatalog(DATA_DICTIONARY_PATH)
        self.assertEqual(catalog.resolve_term("sales"), "revenue")
        self.assertEqual(catalog.resolve_term("earnings"), "profit")
        self.assertEqual(catalog.resolve_term("aov"), "avg_order_value")
        self.assertEqual(catalog.resolve_term("category"), "product_category")


class TestBenchmarkQueries(unittest.TestCase):
    """Tests all 8 benchmark queries against expected ground truth analytical results."""

    @classmethod
    def setUpClass(cls):
        cls.engine = IntelligentAnalyticsEngine()

    def test_q1_total_sales_india_march(self):
        res = self.engine.process_query("Total sales in India for March")
        self.assertAlmostEqual(res["result"], 108.0, places=1)
        self.assertGreaterEqual(res["confidence_score"], 0.95)

    def test_q2_top_2_cities_by_profit(self):
        res = self.engine.process_query("Top 2 cities by profit")
        self.assertIsInstance(res["result"], list)
        self.assertEqual(len(res["result"]), 2)
        cities = [r["city"] for r in res["result"]]
        self.assertEqual(cities, ["New York", "San Francisco"])
        self.assertEqual(res["result"][0]["profit"], 200)
        self.assertEqual(res["result"][1]["profit"], 180)

    def test_q3_average_order_value_by_region(self):
        res = self.engine.process_query("Average order value by region")
        self.assertIsInstance(res["result"], list)
        res_dict = {r["region"]: r["avg_order_value"] for r in res["result"]}
        self.assertAlmostEqual(res_dict["APAC"], 118.50, places=1)
        self.assertAlmostEqual(res_dict["EMEA"], 799.33, places=1)
        self.assertAlmostEqual(res_dict["NA"], 1087.47, places=1)

    def test_q4_regions_missed_target_feb(self):
        res = self.engine.process_query("Which region missed its target in Feb?")
        self.assertIsInstance(res["result"], list)
        regions = [r["region"] for r in res["result"]]
        self.assertEqual(set(regions), {"APAC", "EMEA", "NA"})

    def test_q5_sales_contribution_pct_by_category(self):
        res = self.engine.process_query("Sales contribution % by category")
        self.assertIsInstance(res["result"], list)
        cat_pcts = {r["product_category"]: r["contribution_pct"] for r in res["result"]}
        self.assertAlmostEqual(cat_pcts["Technology"], 88.06, places=1)
        self.assertAlmostEqual(cat_pcts["Furniture"], 9.44, places=1)
        self.assertAlmostEqual(cat_pcts["Office Supplies"], 2.50, places=1)

    def test_q6_top_product_in_each_region(self):
        res = self.engine.process_query("Top product in each region")
        self.assertIsInstance(res["result"], list)
        prod_map = {r["region"]: r["product_name"] for r in res["result"]}
        self.assertEqual(prod_map["APAC"], "Ergo Chair")
        self.assertEqual(prod_map["EMEA"], "Samsung Galaxy")
        self.assertEqual(prod_map["NA"], "Dell XPS")

    def test_q7_yoy_growth_in_revenue(self):
        res = self.engine.process_query("YoY growth in revenue")
        self.assertIn("2024", res["result"])
        self.assertGreaterEqual(res["confidence_score"], 0.90)
        self.assertIn("baseline", res["explanation"].lower())

    def test_q8_revenue_of_top_3_customers_per_region(self):
        res = self.engine.process_query("Revenue of top 3 customers per region")
        self.assertIsInstance(res["result"], list)
        rev_map = {r["region"]: r["revenue"] for r in res["result"]}
        self.assertAlmostEqual(rev_map["APAC"], 474.0, places=1)
        self.assertAlmostEqual(rev_map["EMEA"], 2398.0, places=1)
        self.assertAlmostEqual(rev_map["NA"], 3262.4, places=1)


class TestDualEngineParity(unittest.TestCase):
    """Verifies that both Pandas and SQL execution modes return consistent results."""

    @classmethod
    def setUpClass(cls):
        cls.engine = IntelligentAnalyticsEngine()

    def test_q1_pandas_and_sql_parity(self):
        p_res = self.engine.process_query("Total sales in India for March", mode="pandas")
        s_res = self.engine.process_query("Total sales in India for March", mode="sql")
        self.assertEqual(p_res["result"], s_res["result"])

    def test_q2_pandas_and_sql_parity(self):
        p_res = self.engine.process_query("Top 2 cities by profit", mode="pandas")
        s_res = self.engine.process_query("Top 2 cities by profit", mode="sql")
        p_cities = [r["city"] for r in p_res["result"]]
        s_cities = [r["city"] for r in s_res["result"]]
        self.assertEqual(p_cities, s_cities)


class TestSecuritySandbox(unittest.TestCase):
    """Tests that security sandbox stops malicious code injection."""

    def test_disallowed_imports_blocked(self):
        with self.assertRaises(SecurityViolationError):
            SandboxValidator.validate_code("import os; os.system('whoami')")

        with self.assertRaises(SecurityViolationError):
            SandboxValidator.validate_code("import subprocess; subprocess.Popen('calc.exe')")

    def test_banned_builtins_blocked(self):
        with self.assertRaises(SecurityViolationError):
            SandboxValidator.validate_code("open('secret.txt', 'w')")

        with self.assertRaises(SecurityViolationError):
            SandboxValidator.validate_code("__import__('os').system('dir')")

    def test_dunder_traversal_blocked(self):
        with self.assertRaises(SecurityViolationError):
            SandboxValidator.validate_code("().__class__.__bases__[0]")


class TestUnseenQueriesAndGeneralization(unittest.TestCase):
    """Tests engine adaptability on completely unseen queries without hardcoding."""

    @classmethod
    def setUpClass(cls):
        cls.engine = IntelligentAnalyticsEngine()

    def test_unseen_query_germany_profit(self):
        res = self.engine.process_query("What is the total profit in Germany?")
        self.assertEqual(res["result"], 150)
        self.assertGreaterEqual(res["confidence_score"], 0.95)

    def test_unseen_query_top_products_sales(self):
        res = self.engine.process_query("Top 3 products by sales")
        self.assertEqual(len(res["result"]), 3)
        self.assertEqual(res["result"][0]["product_name"], "Dell XPS")

    def test_unseen_query_furniture_sales(self):
        res = self.engine.process_query("Total sales in Furniture")
        self.assertAlmostEqual(res["result"], 579.0, places=1)


class TestFeedbackLoop(unittest.TestCase):
    """Tests recording and active lookup in feedback_log.csv."""

    @classmethod
    def setUpClass(cls):
        cls.engine = IntelligentAnalyticsEngine()

    def test_feedback_recording_and_matching(self):
        fb_id = self.engine.add_feedback(
            query="Total revenue in India for March",
            generated_logic="df[(df['country'] == 'India') & (df['month'] == '2024-03')]['revenue'].sum()",
            user_rating=5,
            notes="Verified test feedback entry"
        )
        self.assertTrue(fb_id.startswith("FB-"))
        
        # Test lookup
        match = self.engine.feedback_manager.lookup_query_feedback("Total sales in India for March")
        self.assertIsNotNone(match)
        self.assertGreaterEqual(match["similarity"], 0.5)


if __name__ == "__main__":
    unittest.main()
