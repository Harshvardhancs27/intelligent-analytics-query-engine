"""
FastAPI REST API Server for Intelligent Analytics Query Engine.
Provides production HTTP endpoints for query translation, execution, benchmarking, and feedback collection.
"""
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from query_engine.engine import IntelligentAnalyticsEngine
from query_engine.config import DEFAULT_ENGINE_MODE, DATA_DICTIONARY_PATH
from query_engine.data_loader import DataLoader

app = FastAPI(
    title="Intelligent Analytics Query Engine API",
    description="Translates natural language questions into secure Pandas/SQL queries and executes them with confidence scores.",
    version="1.0.0"
)

# Global singleton engine instance
engine = IntelligentAnalyticsEngine()


class QueryRequest(BaseModel):
    query: str = Field(..., example="Total sales in India for March")
    mode: Optional[str] = Field(default="pandas", example="pandas", description="Execution mode: 'pandas' or 'sql'")


class QueryResponse(BaseModel):
    query: str
    generated_logic: str
    result: Any
    confidence_score: float
    explanation: str


class FeedbackRequest(BaseModel):
    query: str
    generated_logic: str
    user_rating: int = Field(..., ge=1, le=5)
    corrected_logic: Optional[str] = ""
    notes: Optional[str] = ""


@app.get("/health", tags=["System"])
def health_check():
    """System health check and dataset summary."""
    return {
        "status": "healthy",
        "sales_records": len(engine.sales_df),
        "target_records": len(engine.targets_df),
        "supported_modes": ["pandas", "sql"]
    }


@app.post("/query", response_model=QueryResponse, tags=["Analytics"])
def execute_query(req: QueryRequest):
    """Translates a natural language query into executable code and returns computed results."""
    try:
        output = engine.process_query(req.query, mode=req.mode or "pandas")
        return output
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/benchmark", response_model=List[QueryResponse], tags=["Analytics"])
def run_benchmark(mode: str = "pandas"):
    """Runs the entire benchmark test suite and returns all query evaluations."""
    try:
        return engine.evaluate_suite(mode=mode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback", tags=["Feedback"])
def submit_feedback(req: FeedbackRequest):
    """Submits analyst feedback to feedback_log.csv to dynamically tune confidence and learning."""
    try:
        feedback_id = engine.add_feedback(
            query=req.query,
            generated_logic=req.generated_logic,
            user_rating=req.user_rating,
            corrected_logic=req.corrected_logic or "",
            notes=req.notes or ""
        )
        return {
            "status": "success",
            "feedback_id": feedback_id,
            "message": "Feedback successfully logged to feedback_log.csv"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data-dictionary", tags=["Metadata"])
def get_data_dictionary():
    """Retrieves business metrics, dimensions, synonyms, and time mappings."""
    return DataLoader.load_json(DATA_DICTIONARY_PATH)
