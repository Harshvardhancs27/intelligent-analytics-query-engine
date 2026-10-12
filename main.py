"""
Command-Line Interface (CLI) for Intelligent Analytics Query Engine.
Runs test suites, evaluates custom natural language queries, manages feedback, and generates output_results.json.
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from query_engine.config import OUTPUT_RESULTS_PATH, NL_QUERIES_PATH, DEFAULT_ENGINE_MODE
from query_engine.engine import IntelligentAnalyticsEngine

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("QueryEngineCLI")


# Ensure stdout handles UTF-8 on Windows
if sys.stdout.encoding != "utf-8" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def format_cli_output(result: dict) -> None:
    """Pretty prints evaluation output to terminal."""
    print("\n" + "=" * 80)
    print(f"[QUERY] {result['query']}")
    print("-" * 80)
    print(f"[GENERATED LOGIC]\n{result['generated_logic']}")
    print("-" * 80)
    print(f"[RESULT]\n{json.dumps(result['result'], indent=2)}")
    print("-" * 80)
    print(f"[CONFIDENCE SCORE] {result['confidence_score']:.2f} / 1.00")
    print(f"[EXPLANATION]\n{result['explanation']}")
    print("=" * 80 + "\n")


def run_suite(engine: IntelligentAnalyticsEngine, mode: str = "pandas", output_file: str = OUTPUT_RESULTS_PATH) -> None:
    """Evaluates the full nl_queries.json test suite and saves output_results.json."""
    print(f"\n>> Executing Test Suite using '{mode.upper()}' engine...")
    start_time = time.time()
    
    results = engine.evaluate_suite(suite_path=NL_QUERIES_PATH, mode=mode)
    duration = time.time() - start_time

    # Write output_results.json strictly in required format
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f">> Successfully processed {len(results)} queries in {duration:.3f}s!")
    print(f">> Results saved to: {output_file}\n")

    for i, res in enumerate(results, 1):
        print(f"[{i}/{len(results)}] {res['query']}")
        print(f"     Confidence: {res['confidence_score']:.2f} | Result Type: {type(res['result']).__name__}")

    avg_conf = sum(r["confidence_score"] for r in results) / len(results)
    print(f"\n[SUMMARY] Suite Average Confidence: {avg_conf:.2f} / 1.00")


def run_adhoc(engine: IntelligentAnalyticsEngine, query_text: str, mode: str = "pandas") -> None:
    """Processes an ad-hoc natural language query."""
    result = engine.process_query(query_text, mode=mode)
    format_cli_output(result)


def main():
    parser = argparse.ArgumentParser(
        description="Production Intelligent Analytics Query Engine (NL to Pandas/SQL)"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Ad-hoc natural language query to translate and execute."
    )
    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["pandas", "sql"],
        default=DEFAULT_ENGINE_MODE,
        help="Backend execution engine: 'pandas' (default) or 'sql'."
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=OUTPUT_RESULTS_PATH,
        help="Destination path for JSON results (default: output_results.json)."
    )
    parser.add_argument(
        "--feedback-rate",
        type=int,
        help="Rate query accuracy (1-5) for feedback loop."
    )
    parser.add_argument(
        "--feedback-notes",
        type=str,
        default="",
        help="Notes/corrections for feedback loop."
    )

    args = parser.parse_args()
    engine = IntelligentAnalyticsEngine()

    if args.query:
        result = engine.process_query(args.query, mode=args.mode)
        format_cli_output(result)

        if args.feedback_rate:
            fb_id = engine.add_feedback(
                query=args.query,
                generated_logic=result["generated_logic"],
                user_rating=args.feedback_rate,
                notes=args.feedback_notes
            )
            print(f"[FEEDBACK] Recorded feedback with ID: {fb_id}")
    else:
        run_suite(engine, mode=args.mode, output_file=args.output)


if __name__ == "__main__":
    main()
